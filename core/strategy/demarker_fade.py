"""Fade DeMarker extremes. High-to-high / low-to-low steps, not Stochastic %K of close."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class DemarkerFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 14
    os_level: float = 0.30
    ob_level: float = 0.70
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class DemarkerFadeStrategy(Strategy):
    name = "demarker_fade"

    def __init__(self, params: DemarkerFadeParams | None = None) -> None:
        super().__init__(params or DemarkerFadeParams())
        self.params: DemarkerFadeParams = self.params
        self.min_bars = int(self.params.period) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        value = ind.demarker(candles["high"], candles["low"], int(params.period))
        signals["demarker"] = value
        if params.side is SignalSide.LONG:
            entry = (value <= params.os_level) & (value > value.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (value >= params.ob_level) & (value < value.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: DeMarker {value.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["DemarkerFadeParams", "DemarkerFadeStrategy"]
