"""Fade Stochastic Momentum Index extremes. Double-smoothed midpoint distance, not %K."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SmiFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    q: int = 25
    r: int = 13
    s: int = 2
    os_level: float = -40.0
    ob_level: float = 40.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class SmiFadeStrategy(Strategy):
    name = "smi_fade"

    def __init__(self, params: SmiFadeParams | None = None) -> None:
        super().__init__(params or SmiFadeParams())
        self.params: SmiFadeParams = self.params
        self.min_bars = int(self.params.q) + int(self.params.r) + int(self.params.s) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        smi = ind.stochastic_momentum_index(
            candles["high"],
            candles["low"],
            candles["close"],
            q=int(params.q),
            r=int(params.r),
            s=int(params.s),
        )
        signals["smi"] = smi
        if params.side is SignalSide.LONG:
            entry = (smi <= params.os_level) & (smi > smi.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (smi >= params.ob_level) & (smi < smi.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: SMI {smi.loc[i]:.1f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["SmiFadeParams", "SmiFadeStrategy"]
