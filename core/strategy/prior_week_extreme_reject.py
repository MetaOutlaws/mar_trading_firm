"""Fade a 4h tag of the prior ISO week's high or low that closes back inside.

The prior ISO week (Monday 00:00 through Sunday, UTC) publishes its raw
high and low only after that Sunday closes. This 4h bar tags that extreme
and closes back through it, still inside the prior week's range
(Quant-locked ``require_close_inside=True``):

- SHORT when ``high_t`` tags ``prior_week_high`` (within
  ``touch_tol_atr * ATR(20)``) and ``close_t < prior_week_high`` and
  ``close_t`` is inside ``[prior_week_low, prior_week_high]``.
- LONG is the inverse on ``prior_week_low``.

A bar that qualifies for both fades is SHORT, not LONG. At most one
entry per ISO week per side. The engine fills at ``t+1`` open. OHLCV
only. Causal: bars ``<= t``. ATR is the prior bar's ATR(20) so this
bar's poke cannot widen the tag band.

Levels are raw prior ISO-week H/L, not a prior UTC day box, not a
Monday 00:00 open, and not floor P/R1/S1. The only searched free param
is ``touch_tol_atr`` (default 0; grid ``[0.0, 0.10]``).

Option B exploratory. SCORE/RETIRE only. This module does not write
approvals and does not start a walk-forward. Live stays off.

Not ``prior_day_extreme_reject`` (118 — prior UTC day H/L).
Not ``week_open_reclaim`` (106 — Monday 00:00 open reclaim).
Not ``classic_floor_pivot_reject`` (129 — P/R1/S1).
Not ``prior_week_high_break``. That family enters when close is through
the prior week extreme. This family enters only when close comes back
inside it. Do not alias that module, its class, or its name.
Not ``monday_range_sweep_reversal`` (Sat–Sun box).
Do not recode those siblings. Hold H&S alone.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# ATR period and close-inside are locked. Walk-forward searches touch_tol_atr only.
# Period is 20, not the ATR(14) used by the prior-day and floor-pivot fades.
ATR_PERIOD = 20
# Endpoints only. Do not insert a midpoint.
TOUCH_TOL_GRID = [0.0, 0.10]


@dataclass(frozen=True)
class PriorWeekExtremeRejectParams(StrategyParams):
    # SHORT-priority family. A two-sided bar is a short, not a long.
    side: SignalSide = SignalSide.SHORT
    # Tag slack as a multiple of prior-bar ATR(20). Quant grid: [0.0, 0.10].
    touch_tol_atr: float = 0.0
    # Quant-locked True. generate_signals always applies the gate.
    require_close_inside: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class PriorWeekExtremeRejectStrategy(Strategy):
    name = "prior_week_extreme_reject"

    def __init__(self, params: PriorWeekExtremeRejectParams | None = None) -> None:
        super().__init__(params or PriorWeekExtremeRejectParams())
        self.params: PriorWeekExtremeRejectParams = self.params
        # ATR(20) seed plus the shift that publishes ATR known before bar t.
        # The week level is NaN until Sunday closes, so this warmup is the
        # indicator floor, not a second copy of the calendar week.
        self.min_bars = ATR_PERIOD + 1

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
        # Last completed ISO week (Mon–Sun, UTC). Mid-week bars never see
        # the still-forming week's extreme. Not a rolling 7-day window.
        prior_high, prior_low = ind.prior_utc_week_range(high, low)
        # Prior-bar ATR(20). Period is the module lock, not a param.
        atr = ind.atr(high, low, close, ATR_PERIOD).shift(1)
        touch = float(params.touch_tol_atr) * atr

        # Tag = trade to (or through) the prior week extreme, within slack.
        # NaN ATR cannot size the band, so those bars do not tag.
        tagged_high = prior_high.notna() & atr.notna() & (high >= prior_high - touch)
        tagged_low = prior_low.notna() & atr.notna() & (low <= prior_low + touch)
        # Inclusive week box. require_close_inside is locked True, including
        # when a caller passes False. A close through the extreme is
        # prior_week_high_break (close > high, or close < low). That print
        # is not a reject and must stay flat here.
        inside = (close >= prior_low) & (close <= prior_high)
        close_back_below_high = close < prior_high
        close_back_above_low = close > prior_low
        short_raw = tagged_high & close_back_below_high & inside
        long_raw = tagged_low & close_back_above_low & inside
        # SHORT priority: a bar that tags both extremes is a short, not a long.
        long_raw = long_raw & ~short_raw.fillna(False)

        signals["prior_week_high"] = prior_high
        signals["prior_week_low"] = prior_low
        signals["touch"] = touch
        signals["atr"] = atr

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One fade per ISO week. Calendar week, not a rolling Donchian.
        week_key = ind.iso_week_key(candles.index)
        raw = raw.fillna(False)
        entry = raw & raw.groupby(week_key).cumsum().eq(1)
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
                    f"{side_value}: prior-week extreme reject close {close.loc[i]:.4f} vs "
                    f"{prior_high.loc[i]:.4f}/{prior_low.loc[i]:.4f} "
                    f"touch {touch.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "TOUCH_TOL_GRID",
    "PriorWeekExtremeRejectParams",
    "PriorWeekExtremeRejectStrategy",
]
