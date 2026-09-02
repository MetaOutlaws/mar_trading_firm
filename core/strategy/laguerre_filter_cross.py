"""Trade the Laguerre filter crossing its prior-bar trigger. Gamma FIR of price, not RSI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class LaguerreFilterCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    gamma: float = 0.5
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class LaguerreFilterCrossStrategy(Strategy):
    name = "laguerre_filter_cross"

    def __init__(self, params: LaguerreFilterCrossParams | None = None) -> None:
        super().__init__(params or LaguerreFilterCrossParams())
        self.params: LaguerreFilterCrossParams = self.params
        self.min_bars = 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        line = ind.laguerre_filter(candles["close"], float(params.gamma))
        trigger = line.shift(1)
        signals["laguerre"] = line
        signals["trigger"] = trigger
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
                f"{side_value}: Laguerre {line.loc[i]:.2f} vs trigger {trigger.loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["LaguerreFilterCrossParams", "LaguerreFilterCrossStrategy"]
