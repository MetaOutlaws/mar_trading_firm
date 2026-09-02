"""Trade Rainbow Oscillator crossing zero. SMA ribbon, not a dual-EMA MACD."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class RainbowOscillatorCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    steps: int = 10
    step: int = 2
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class RainbowOscillatorCrossStrategy(Strategy):
    name = "rainbow_oscillator_cross"

    def __init__(self, params: RainbowOscillatorCrossParams | None = None) -> None:
        super().__init__(params or RainbowOscillatorCrossParams())
        self.params: RainbowOscillatorCrossParams = self.params
        self.min_bars = int(self.params.steps) * int(self.params.step) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        osc = ind.rainbow_oscillator(
            candles["close"], steps=int(params.steps), step=int(params.step)
        )
        signals["rainbow"] = osc
        prev = osc.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev <= 0) & (osc > 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev >= 0) & (osc < 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: rainbow {osc.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["RainbowOscillatorCrossParams", "RainbowOscillatorCrossStrategy"]
