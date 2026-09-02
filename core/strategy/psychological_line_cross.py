"""Trade PSY crossing 50. Count of up-closes, not RSI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class PsychologicalLineCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 12
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class PsychologicalLineCrossStrategy(Strategy):
    name = "psychological_line_cross"

    def __init__(self, params: PsychologicalLineCrossParams | None = None) -> None:
        super().__init__(params or PsychologicalLineCrossParams())
        self.params: PsychologicalLineCrossParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        psy = ind.psychological_line(candles["close"], int(params.period))
        signals["psy"] = psy
        prev = psy.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev <= 50.0) & (psy > 50.0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev >= 50.0) & (psy < 50.0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: PSY {psy.loc[i]:.1f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["PsychologicalLineCrossParams", "PsychologicalLineCrossStrategy"]
