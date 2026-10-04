"""Bar execution for fixed, trailing, and partial exits.

Trails are updated from a completed bar and applied on the next bar.
A same-bar high must not tighten the stop that the same bar is tested against.
Gap fills use the open when that open is worse than the stop.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import study
from entry_trailing_20261004.budget import FEE, MAX_HOLD_MINUTES

MINUTE = pd.Timedelta(minutes=1)


@dataclass(frozen=True)
class ExitSpec:
    """One pre-registered exit. holding is minutes, entry bar included."""

    name: str
    stop_pct: float = 0.01
    target_pct: float | None = None
    activation_pct: float | None = None
    trail_pct: float | None = None
    atr_mult: float | None = None
    atr_floor_pct: float = 0.003
    atr_cap_pct: float = 0.020
    partial_fraction: float = 0.0
    holding: int = MAX_HOLD_MINUTES


def exit_specs() -> dict[str, ExitSpec]:
    """The four Stage 3 exits. There is not a fifth."""
    return {
        'fixed': ExitSpec('fixed', target_pct=0.02),
        'trail': ExitSpec('trail', activation_pct=0.01, trail_pct=0.008),
        'trail_atr': ExitSpec('trail_atr', activation_pct=0.01, atr_mult=1.5),
        'partial_trail': ExitSpec(
            'partial_trail', activation_pct=0.01, trail_pct=0.008, partial_fraction=0.5,
        ),
    }


class FundingBook:
    """Cumulative funding in price units, matching study.Tape.

    fp[k] sums funding_rate * minute-open mark for the first k events.
    Search uses nanoseconds so microsecond and nanosecond indexes agree.
    """

    def __init__(self, candles: pd.DataFrame, funding: pd.DataFrame):
        opens = candles['open'].to_numpy(dtype=float)
        if funding is None or len(funding) == 0:
            self.ft = np.array([], dtype=np.int64)
            self.fp = np.array([0.0])
            return
        self.ft = study.epoch_ns(funding.index)
        loc = candles.index.get_indexer(funding.index.floor('min'), method='pad')
        rates = funding['funding_rate'].to_numpy(dtype=float)
        vals = rates * opens[np.clip(loc, 0, len(opens) - 1)]
        self.fp = np.r_[0.0, np.cumsum(vals)]

    def charge(self, side: int, entry, exit_bar, ep: float, fraction: float, exact_close: bool) -> float:
        """Funding return for `fraction` of the original unit notional.

        Entry timestamp is excluded. exact_close includes the exit minute.
        Otherwise the more costly of the two minute bounds is used.
        """
        if fraction == 0 or ep == 0 or len(self.ft) == 0:
            return 0.0
        a = int(np.searchsorted(self.ft, np.int64(entry.value), side='right'))
        x = int(np.searchsorted(self.ft, np.int64(exit_bar.value), side='right'))
        y = int(np.searchsorted(self.ft, np.int64((exit_bar + MINUTE).value), side='right'))
        early = fraction * side * (self.fp[x] - self.fp[a]) / ep
        late = fraction * side * (self.fp[y] - self.fp[a]) / ep
        return float(late if exact_close else max(early, late))


def window_inside(ts, start, end, horizon_minutes: int) -> bool:
    """True when the whole hold lies inside [start, end]."""
    return bool(ts >= start and ts + pd.Timedelta(minutes=horizon_minutes) <= end)


def _stop_quote(side: int, stop: float, bar_open: float) -> float:
    """Gap through the stop fills at the open, which is worse than the stop."""
    if side == 1:
        return min(stop, bar_open)
    return max(stop, bar_open)


def _stop_reason(tightened: bool, partial_done: bool) -> str:
    if partial_done and tightened:
        return 'partial_trail'
    if partial_done:
        return 'partial_stop'
    if tightened:
        return 'trail'
    return 'stop'


def _raw_trail(side: int, extreme: float, ep: float, spec: ExitSpec, atr_price: float | None) -> float | None:
    """Protective price implied by the current completed extreme, before the monotonic clamp."""
    if spec.atr_mult is not None:
        if atr_price is None or not np.isfinite(atr_price):
            return None
        distance = float(np.clip(spec.atr_mult * atr_price, spec.atr_floor_pct * ep, spec.atr_cap_pct * ep))
        return extreme - side * distance
    if spec.trail_pct is not None:
        # 0.8% of the extreme price, not of the entry.
        return extreme * (1 - side * spec.trail_pct)
    return None


def _activation_reached(side: int, extreme: float, ep: float, activation_pct: float) -> bool:
    level = ep * (1 + side * activation_pct)
    if side == 1:
        return extreme >= level
    return extreme <= level


def simulate_trade(
    index: pd.DatetimeIndex,
    open_,
    high,
    low,
    close,
    entry_i: int,
    side: int,
    slip: float,
    spec: ExitSpec,
    funding: FundingBook,
    atr_price: float | None = None,
) -> dict | None:
    """Simulate one entry. Returns None when the hold does not fit on the tape."""
    holding = spec.holding
    n = len(index)
    if entry_i < 0 or entry_i + holding > n:
        return None
    side = int(side)
    ep = float(open_[entry_i] * (1 + side * slip))
    if not np.isfinite(ep) or ep <= 0:
        return None
    initial = ep * (1 - side * spec.stop_pct)
    protective = initial
    extreme = ep
    tightened = False
    activated = False
    partial_done = False
    partial_i = None
    partial_quote = None
    target = None if spec.target_pct is None else ep * (1 + side * spec.target_pct)
    partial_level = None
    if spec.partial_fraction > 0 and spec.activation_pct is not None:
        partial_level = ep * (1 + side * spec.activation_pct)

    reason = None
    ambiguous = False
    exit_i = None
    exit_quote = None

    for off in range(holding):
        j = entry_i + off
        bar_open = float(open_[j])
        bar_high = float(high[j])
        bar_low = float(low[j])
        bar_close = float(close[j])
        if side == 1:
            stop_hit = bar_low <= protective
            target_hit = target is not None and bar_high >= target
            partial_hit = (not partial_done) and partial_level is not None and bar_high >= partial_level
        else:
            stop_hit = bar_high >= protective
            target_hit = target is not None and bar_low <= target
            partial_hit = (not partial_done) and partial_level is not None and bar_low <= partial_level

        # Stop known at the open wins ties against a target or a partial on this bar.
        if stop_hit and (target_hit or partial_hit):
            ambiguous = True
            exit_quote = _stop_quote(side, protective, bar_open)
            exit_i = j
            reason = _stop_reason(tightened, partial_done)
            break
        if stop_hit:
            exit_quote = _stop_quote(side, protective, bar_open)
            exit_i = j
            reason = _stop_reason(tightened, partial_done)
            break
        if target_hit:
            exit_quote = float(target)
            exit_i = j
            reason = 'target'
            break
        if partial_hit:
            # Quote stays at the partial level. A favourable gap is not an improvement.
            partial_quote = float(partial_level)
            partial_i = j
            partial_done = True
        if off == holding - 1:
            exit_quote = bar_close
            exit_i = j
            reason = 'partial_time' if partial_done else 'time'
            break

        # Completed-bar extreme. It can tighten the stop only for the next bar.
        if side == 1:
            extreme = max(extreme, bar_high)
        else:
            extreme = min(extreme, bar_low)
        if spec.activation_pct is not None and _activation_reached(side, extreme, ep, spec.activation_pct):
            activated = True
            raw = _raw_trail(side, extreme, ep, spec, atr_price)
            if raw is not None:
                new_prot = max(protective, raw) if side == 1 else min(protective, raw)
                if new_prot != protective:
                    tightened = True
                protective = new_prot

    assert exit_i is not None and exit_quote is not None and reason is not None
    if partial_done:
        frac = float(spec.partial_fraction)
        xp_p = partial_quote * (1 - side * slip)
        xp_r = exit_quote * (1 - side * slip)
        gross = frac * side * (xp_p - ep) / ep + (1 - frac) * side * (xp_r - ep) / ep
        # Entry fee once, then a fee on each exit fill's notional.
        fees = FEE * (1 + frac * xp_p / ep + (1 - frac) * xp_r / ep)
        fund = funding.charge(side, index[entry_i], index[partial_i], ep, frac, False)
        fund += funding.charge(
            side, index[entry_i], index[exit_i], ep, 1 - frac, reason == 'partial_time',
        )
        exit_price = xp_r
        partial_price = xp_p
        realized = frac * side * (partial_quote - ep) / ep + (1 - frac) * side * (exit_quote - ep) / ep
    else:
        xp = exit_quote * (1 - side * slip)
        gross = side * (xp - ep) / ep
        fees = FEE * (1 + xp / ep)
        fund = funding.charge(side, index[entry_i], index[exit_i], ep, 1.0, reason == 'time')
        exit_price = xp
        partial_price = np.nan
        realized = side * (exit_quote - ep) / ep

    window_h = high[entry_i:exit_i + 1]
    window_l = low[entry_i:exit_i + 1]
    if side == 1:
        mfe = float(window_h.max() - ep) / ep
        mae = float(ep - window_l.min()) / ep
    else:
        mfe = float(ep - window_l.min()) / ep
        mae = float(window_h.max() - ep) / ep
    mae = max(0.0, mae)
    return {
        'entry': index[entry_i],
        'exit_bar': index[exit_i],
        'exit_i': int(exit_i),
        'side': side,
        'entry_price': ep,
        'exit_price': float(exit_price),
        'partial_price': float(partial_price) if partial_price == partial_price else np.nan,
        'gross_return': float(gross),
        'fees': float(fees),
        'funding': float(fund),
        'net_return': float(gross - fees - fund),
        'reason': reason,
        'ambiguous': bool(ambiguous),
        'holding_minutes': int(exit_i - entry_i + 1),
        'mfe': float(mfe),
        'mae': float(mae),
        'giveback': float(mfe - realized),
        'activated': bool(activated),
    }


def fixed_horizon_trade(
    index, open_, high, low, close, entry_i: int, side: int, slip: float,
    funding: FundingBook, holding: int = 240,
) -> dict | None:
    """Mark-to-horizon at the last bar close. No stop and no target."""
    if entry_i < 0 or entry_i + holding > len(index):
        return None
    side = int(side)
    j = entry_i + holding - 1
    ep = float(open_[entry_i] * (1 + side * slip))
    quote = float(close[j])
    xp = quote * (1 - side * slip)
    gross = side * (xp - ep) / ep
    fees = FEE * (1 + xp / ep)
    fund = funding.charge(side, index[entry_i], index[j], ep, 1.0, True)
    if side == 1:
        mfe = float(high[entry_i:j + 1].max() - ep) / ep
        mae = max(0.0, float(ep - low[entry_i:j + 1].min()) / ep)
    else:
        mfe = float(ep - low[entry_i:j + 1].min()) / ep
        mae = max(0.0, float(high[entry_i:j + 1].max() - ep) / ep)
    realized = side * (quote - ep) / ep
    return {
        'entry': index[entry_i],
        'exit_bar': index[j],
        'exit_i': int(j),
        'side': side,
        'entry_price': ep,
        'exit_price': float(xp),
        'partial_price': np.nan,
        'gross_return': float(gross),
        'fees': float(fees),
        'funding': float(fund),
        'net_return': float(gross - fees - fund),
        'reason': 'horizon',
        'ambiguous': False,
        'holding_minutes': int(holding),
        'mfe': float(mfe),
        'mae': float(mae),
        'giveback': float(mfe - realized),
        'activated': False,
    }


def run_entries(
    candles: pd.DataFrame,
    funding: FundingBook,
    times,
    side: int,
    slip: float,
    spec: ExitSpec,
    start,
    end,
    atr_at=None,
    one_position: bool = False,
) -> pd.DataFrame:
    """Paired mode keeps every in-window signal. Chronological mode keeps one position."""
    index = candles.index
    open_ = candles['open'].to_numpy(dtype=float)
    high = candles['high'].to_numpy(dtype=float)
    low = candles['low'].to_numpy(dtype=float)
    close = candles['close'].to_numpy(dtype=float)
    rows = []
    last = -1
    for ts in times:
        if not window_inside(ts, start, end, spec.holding):
            continue
        i = int(index.get_indexer([ts])[0])
        if i < 0:
            continue
        if one_position and i <= last:
            continue
        atr = None if atr_at is None else atr_at.get(ts, None)
        row = simulate_trade(index, open_, high, low, close, i, side, slip, spec, funding, atr)
        if row is None:
            continue
        rows.append(row)
        if one_position:
            last = row['exit_i']
    return pd.DataFrame(rows)


def decluster_times(times, minutes: int = 240):
    """Keep a time only when it starts at least `minutes` after the previous keep."""
    kept = []
    last = None
    span = pd.Timedelta(minutes=minutes)
    for ts in pd.DatetimeIndex(times).sort_values():
        if last is None or ts >= last + span:
            kept.append(ts)
            last = ts
    return pd.DatetimeIndex(kept)


def _losing_streak(nets: np.ndarray) -> int:
    best = current = 0
    for value in nets:
        if value < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def score_trades(frame: pd.DataFrame) -> dict:
    """Unit-notional diagnostics. Drawdown is the additive cumulative-sum decline."""
    empty = {
        'trades': 0, 'mean': None, 'pf': None, 'win_rate': None, 'payoff': None,
        'mean_mae': None, 'mean_giveback': None, 'mean_holding_minutes': None,
        'losing_streak': 0, 'max_drawdown_unit_notional': None, 'exit_reasons': {},
    }
    if frame is None or len(frame) == 0:
        return empty
    nets = frame['net_return'].to_numpy(dtype=float)
    wins = nets[nets > 0]
    losses = nets[nets < 0]
    loss_sum = float(-losses.sum()) if len(losses) else 0.0
    pf = float(wins.sum() / loss_sum) if loss_sum > 0 else None
    payoff = None
    if len(wins) and len(losses):
        payoff = float(wins.mean() / abs(losses.mean()))
    curve = np.r_[0.0, np.cumsum(nets)]
    peak = np.maximum.accumulate(curve)
    reasons = {str(k): int(v) for k, v in frame['reason'].value_counts().items()}
    return {
        'trades': int(len(nets)),
        'mean': float(nets.mean()),
        'pf': pf,
        'win_rate': float((nets > 0).mean()),
        'payoff': payoff,
        'mean_mae': float(frame['mae'].mean()),
        'mean_giveback': float(frame['giveback'].mean()),
        'mean_holding_minutes': float(frame['holding_minutes'].mean()),
        'losing_streak': _losing_streak(nets),
        'max_drawdown_unit_notional': float((peak - curve).max()),
        'exit_reasons': reasons,
    }


def passes_screen(discovery: dict, validation: dict, stress_d: dict, stress_v: dict) -> bool:
    """Necessary screen from the addendum. Not sufficient, and not a 2026 test."""
    def ok(stats: dict) -> bool:
        return (
            stats['trades'] >= 50
            and stats['mean'] is not None and stats['mean'] > 0
            and stats['pf'] is not None and stats['pf'] >= 1.15
        )
    return (
        ok(discovery) and ok(validation)
        and stress_d['mean'] is not None and stress_d['mean'] > 0
        and stress_v['mean'] is not None and stress_v['mean'] > 0
    )
