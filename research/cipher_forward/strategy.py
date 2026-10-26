"""Causal, frozen W11S/T30 short candidate and its original-2R fill gate.

Transparent public-indicator proxy, not the proprietary Market Cipher formula.
This module evaluates inputs; it neither fetches data nor submits orders.
"""
from __future__ import annotations

import math
import numpy as np

from .features import compute

MINUTE = 60_000
HOUR = 60 * MINUTE
MIN_TURNOVER = 2_835_443.3309875005
MAX_STRUCTURAL_STOP_PERCENT = 4.818264711062109
# Desk read is 0.31% per leg. desk031 is fee 0.00055 plus slip 0.00255 on
# entry, on a non-stop exit, and on a stop exit. baseline, moderate, and
# severe are unchanged. Do not edit those three tuples. Labels live in desk_cost.py.
FEE = .00055
COSTS = {
    "desk031": (.00255, .00255),
    "baseline": (.002, 0.),
    "moderate": (.003, .002),
    "severe": (.01, .01),
}


def validate_history(bars, seed_start_ms: int, asof_ms: int):
    """Absolute UTC clock; reject partial bars and an implicitly rolling seed.

    Caller persists seed_start_ms AND the complete growing history (or an
    independently verified equivalent state). Missing rows are six NaNs.
    The mandatory empty row at the seed boundary matches the research kernel.
    """
    if (type(seed_start_ms) is not int or type(asof_ms) is not int
            or seed_start_ms < 0 or seed_start_ms % (4 * HOUR)
            or asof_ms % HOUR or asof_ms < seed_start_ms):
        raise ValueError("invalid completed-hour clock")
    a = np.asarray(bars, dtype=np.float64)
    if a.ndim != 2 or a.shape != ((asof_ms - seed_start_ms) // HOUR + 1, 6):
        raise ValueError("history does not end exactly at asof")
    missing = np.isnan(a).all(axis=1)
    valid = np.isfinite(a).all(axis=1)
    if not missing[0] or not (missing | valid).all():
        raise ValueError("empty seed row and complete OHLCV/turnover rows required")
    q = a[valid]
    if len(q) and (np.any(q[:, :4] <= 0) or np.any(q[:, 4:] < 0)
                  or np.any(q[:, 1] < np.max(q[:, [0, 2, 3]], axis=1))
                  or np.any(q[:, 2] > np.min(q[:, [0, 1, 3]], axis=1))):
        raise ValueError("invalid OHLCV/turnover")
    return a


def from_feature(symbol: str, row, seed_start_ms: int) -> dict:
    """Translate one already-computed, close-labelled feature row."""
    signal_ms = seed_start_ms + int(row['hour']) * HOUR
    good = bool(row['ready'] and row['side'] == -1 and row['flow'] and row['trend'])
    stop, close = float(row['stop']), float(row['close'])
    risk = stop - close
    structural = 100 * risk / close if close > 0 else math.nan
    good = good and all(math.isfinite(x) for x in (stop, close, risk)) and risk > 0
    # The extended target must not be used to relax the old entry eligibility.
    target2 = close - 2 * risk
    target3 = close - 3 * risk
    filtered = bool(good and row['turnover'] >= MIN_TURNOVER
                    and structural <= MAX_STRUCTURAL_STOP_PERCENT)
    out = dict(uid=f"C3|{symbol}|{signal_ms}", symbol=symbol, source='C3', side=-1,
               signal_ms=signal_ms, action_ms=signal_ms + MINUTE,
               action_deadline_ms=signal_ms + 2 * MINUTE,
               context_ms=seed_start_ms + int(row['context_hour']) * HOUR
                   if row['context_hour'] >= 0 else None,
               eligible_signal=good, filter_pass=filtered,
               reason='candidate_requires_original_2R_fill_gate' if good else 'no_signal',
               signal_close=close, stop=stop, original_target=target2, target=target3,
               structural_stop_pct=structural, turnover=float(row['turnover']),
               w1=float(row['w1']), w2=float(row['w2']), cmf=float(row['cmf']),
               seed_start_ms=seed_start_ms)
    return {k: None if isinstance(v, float) and not math.isfinite(v) else v
            for k, v in out.items()}


def decision(symbol: str, bars, seed_start_ms: int, asof_ms: int) -> dict:
    a = validate_history(bars, seed_start_ms, asof_ms)
    # Small histories never reach 200 complete 4h bars; no kernel padding tricks.
    if len(a) < 801:
        return dict(symbol=symbol, source='C3', eligible_signal=False,
                    reason='warmup', signal_ms=asof_ms, seed_start_ms=seed_start_ms)
    return from_feature(symbol, compute(a).iloc[-1], seed_start_ms)


def fill_gate(signal: dict, entry_fill: float, *, fee: float = FEE,
              market_slip: float = .002, total_stop_slip: float = 0.) -> dict:
    """Actual adverse entry fill supplied by adapter; never apply slip twice.

    Planned stop/old-target prices retain the research cost convention. Return
    price-risk and fee-aware planned loss separately; R uses the former.
    """
    numbers = (entry_fill, fee, market_slip, total_stop_slip,
               signal.get('stop'), signal.get('original_target'), signal.get('target'))
    if (any(isinstance(x, bool) or not isinstance(x, (int, float))
            or not math.isfinite(x) for x in numbers)
            or entry_fill <= 0 or not 0 <= fee < 1
            or not 0 <= market_slip < 1 or not 0 <= total_stop_slip < 1):
        raise ValueError('invalid fill/cost geometry')
    stop = signal['stop']
    old_target = signal['original_target']
    risk = stop - entry_fill
    planned_stop = stop * (1 + total_stop_slip)
    planned_old_target = old_target * (1 + market_slip)
    loss = planned_stop - entry_fill + fee * (entry_fill + planned_stop)
    gain = entry_fill - planned_old_target - fee * (entry_fill + planned_old_target)
    rr = gain / loss if loss > 0 else None
    eligible = bool(signal.get('eligible_signal') is True and signal.get('side') == -1
                    and 0 < signal['target'] < old_target < entry_fill < stop
                    and .005 <= risk / entry_fill <= .15 and loss > 0 and rr >= 1.5)
    return dict(eligible=eligible, price_risk_unit=risk, planned_loss_unit=loss,
                planned_gain_unit=gain, original_planned_rr=rr,
                reason='eligible' if eligible else 'original_2R_fill_gate')
