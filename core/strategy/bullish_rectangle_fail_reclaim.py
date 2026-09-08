"""Fade a failed probe of a flat dual-rail rectangle (support + resistance).

A rectangle is two multi-touch horizontal rails in ``lookback``:

- Upper rail (resistance): at least ``min_touches_per_rail`` published
  swing highs whose span is ``<= atr_tol · ATR(20)``.
- Lower rail (support): the same rule on swing lows.
- Both rails are required. A one-sided Donchian edge is not a box.

Fail-reclaim only (not a breakout continuation):

- LONG: a prior bar *closes* below support, then ``close_t`` is back
  inside ``[support, resistance]`` within ``max_bars_outside``.
- SHORT: a prior bar *closes* above resistance, then ``close_t`` is
  back inside the same frozen box.

Quant-locked (not searched):

- ``require_close_inside = True``
- ATR period ``20``
- ``min_touches_per_rail = 2``
- ``PIVOT_LEFT = 3``
- ``max_bars_outside = 2`` (not a ``[1, 2]`` grid)

Free search (2 only): ``lookback`` ``[24, 32]``, ``atr_tol`` ``[0.10, 0.15]``.

OHLCV only. Causal: bars ``<= t``. The engine fills at ``t+1`` open.

Not ``failed_range_break_reversion`` (119 — Donchian close-through, no
dual-rail multi-touch flat rectangle).
Not ``failed_break_reclaim`` (130 — Donchian wick-probe, no flat
rectangle rails / multi-touch box).
Not a triangle / wedge / H&S / cup / pennant recode.
Do not recode spent families 118–132. Do not code ``three_black_crows``
or ``displacement_gap_follow``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Swing confirmation matches the other chart-pattern sleeves. Not searched.
PIVOT_LEFT = 3
# Quant lock: each rail needs this many published swings. Not searched.
MIN_TOUCHES_PER_RAIL = 2
# Wilder ATR window for the flat-rail band. Not a free search param.
ATR_PERIOD = 20
# Quant lock: close-outside then close-inside must print within this many
# bars. Not a [1, 2] search grid — keeps this clearer of job 119.
MAX_BARS_OUTSIDE_LOCKED = 2
REQUIRE_CLOSE_INSIDE_LOCKED = True


@dataclass(frozen=True)
class BullishRectangleFailReclaimParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Publication window that must hold both flat rails. Quant grid: [24, 32].
    lookback: int = 32
    # Flat-rail band as a multiple of ATR(20). Quant grid: [0.10, 0.15].
    atr_tol: float = 0.15
    # Quant-locked. Walk-forward must not search this.
    max_bars_outside: int = MAX_BARS_OUTSIDE_LOCKED
    # Quant-locked True: fade only if close_t sits back inside the box.
    require_close_inside: bool = REQUIRE_CLOSE_INSIDE_LOCKED
    # Quant-locked. Walk-forward must not search this.
    min_touches_per_rail: int = MIN_TOUCHES_PER_RAIL
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class BullishRectangleFailReclaimStrategy(Strategy):
    name = "bullish_rectangle_fail_reclaim"

    def __init__(self, params: BullishRectangleFailReclaimParams | None = None) -> None:
        super().__init__(params or BullishRectangleFailReclaimParams())
        self.params: BullishRectangleFailReclaimParams = self.params
        lookback = max(2, int(self.params.lookback))
        # Lookback + pivot confirmation + room for the locked fail window.
        self.min_bars = lookback + 2 * PIVOT_LEFT + MAX_BARS_OUTSIDE_LOCKED + 3

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
        lookback = max(2, int(params.lookback))
        atr_tol = float(params.atr_tol)
        # Locks stay locked even if a caller passes another value.
        max_bars = MAX_BARS_OUTSIDE_LOCKED
        min_touches = MIN_TOUCHES_PER_RAIL
        close_inside = REQUIRE_CLOSE_INSIDE_LOCKED

        # Causal swings: only pivots published on bars <= t are visible.
        structure = ind.lookback_swing_structure(
            high, low, lookback=lookback, left=PIVOT_LEFT
        )
        atr = ind.atr(high, low, close, ATR_PERIOD)
        tol = atr_tol * atr
        upper_rail = structure["highs_max"]
        lower_rail = structure["lows_min"]
        # Dual-rail flat box. One sloped rail is a triangle / wedge, not this.
        is_rectangle = (
            structure["n_highs"].ge(min_touches)
            & structure["n_lows"].ge(min_touches)
            & (structure["highs_max"] - structure["highs_min"] <= tol)
            & (structure["lows_max"] - structure["lows_min"] <= tol)
            & upper_rail.gt(lower_rail)
        )

        # Close-through of a published rail — not a wick tag, not a hold.
        # First close-outside freezes the box. A held breakout that stays
        # outside past max_bars_outside expires; it is not a late fade.
        n = len(candles)
        close_v = close.to_numpy(dtype="float64", copy=False)
        upper_v = upper_rail.to_numpy(dtype="float64", copy=False)
        lower_v = lower_rail.to_numpy(dtype="float64", copy=False)
        rect_v = is_rectangle.fillna(False).to_numpy(dtype=bool, copy=False)

        long_raw = np.zeros(n, dtype=bool)
        short_raw = np.zeros(n, dtype=bool)
        frozen_high = np.full(n, np.nan)
        frozen_low = np.full(n, np.nan)
        bars_since = np.full(n, np.nan)

        direction = 0  # +1 down-break (LONG setup), -1 up-break (SHORT setup)
        fh = fl = np.nan
        count = 0
        # Do not re-arm a held breakout as a fresh 2-bar event on the way back.
        armed = True

        for i in range(n):
            u = upper_v[i]
            lo = lower_v[i]
            c = close_v[i]
            rect = bool(rect_v[i]) and np.isfinite(u) and np.isfinite(lo)

            if direction == 0:
                if armed and rect:
                    up = c > u
                    down = c < lo
                    if up and not down:
                        direction = -1
                        fh, fl = u, lo
                        count = 0
                        armed = False
                    elif down and not up:
                        direction = 1
                        fh, fl = u, lo
                        count = 0
                        armed = False
                elif np.isfinite(fh) and np.isfinite(fl) and fl <= c <= fh:
                    # Back inside the last frozen box after an expire / fire.
                    armed = True
                continue

            count += 1
            frozen_high[i] = fh
            frozen_low[i] = fl
            bars_since[i] = float(count)
            inside = c < fh if direction == -1 else c > fl
            if close_inside:
                inside = inside and (c >= fl if direction == -1 else c <= fh)
            if inside and count <= max_bars:
                if direction == -1:
                    short_raw[i] = True
                else:
                    long_raw[i] = True
                direction = 0
                armed = True
            elif count >= max_bars:
                # Held breakout. Wait for a close back inside before re-arming.
                direction = 0
                armed = False

        signals["upper_rail"] = upper_rail
        signals["lower_rail"] = lower_rail
        signals["atr_tol_band"] = tol
        signals["n_highs"] = structure["n_highs"]
        signals["n_lows"] = structure["n_lows"]
        signals["break_high"] = frozen_high
        signals["break_low"] = frozen_low
        signals["bars_since_break"] = bars_since

        if params.side is SignalSide.LONG:
            raw = pd.Series(long_raw, index=candles.index)
            signal_value, side_value = 1, SignalSide.LONG.value
            event_level = pd.Series(frozen_low, index=candles.index)
            other_level = pd.Series(frozen_high, index=candles.index)
        else:
            raw = pd.Series(short_raw, index=candles.index)
            signal_value, side_value = -1, SignalSide.SHORT.value
            event_level = pd.Series(frozen_high, index=candles.index)
            other_level = pd.Series(frozen_low, index=candles.index)

        entry = raw.fillna(False)
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
                    f"{side_value}: rectangle fail-reclaim close {close.loc[i]:.4f} "
                    f"vs broken {event_level.loc[i]:.4f} "
                    f"inside {other_level.loc[i]:.4f} "
                    f"after {int(bars_since[candles.index.get_loc(i)])} bar(s)"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "MAX_BARS_OUTSIDE_LOCKED",
    "MIN_TOUCHES_PER_RAIL",
    "PIVOT_LEFT",
    "REQUIRE_CLOSE_INSIDE_LOCKED",
    "BullishRectangleFailReclaimParams",
    "BullishRectangleFailReclaimStrategy",
]
