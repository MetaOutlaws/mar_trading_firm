"""Trade when Elder Impulse turns green or red. EMA slope AND MACD histogram, not ADX."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ElderImpulseTrendParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    ema_len: int = 13
    fast: int = 12
    slow: int = 26
    signal: int = 9
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class ElderImpulseTrendStrategy(Strategy):
    name = "elder_impulse_trend"

    def __init__(self, params: ElderImpulseTrendParams | None = None) -> None:
        super().__init__(params or ElderImpulseTrendParams())
        self.params: ElderImpulseTrendParams = self.params
        self.min_bars = int(self.params.slow) + int(self.params.signal) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        color = ind.elder_impulse(
            candles["close"],
            ema_len=int(params.ema_len),
            fast=int(params.fast),
            slow=int(params.slow),
            signal=int(params.signal),
        )
        signals["impulse"] = color
        prev = color.shift(1)
        if params.side is SignalSide.LONG:
            entry = (color == 1) & (prev != 1)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (color == -1) & (prev != -1)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: impulse {int(color.loc[i])}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["ElderImpulseTrendParams", "ElderImpulseTrendStrategy"]
