"""Trade Chaikin Oscillator crossing zero. ADL uses bar location, not OBV."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ChaikinOscillatorCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    fast: int = 3
    slow: int = 10
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ChaikinOscillatorCrossStrategy(Strategy):
    name = "chaikin_oscillator_cross"

    def __init__(self, params: ChaikinOscillatorCrossParams | None = None) -> None:
        super().__init__(params or ChaikinOscillatorCrossParams())
        self.params: ChaikinOscillatorCrossParams = self.params
        self.min_bars = int(self.params.slow) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        osc = ind.chaikin_oscillator(
            candles["high"],
            candles["low"],
            candles["close"],
            candles["volume"],
            fast=int(params.fast),
            slow=int(params.slow),
        )
        signals["chaikin"] = osc
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
                f"{side_value}: Chaikin {osc.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["ChaikinOscillatorCrossParams", "ChaikinOscillatorCrossStrategy"]
