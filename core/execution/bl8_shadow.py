"""Transactional, isolated BL8 paper ledger. No real-order capability."""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from decimal import Decimal, ROUND_DOWN

from core.risk.limits import PAPER_LIMITS
from core.risk.sizing import size_position
from core.strategy.bl8 import fill_gate

FEE = .00055
SLIP = .002
MAX_QUOTE_AGE_MS = 5000
# Same default as the hourly paper broker and build_engine. This book does not
# read the hourly account; the percentage caps are applied to this equity.
HOURLY_PAPER_STARTING_EQUITY = 10_000.0


def depth_fill(book: dict, quantity: float, buy: bool, now: int) -> float:
    if not 0 <= now-int(book['ts']) <= MAX_QUOTE_AGE_MS:
        raise ValueError('stale_or_future_quote')
    if not math.isfinite(quantity) or quantity <= 0:
        raise ValueError('invalid_quantity')
    bids, asks = book['b'], book['a']
    if not bids or not asks or float(bids[0][0]) >= float(asks[0][0]):
        raise ValueError('empty_or_crossed_book')
    for levels, sign in [(bids, -1), (asks, 1)]:
        prior = None
        for px, sz in levels:
            px, sz = float(px), float(sz)
            if not math.isfinite(px+sz) or px <= 0 or sz <= 0:
                raise ValueError('invalid_depth')
            if prior is not None and sign*(px-prior) <= 0:
                raise ValueError('unsorted_depth')
            prior = px
    remain = quantity; amount = 0.
    for px, size in asks if buy else bids:
        take = min(remain, float(size)); amount += take*float(px); remain -= take
        if remain <= quantity*1e-12:
            return amount/quantity
    raise ValueError('insufficient_visible_depth')


def _floor_step(quantity: float, step: Decimal) -> float:
    """Round quantity down to the exchange step. Never round up toward a minimum."""
    if not math.isfinite(quantity) or quantity <= 0:
        return 0.0
    floored = (Decimal(str(quantity)) / step).to_integral_value(rounding=ROUND_DOWN) * step
    return float(floored)


