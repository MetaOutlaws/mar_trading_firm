"""Trade McGinley Dynamic crossing price. Fourth-power speed adjust, not CMO."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class McginleyDynamicCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 12
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class McginleyDynamicCrossStrategy(Strategy):
    name = "mcginley_dynamic_cross"

    def __init__(self, params: McginleyDynamicCrossParams | None = None) -> None:
        super().__init__(params or McginleyDynamicCrossParams())
        self.params: McginleyDynamicCrossParams = self.params
        self.min_bars = int(self.params.period) + 4

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        line = ind.mcginley_dynamic(candles["close"], int(params.period))
        close = candles["close"]
        signals["mcginley"] = line
        prev_close = close.shift(1)
        prev_line = line.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev_close <= prev_line) & (close > line)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev_close >= prev_line) & (close < line)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: close {close.loc[i]:.2f} vs MD {line.loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["McginleyDynamicCrossParams", "McginleyDynamicCrossStrategy"]
