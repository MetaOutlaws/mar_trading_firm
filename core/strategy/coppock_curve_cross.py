"""Trade Coppock Curve crossing zero. WMA of two ROCs, not a triple EMA."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class CoppockCurveCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    roc_long: int = 14
    roc_short: int = 11
    wma_len: int = 10
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class CoppockCurveCrossStrategy(Strategy):
    name = "coppock_curve_cross"

    def __init__(self, params: CoppockCurveCrossParams | None = None) -> None:
        super().__init__(params or CoppockCurveCrossParams())
        self.params: CoppockCurveCrossParams = self.params
        self.min_bars = int(self.params.roc_long) + int(self.params.wma_len) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        curve = ind.coppock_curve(
            candles["close"],
            roc_long=int(params.roc_long),
            roc_short=int(params.roc_short),
            wma_len=int(params.wma_len),
        )
        signals["coppock"] = curve
        prev = curve.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev <= 0) & (curve > 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev >= 0) & (curve < 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: Coppock {curve.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["CoppockCurveCrossParams", "CoppockCurveCrossStrategy"]