class Ledger:
    def __init__(self, path: Path, config_sha: str, *, starting_equity: float = HOURLY_PAPER_STARTING_EQUITY, limits=None):
        # limits defaults to PAPER_LIMITS (1% risk, 10% position, 50% exposure, 1x, 5 USDT).
        self.starting_equity = float(starting_equity)
        self.limits = PAPER_LIMITS if limits is None else limits
        if not math.isfinite(self.starting_equity) or self.starting_equity <= 0:
            raise ValueError('starting equity must be positive')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS observations(id INTEGER PRIMARY KEY,t INTEGER,kind TEXT,payload TEXT);
          CREATE TABLE IF NOT EXISTS signals(uid TEXT PRIMARY KEY,symbol TEXT,status TEXT,payload TEXT);
          CREATE TABLE IF NOT EXISTS positions(uid TEXT PRIMARY KEY,symbol TEXT,status TEXT,payload TEXT);
          CREATE UNIQUE INDEX IF NOT EXISTS one_open_token ON positions(symbol) WHERE status='open';
          CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,uid TEXT,t INTEGER,kind TEXT,amount REAL,payload TEXT);
          CREATE TABLE IF NOT EXISTS equity_samples(t INTEGER PRIMARY KEY,cash REAL,unrealized REAL,equity REAL,complete_marks INTEGER,funding_known INTEGER);
        ''')
        old = self.db.execute("SELECT v FROM meta WHERE k='config_sha'").fetchone()
        if old and old[0] != config_sha: raise ValueError('configuration mismatch; never reuse a changed-rule book')
        with self.db: self.db.execute("INSERT OR IGNORE INTO meta VALUES('config_sha',?)", (config_sha,))

    def observe(self, t, kind, payload):
        with self.db: self.db.execute('INSERT INTO observations(t,kind,payload) VALUES(?,?,?)', (t,kind,json.dumps(payload,allow_nan=False)))

    def event(self, identity, uid, t, kind, amount, payload):
        if not math.isfinite(amount): raise ValueError('nonfinite cash')
        self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?)', (identity,uid,t,kind,amount,json.dumps(payload,allow_nan=False)))

    def signals(self):
        return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM signals WHERE status='pending'")]

    def positions(self, status='open'):
        return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM positions WHERE status=?',(status,))]

    def signal(self, signal, now):
        if not signal.get('eligible_signal'): return
        if signal['signal_ms'] > now: raise ValueError('future_signal')
        status = 'pending' if now <= signal['action_ms']+60_000 else 'missed_late_discovery'
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO signals VALUES(?,?,?,?)', (signal['uid'],signal['symbol'],status,json.dumps(signal)))

    def reject(self, signal, now, reason):
        with self.db:
            self.db.execute('UPDATE signals SET status=? WHERE uid=? AND status=?',(reason,signal['uid'],'pending'))
            self.db.execute('INSERT INTO observations(t,kind,payload) VALUES(?,?,?)',(now,'entry_rejected',json.dumps({'uid':signal['uid'],'reason':reason})))
        return None

    def _paper_equity_and_exposure(self):
        """Account equity and committed open notional for the shared sizer.

        Cash events are PnL only, so equity is the isolated starting equity plus
        realised cash plus unrealised mark-to-entry. Exposure is entry notional
        of open positions, the size those entries already consumed.
        """
        cash=self.db.execute('SELECT coalesce(sum(amount),0) FROM events').fetchone()[0]
        unrealized=0.; exposure=0.
        for p in self.positions():
            unrealized += p['quantity']*(p.get('mark_price', p['entry_price'])-p['entry_price'])
            exposure += p['quantity']*p['entry_price']
        return self.starting_equity+cash+unrealized, exposure

    def enter(self, signal, book, instrument, now, *, entries_enabled=True):
        row=self.db.execute('SELECT status FROM signals WHERE uid=?',(signal['uid'],)).fetchone()
        if row is None or row[0]!='pending': return None
        if now < signal['action_ms']: return None
        if not entries_enabled: return self.reject(signal,now,'entries_disabled')
        if now > signal['action_ms']+60_000: return self.reject(signal,now,'missed_action')
        if book.get('s') != signal['symbol'] or int(book['ts']) < signal['action_ms']:
            raise ValueError('wrong_symbol_or_pre_action_quote')
        if instrument.get('symbol') != signal['symbol'] or instrument.get('status')!='Trading':
            return self.reject(signal,now,'instrument_unavailable')
        latest=self.db.execute('SELECT payload FROM positions WHERE symbol=? ORDER BY rowid DESC LIMIT 1',(signal['symbol'],)).fetchone()
        if latest:
            p=json.loads(latest[0])
            if p.get('exit_ms') is None or now//60_000 <= p['exit_ms']//60_000:
                return self.reject(signal,now,'token_busy_inclusive_exit_minute')
        # Reference price is the touch ask plus the modeled entry slip. Depth is
        # checked after the lot floor; a worse walk can only reject, never enlarge.
        ep=float(book['a'][0][0])*(1+SLIP)
        if not fill_gate(signal,ep): return self.reject(signal,now,'fill_gate')
        lot=instrument['lotSizeFilter'];step=Decimal(lot['qtyStep'])
        if not step.is_finite() or step<=0: raise ValueError('invalid_lot_step')
        minqty=float(lot['minOrderQty']);minvalue=float(lot.get('minNotionalValue','0'))
        maxqty=float(lot.get('maxMktOrderQty',lot.get('maxOrderQty','0')))
        if not all(math.isfinite(v) for v in [minqty,minvalue,maxqty]) or minqty<=0 or minvalue<0 or maxqty<minqty:
            raise ValueError('invalid_instrument_limits')
        equity, exposure = self._paper_equity_and_exposure()
        stop_distance = abs(ep-float(signal['stop']))/ep if ep>0 else 0.0
        raw_qty, raw_notional, _risk, notes, _reduced = size_position(
            equity=equity, stop_distance_pct=stop_distance, entry_price=ep,
            total_exposure=exposure, limits=self.limits)
        # Floor to the lot step. If that falls under 5 USDT or the exchange
        # minimum, reject. Do not bump the quantity up to clear either floor.
        qty=_floor_step(raw_qty, step)
        notional=qty*ep
        if qty<=0 or notional < self.limits.min_notional_usdt:
            return self.reject(signal,now,'below_min_notional')
        if qty<minqty or notional<minvalue:
            return self.reject(signal,now,'below_exchange_minimum')
        if qty>maxqty:
            return self.reject(signal,now,'quantity_above_exchange_maximum')
        ep=depth_fill(book,qty,True,now)*(1+SLIP)
        if not fill_gate(signal,ep): return self.reject(signal,now,'fill_gate_after_depth')
        filled_distance=abs(ep-float(signal['stop']))/ep
        _qty, cap_notional, cap_risk, _notes, _reduced = size_position(
            equity=equity, stop_distance_pct=filled_distance, entry_price=ep,
            total_exposure=exposure, limits=self.limits)
        risk=qty*(ep-signal['stop']); filled_notional=qty*ep
        # Depth can only raise a buy. If the walked price breaks a cap, reject.
        if filled_notional > cap_notional+1e-6 or risk > cap_risk+1e-6:
            return self.reject(signal,now,'depth_exceeds_paper_limits')
        p=signal|{'entry_ms':now,'entry_quote_ms':int(book['ts']),'entry_price':ep,'quantity':qty,
                  'notional_usdt':filled_notional,'initial_risk_usdt':risk,'entry_fee':qty*ep*FEE,'exit_ms':None,
                  'funding_observed_through':None,'funding_status':'unknown',
                  'model':'visible_depth_plus_20bp; stop_visible_bid_depth_no_extra_slip',
                  'mark_price':float(book['b'][0][0]),'mark_ms':int(book['ts']),
                  'account_risk_allocation':'hourly_paper_limits',
                  'sizing_notes':notes,'sizing':{
                      'equity_usdt':equity,'open_exposure_usdt':exposure,
                      'starting_equity_usdt':self.starting_equity,
                      'raw_notional_usdt':raw_notional,
                      'max_risk_per_trade_pct':self.limits.max_risk_per_trade_pct,
                      'max_position_pct':self.limits.max_position_pct,
                      'max_total_exposure_pct':self.limits.max_total_exposure_pct,
                      'max_leverage':self.limits.max_leverage,
                      'min_notional_usdt':self.limits.min_notional_usdt,
                      'notes':notes}}
        with self.db:
            self.db.execute('INSERT INTO positions VALUES(?,?,?,?)',(signal['uid'],signal['symbol'],'open',json.dumps(p)))
            self.event(signal['uid']+'|entryfee',signal['uid'],now,'entry_fee',-p['entry_fee'],{'quote':book,'instrument':instrument})
            self.db.execute("UPDATE signals SET status='filled' WHERE uid=?",(signal['uid'],))
        return p

    def mark(self, uid, book, now):
        row=self.db.execute("SELECT payload FROM positions WHERE uid=? AND status='open'",(uid,)).fetchone()
        if row is None:return
        p=json.loads(row[0])
        if book.get('s')!=p['symbol']:raise ValueError('wrong_mark_symbol')
        # Validate depth and age, but mark at best bid; liquidation cost stays separate.
        depth_fill(book,p['quantity'],False,now)
        if int(book['ts'])<p.get('mark_ms',0):raise ValueError('out_of_order_mark')
        p.update(mark_price=float(book['b'][0][0]),mark_ms=int(book['ts']))
        with self.db:self.db.execute('UPDATE positions SET payload=? WHERE uid=?',(json.dumps(p),uid))

    def equity(self, now):
        ps=self.positions();cash=self.db.execute('SELECT coalesce(sum(amount),0) FROM events').fetchone()[0]
        unrealized=sum(p['quantity']*(p.get('mark_price',p['entry_price'])-p['entry_price']) for p in ps)
        complete=all(0<=now-p.get('mark_ms',0)<=15_000 for p in ps)
        known=all(p['funding_status'] in ('observed_through_timestamp','observed_through_exit') for p in ps+self.positions('closed'))
        old=self.db.execute("SELECT v FROM meta WHERE k='equity_extremes'").fetchone()
        peak,drawdown=json.loads(old[0]) if old else [0.,0.]
        if complete:peak=max(peak,cash+unrealized);drawdown=max(drawdown,peak-cash-unrealized)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO equity_samples VALUES(?,?,?,?,?,?)',(now,cash,unrealized,cash+unrealized,int(complete),int(known)))
            self.db.execute("INSERT OR REPLACE INTO meta VALUES('equity_extremes',?)",(json.dumps([peak,drawdown]),))
        return {'cash_pnl_usdt':cash,'unrealized_pnl_usdt':unrealized,'equity_pnl_usdt':cash+unrealized,
                'account_equity_usdt':self.starting_equity+cash+unrealized,
                'all_open_marks_fresh':complete,'funding_observations_available':known,
                'sampled_provisional_drawdown_usdt':drawdown,'quote_mark_basis':'best bid; exit fees and modeled exit slip not deducted until filled'}

    def exit(self, uid, book, now):
        row=self.db.execute('SELECT status,payload FROM positions WHERE uid=?',(uid,)).fetchone()
        if row is None or row['status']!='open': return None
        p=json.loads(row['payload'])
        if book.get('s')!=p['symbol'] or now//60_000<=p['entry_ms']//60_000: return None
        quote=depth_fill(book,p['quantity'],False,now);bid=float(book['b'][0][0])
        reason='stop' if bid<=p['stop'] else 'target' if bid>=p['target'] else None
        if reason is None: return None
        fill=quote if reason=='stop' else quote*(1-SLIP);gross=p['quantity']*(fill-p['entry_price']);fee=p['quantity']*fill*FEE
        p.update(exit_ms=now,exit_price=fill,exit_fee=fee,gross_pnl=gross,exit_reason=reason,funding_status='pending_exit_reconciliation')
        with self.db:
            self.event(uid+'|close',uid,now,'close',gross-fee,{'quote':book,'exit_reason':reason,'gross':gross,'exit_fee':fee})
            self.db.execute("UPDATE positions SET status='closed',payload=? WHERE uid=?",(json.dumps(p),uid))
        return p

    def funding(self, uid, through, observations, *, complete):
        row=self.db.execute('SELECT payload FROM positions WHERE uid=?',(uid,)).fetchone()
        if row is None: raise ValueError('unknown_position')
        p=json.loads(row[0]);end=p['exit_ms'] or through
        if through<p['entry_ms']: raise ValueError('funding_before_entry')
        valued={}
        for obs in observations:
            t=int(obs['t']);rate=float(obs['rate']);price=float(obs['price'])
            if not (p['entry_ms']<t<=min(through,end)): raise ValueError('funding_outside_holding_window')
            if not math.isfinite(rate+price) or price<=0: raise ValueError('invalid_funding')
            if t in valued and valued[t]!=obs: raise ValueError('conflicting_settlement')
            valued[t]=obs
        # Do not claim a complete snapshot that silently dropped a prior settlement.
        prior=self.db.execute("SELECT t FROM events WHERE uid=? AND kind='funding'",(uid,)).fetchall()
        if complete and not {r[0] for r in prior}.issubset(valued): raise ValueError('funding_snapshot_omitted_prior')
        with self.db:
            for t,obs in sorted(valued.items()):
                identity=f'{uid}|funding|{t}';charge=p['quantity']*float(obs['rate'])*float(obs['price'])
                old=self.db.execute('SELECT amount,payload FROM events WHERE id=?',(identity,)).fetchone()
                if old:
                    if not math.isclose(old['amount'],-charge,abs_tol=1e-12): raise ValueError('immutable_funding_changed')
                else: self.event(identity,uid,t,'funding',-charge,obs)
            p['funding_observed_through']=max(p.get('funding_observed_through') or 0,through) if complete else p.get('funding_observed_through')
            p['funding_status']='observed_through_exit' if complete and p['exit_ms'] and through>=p['exit_ms'] else 'observed_through_timestamp' if complete else 'incomplete'
            self.db.execute('UPDATE positions SET payload=? WHERE uid=?',(json.dumps(p),uid))

    def audit(self):
        events=[dict(r) for r in self.db.execute('SELECT * FROM events ORDER BY t,id')];positions=self.positions()+self.positions('closed');issues=[];rows=[]
        for p in positions:
            es=[e for e in events if e['uid']==p['uid']];kinds=[e['kind'] for e in es]
            if kinds.count('entry_fee')!=1 or kinds.count('close')!=int(p['exit_ms'] is not None): issues.append(p['uid']+' event count')
            funding=-sum(e['amount'] for e in es if e['kind']=='funding');net=sum(e['amount'] for e in es)
            expected=-p['entry_fee']-funding+(p.get('gross_pnl',0)-p.get('exit_fee',0))
            if not math.isclose(net,expected,abs_tol=1e-9): issues.append(p['uid']+' cash bridge')
            final=p['funding_status']=='observed_through_exit'
            rows.append({'uid':p['uid'],'symbol':p['symbol'],'closed':p['exit_ms'] is not None,
                         'cash_contribution_usdt':net,'net_R':net/p['initial_risk_usdt'] if final else None,
                         'provisional_net_R':net/p['initial_risk_usdt'],'funding_usdt':funding,'funding_status':p['funding_status']})
        return {'cash_accounting_pass':not issues,'issues':issues,'positions':rows,
                'cash_pnl_usdt':sum(e['amount'] for e in events),'open_positions':len(self.positions()),
                'closed_positions':len(self.positions('closed')),'cash_events':len(events),
                'account_return_percent':None,'forward_profitability_validated':False,
                'note':'Sized with hourly PAPER_LIMITS on this isolated book: 1% risk, 10% position, 50% exposure, 1x leverage. Below 5 USDT is rejected and never upsized. Live orders are not possible from this ledger.'}
