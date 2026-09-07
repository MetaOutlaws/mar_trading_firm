"""Break a converging wedge (both rails slope and converge).

Rising wedge (HH+HL both slope up, converge): SHORT on a close below the
lower rail. Falling wedge (LH+LL both slope down, converge): LONG on a
close above the upper rail.

Rails are OLS fits through the last ``min_touches`` published swing highs
and swing lows in ``lookback``. ``min_touches`` is Quant-locked at 3 and is
not searched. Free param is ``lookback`` in ``[30, 40]``. No volume gate.
OHLCV only. Causal: bars ``<= t``. The engine fills at ``t+1`` open.

Not ``ascending_triangle_break`` (one rail flat, volume through a cap).
Not ``ib_fail_reversion`` (124 — inside-bar fail).
Not ``nr7_fail_reversion`` / ``orb_fail_reversion`` / ``asia_range_london_reject``
/ ``prior_day_extreme_reject`` / ``failed_range_break_reversion`` (118–123).
Not ``engulfing_reversal`` / ``prior_week_high_break``.
Not H&S / ``asia_close_inventory_fade`` / Wyckoff.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Pivot confirmation matches the other chart-pattern sleeves. Not searched.
PIVOT_LEFT = 3
# Quant lock: each rail needs this many published swings. Not searched.
MIN_TOUCHES = 3


@dataclass(frozen=True)
class ConvergingWedgeBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Publication window that must hold the last min_touches swings per rail.
    lookback: int = 40
    # Quant-locked. Walk-forward must not search this.
    min_touches: int = MIN_TOUCHES
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ConvergingWedgeBreakStrategy(Strategy):
    name = "converging_wedge_break"

    def __init__(self, params: ConvergingWedgeBreakParams | None = None) -> None:
        super().__init__(params or ConvergingWedgeBreakParams())
        self.params: ConvergingWedgeBreakParams = self.params
        lookback = int(self.params.lookback)
        # Lookback window plus pivot confirmation on both sides of the last swing.
        self.min_bars = lookback + 2 * PIVOT_LEFT + 3

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
        rails = ind.converging_wedge_rails(
            high, low, lookback=lookback, min_touches=min_touches, left=PIVOT_LEFT
        )
        prev_close = close.shift(1)
        # First close through the broken rail. A held breakout (already through
        # on the prior bar) does not fire again.
        long_raw = (
            rails["falling_wedge"]
            & rails["upper_rail"].notna()
            & (prev_close <= rails["upper_rail"])
            & (close > rails["upper_rail"])
        )
        short_raw = (
            rails["rising_wedge"]
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

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            level = rails["upper_rail"]
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = rails["lower_rail"]

        raw = raw.fillna(False)
        # One entry per wedge identity (touch counts + rail slopes).
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
                    f"{side_value}: converging-wedge break "
                    f"close {close.loc[i]:.4f} vs rail {level.loc[i]:.4f} "
                    f"u_slope {rails['upper_slope'].loc[i]:.4f} "
                    f"l_slope {rails['lower_slope'].loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "MIN_TOUCHES",
    "PIVOT_LEFT",
    "ConvergingWedgeBreakParams",
    "ConvergingWedgeBreakStrategy",
]
