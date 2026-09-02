"""Fade Kairi Relative Index extremes. Percent from SMA, not Bollinger z-score."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class KairiRelativeFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 20
    os_level: float = -5.0
    ob_level: float = 5.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class KairiRelativeFadeStrategy(Strategy):
    name = "kairi_relative_fade"

    def __init__(self, params: KairiRelativeFadeParams | None = None) -> None:
        super().__init__(params or KairiRelativeFadeParams())
        self.params: KairiRelativeFadeParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        kairi = ind.kairi_relative(candles["close"], int(params.period))
        signals["kairi"] = kairi
        if params.side is SignalSide.LONG:
            entry = (kairi <= params.os_level) & (kairi > kairi.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (kairi >= params.ob_level) & (kairi < kairi.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: Kairi {kairi.loc[i]:.2f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["KairiRelativeFadeParams", "KairiRelativeFadeStrategy"]
