"""Public-data paper comparison. No order endpoint and no broker dependency.

One SQLite transaction commits decisions, fills, cash, recovery state and the
opportunity ledgers together. Sixteen internal simulated portfolios share one
service: four strategy variants at four cost settings. The persisted
`accounts` key is simulated cash and risk for those portfolios. It is not an
exchange account, a testnet account, or a subaccount.
Opportunity books are overlapping counterfactuals, not simulated-portfolio returns.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from decimal import Decimal, ROUND_DOWN
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
import zlib

from .quotes import depth_fill
from .allocation import membership, planned_notional, ordered_candidates
from .strategy import fill_gate as cipher_gate, COSTS
from .config import frozen_config
from .bl8 import fill_gate
from .storage import StorageWriteBlocked, ledger_nbytes
from core.strategy.f111_semantics import initial_brackets, new_protection_state, step_protection

MINUTE = 60_000
DAY = 1_440 * MINUTE
# Event payloads keep the top of book, not the full 200-level array, and they
# repeat that array at most once per interval. The event hash is the full quote.
STORED_LEVELS = 25
QUOTE_SNAPSHOT_INTERVAL_MS = 15 * MINUTE
BOOKS = tuple(f'{cost}:{arm}' for cost in COSTS for arm in ('I','IC','IM','IF'))
OPPORTUNITIES = tuple(f'{cost}:OPPORTUNITY' for cost in COSTS)
ALL_BOOKS = BOOKS + OPPORTUNITIES
EXIT_TICK = 15_000
CYCLES_PER_DAY = 24 * 60 * 60 * 1000 // EXIT_TICK
QUOTE_SNAPSHOTS_PER_DAY = 24 * 60 * 60 * 1000 // QUOTE_SNAPSHOT_INTERVAL_MS
# Quoted from the 2026-10-26 capacity review. Not remeasured on exchange bars.
HISTORY_SNAPSHOT_BYTES_PER_DAY_QUOTED = 51 * 1024 * 1024
FEE = .00055
SLIP = .002


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def calendar_year(ms: int) -> str:
    return str(datetime.fromtimestamp(int(ms) / 1000, timezone.utc).year)


def calendar_from_samples(samples) -> dict:
    """Year rows from ordered equity samples. Prior cash starts at 20,000."""
    calendar = {}
    prior = 20000.
    for sample in samples:
        y = calendar_year(sample['at_ms'])
        if y not in calendar:
            calendar[y] = dict(start_equity=prior, end_equity=prior, complete=True)
        calendar[y]['end_equity'] = sample['equity']
        calendar[y]['complete'] &= bool(sample['complete_marks'] and sample['funding_known'])
        prior = sample['equity']
    for val in calendar.values():
        val['net_usdt'] = val['end_equity'] - val['start_equity']
        val['return_pct'] = (
            100 * (val['end_equity'] / val['start_equity'] - 1) if val['start_equity'] > 0 else None)
    return calendar


def stored_quote(quote: dict, *, include_levels: bool) -> dict:
    """Copy a quote for disk. The full-book hash stays even when levels are omitted."""
    kept = {key: quote[key] for key in quote if key not in ('b', 'a')}
    kept['full_sha256'] = digest(quote)
    if include_levels:
        kept['b'] = list(quote.get('b') or [])[:STORED_LEVELS]
        kept['a'] = list(quote.get('a') or [])[:STORED_LEVELS]
        kept['stored_levels'] = STORED_LEVELS
        kept['levels_omitted'] = False
    else:
        kept['levels_omitted'] = True
    return kept


def persist_quote(quote):
    """Trim a position quote once. A quote already stored is left unchanged."""
    if not quote:
        return quote
    bids = quote.get('b') or []
    asks = quote.get('a') or []
    if quote.get('full_sha256') and len(bids) <= STORED_LEVELS and len(asks) <= STORED_LEVELS:
        return quote
    return stored_quote(quote, include_levels=True)


def event_identity(now, quotes, instruments, candidates, settlements, manual_halt) -> dict:
    """Hash input. Depends on the full quotes, not on which levels were stored."""
    return dict(
        now=now,
        quote_sha256={symbol: digest(quote) for symbol, quote in quotes.items()},
        instruments=instruments,
        candidates=list(candidates),
        settlements=settlements or {},
        manual_halt=manual_halt,
    )


def compact_event_payload(now, quotes, instruments, candidates, settlements, manual_halt, *, include_levels: bool) -> dict:
    return dict(
        now=now,
        quotes={symbol: stored_quote(quote, include_levels=include_levels) for symbol, quote in quotes.items()},
        instruments=instruments,
        candidates=list(candidates),
        settlements=settlements or {},
        manual_halt=manual_halt,
        levels_included=bool(include_levels),
        stored_levels=STORED_LEVELS,
    )


def project_quote_event_bytes_per_day(snapshot_bytes: int, hash_only_bytes: int) -> int:
    """One shared feed. Portfolio count does not multiply these payloads."""
    snapshots = QUOTE_SNAPSHOTS_PER_DAY
    return snapshots * int(snapshot_bytes) + (CYCLES_PER_DAY - snapshots) * int(hash_only_bytes)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_config(config):
    if config != frozen_config():
        raise ValueError('frozen paper configuration mismatch; new release required')


def fresh_quote(quote, symbol, now):
    if not quote or quote.get('s') != symbol:
        raise ValueError('missing or wrong-symbol quote')
    depth_fill(quote, 1e-12, True, now)
    depth_fill(quote, 1e-12, False, now)
    return float(quote['b'][0][0]), float(quote['a'][0][0])


def expected_funding(position, through):
    interval = int(position['funding_interval']) * MINUTE
    if interval <= 0:
        raise ValueError('unknown funding interval')
    return set(range((position['entry_ms'] // interval + 1) * interval,
                     int(through) + 1, interval))


def funding_known(position, through):
    return expected_funding(position, through) <= set(map(int, position['settlements']))


def observe_close(account, position):
    """Exactly the frozen C24 rule; zero counts as a non-positive close."""
    net = position['net_pnl']
    if net > 0:
        account['streak'] = account['raw_streak'] = 0
        account['last_loss_ms'] = None
    else:
        account['streak'] += 1
        account['raw_streak'] += 1
        account['last_loss_ms'] = position['exit_ms']
    account['last_close_key'] = [position['exit_ms'], position['uid']]
    day = str(position['exit_ms'] // DAY)
    account['closed_daily'][day] = account['closed_daily'].get(day, 0.) + net
    account['realised_pnl'] += net
    account['closed_trades'] += 1


def recover(account, policy, now):
    at = now // MINUTE * MINUTE
    if (policy == 'C24' and account['streak'] >= 6
            and account['last_loss_ms'] is not None
            and at >= account['last_loss_ms'] + DAY):
        account['recovery_events'].append(dict(at_ms=at, before=account['streak'],
                                               last_loss_ms=account['last_loss_ms']))
        account['streak'] = 0
        account['last_loss_ms'] = None
        # Raw streak and all other halt reasons survive a timed recovery.


def make_account():
    return dict(cash=20000., equity=20000., peak=20000., realised_pnl=0.,
                closed_trades=0, streak=0, raw_streak=0, last_loss_ms=None,
                last_close_key=None, recovery_events=[], closed_daily={},
                entries_daily={}, killed=None, supervision_gap=None,
                mark_minute=None, mark_ms=None, maximum_drawdown=0.)


class PaperTrial:
    def __init__(self, path: Path, config: dict, *, create=False):
        validate_config(config)
        self.path = Path(path)
        self.config = config
        self.limits = SimpleNamespace(max_drawdown_pct=.15)
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch(exist_ok=False, mode=0o600)
        if not self.path.is_file():
            raise ValueError('book missing: initialize explicitly; never silently reset a lost ledger')
        self.writes_blocked = False
        self.block_reason = ''
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        # Incremental vacuum has to be selected before the schema is written.
        # A later open cannot turn it on for a database that already has tables.
        if create:
            self.db.execute('PRAGMA auto_vacuum=INCREMENTAL')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA busy_timeout=5000')
        if create:
            self.db.executescript('''
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
                CREATE TABLE events (id TEXT PRIMARY KEY, hash TEXT NOT NULL, at_ms INTEGER NOT NULL, result TEXT NOT NULL, payload BLOB NOT NULL);
                CREATE TABLE signals (uid TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE decisions (book TEXT, uid TEXT, at_ms INTEGER, status TEXT, body TEXT, PRIMARY KEY(book,uid));
                CREATE TABLE positions (book TEXT, uid TEXT, status TEXT, body TEXT, PRIMARY KEY(book,uid));
                CREATE TABLE feed (key TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE observations (id INTEGER PRIMARY KEY, at_ms INTEGER, kind TEXT, body TEXT);
                CREATE TABLE history_snapshots (hour INTEGER PRIMARY KEY, sha256 TEXT NOT NULL, payload BLOB NOT NULL);
                CREATE TABLE equity_samples (book TEXT, minute INTEGER, at_ms INTEGER, equity REAL, peak REAL, complete_marks INTEGER, funding_known INTEGER, PRIMARY KEY(book,minute));
                CREATE TABLE equity_year_summaries (book TEXT NOT NULL, year TEXT NOT NULL, start_equity REAL NOT NULL, end_equity REAL NOT NULL, complete INTEGER NOT NULL, net_usdt REAL NOT NULL, return_pct REAL, min_at_ms INTEGER NOT NULL, max_at_ms INTEGER NOT NULL, PRIMARY KEY(book, year));
                CREATE INDEX positions_status ON positions(status);
            ''')
            with self.transaction():
                self.db.execute('INSERT INTO meta VALUES (?,?)', ('config', canonical(config)))
                self.db.execute('INSERT INTO meta VALUES (?,?)', ('config_sha256', digest(config)))
                self.db.execute('INSERT INTO state VALUES (1,?)', (canonical(
                    dict(version=1, last_cycle_ms=None, accounts={b: make_account() for b in BOOKS})),))
        self.db.execute('''CREATE TABLE IF NOT EXISTS equity_year_summaries (
            book TEXT NOT NULL, year TEXT NOT NULL, start_equity REAL NOT NULL,
            end_equity REAL NOT NULL, complete INTEGER NOT NULL, net_usdt REAL NOT NULL,
            return_pct REAL, min_at_ms INTEGER NOT NULL, max_at_ms INTEGER NOT NULL,
            PRIMARY KEY(book, year))''')
        if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('paper ledger integrity check failed')
        row = self.db.execute("SELECT value FROM meta WHERE key='config_sha256'").fetchone()
        if row is None or row[0] != digest(config):
            raise ValueError('configuration changed: a new book is required')
        self.reconcile()

    def block_writes(self, reason: str):
        """Refuse new ledger writes. The caller also disables entries."""
        self.writes_blocked = True
        self.block_reason = reason

    def allow_writes(self):
        self.writes_blocked = False
        self.block_reason = ''

    def _require_writes(self):
        if self.writes_blocked:
            raise StorageWriteBlocked(self.block_reason or 'ledger writes blocked')

    @contextmanager
    def transaction(self):
        self._require_writes()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def state(self):
        return json.loads(self.db.execute('SELECT body FROM state WHERE id=1').fetchone()[0])

    def reconcile(self):
        nested=self.db.in_transaction
        if not nested: self.db.execute('BEGIN')
        try: return self._reconcile()
        finally:
            if not nested: self.db.execute('ROLLBACK')

    def _reconcile(self):
        state=self.state()
        if state.get('version')!=1 or set(state['accounts'])!=set(BOOKS):
            raise ValueError('wrong book or state schema')
        positions=self.positions(None)
        for book,account in state['accounts'].items():
            ps=[p for p in positions if p['book']==book]
            expected=20000+sum(-p['entry_fee']-p['funding']+
                (p.get('gross_pnl',0)-p['exit_fee'] if p['exit_ms'] is not None else 0) for p in ps)
            closed=sum(p['net_pnl'] for p in ps if p['status']=='closed')
            if (not finite(account['cash']) or abs(expected-account['cash'])>1e-6
                    or not finite(account['realised_pnl']) or abs(closed-account['realised_pnl'])>1e-6):
                raise ValueError('simulated-portfolio cash or realised P&L does not reconcile')
            if account['streak']<0 or account['raw_streak']<account['streak'] or account['peak']<=0:
                raise ValueError('invalid persisted risk state')
        return True

    def positions(self, statuses=('open', 'pending_funding')):
        query = 'SELECT body FROM positions'
        args = ()
        if statuses is not None:
            query += ' WHERE status IN (' + ','.join('?' for _ in statuses) + ')'
            args = statuses
        return [json.loads(r[0]) for r in self.db.execute(query, args)]

    def save_position(self, p):
        if p.get('entry_quote') is not None:
            p['entry_quote'] = persist_quote(p['entry_quote'])
        if p.get('exit_quote') is not None:
            p['exit_quote'] = persist_quote(p['exit_quote'])
        self.db.execute('INSERT OR REPLACE INTO positions VALUES (?,?,?,?)',
                        (p['book'], p['uid'], p['status'], canonical(p)))

    def _fold_equity_sample(self, book, at_ms, equity, complete_marks, funding_known):
        """Update the year summary in this same transaction as the sample insert."""
        y = calendar_year(at_ms)
        rows = [dict(row) for row in self.db.execute(
            'SELECT * FROM equity_year_summaries WHERE book=?', (book,))]
        current = next((row for row in rows if row['year'] == y), None)
        fresh = bool(complete_marks and funding_known)
        if current is None:
            earlier = [row for row in rows if row['year'] < y]
            prior = max(earlier, key=lambda row: row['year'])['end_equity'] if earlier else 20000.
            start = prior
            end = equity
            complete = fresh
            net = end - start
            ret = 100 * (end / start - 1) if start > 0 else None
            self.db.execute(
                'INSERT INTO equity_year_summaries VALUES (?,?,?,?,?,?,?,?,?)',
                (book, y, start, end, int(complete), net, ret, int(at_ms), int(at_ms)))
            return
        start = current['start_equity']
        end = equity
        complete = bool(current['complete']) and fresh
        net = end - start
        ret = 100 * (end / start - 1) if start > 0 else None
        self.db.execute(
            '''UPDATE equity_year_summaries
               SET end_equity=?, complete=?, net_usdt=?, return_pct=?, min_at_ms=?, max_at_ms=?
               WHERE book=? AND year=?''',
            (end, int(complete), net, ret, min(int(current['min_at_ms']), int(at_ms)),
             max(int(current['max_at_ms']), int(at_ms)), book, y))

    def feed(self, key, default=None):
        row = self.db.execute('SELECT body FROM feed WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def save_feed(self, key, value):
        self._require_writes()
        encoded=canonical(value)
        row=self.db.execute('SELECT body FROM feed WHERE key=?',(key,)).fetchone()
        if row is None or row[0]!=encoded:
            self.db.execute('INSERT OR REPLACE INTO feed VALUES (?,?)', (key, encoded))

    def observe(self, now, kind, payload):
        self._require_writes()
        self.db.execute('INSERT INTO observations(at_ms,kind,body) VALUES (?,?,?)',
                        (now, kind, canonical(payload)))

    def history_snapshot(self, hour, histories):
        """First observed completed-bar input for the hour, never silently revised."""
        self._require_writes()
        raw=canonical(histories).encode();sha=hashlib.sha256(raw).hexdigest()
        old=self.db.execute('SELECT sha256 FROM history_snapshots WHERE hour=?',(hour,)).fetchone()
        if old:
            if old[0]!=sha:
                self.observe(hour,'history_revision',dict(first_sha256=old[0],new_sha256=sha))
            return
        self.db.execute('INSERT INTO history_snapshots VALUES (?,?,?)',(hour,sha,zlib.compress(raw)))

    def _fund(self, p, settlements, accounts):
        end = p['exit_ms'] or settlements.get('through_ms', p['entry_ms'])
        for row in settlements.get('rows', []):
            t = int(row['t'])
            if not p['entry_ms'] < t <= end:
                continue
            if t not in expected_funding(p, end):
                raise ValueError('funding schedule changed; reconciliation required')
            if not all(finite(row[k]) for k in ('rate', 'price')) or row['price'] <= 0:
                raise ValueError('invalid funding observation')
            key = str(t)
            value = {k: row[k] for k in ('t', 'rate', 'price')}
            prior = p['settlements'].get(key)
            if prior is not None:
                if prior != value:
                    raise ValueError('conflicting funding observation')
                continue
            p['settlements'][key] = value
            amount = p['side'] * p['quantity'] * row['price'] * row['rate']
            p['funding'] += amount
            if p['book'] in accounts:
                accounts[p['book']]['cash'] -= amount

    def _mark_account(self, account, positions, now):
        active = [p for p in positions if p['status'] == 'open']
        complete = all(p.get('mark_ms') is not None and 0 <= now-p['mark_ms'] <= 5000 for p in active)
        if not complete or any(not funding_known(p, p['exit_ms'] or now) for p in positions if p['status'] != 'closed'):
            return False
        minute = now // MINUTE
        if (active and account['mark_minute'] is not None
                and minute > account['mark_minute'] + 1):
            account['supervision_gap'] = account['supervision_gap'] or dict(
                from_minute=account['mark_minute']+1, to_minute=minute-1)
        eq = account['cash'] + sum(p['side'] * p['quantity'] * (p['mark']-p['entry']) for p in active)
        account['equity'] = eq
        account['peak'] = max(account['peak'], eq)
        dd = max(0., 1-eq/account['peak'])
        account['maximum_drawdown'] = max(account['maximum_drawdown'], dd)
        account['mark_minute'], account['mark_ms'] = minute, now
        if dd >= self.limits.max_drawdown_pct and account['killed'] is None:
            account['killed'] = dict(reason='maximum_drawdown', at_ms=now, equity=eq, peak=account['peak'])
        return True

    def _entry(self, book, signal, quote, instrument, now, account, positions):
        bid, ask = fresh_quote(quote, signal['symbol'], now)
        side = signal['side']
        if int(quote['ts']) < signal['action_ms']:
            raise ValueError('quote predates action')
        if instrument.get('symbol') != signal['symbol'] or instrument.get('status') != 'Trading':
            raise ValueError('instrument unavailable')
        interval = int(instrument.get('fundingInterval', 0))
        if interval <= 0 or 1440 % interval:
            raise ValueError('funding schedule unknown')
        lot = instrument['lotSizeFilter']
        step = Decimal(str(lot['qtyStep']))
        if not step.is_finite() or step <= 0:
            raise ValueError('invalid quantity step')
        minqty, maxqty, minvalue = (float(lot['minOrderQty']), float(lot['maxMktOrderQty']),
                                     max(5., float(lot.get('minNotionalValue', 5))))
        if not all(finite(x) for x in (minqty,maxqty,minvalue)) or not 0 < minqty <= maxqty:
            raise ValueError('invalid instrument limits')
        cost, arm = book.split(':')
        slip, stop_slip = COSTS[cost]
        px = (ask if side == 1 else bid) * (1 + side * slip)
        quantity = None
        for _ in range(12):
            if signal['source'] == 'H':
                brackets = initial_brackets(px, side, signal['prior_atr'])
                stop, target = brackets['initial_stop'], brackets['target']
            else:
                stop, target = signal['stop'], signal['target']
                if signal['source'] == 'B' and not fill_gate(signal, px):
                    raise ValueError('BL8 actual-fill gate')
                if signal['source'] == 'C3' and not cipher_gate(signal, px,
                        market_slip=slip, total_stop_slip=stop_slip)['eligible']:
                    raise ValueError('original_2R_fill_gate')
            distance = side*(px-stop)/px
            if not all(finite(x) for x in (stop,target,distance)) or min(stop,target) <= 0 or distance <= 0 or side*(target-px) <= 0:
                raise ValueError('invalid bracket')
            planned_stop = stop*(1-side*stop_slip)
            loss_fraction = (side*(px-planned_stop)+FEE*(px+planned_stop))/px
            if account:
                reasons = []
                active = [p for p in positions if p['status']=='open']
                day = str(now//DAY)
                if account['equity'] <= 0: reasons.append('nonpositive_equity')
                if account['streak'] >= 6: reasons.append('consecutive_losses')
                if account['closed_daily'].get(day,0) <= -.03*account['equity']: reasons.append('daily_loss')
                if account['entries_daily'].get(day,0) >= 20: reasons.append('daily_entry_limit')
                if len(active) >= 15: reasons.append('position_limit')
                if sum(p['sector']==signal['sector'] for p in active) >= 2: reasons.append('sector_limit')
                if not (.08 if signal['source']=='B' else .005) <= distance <= .15: reasons.append('stop_distance')
                if reasons: return None, reasons
                gross = sum(p['quantity']*p['mark'] for p in active)
                cap = planned_notional(arm, signal['source'], account['equity'], gross,
                                       loss_fraction, filter_pass=signal.get('filter_pass',False))/px
            else:
                cap = self.config['opportunity_notional_usdt']/px
            cap = min(cap,maxqty,quantity if quantity is not None else maxqty)
            qty = float((Decimal(str(cap))/step).to_integral_value(rounding=ROUND_DOWN)*step)
            if qty < minqty or qty*px < minvalue:
                raise ValueError('below exchange minimum or gross headroom')
            new_px = depth_fill(quote,qty,side==1,now)*(1+side*slip)
            if quantity == qty and abs(new_px-px) <= max(px,1)*1e-12:
                break
            quantity, px = qty,new_px
        else:
            raise ValueError('sizing did not converge')
        p = dict(book=book,uid=signal['uid'],symbol=signal['symbol'],source=signal['source'],
                 sector=signal['sector'],regime=signal.get('regime','unknown'),side=side,
                 entry_ms=now,action_ms=signal['action_ms'],entry=px,quantity=qty,
                 stop=stop,target=target,status='open',exit_ms=None,exit=None,
                 entry_fee=qty*px*FEE,exit_fee=0.,funding=0.,settlements={},
                 funding_interval=interval,mark=bid if side==1 else ask,mark_ms=int(quote['ts']),
                 last_exit_minute=now//MINUTE,last_exit_tick=now//EXIT_TICK,
                 last_protection_minute=now//MINUTE,net_pnl=None,protection=None,
                 missed_exit_minutes=0,missed_exit_ticks=0,pending_exit_reason=None,
                 planned_loss_usdt=qty*px*loss_fraction,original_risk_usdt=qty*px*distance,
                 entry_slippage_usdt=qty*abs(px-new_px/(1+side*slip)),
                 entry_depth_usdt=qty*abs(new_px/(1+side*slip)-(ask if side==1 else bid)),
                 entry_half_spread_usdt=qty*(ask-bid)/2,
                 decision_latency_ms=now-signal['action_ms'],quote_age_ms=now-int(quote['ts']),
                 execution_basis='fresh_visible_depth_plus_frozen_costs',entry_quote=quote)
        if signal['source']=='H':
            p['protection']=new_protection_state(entry_price=px,side=side,
                prior_atr=signal['prior_atr'],quantity=qty,entry_fee=p['entry_fee'])
        return p, []

    def cycle(self, event_id, now, quotes, instruments, candidates=(), settlements=None, *, manual_halt=False):
        """Inputs contain only observations known now. An exact replay cannot trade twice."""
        candidates = list(candidates)
        identity = event_identity(now, quotes, instruments, candidates, settlements or {}, manual_halt)
        input_hash = digest(identity)
        with self.transaction():
            previous = self.db.execute('SELECT hash FROM events WHERE id=?', (event_id,)).fetchone()
            if previous:
                if previous[0] != input_hash:
                    raise ValueError('conflicting event replay')
                return {'duplicate': True, 'new_entries': 0}
            state = self.state()
            last_snapshot = state.get('last_quote_snapshot_ms')
            include_levels = (
                last_snapshot is None or int(now) - int(last_snapshot) >= QUOTE_SNAPSHOT_INTERVAL_MS)
            payload = compact_event_payload(
                now, quotes, instruments, candidates, settlements or {}, manual_halt,
                include_levels=include_levels)
            if include_levels:
                state['last_quote_snapshot_ms'] = int(now)
            if state['last_cycle_ms'] is not None and now <= state['last_cycle_ms']:
                raise ValueError('out-of-order cycle')
            accounts = state['accounts']
            positions = self.positions()
            # Occupancy includes an exit earlier in this same minute, including
            # when it was committed by a previous cycle before this restart.
            positions += [json.loads(r[0]) for r in self.db.execute(
                "SELECT body FROM positions WHERE status='closed' AND json_extract(body,'$.exit_ms')>=?",
                (now//MINUTE*MINUTE,))]
            output = dict(new_entries=0, opportunity_entries=0, exits=0, rejections=0)
            for p in positions:
                self._fund(p, (settlements or {}).get(p['symbol'], {}), accounts)
                if p['status'] != 'open':
                    continue
                try:
                    bid, ask = fresh_quote(quotes.get(p['symbol']), p['symbol'], now)
                except ValueError:
                    continue
                q = quotes[p['symbol']]
                p['mark'], p['mark_ms'] = (bid if p['side']==1 else ask), int(q['ts'])
            # Mark BEFORE exits, including gaps where the last open position now exits.
            for book, account in accounts.items():
                self._mark_account(account, [p for p in positions if p['book']==book], now)
            for p in positions:
                if p['status']!='open' or now//EXIT_TICK <= p['last_exit_tick']:
                    continue
                if not 0 <= now-p['mark_ms'] <= 5000:
                    continue
                missed=max(0,now//MINUTE-p['last_exit_minute']-1)
                reason = p['pending_exit_reason']
                proposed_protection = p['protection']
                if reason is None:
                    if p['source']=='H':
                        if now//MINUTE > p['last_protection_minute']:
                            fraction = p['funding']/(p['quantity']*p['entry']) if funding_known(p,now) else None
                            proposed_protection, exit_row = step_protection(p['protection'],p['mark'],
                                funding_fraction=fraction,sample_id=str(now//MINUTE))
                            p['last_protection_minute']=now//MINUTE
                            reason=exit_row['reason'] if exit_row else None
                        else:
                            level=p['protection']['effective_level']
                            active_stop=p['entry']*(1+p['side']*level)
                            if p['side']*(p['mark']-active_stop)<=0:
                                reason=4 if level > -p['protection']['stop_return']+1e-12 else 1
                            elif p['side']*(p['mark']-p['target'])>=0: reason=2
                    elif p['side']*(p['mark']-p['stop'])<=0: reason=1
                    elif p['side']*(p['mark']-p['target'])>=0: reason=2
                if reason is not None:
                    p['pending_exit_reason']=reason
                    p['protection']=proposed_protection
                    try:
                        px = depth_fill(quotes[p['symbol']], p['quantity'], p['side']==-1, now)
                    except ValueError:
                        continue  # no fabricated liquidity; retry the triggered exit
                    slip, stop_slip = COSTS[p['book'].split(':')[0]]
                    raw=px
                    bid,ask=fresh_quote(quotes[p['symbol']],p['symbol'],now)
                    px *= 1-p['side']*(slip if reason==2 else stop_slip)
                    p['exit_slippage_usdt']=p['quantity']*abs(px-raw)
                    p['exit_depth_usdt']=p['quantity']*abs(raw-(bid if p['side']==1 else ask))
                    p.update(exit=px, exit_ms=now, exit_reason=reason, status='pending_funding',
                             exit_fee=p['quantity']*px*FEE, exit_quote=quotes[p['symbol']])
                    p['gross_pnl'] = p['side']*p['quantity']*(px-p['entry'])
                    if p['book'] in accounts:
                        accounts[p['book']]['cash'] += p['gross_pnl']-p['exit_fee']
                    output['exits'] += 1
                p['protection'] = proposed_protection
                p['missed_exit_minutes'] += missed
                p['last_exit_minute'] = now//MINUTE
                p['missed_exit_ticks'] += max(0, now//EXIT_TICK-p['last_exit_tick']-1)
                p['last_exit_tick'] = now//EXIT_TICK
            # Net closes are consumed in observed exit-time/UID order. Unknown funding
            # keeps later closes queued and blocks account admissions.
            for book in ALL_BOOKS:
                pending = sorted((p for p in positions if p['book']==book and p['status']=='pending_funding'),
                                 key=lambda p: (p['exit_ms'], p['uid']))
                for p in pending:
                    if not funding_known(p, p['exit_ms']):
                        break
                    if (book in accounts and p['exit_ms']//EXIT_TICK == now//EXIT_TICK
                            and any(other['book']==book and other['status']=='open'
                                    and other['last_exit_tick']<now//EXIT_TICK for other in positions)):
                        # Exits still execute when one token's quote is missing.
                        # Wait for the rest of this tick's samples before
                        # ordering net closes by UID and permitting new entries.
                        break
                    p['net_pnl'] = p['gross_pnl']-p['entry_fee']-p['exit_fee']-p['funding']
                    p['status'] = 'closed'
                    if book in accounts:
                        key = [p['exit_ms'], p['uid']]
                        prior = accounts[book]['last_close_key']
                        if prior is not None and key < prior:
                            accounts[book]['supervision_gap'] = {'reason':'late_close_order'}
                        observe_close(accounts[book], p)
            complete = {book: self._mark_account(account, [p for p in positions if p['book']==book], now)
                        for book, account in accounts.items()}
            for s in ordered_candidates(candidates):
                encoded = canonical(s)
                prior = self.db.execute('SELECT body FROM signals WHERE uid=?', (s['uid'],)).fetchone()
                if prior:
                    if prior[0] != encoded:
                        raise ValueError('conflicting signal UID')
                    continue
                if s['symbol'] not in self.config['universe'] or s['side'] not in (-1,1) or s['source'] not in ('H','B','C3'):
                    raise ValueError('invalid candidate')
                self.db.execute('INSERT INTO signals VALUES (?,?)', (s['uid'], encoded))
                for book in ALL_BOOKS:
                    account = accounts.get(book)
                    owned = [p for p in positions if p['book']==book]
                    reasons = []
                    p = None
                    if account and not membership(book.split(':')[1],s['source'],filter_pass=s.get('filter_pass',False)):
                        reasons.append('not_in_book_or_fixed_filter')
                    if any(o['symbol']==s['symbol'] and o['source']==s['source'] and o['action_ms']==s['action_ms'] and o['side']!=s['side'] for o in candidates):
                        reasons.append('conflicting_directions')
                    if not s.get('eligible_signal',False): reasons.append('ineligible_signal')
                    if not s['action_ms'] <= now < s['action_ms']+MINUTE:
                        reasons.append('missed_action_window')
                    if account:
                        unknown_funding = any(p['status']=='pending_funding' or
                            (p['status']=='open' and not funding_known(p,now)) for p in owned)
                        if not unknown_funding:
                            recover(account, 'C24', now)
                        if manual_halt: reasons.append('manual_entry_halt')
                        if account['killed']: reasons.append('drawdown_latched')
                        if account['supervision_gap']: reasons.append('supervision_gap_requires_reconciliation')
                        if not complete[book]: reasons.append('incomplete_fresh_marks')
                        if unknown_funding:
                            reasons.append('funding_unknown')
                        if any(p['symbol']==s['symbol'] and (p['status']=='open' or
                            p['exit_ms'] is not None and p['exit_ms']//MINUTE == now//MINUTE) for p in owned):
                            reasons.append('symbol_occupied_inclusive_exit_minute')
                    if not reasons:
                        try:
                            p, reasons = self._entry(book, s, quotes.get(s['symbol']),
                                instruments.get(s['symbol'], {}), now, account, owned)
                        except (ValueError, KeyError, TypeError) as exc:
                            reasons = [str(exc)]
                    if p is not None:
                        positions.append(p)
                        if account:
                            account['cash'] -= p['entry_fee']
                            day = str(now//DAY)
                            account['entries_daily'][day] = account['entries_daily'].get(day,0)+1
                            self._mark_account(account, owned+[p], now)
                            output['new_entries'] += 1
                        else:
                            output['opportunity_entries'] += 1
                    else:
                        output['rejections'] += 1
                    self.db.execute('INSERT INTO decisions VALUES (?,?,?,?,?)',
                        (book, s['uid'], now, 'entered' if p else 'rejected', canonical(dict(reasons=reasons))))
            for p in positions:
                self.save_position(p)
            for book, account in accounts.items():
                known = all(funding_known(p, p['exit_ms'] or now) for p in positions
                            if p['book']==book and p['status']!='closed')
                self.db.execute('INSERT OR REPLACE INTO equity_samples VALUES (?,?,?,?,?,?,?)',
                    (book,now//MINUTE,now,account['equity'],account['peak'],int(complete[book]),int(known)))
                self._fold_equity_sample(
                    book, now, account['equity'], int(complete[book]), int(known))
            state['last_cycle_ms'] = now
            self.db.execute('UPDATE state SET body=? WHERE id=1', (canonical(state),))
            self.db.execute('INSERT INTO events VALUES (?,?,?,?,?)', (event_id,input_hash,now,canonical(output),zlib.compress(canonical(payload).encode())))
            return output

    def _drop_oldest_append_only(self):
        """Remove one batch of history that is not the book. Return whether any row changed.

        Positions, cash, decisions, signals, feed and event identities stay.
        Clearing an event payload keeps the id and hash, so a replay of that
        cycle still cannot trade a second time.
        """
        ids=[row[0] for row in self.db.execute(
            'SELECT id FROM observations ORDER BY at_ms, id LIMIT 500')]
        if ids:
            self.db.executemany('DELETE FROM observations WHERE id=?', [(i,) for i in ids])
            return True
        samples=self.db.execute(
            'SELECT book, minute FROM equity_samples ORDER BY at_ms, book LIMIT 500').fetchall()
        if samples:
            self.db.executemany('DELETE FROM equity_samples WHERE book=? AND minute=?', samples)
            return True
        event=self.db.execute(
            'SELECT id FROM events WHERE length(payload)>0 ORDER BY at_ms, id LIMIT 1').fetchone()
        if event:
            self.db.execute('UPDATE events SET payload=? WHERE id=?', (b'', event[0]))
            return True
        snapshot=self.db.execute(
            'SELECT hour FROM history_snapshots WHERE length(payload)>0 ORDER BY hour LIMIT 1').fetchone()
        if snapshot:
            self.db.execute('UPDATE history_snapshots SET payload=? WHERE hour=?', (b'', snapshot[0]))
            return True
        return False

    def _reclaim_pages(self, *, min_free_bytes, main_free_bytes):
        """Shrink the file only when doing so cannot spend the free-space reserve.

        VACUUM writes a second copy. Skip it when the ledger volume, or the
        main paper volume, would fall to the halt threshold. Incremental
        vacuum reclaims pages that were reserved at database creation and does
        not need that second copy.
        """
        size=ledger_nbytes(self.path)
        ledger_free=shutil.disk_usage(self.path).free
        reserve=min(ledger_free, main_free_bytes if main_free_bytes is not None else ledger_free)
        if reserve > size + min_free_bytes:
            self.db.execute('VACUUM')
        else:
            self.db.execute('PRAGMA incremental_vacuum')
        self.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')

    def enforce_retention(self, now, *, max_age_ms, max_bytes, min_free_bytes, main_free_bytes):
        """Apply the age limit, then the size cap. Return True if still over the cap.

        Active book rows are never deleted. If they alone exceed the cap, the
        caller stops further writes instead of discarding positions.
        """
        cutoff=int(now)-int(max_age_ms)
        with self.transaction():
            removed=0
            for statement, args in (
                ('DELETE FROM observations WHERE at_ms < ?', (cutoff,)),
                ('DELETE FROM equity_samples WHERE at_ms < ?', (cutoff,)),
                ('UPDATE events SET payload=? WHERE at_ms < ? AND length(payload)>0', (b'', cutoff)),
                ('UPDATE history_snapshots SET payload=? WHERE hour < ? AND length(payload)>0', (b'', cutoff)),
            ):
                removed += self.db.execute(statement, args).rowcount
        if removed or ledger_nbytes(self.path) > max_bytes:
            self._reclaim_pages(min_free_bytes=min_free_bytes, main_free_bytes=main_free_bytes)
        while ledger_nbytes(self.path) > max_bytes:
            with self.transaction():
                changed=self._drop_oldest_append_only()
            if not changed:
                break
            self._reclaim_pages(min_free_bytes=min_free_bytes, main_free_bytes=main_free_bytes)
        return ledger_nbytes(self.path) > max_bytes

    def report(self, now):
        state = self.state()
        counts = [dict(row) for row in self.db.execute('SELECT book,status,count(*) AS count FROM decisions GROUP BY book,status')]
        cutoff = self.feed('first_forward_hour')
        # Status lists open risk for supervision, but a fill dated inside the
        # warmup window is not shown as a performance position.
        opens = self.positions()
        if cutoff is not None:
            opens = [p for p in opens if int(p['entry_ms']) >= int(cutoff)]
        return dict(paper_only=True, config_sha256=digest(self.config), observed_ms=now,
                    last_cycle_ms=state['last_cycle_ms'], accounts=state['accounts'], decisions=counts,
                    one_paper_service=True, internal_simulated_portfolios=len(BOOKS),
                    portfolio_looks_statement='The 16 portfolios are 16 looks at one idea, not 16 tests.',
                    simulation='One paper service, 16 internal simulated portfolios. Not exchange accounts, testnet accounts, subaccounts, or new capital.',
                    opportunity_basis='independent 2000 USDT notional per signal; not a simulated-portfolio return',
                    pricing=self.config['costs'], exit_tick_ms=EXIT_TICK,
                    open_positions=[{k:p[k] for k in ('book','uid','symbol','quantity','entry','status')} for p in opens],
                    warmup_performance_suppressed=True,
                    activation_verified=False)
