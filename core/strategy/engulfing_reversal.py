"""Reverse when a bar's body fully engulfs the prior body.

Two-bar engulfing is pattern math, not an RSI fade and not inside-bar.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class EngulfingParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class EngulfingReversalStrategy(Strategy):
    name = "engulfing_reversal"

    def __init__(self, params: EngulfingParams | None = None) -> None:
        super().__init__(params or EngulfingParams())
        self.params: EngulfingParams = self.params
        self.min_bars = 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        direction = ind.engulfing_direction(candles["open"], candles["close"])
        signals["engulfing"] = direction
        if params.side is SignalSide.LONG:
            entry = direction.eq(1)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = direction.eq(-1)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: engulfing close {candles['close'].loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["EngulfingParams", "EngulfingReversalStrategy"]
