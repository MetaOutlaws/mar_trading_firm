"""Fade a multi-bar range/swing probe that fails and closes back inside.

Range high/low is the ``lookback`` window of *prior* bars only (Donchian
channel ending at t-1). The current bar cannot lift or lower its own
range. A probe is then frozen against that published edge:

- SHORT: highs print beyond ``range_high`` for ``min_probe_bars``
  consecutive bars, then ``close_t`` is back below ``range_high`` and
  still inside ``[range_low, range_high]``.
- LONG: lows print beyond ``range_low`` for ``min_probe_bars``, then
  ``close_t`` is back above ``range_low`` and still inside.

Quant-locked ``require_close_inside=True``: a close that blows through
the far rail is not a reclaim. Probe bars are *high/low* tags (wick
allowed). That is not a single-bar close-through
(``failed_range_break_reversion`` — 119) and not a same-bar wick spring
(``wyckoff_spring_reclaim`` — 127, ``hold_bars`` 1–2). Free params are
only ``lookback`` (grid ``[16, 20]``) and ``min_probe_bars`` (grid
``[2, 3]``). ATR period is locked at 20 if a tolerance is ever added;
this sleeve does not search ATR. No volume gate. OHLCV only. Causal:
bars ``<= t``. The engine fills at ``t+1`` open.

Not ``prior_day_extreme_reject`` (118 — prior UTC day H/L).
Not ``failed_range_break_reversion`` (119 — single-bar closed-outside).
Not ``ib_fail_reversion`` (124 — London IB mother).
Not ``wyckoff_spring_reclaim`` (127 — same-bar / next-bar wick spring).
Not ``classic_floor_pivot_reject`` (129 — P/R1/S1).
Do not recode spent families 118–129. Do not code ``displacement_gap_follow``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked if a tolerance is ever added. Not a free / searched param.
ATR_PERIOD = 20


@dataclass(frozen=True)
class FailedBreakReclaimParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Prior-bar range window. Quant grid: [16, 20].
    lookback: int = 20
    # Consecutive highs/lows beyond the frozen edge. Quant grid: [2, 3].
    min_probe_bars: int = 2
    # Quant-locked True: fade only if close_t sits back inside the range.
    require_close_inside: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class FailedBreakReclaimStrategy(Strategy):
    name = "failed_break_reclaim"

    def __init__(self, params: FailedBreakReclaimParams | None = None) -> None:
        super().__init__(params or FailedBreakReclaimParams())
        self.params: FailedBreakReclaimParams = self.params
        lookback = max(1, int(self.params.lookback))
        min_probe = max(2, int(self.params.min_probe_bars))
        # Channel warmup plus room for a multi-bar probe and reclaim close.
        self.min_bars = lookback + min_probe + 1

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        lookback = max(1, int(params.lookback))
        min_probe = max(2, int(params.min_probe_bars))
        close_inside = bool(params.require_close_inside)

        # Prior-bar N-window. Current wick cannot set the published edge.
        native_high = high.shift(1).rolling(lookback, min_periods=lookback).max()
        native_low = low.shift(1).rolling(lookback, min_periods=lookback).min()

        n = len(candles)
        high_v = high.to_numpy(dtype="float64", copy=False)
        low_v = low.to_numpy(dtype="float64", copy=False)
        close_v = close.to_numpy(dtype="float64", copy=False)
        nh_v = native_high.to_numpy(dtype="float64", copy=False)
        nl_v = native_low.to_numpy(dtype="float64", copy=False)

        long_raw = np.zeros(n, dtype=bool)
        short_raw = np.zeros(n, dtype=bool)
        frozen_high = np.full(n, np.nan)
        frozen_low = np.full(n, np.nan)
        probe_count = np.full(n, np.nan)

        # Event state is causal: only bars <= i update the frozen edge.
        direction = 0  # +1 down-probe (LONG setup), -1 up-probe (SHORT setup)
        fh = fl = np.nan
        count = 0
        fired = False

        for i in range(n):
            nh = nh_v[i]
            nl = nl_v[i]
            if not np.isfinite(nh) or not np.isfinite(nl):
                continue

            if direction == 0:
                # New probe against this bar's prior-only range.
                up = high_v[i] > nh
                down = low_v[i] < nl
                if up and not down:
                    direction = -1
                    fh, fl = nh, nl
                    count = 1
                    fired = False
                elif down and not up:
                    direction = 1
                    fh, fl = nh, nl
                    count = 1
                    fired = False
            elif direction == -1:
                # Frozen up-probe. Later probe bars do not lift the edge.
                if high_v[i] > fh:
                    count += 1
                inside = close_v[i] < fh
                if close_inside:
                    inside = inside and close_v[i] >= fl
                if count >= min_probe and inside and not fired:
                    short_raw[i] = True
                    fired = True
                if high_v[i] <= fh:
                    direction = 0
            else:
                if low_v[i] < fl:
                    count += 1
                inside = close_v[i] > fl
                if close_inside:
                    inside = inside and close_v[i] <= fh
                if count >= min_probe and inside and not fired:
                    long_raw[i] = True
                    fired = True
                if low_v[i] >= fl:
                    direction = 0

            # Keep the frozen edge on the fire / last-probe bar after reset.
            if direction != 0 or short_raw[i] or long_raw[i]:
                frozen_high[i] = fh
                frozen_low[i] = fl
                probe_count[i] = float(count)

        # Diagnostics: frozen event range while a probe is live, else native.
        range_high = pd.Series(frozen_high, index=candles.index).fillna(native_high)
        range_low = pd.Series(frozen_low, index=candles.index).fillna(native_low)
        signals["range_high"] = range_high
        signals["range_low"] = range_low
        signals["probe_bars"] = probe_count

        if params.side is SignalSide.LONG:
            entry = pd.Series(long_raw, index=candles.index)
            signal_value, side_value = 1, SignalSide.LONG.value
            event_level, other_level = range_low, range_high
        else:
            entry = pd.Series(short_raw, index=candles.index)
            signal_value, side_value = -1, SignalSide.SHORT.value
            event_level, other_level = range_high, range_low

        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (other_level - event_level).abs().replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - event_level) / width).clip(0.0, 1.0)
        else:
            score = ((event_level - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: failed-break reclaim close {close.loc[i]:.4f} "
                    f"vs frozen {event_level.loc[i]:.4f} "
                    f"inside {other_level.loc[i]:.4f} "
                    f"after {int(probe_count[candles.index.get_loc(i)])} probe bar(s)"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "FailedBreakReclaimParams",
    "FailedBreakReclaimStrategy",
]
