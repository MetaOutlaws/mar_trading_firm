"""Trade Gator Oscillator turning from sleep to awake. Offset SMMA of median, not MACD."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class GatorOscillatorCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    jaw: int = 13
    teeth: int = 8
    lips: int = 5
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class GatorOscillatorCrossStrategy(Strategy):
    name = "gator_oscillator_cross"

    def __init__(self, params: GatorOscillatorCrossParams | None = None) -> None:
        super().__init__(params or GatorOscillatorCrossParams())
        self.params: GatorOscillatorCrossParams = self.params
        # Jaw SMMA(13) lagged 8 bars is the longest seed.
        self.min_bars = int(self.params.jaw) + 8 + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        upper, lower, _jaw, teeth, lips = ind.gator_lines(
            candles["high"],
            candles["low"],
            jaw=int(params.jaw),
            teeth=int(params.teeth),
            lips=int(params.lips),
        )
        signals["gator_upper"] = upper
        signals["gator_lower"] = lower
        expanding = (upper > upper.shift(1)) & (lower > lower.shift(1))
        was_sleeping = (upper.shift(1) <= upper.shift(2)) | (lower.shift(1) <= lower.shift(2))
        awake = expanding & was_sleeping
        if params.side is SignalSide.LONG:
            entry = awake & (lips > teeth)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = awake & (lips < teeth)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: gator awake {upper.loc[i]:.4f}/{lower.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["GatorOscillatorCrossParams", "GatorOscillatorCrossStrategy"]
