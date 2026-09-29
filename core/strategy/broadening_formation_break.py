"""Break an expanding megaphone (broadening formation).

One pattern, both directions. Swing highs print higher highs on a rising
upper rail (slope > 0) and swing lows print lower lows on a falling lower
rail (slope < 0). LONG when ``close_t`` breaks above the upper rail. SHORT
when ``close_t`` breaks below the lower rail. A wick through the rail
without the close does not fire.

Rails are OLS fits through the last ``min_touches`` published swing highs
and swing lows in ``lookback``. Each of those swings must sit within one
ATR(20) of its rail. That ATR is the touch tolerance only: it is not a
break-size filter, not a free parameter, and not a volume-profile input.

Free params (walk grid, not started from this coding change):
``lookback`` in ``{32, 48}``, ``min_touches`` in ``{3, 4}``.

Locked: expanding rails, break on the close, ATR period 20, touch multiple
1.0, pivot confirmation, fill at ``t+1`` open (engine, not this file), no
volume gate, no session gate, no volume profile.

Not ``converging_wedge_break`` (Job 125 — both rails slope the same way and
converge; do not recode it). Not ``ascending_triangle_break`` (flat cap).
Not ``failed_range_break_reversion`` / ``double_top_neckline_break``. Not
``round_number_fade`` / ``consecutive_bar_exhaustion`` / ``mass_index_reversal``.
Not head-and-shoulders (coded separately).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Pivot confirmation matches the other chart-pattern sleeves. Not searched.
PIVOT_LEFT = 3
# Locked ATR window. Used only as the distance a swing may sit off its rail.
ATR_PERIOD = 20
# One ATR(20). Not searched — the break itself is a raw close through the rail.
TOUCH_TOL_ATR = 1.0
# Searched grids. Endpoints only; do not insert interiors.
LOOKBACK_GRID = [32, 48]
MIN_TOUCHES_GRID = [3, 4]


@dataclass(frozen=True)
class BroadeningFormationBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Publication window that must hold the last min_touches swings per rail.
    lookback: int = 48
    # How many recent swing highs / lows must define each expanding rail.
    min_touches: int = 3
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class BroadeningFormationBreakStrategy(Strategy):
    name = "broadening_formation_break"

    def __init__(self, params: BroadeningFormationBreakParams | None = None) -> None:
        super().__init__(params or BroadeningFormationBreakParams())
        self.params: BroadeningFormationBreakParams = self.params
        lookback = int(self.params.lookback)
        # Lookback, pivot confirmation on both sides, and the ATR(20) seed.
        self.min_bars = lookback + 2 * PIVOT_LEFT + ATR_PERIOD + 3

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
        lookback = int(params.lookback)
        min_touches = int(params.min_touches)
        # ATR known before the signal bar. The break bar's own range must not
        # loosen the touch test that qualifies the rails.
        atr_known = ind.atr(high, low, close, ATR_PERIOD).shift(1)
        touch_tol = atr_known * TOUCH_TOL_ATR
        rails = ind.broadening_formation_rails(
            high,
            low,
            lookback=lookback,
            min_touches=min_touches,
            left=PIVOT_LEFT,
            touch_tol=touch_tol,
        )
        prev_close = close.shift(1)
        formed = rails["broadening"].fillna(False)
        # First close through the rail. A held breakout (already through on
        # this bar's rail) does not fire again. Wicks do not count.
        long_raw = (
            formed
            & rails["upper_rail"].notna()
            & (prev_close <= rails["upper_rail"])
            & (close > rails["upper_rail"])
        )
        short_raw = (
            formed
            & rails["lower_rail"].notna()
            & (prev_close >= rails["lower_rail"])
            & (close < rails["lower_rail"])
        )

        signals["upper_rail"] = rails["upper_rail"]
        signals["lower_rail"] = rails["lower_rail"]
        signals["upper_slope"] = rails["upper_slope"]
        signals["lower_slope"] = rails["lower_slope"]
        signals["n_highs"] = rails["n_highs"]
        signals["n_lows"] = rails["n_lows"]
        signals["n_high_touches"] = rails["n_high_touches"]
        signals["n_low_touches"] = rails["n_low_touches"]
        signals["high_residual"] = rails["high_residual"]
        signals["low_residual"] = rails["low_residual"]
        signals["atr_touch_tol"] = touch_tol

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            level = rails["upper_rail"]
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = rails["lower_rail"]

        raw = raw.fillna(False)
        # One entry per megaphone identity (touch counts + rail slopes).
        key = (
            rails["n_highs"].astype(str)
            + "|"
            + rails["n_lows"].astype(str)
            + "|"
            + rails["upper_slope"].round(8).astype(str)
            + "|"
            + rails["lower_slope"].round(8).astype(str)
        )
        entry = raw & raw.groupby(key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (rails["upper_rail"] - rails["lower_rail"]).abs().replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - rails["upper_rail"]) / width).clip(0.0, 1.0)
        else:
            score = ((rails["lower_rail"] - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: broadening-formation break "
                    f"close {close.loc[i]:.4f} vs rail {level.loc[i]:.4f} "
                    f"u_slope {rails['upper_slope'].loc[i]:.4f} "
                    f"l_slope {rails['lower_slope'].loc[i]:.4f} "
                    f"touch_tol {touch_tol.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "LOOKBACK_GRID",
    "MIN_TOUCHES_GRID",
    "PIVOT_LEFT",
    "TOUCH_TOL_ATR",
    "BroadeningFormationBreakParams",
    "BroadeningFormationBreakStrategy",
]
