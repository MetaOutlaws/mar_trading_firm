"""Fade a failed higher-high (or failed lower-low) against the prior swing.

Two consecutive confirmed swings: the second extends, then the close comes
back through the first. Not a single wick through one pivot.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class FailedHigherHighParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    pivot_left: int = 3
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class FailedHigherHighStrategy(Strategy):
    name = "failed_higher_high"

    def __init__(self, params: FailedHigherHighParams | None = None) -> None:
        super().__init__(params or FailedHigherHighParams())
        self.params: FailedHigherHighParams = self.params
        self.min_bars = 24

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        swing_high, swing_low = ind.confirmed_swings(
            candles["high"], candles["low"], left=params.pivot_left
        )
        close = candles["close"]
        prev_high = ind.prior_distinct_level(swing_high)
        prev_low = ind.prior_distinct_level(swing_low)
        signals["swing_high"] = swing_high
        signals["prior_swing_high"] = prev_high
        signals["swing_low"] = swing_low
        signals["prior_swing_low"] = prev_low
        if params.side is SignalSide.LONG:
            # Failed lower-low: second swing undercuts the first, close back above it.
            structure = prev_low.notna() & (swing_low < prev_low)
            raw = structure & (close > prev_low)
            signal_value, side_value = 1, SignalSide.LONG.value
            key = swing_low.astype(str) + "|" + prev_low.astype(str)
        else:
            structure = prev_high.notna() & (swing_high > prev_high)
            raw = structure & (close < prev_high)
            signal_value, side_value = -1, SignalSide.SHORT.value
            key = swing_high.astype(str) + "|" + prev_high.astype(str)
        raw = raw.fillna(False)
        entry = raw & raw.groupby(key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: failed two-swing vs {prev_high.loc[i]:.4f}/{prev_low.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["FailedHigherHighParams", "FailedHigherHighStrategy"]
