"""Fade Chande Momentum Oscillator extremes. Sum-of-change, not Wilder RSI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ChandeMomentumFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 14
    os_level: float = -50.0
    ob_level: float = 50.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ChandeMomentumFadeStrategy(Strategy):
    name = "chande_momentum_fade"

    def __init__(self, params: ChandeMomentumFadeParams | None = None) -> None:
        super().__init__(params or ChandeMomentumFadeParams())
        self.params: ChandeMomentumFadeParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        cmo = ind.chande_momentum(candles["close"], int(params.period))
        signals["cmo"] = cmo
        if params.side is SignalSide.LONG:
            entry = (cmo <= params.os_level) & (cmo > cmo.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (cmo >= params.ob_level) & (cmo < cmo.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: CMO {cmo.loc[i]:.1f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["ChandeMomentumFadeParams", "ChandeMomentumFadeStrategy"]
