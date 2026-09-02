"""Trade Fisher Transform crossing its trigger. Gaussian map of median, not RSI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class FisherTransformCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 10
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class FisherTransformCrossStrategy(Strategy):
    name = "fisher_transform_cross"

    def __init__(self, params: FisherTransformCrossParams | None = None) -> None:
        super().__init__(params or FisherTransformCrossParams())
        self.params: FisherTransformCrossParams = self.params
        self.min_bars = int(self.params.period) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        line, trigger = ind.fisher_transform(
            candles["high"], candles["low"], period=int(params.period)
        )
        signals["fisher"] = line
        signals["fisher_trigger"] = trigger
        prev_line = line.shift(1)
        prev_trig = trigger.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev_line <= prev_trig) & (line > trigger)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev_line >= prev_trig) & (line < trigger)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: Fisher {line.loc[i]:.3f} trig {trigger.loc[i]:.3f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["FisherTransformCrossParams", "FisherTransformCrossStrategy"]
