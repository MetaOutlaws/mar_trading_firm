"""Reject a 4h tag of classic floor-trader R1/S1 from the prior UTC day.

Levels are published after that UTC day closes, from its H, L, C only:

- P  = (H + L + C) / 3
- R1 = 2P - L
- S1 = 2P - H

This 4h bar tags the pivot extreme and closes back through the pivot:

- SHORT when ``high_t`` tags R1 (within ``touch_tol_atr * ATR``) and
  ``close_t < P``.
- LONG when ``low_t`` tags S1 (within ``touch_tol_atr * ATR``) and
  ``close_t > P``.

The P/R1/S1 formula is locked (not searched). The only free param is
``touch_tol_atr`` (default 0; grid ``[0.0, 0.10]``). OHLCV only. Causal:
bars ``<= t``. The engine fills at ``t+1`` open.

Not ``prior_day_extreme_reject`` (118 — raw prior UTC day H/L).
Not ``prior_session_mid_reclaim`` (107 — 8h session midpoint).
Not ``week_open_reclaim`` (Monday 00:00 open reclaim).
Not ``prior_close_magnet_fade`` (128 — prior-bar close stretch).
Not ``prior_day_pivot_breakout`` (close-through R1/S1 follow).
Do not recode spent families 118–128. Do not code H&S / asia_close /
``displacement_gap_follow``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# ATR period is locked. Walk-forward searches touch_tol_atr only.
ATR_PERIOD = 14


@dataclass(frozen=True)
class ClassicFloorPivotRejectParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Tag slack as a multiple of prior-bar ATR. Quant grid: [0.0, 0.10].
    touch_tol_atr: float = 0.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ClassicFloorPivotRejectStrategy(Strategy):
    name = "classic_floor_pivot_reject"

    def __init__(self, params: ClassicFloorPivotRejectParams | None = None) -> None:
        super().__init__(params or ClassicFloorPivotRejectParams())
        self.params: ClassicFloorPivotRejectParams = self.params
        # One completed UTC day plus ATR warmup. Works on 4h or hourly tapes.
        self.min_bars = ATR_PERIOD + 8

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
        # Locked floor-trader formula from the prior completed UTC day.
        pivot, r1, s1 = ind.prior_day_floor_pivots(high, low, close)
        # Prior-bar ATR so this bar's poke cannot widen the tag band.
        atr = ind.atr(high, low, close, ATR_PERIOD).shift(1)
        touch = float(params.touch_tol_atr) * atr.fillna(0.0)

        # Tag = trade to (or through) R1/S1, within touch slack. Not raw H/L.
        tagged_r1 = r1.notna() & pivot.notna() & (high >= r1 - touch)
        tagged_s1 = s1.notna() & pivot.notna() & (low <= s1 + touch)
        # Reject = close back through the pivot. A held break through P is not a fade.
        short_raw = tagged_r1 & (close < pivot)
        long_raw = tagged_s1 & (close > pivot)

        signals["pivot"] = pivot
        signals["r1"] = r1
        signals["s1"] = s1
        signals["touch"] = touch
        signals["atr"] = atr

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One fade per UTC day. Calendar box, not a rolling Donchian.
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (r1 - s1).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((s1 - low) / width).clip(0.0, 1.0)
        else:
            score = ((high - r1) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: floor-pivot reject close {close.loc[i]:.4f} vs "
                    f"P/R1/S1 {pivot.loc[i]:.4f}/{r1.loc[i]:.4f}/{s1.loc[i]:.4f} "
                    f"touch {touch.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "ClassicFloorPivotRejectParams",
    "ClassicFloorPivotRejectStrategy",
]
