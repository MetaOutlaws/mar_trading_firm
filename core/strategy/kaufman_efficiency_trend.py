"""Trade in the direction of a high Kaufman Efficiency Ratio move. Path-efficiency, not ADX."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class KaufmanEfficiencyTrendParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 10
    min_er: float = 0.5
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class KaufmanEfficiencyTrendStrategy(Strategy):
    name = "kaufman_efficiency_trend"

    def __init__(self, params: KaufmanEfficiencyTrendParams | None = None) -> None:
        super().__init__(params or KaufmanEfficiencyTrendParams())
        self.params: KaufmanEfficiencyTrendParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        er = ind.kaufman_efficiency(candles["close"], int(params.period))
        close = candles["close"]
        signals["er"] = er
        efficient = er >= params.min_er
        if params.side is SignalSide.LONG:
            entry = efficient & (close > close.shift(int(params.period)))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = efficient & (close < close.shift(int(params.period)))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: ER {er.loc[i]:.2f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["KaufmanEfficiencyTrendParams", "KaufmanEfficiencyTrendStrategy"]
