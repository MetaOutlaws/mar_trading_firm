"""Frozen BL8 long rebound decision; completed, UTC close-labelled bars only.

Standalone standard-library implementation for the isolated public-data paper
observer. It imports neither credentials nor any exchange order client.
"""
from __future__ import annotations

import math
import statistics

MINUTE = 60_000
HOUR = 60 * MINUTE


def _sum20(values):
    """Frozen NumPy float64 contiguous-window pairwise reduction, length20.

    Exact arithmetic order matters at a strict band boundary. Keep this small
    reduction here so the isolated observer needs no numerical dependency.
    Historical parity tests compare all retained candidate windows.
    """
    if len(values)!=20:raise ValueError('band window must contain20 closes')
    r=[float(v) for v in values[:8]]
    for j in range(8):r[j]+=float(values[j+8])
    total=((r[0]+r[1])+(r[2]+r[3]))+((r[4]+r[5])+(r[6]+r[7]))
    for value in values[16:]:total+=float(value)
    return total


def decision(symbol: str, hours: list[dict], four_hours: list[dict], asof: int) -> dict:
    """Bars use close timestamp ``t`` and o/h/l/c values; no partial bars."""
    out = {"symbol": symbol, "eligible_signal": False, "reason": "missing_context"}
    for bars, duration, minimum in [(hours, HOUR, 25), (four_hours, 4 * HOUR, 18)]:
        if len(bars) < minimum:
            return out
        if any(b["t"] > asof or b["t"] % duration for b in bars):
            raise ValueError("future or unaligned completed bar")
        if any(bars[i]["t"] - bars[i-1]["t"] != duration for i in range(1, len(bars))):
            raise ValueError("missing or duplicate completed bar")
        for b in bars:
            if not all(math.isfinite(b[k]) and b[k] > 0 for k in "ohlc"):
                raise ValueError("invalid price")
            if not (b['l'] <= min(b['o'], b['c']) <= max(b['o'], b['c']) <= b['h']):
                raise ValueError("inconsistent OHLC")
    h, prev = hours[-1], hours[-2]
    if h['t'] != asof // HOUR * HOUR or not 0 <= h['t'] - four_hours[-1]['t'] < 4*HOUR:
        return out | {"reason": "stale_context"}
    window = [b['c'] for b in hours[-22:-2]]
    mean = _sum20(window)/20
    # population std of exactly 20 prior closes, excluding trigger and previous bar
    deviations=[float(v)-mean for v in window]
    sd = math.sqrt(_sum20([v*v for v in deviations])/20)
    atr = statistics.fmean([max(hours[i]['h']-hours[i]['l'],
                                     abs(hours[i]['h']-hours[i-1]['c']),
                                     abs(hours[i]['l']-hours[i-1]['c']))
                            for i in range(len(hours)-15, len(hours)-1)])
    width = max(b['h'] for b in hours[-25:-1]) - min(b['l'] for b in hours[-25:-1])
    b = four_hours
    distance = sum(abs(b[i]['c']-b[i-1]['c']) for i in range(len(b)-12, len(b)))
    r48 = b[-1]['c']-b[-13]['c']; er = abs(r48)/distance if distance else 0.
    high, low = max(x['h'] for x in b[-12:]), min(x['l'] for x in b[-12:])
    oldmid = (max(x['h'] for x in b[-18:-6])+min(x['l'] for x in b[-18:-6]))/2
    width4 = high-low
    if atr <= 0 or width <= 0 or width4 <= 0:
        return out
    stability = abs((high+low)/2-oldmid)/width4; widthpct = width4/b[-1]['c']
    regime = 'transition'
    if er >= .45: regime = 'trend_up' if r48 >= 0 else 'trend_down'
    elif er <= .25:
        regime = ('stable_wide_range' if widthpct >= .0204 else 'tight_range') if stability <= .25 else 'unstable_chop'
    stop = min(h['l'], prev['l']) - .5*atr
    eligible = (h['c'] > h['o'] and sd > 0 and prev['c'] < mean-2*sd
                and h['c'] > mean-2*sd and h['c'] < mean
                and mean/h['c']-1 >= .0102 and h['c'] > stop)
    return out | {"uid": f"{symbol}|B|1|{h['t']*1_000_000}", "signal_ms": h['t'],
                  "action_ms": h['t']+MINUTE, "eligible_signal": bool(eligible),
                  "reason": "candidate_requires_fill_gate" if eligible else "no_signal",
                  "stop": stop, "target": mean, "atr": atr, "band_std": sd,
                  "context_ms": b[-1]['t'], "regime": regime, "width_pct": widthpct}


def fill_gate(signal: dict, fill: float) -> bool:
    return (signal.get('eligible_signal') is True and math.isfinite(fill) and fill > 0
            and 0 < signal['stop'] < fill < signal['target']
            and (fill-signal['stop'])/fill >= .08)
