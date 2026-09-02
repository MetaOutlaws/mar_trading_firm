"""Trade TSI crossing zero. Double-smoothed momentum, not CMO and not RSI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class TsiCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    long: int = 25
    short: int = 13
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class TsiCrossStrategy(Strategy):
    name = "tsi_cross"

    def __init__(self, params: TsiCrossParams | None = None) -> None:
        super().__init__(params or TsiCrossParams())
        self.params: TsiCrossParams = self.params
        self.min_bars = int(self.params.long) + int(self.params.short) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        value = ind.tsi(candles["close"], long=int(params.long), short=int(params.short))
        signals["tsi"] = value
        prev = value.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev <= 0) & (value > 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev >= 0) & (value < 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: TSI {value.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["TsiCrossParams", "TsiCrossStrategy"]
