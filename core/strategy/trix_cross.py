"""Trade TRIX crossing zero. Triple-smoothed ROC, not a single EMA+ADX trend."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class TrixCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 15
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class TrixCrossStrategy(Strategy):
    name = "trix_cross"

    def __init__(self, params: TrixCrossParams | None = None) -> None:
        super().__init__(params or TrixCrossParams())
        self.params: TrixCrossParams = self.params
        # Three stacked EMAs need extra seed bars before TRIX is defined.
        self.min_bars = int(self.params.period) * 3 + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        value = ind.trix(candles["close"], int(params.period))
        signals["trix"] = value
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
                f"{side_value}: TRIX {value.loc[i]:.4f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["TrixCrossParams", "TrixCrossStrategy"]
