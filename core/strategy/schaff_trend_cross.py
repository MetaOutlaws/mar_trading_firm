"""Trade STC crossing 25/75. Stochastic of MACD, not %K of price and not ema_adx_trend."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SchaffTrendCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    fast: int = 23
    slow: int = 50
    cycle: int = 10
    smooth: int = 3
    os_level: float = 25.0
    ob_level: float = 75.0
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class SchaffTrendCrossStrategy(Strategy):
    name = "schaff_trend_cross"

    def __init__(self, params: SchaffTrendCrossParams | None = None) -> None:
        super().__init__(params or SchaffTrendCrossParams())
        self.params: SchaffTrendCrossParams = self.params
        self.min_bars = int(self.params.slow) + int(self.params.cycle) * 2 + 4

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        stc = ind.schaff_trend(
            candles["close"],
            fast=int(params.fast),
            slow=int(params.slow),
            cycle=int(params.cycle),
            smooth=int(params.smooth),
        )
        signals["stc"] = stc
        prev = stc.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev <= params.os_level) & (stc > params.os_level)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev >= params.ob_level) & (stc < params.ob_level)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: STC {stc.loc[i]:.1f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["SchaffTrendCrossParams", "SchaffTrendCrossStrategy"]
