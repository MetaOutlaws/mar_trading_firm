"""Public-data paper comparison. No order endpoint or live broker dependency.

One SQLite transaction commits decisions, fills, cash, recovery state and the
opportunity ledger together. The third book is a collection of independent
counterfactual trades, deliberately NOT a funded portfolio.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal, ROUND_DOWN
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from core.execution.bl8_shadow import depth_fill
from core.risk.engine import RiskEngine, TradeIntent, PortfolioState, OpenPosition
from core.risk.killswitch import KillSwitchState
from core.risk.limits import PAPER_LIMITS
from core.strategy.bl8 import fill_gate
from core.strategy.f111_semantics import initial_brackets, new_protection_state, step_protection

MINUTE = 60_000
DAY = 1_440 * MINUTE
BOOKS = ('NONE', 'C24')
OPPORTUNITY = 'OPPORTUNITY'
FEE = .00055
SLIP = .002


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


class MemorySwitch:
    def __init__(self):
        self.state = KillSwitchState()

    def read(self):
        return self.state

    def trip(self, reason, detail='', tripped_by='recovery_paper'):
        self.state = KillSwitchState(True, reason, detail, 'paper', tripped_by)
        return self.state


def validate_config(config):
    required = dict(mode='paper_comparison', live_authorized=False,
                    starting_equity_usdt=20000, max_open_positions=15,
                    risk_fraction=.01, position_fraction=.1, gross_fraction=.5,
                    fee_per_side=FEE, entry_slippage=SLIP,
                    recovery_minutes=1440, source_order=['H', 'B'],
                    opportunity_notional_usdt=2000)
    for key, value in required.items():
        if config.get(key) != value:
            raise ValueError(f'frozen paper configuration mismatch: {key}')
    if len(config['universe']) != 96 or len(set(config['universe'])) != 96:
        raise ValueError('the original 96-symbol universe is required')


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
        account['last_loss_ms'] = position['exit_ms'] // MINUTE * MINUTE
    account['last_close_key'] = [position['exit_ms'] // MINUTE, position['uid']]
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
        self.limits = replace(PAPER_LIMITS, max_concurrent_positions=15)
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch(exist_ok=False, mode=0o600)
        if not self.path.is_file():
            raise ValueError('book missing: initialize explicitly; never silently reset a lost ledger')
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA busy_timeout=5000')
        if create:
            self.db.executescript('''
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
                CREATE TABLE events (id TEXT PRIMARY KEY, hash TEXT NOT NULL, at_ms INTEGER NOT NULL, result TEXT NOT NULL);
                CREATE TABLE signals (uid TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE decisions (book TEXT, uid TEXT, at_ms INTEGER, status TEXT, body TEXT, PRIMARY KEY(book,uid));
                CREATE TABLE positions (book TEXT, uid TEXT, status TEXT, body TEXT, PRIMARY KEY(book,uid));
                CREATE TABLE feed (key TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE observations (id INTEGER PRIMARY KEY, at_ms INTEGER, kind TEXT, body TEXT);
                CREATE TABLE equity_samples (book TEXT, minute INTEGER, at_ms INTEGER, equity REAL, peak REAL, complete_marks INTEGER, funding_known INTEGER, PRIMARY KEY(book,minute));
                CREATE INDEX positions_status ON positions(status);
            ''')
            with self.transaction():
                self.db.execute('INSERT INTO meta VALUES (?,?)', ('config', canonical(config)))
                self.db.execute('INSERT INTO meta VALUES (?,?)', ('config_sha256', digest(config)))
                self.db.execute('INSERT INTO state VALUES (1,?)', (canonical(
                    dict(version=1, last_cycle_ms=None, accounts={b: make_account() for b in BOOKS})),))
        if self.db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('paper ledger integrity check failed')
        row = self.db.execute("SELECT value FROM meta WHERE key='config_sha256'").fetchone()
        if row is None or row[0] != digest(config):
            raise ValueError('configuration changed: a new book is required')
        self.reconcile()

    @contextmanager
    def transaction(self):
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
                raise ValueError('account cash or realised P&L does not reconcile')
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
        self.db.execute('INSERT OR REPLACE INTO positions VALUES (?,?,?,?)',
                        (p['book'], p['uid'], p['status'], canonical(p)))

    def feed(self, key, default=None):
        row = self.db.execute('SELECT body FROM feed WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def save_feed(self, key, value):
        encoded=canonical(value)
        row=self.db.execute('SELECT body FROM feed WHERE key=?',(key,)).fetchone()
        if row is None or row[0]!=encoded:
            self.db.execute('INSERT OR REPLACE INTO feed VALUES (?,?)', (key, encoded))

    def observe(self, now, kind, payload):
        self.db.execute('INSERT INTO observations(at_ms,kind,body) VALUES (?,?,?)',
                        (now, kind, canonical(payload)))

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
        if not complete:
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

    def _state_for_risk(self, account, positions, now):
        day = str(now // DAY)
        return PortfolioState(account['equity'], account['peak'], [
            OpenPosition(p['symbol'], 'LONG' if p['side']==1 else 'SHORT', p['quantity'],
                         p['entry'], p['quantity']*p['mark'], p['sector'])
            for p in positions if p['status']=='open'],
            account['entries_daily'].get(day, 0), account['closed_daily'].get(day, 0.),
            account['streak'], day)

    def _entry(self, book, signal, quote, instrument, now, account, positions):
        bid, ask = fresh_quote(quote, signal['symbol'], now)
        side = signal['side']
        if int(quote['ts']) < signal['action_ms']:
            raise ValueError('quote predates action')
        if instrument.get('symbol') != signal['symbol'] or instrument.get('status') != 'Trading':
            raise ValueError('instrument unavailable')
        interval = int(instrument.get('fundingInterval', 0))
        if interval <= 0:
            raise ValueError('funding schedule unknown')
        lot = instrument['lotSizeFilter']
        step = Decimal(str(lot['qtyStep']))
        if step <= 0:
            raise ValueError('invalid quantity step')
        px = (ask if side==1 else bid)*(1+side*SLIP)
        engine = RiskEngine(self.limits, MemorySwitch())
        state = self._state_for_risk(account, positions, now) if account else None
        quantity = None
        # Never increase quantity after the first depth calculation.
        for _ in range(12):
            if signal['source']=='H':
                brackets = initial_brackets(px, side, signal['prior_atr'])
                stop, target = brackets['initial_stop'], brackets['target']
            else:
                stop, target = signal['stop'], signal['target']
                if not fill_gate(signal, px):
                    raise ValueError('BL8 actual-fill gate')
            distance = abs(px-stop)/px
            if not 0 < stop or distance <= 0 or side*(target-px) <= 0:
                raise ValueError('invalid bracket')
            loss_fraction = distance + FEE*(1+stop/px)
            if account:
                intent = TradeIntent(signal['symbol'], 'LONG' if side==1 else 'SHORT', px,
                                     stop, target, signal['source'], 0., signal['sector'])
                ruling = engine.evaluate(intent, state)
                if not ruling.is_approved:
                    return None, ruling.reasons
                cap = min(ruling.quantity, account['equity']*.01/(px*loss_fraction))
            else:
                cap = self.config['opportunity_notional_usdt']/px
            cap = min(cap, float(lot['maxMktOrderQty']))
            cap = min(cap, quantity) if quantity is not None else cap
            qty = float((Decimal(str(cap))/step).to_integral_value(rounding=ROUND_DOWN)*step)
            if qty < float(lot['minOrderQty']) or qty*px < max(5., float(lot.get('minNotionalValue', 5))):
                raise ValueError('below exchange minimum')
            new_px = depth_fill(quote, qty, side==1, now)*(1+side*SLIP)
            if quantity == qty and abs(new_px-px) <= max(px,1)*1e-12:
                break
            quantity, px = qty, new_px
        else:
            raise ValueError('sizing did not converge')
        p = dict(book=book, uid=signal['uid'], symbol=signal['symbol'], source=signal['source'],
                 sector=signal['sector'], regime=signal.get('regime','unknown'), side=side,
                 entry_ms=now, action_ms=signal['action_ms'], entry=px, quantity=qty,
                 stop=stop, target=target, status='open', exit_ms=None, exit=None,
                 entry_fee=qty*px*FEE, exit_fee=0., funding=0., settlements={},
                 funding_interval=interval, mark=bid if side==1 else ask, mark_ms=int(quote['ts']),
                 last_exit_minute=now//MINUTE, net_pnl=None, protection=None,
                 missed_exit_minutes=0,
                 planned_loss_usdt=qty*px*loss_fraction,
                 execution_basis='fresh_visible_depth_plus_frozen_costs')
        p['entry_quote'] = quote
        if signal['source']=='H':
            p['protection'] = new_protection_state(entry_price=px, side=side,
                prior_atr=signal['prior_atr'], quantity=qty, entry_fee=p['entry_fee'])
        return p, []

    def cycle(self, event_id, now, quotes, instruments, candidates=(), settlements=None, *, manual_halt=False):
        """Inputs contain only observations known now. An exact replay cannot trade twice."""
        payload = dict(now=now, quotes=quotes, instruments=instruments, candidates=list(candidates),
                       settlements=settlements or {}, manual_halt=manual_halt)
        input_hash = digest(payload)
        with self.transaction():
            previous = self.db.execute('SELECT hash FROM events WHERE id=?', (event_id,)).fetchone()
            if previous:
                if previous[0] != input_hash:
                    raise ValueError('conflicting event replay')
                return {'duplicate': True, 'new_entries': 0}
            state = self.state()
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
                if p['status']!='open' or now//MINUTE <= p['last_exit_minute']:
                    continue
                if not 0 <= now-p['mark_ms'] <= 5000:
                    continue
                missed=max(0,now//MINUTE-p['last_exit_minute']-1)
                reason = None
                proposed_protection = p['protection']
                if p['source']=='H':
                    fraction = p['funding']/(p['quantity']*p['entry']) if funding_known(p, now) else None
                    proposed_protection, exit_row = step_protection(p['protection'], p['mark'],
                        funding_fraction=fraction, sample_id=str(now//MINUTE))
                    reason = exit_row['reason'] if exit_row else None
                elif p['mark'] <= p['stop']:
                    reason = 1
                elif p['mark'] >= p['target']:
                    reason = 2
                if reason is not None:
                    try:
                        px = depth_fill(quotes[p['symbol']], p['quantity'], p['side']==-1, now)
                    except ValueError:
                        continue  # no fabricated liquidity; retry the triggered exit
                    if reason == 2:
                        px *= 1-p['side']*SLIP
                    p.update(exit=px, exit_ms=now, exit_reason=reason, status='pending_funding',
                             exit_fee=p['quantity']*px*FEE, exit_quote=quotes[p['symbol']])
                    p['gross_pnl'] = p['side']*p['quantity']*(px-p['entry'])
                    if p['book'] in accounts:
                        accounts[p['book']]['cash'] += p['gross_pnl']-p['exit_fee']
                    output['exits'] += 1
                p['protection'] = proposed_protection
                p['missed_exit_minutes'] += missed
                p['last_exit_minute'] = now//MINUTE
            # Net closes are consumed in exit-minute/UID order. Unknown funding
            # keeps later closes queued and blocks account admissions.
            for book in (*BOOKS, OPPORTUNITY):
                pending = sorted((p for p in positions if p['book']==book and p['status']=='pending_funding'),
                                 key=lambda p: (p['exit_ms']//MINUTE, p['uid']))
                for p in pending:
                    if not funding_known(p, p['exit_ms']):
                        break
                    if (book in accounts and p['exit_ms']//MINUTE == now//MINUTE
                            and any(other['book']==book and other['status']=='open'
                                    and other['last_exit_minute']<now//MINUTE for other in positions)):
                        # Exits still execute when one token's quote is missing.
                        # Wait for the rest of this minute's samples before
                        # ordering net closes by UID and permitting new entries.
                        break
                    p['net_pnl'] = p['gross_pnl']-p['entry_fee']-p['exit_fee']-p['funding']
                    p['status'] = 'closed'
                    if book in accounts:
                        key = [p['exit_ms']//MINUTE, p['uid']]
                        prior = accounts[book]['last_close_key']
                        if prior is not None and key < prior:
                            accounts[book]['supervision_gap'] = {'reason':'late_close_order'}
                        observe_close(accounts[book], p)
            complete = {book: self._mark_account(account, [p for p in positions if p['book']==book], now)
                        for book, account in accounts.items()}
            for s in sorted(candidates, key=lambda s:(s['action_ms'], 0 if s['source']=='H' else 1, s['symbol'], s['uid'])):
                encoded = canonical(s)
                prior = self.db.execute('SELECT body FROM signals WHERE uid=?', (s['uid'],)).fetchone()
                if prior:
                    if prior[0] != encoded:
                        raise ValueError('conflicting signal UID')
                    continue
                if s['symbol'] not in self.config['universe'] or s['side'] not in (-1,1) or s['source'] not in ('H','B'):
                    raise ValueError('invalid candidate')
                self.db.execute('INSERT INTO signals VALUES (?,?)', (s['uid'], encoded))
                for book in (*BOOKS, OPPORTUNITY):
                    account = accounts.get(book)
                    owned = [p for p in positions if p['book']==book]
                    reasons = []
                    p = None
                    if not s['action_ms'] <= now < s['action_ms']+MINUTE:
                        reasons.append('missed_action_window')
                    if account:
                        unknown_funding = any(p['status']=='pending_funding' or
                            (p['status']=='open' and not funding_known(p,now)) for p in owned)
                        if not unknown_funding:
                            recover(account, book, now)
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
            state['last_cycle_ms'] = now
            self.db.execute('UPDATE state SET body=? WHERE id=1', (canonical(state),))
            self.db.execute('INSERT INTO events VALUES (?,?,?,?)', (event_id,input_hash,now,canonical(output)))
            return output

    def report(self, now):
        state = self.state()
        counts = [dict(row) for row in self.db.execute('SELECT book,status,count(*) AS count FROM decisions GROUP BY book,status')]
        return dict(paper_only=True, config_sha256=digest(self.config), observed_ms=now,
                    last_cycle_ms=state['last_cycle_ms'], accounts=state['accounts'], decisions=counts,
                    opportunity_basis='independent 2000 USDT notional per signal; NOT portfolio ROI',
                    pricing='visible book depth + 0.20% adverse entry/target slippage; 0.055% each-leg fee; observed signed funding',
                    open_positions=[{k:p[k] for k in ('book','uid','symbol','quantity','entry','status')} for p in self.positions()],
                    activation_verified=False)
