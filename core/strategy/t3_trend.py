"""Trade in the direction of a T3 turn. Six-pole EMA cascade, not Hull MA."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class T3TrendParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 5
    vfactor: float = 0.7
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class T3TrendStrategy(Strategy):
    name = "t3_trend"

    def __init__(self, params: T3TrendParams | None = None) -> None:
        super().__init__(params or T3TrendParams())
        self.params: T3TrendParams = self.params
        # Six cascaded EMAs need several seeds before a turn is defined.
        self.min_bars = int(self.params.period) * 6 + 4

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        line = ind.tillson_t3(candles["close"], int(params.period), float(params.vfactor))
        signals["t3"] = line
        prev = line.shift(1)
        prev2 = line.shift(2)
        if params.side is SignalSide.LONG:
            entry = (prev2 >= prev) & (line > prev)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev2 <= prev) & (line < prev)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: T3 {line.loc[i]:.2f} turn" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["T3TrendParams", "T3TrendStrategy"]
