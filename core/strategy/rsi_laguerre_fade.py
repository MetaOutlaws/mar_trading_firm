"""Fade Laguerre RSI extremes. Four-pole gamma filter mapped to 0..1, not Wilder RSI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class RsiLaguerreFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    gamma: float = 0.5
    os_level: float = 0.20
    ob_level: float = 0.80
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class RsiLaguerreFadeStrategy(Strategy):
    name = "rsi_laguerre_fade"

    def __init__(self, params: RsiLaguerreFadeParams | None = None) -> None:
        super().__init__(params or RsiLaguerreFadeParams())
        self.params: RsiLaguerreFadeParams = self.params
        self.min_bars = 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        value = ind.rsi_laguerre(candles["close"], float(params.gamma))
        signals["rsi_laguerre"] = value
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
                f"{side_value}: Laguerre RSI {value.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["RsiLaguerreFadeParams", "RsiLaguerreFadeStrategy"]
