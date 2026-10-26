"""Causal shared H/B/C3 feed for every internal simulated portfolio."""
from dataclasses import replace
import math
from pathlib import Path

import pandas as pd

from config.universe import SECTORS
from core.strategy.base import SignalSide
from .bl8 import decision as bl8_decision
from .strategy import decision as cipher_decision
from .seed import SeedStore
from core.strategy.f111_semantics import update_touch
from core.strategy.l01_context import ContextStore, decision as l01_decision, advance, utc
from core.strategy.mar_f111_r12_extension_latefloor_v1 import MarF111R12ExtensionLatefloorV1Strategy as HourlyRule

MINUTE = 60_000
HOUR = 60*MINUTE


def sector(symbol):
    return next((name for name, symbols in SECTORS.items() if symbol in symbols), 'other')


def parse_bars(rows, duration, asof):
    bars = sorted([dict(t=int(r[0])+duration, o=float(r[1]), h=float(r[2]),
                        l=float(r[3]), c=float(r[4]), v=float(r[5]))
                   for r in rows if int(r[0])+duration <= asof], key=lambda r:r['t'])
    if not bars or len({b['t'] for b in bars}) != len(bars):
        raise ValueError('missing/duplicate bars')
    for b in bars:
        if (b['t'] % duration or not all(math.isfinite(b[k]) for k in ('o','h','l','c','v'))
                or min(b['o'],b['h'],b['l'],b['c']) <= 0 or b['v'] < 0
                or b['h'] < max(b['o'],b['c'],b['l']) or b['l'] > min(b['o'],b['c'])):
            raise ValueError('invalid OHLCV')
    if any(b['t']-a['t'] != duration for a,b in zip(bars,bars[1:])):
        raise ValueError('non-contiguous bars')
    return bars


def frame(bars):
    return pd.DataFrame([dict(open=b['o'],high=b['h'],low=b['l'],close=b['c'],volume=b['v']) for b in bars],
                        index=pd.to_datetime([b['t']-HOUR for b in bars],unit='ms',utc=True))


def hourly_candidates(symbol, hours, btc, asof, context_state):
    if len(hours)<HourlyRule.min_bars or hours[-1]['t'] != asof:
        raise ValueError('hourly history incomplete')
    bars, btc_frame = frame(hours), frame(btc)
    pending, observations = [], []
    for side in (SignalSide.LONG, SignalSide.SHORT):
        rule = HourlyRule(replace(HourlyRule().params, side=side))
        last = rule.generate_signals(rule.prepare_market_context(symbol, bars, btc_frame)).iloc[-1]
        reason = str(last.get('f111_rejection_reason') or '')
        passed = int(last.get('signal',0)) != 0
        info = {}
        if passed:
            try:
                ctx = context_state() if side is SignalSide.LONG and callable(context_state) else context_state
            except (ValueError, OSError, KeyError) as exc:
                ctx=None
                info['context_error']=str(exc)
            passed, reason, info = l01_decision(side.value, ctx, pd.Timestamp(asof,unit='ms',tz='UTC'))
        observations.append(dict(symbol=symbol, source='H', side=side.value, signal_ms=asof,
                                 passed=bool(passed), reason=reason, context=info))
        if passed:
            pending.append(dict(uid=f'{symbol}|H|{side.sign}|{asof*1_000_000}', symbol=symbol,
                source='H',side=int(side.sign),sector=sector(symbol),signal_ms=asof,
                boundary=float(last.entry_boundary),prior_atr=float(last.prior_atr),
                next_minute=asof,touched=False,eligible_signal=True))
    return pending, observations


def advance_retest(pending, bars, asof):
    """Only completed minutes; a reclaim schedules the immediately next minute."""
    out = dict(pending)
    rows = {b['t']-MINUTE:b for b in bars}
    while out['next_minute']+MINUTE <= asof:
        t = out['next_minute']
        if t >= out['signal_ms']+HOUR:
            return None, None, 'retest_expired'
        if t not in rows:
            return None, None, 'retest_missing_minute'
        b = rows[t]
        out['touched'], reclaimed = update_touch(out['side'],b['h'],b['l'],b['c'],out['boundary'],out['touched'])
        out['next_minute'] += MINUTE
        if reclaimed:
            signal = {k:v for k,v in out.items() if k not in ('next_minute','touched')}
            signal['action_ms'] = t+MINUTE
            return None, signal, 'candidate'
    return out, None, 'pending'


class SignalFeed:
    def __init__(self, get, universe, context_root, seed_root):
        self.get, self.universe = get, universe
        self.context = ContextStore(root=Path(context_root))
        self.seed = SeedStore(seed_root, universe)

    def histories(self, symbol, asof):
        rows = self.get('instruments-info',symbol=symbol)['result']['list']
        matches = [r for r in rows if r.get('symbol')==symbol and r.get('status')=='Trading']
        if len(matches)!=1:
            return dict(symbol=symbol,unavailable=True,reason='instrument_not_trading')
        histories=[]
        for interval,duration,count in [('60',HOUR,860),('240',4*HOUR,40)]:
            data=self.get('kline',symbol=symbol,interval=interval,end=asof-1,limit=count)
            histories.append(parse_bars(data['result']['list'],duration,asof))
        return dict(symbol=symbol,instrument=matches[0],hours=histories[0],four=histories[1])

    def evaluate(self, history, btc, asof):
        symbol=history['symbol']
        if history.get('unavailable'):
            return [],[],[history]
        observations=[]
        pending=[]
        try:
            pending,rows=hourly_candidates(symbol,history['hours'],btc,asof,lambda:self.long_context(symbol,asof))
            observations.extend(rows)
        except (ValueError, OSError, KeyError) as exc:
            observations.append(dict(symbol=symbol,source='H',error=str(exc)))
        candidates=[]
        try:
            signal=bl8_decision(symbol,history['hours'],history['four'],asof)
            observations.append(signal)
            if signal.get('eligible_signal'):
                candidates.append(signal|dict(source='B',side=1,sector=sector(symbol)))
        except (ValueError, KeyError) as exc:
            observations.append(dict(symbol=symbol,source='B',error=str(exc)))
        try:
            a=self.seed.advance(symbol,asof,self.get)
            signal=cipher_decision(symbol,a,self.seed.start,asof)
            observations.append(signal)
            if signal.get('eligible_signal'):
                candidates.append(signal|dict(sector=sector(symbol)))
        except (ValueError, OSError, KeyError) as exc:
            observations.append(dict(symbol=symbol,source='C3',error=str(exc)))
        return pending,candidates,observations

    def long_context(self, symbol, asof):
        state=self.context.read(symbol)
        target=utc(pd.Timestamp(asof,unit='ms',tz='UTC')).floor('4h')
        start=utc(state['processed_through'])
        if start>=target:
            return state
        if target-start>pd.Timedelta(hours=8):
            raise ValueError('l01_context_prepare_required')
        # Continue the exact seed in memory. The production context stays read-only.
        rows=self.get('kline',symbol=symbol,interval='1',start=int(start.timestamp()*1000),
                      end=int(target.timestamp()*1000)-1,limit=1000)['result']['list']
        bars=parse_bars(rows,MINUTE,asof)
        values=pd.DataFrame({'close':[b['c'] for b in bars]},
            index=pd.to_datetime([b['t']-MINUTE for b in bars],unit='ms',utc=True))
        return advance(state,values,target)

    def retest_bars(self, symbol, asof):
        rows=self.get('kline',symbol=symbol,interval='1',end=asof-1,limit=65)['result']['list']
        return parse_bars(rows,MINUTE,asof)
