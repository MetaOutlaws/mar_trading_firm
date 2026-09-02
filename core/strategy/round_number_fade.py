"""Fade a rejection of a psychological round price.

Round-number grid from magnitude (1/10/100/1000), not floor pivots.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class RoundNumberParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class RoundNumberFadeStrategy(Strategy):
    name = "round_number_fade"

    def __init__(self, params: RoundNumberParams | None = None) -> None:
        super().__init__(params or RoundNumberParams())
        self.params: RoundNumberParams = self.params
        self.min_bars = 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        level = ind.psychological_round(candles["close"])
        close = candles["close"]
        high = candles["high"]
        low = candles["low"]
        touched = (low <= level) & (high >= level)
        signals["round_level"] = level
        if params.side is SignalSide.LONG:
            entry = touched & (low < level) & (close > level)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = touched & (high > level) & (close < level)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        depth = ((high - low).replace(0, pd.NA)).clip(lower=1e-12)
        if params.side is SignalSide.LONG:
            score = ((level - low) / depth).clip(0.0, 1.0)
        else:
            score = ((high - level) / depth).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: rejected round {level.loc[i]:.4f} close {close.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["RoundNumberParams", "RoundNumberFadeStrategy"]
