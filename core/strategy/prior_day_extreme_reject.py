"""Fade a 4h tag of the prior UTC day's high or low that closes back inside.

Prior UTC calendar day high/low is published after midnight. This 4h bar
tags that extreme and closes back through it (preferably still inside the
prior day's range):

- SHORT when ``high_t >= prior_day_high`` and ``close_t < prior_day_high``.
- LONG when ``low_t <= prior_day_low`` and ``close_t > prior_day_low``.

Free params are at most two: ``touch_tol_atr`` (default 0) and
``require_close_inside`` (default True). OHLCV only. Causal: bars ``<= t``.
The engine fills at ``t+1`` open.

Not ``monday_range_sweep_reversal`` (weekend Sat–Sun box, Monday London/NY).
Not ``week_open_reclaim`` (Monday 00:00 open reclaim).
Not ``equal_high_low_restest_fade`` (rolling equal H/L cluster).
Not ``double_top_neckline_break`` / ``double_bottom_neckline_break``.
Not ``classic_floor_pivot_reject`` / ``prior_day_pivot_breakout`` (P/R1/S1).
Not ``session_boundary_volume_fade`` (weak-volume sweep, no close-inside).
Do not recode ``asia_close_inventory_fade`` or ``wyckoff_spring_reclaim``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# ATR period is locked. Walk-forward searches touch_tol_atr and the close-inside flag.
ATR_PERIOD = 14


@dataclass(frozen=True)
class PriorDayExtremeRejectParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Tag slack as a multiple of prior-bar ATR. 0 = must reach the extreme.
    touch_tol_atr: float = 0.0
    # When True, close must sit inside the prior UTC day box, not only recross the tag.
    require_close_inside: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class PriorDayExtremeRejectStrategy(Strategy):
    name = "prior_day_extreme_reject"

    def __init__(self, params: PriorDayExtremeRejectParams | None = None) -> None:
        super().__init__(params or PriorDayExtremeRejectParams())
        self.params: PriorDayExtremeRejectParams = self.params
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
        # Causal snapshot of yesterday's H/L on the first bar of today. Not P/R1/S1.
        prior_high, prior_low = ind.prior_utc_day_range(high, low)
        # Prior-bar ATR so this bar's poke cannot widen the tag band.
        atr = ind.atr(high, low, close, ATR_PERIOD).shift(1)
        touch = float(params.touch_tol_atr) * atr.fillna(0.0)
        close_inside = bool(params.require_close_inside)

        # Tag = trade to (or through) the prior UTC day extreme, within touch slack.
        tagged_high = prior_high.notna() & (high >= prior_high - touch)
        tagged_low = prior_low.notna() & (low <= prior_low + touch)
        # Reject = close back through the tagged extreme. Held breakouts do not fade.
        short_raw = tagged_high & (close < prior_high)
        long_raw = tagged_low & (close > prior_low)
        if close_inside:
            # Prefer a close that is still inside the prior day's range.
            short_raw = short_raw & (close >= prior_low)
            long_raw = long_raw & (close <= prior_high)

        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["touch"] = touch
        signals["atr"] = atr

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One fade per UTC day. Calendar box, not a rolling Donchian or weekend box.
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (prior_high - prior_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((prior_low - low) / width).clip(0.0, 1.0)
        else:
            score = ((high - prior_high) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: prior-day extreme reject close {close.loc[i]:.4f} vs "
                    f"{prior_high.loc[i]:.4f}/{prior_low.loc[i]:.4f} "
                    f"touch {touch.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "PriorDayExtremeRejectParams",
    "PriorDayExtremeRejectStrategy",
]
