"""Trade Aroon up crossing Aroon down. Time-since-extreme, not a channel break."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class AroonCrossoverParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 25
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class AroonCrossoverStrategy(Strategy):
    name = "aroon_crossover"

    def __init__(self, params: AroonCrossoverParams | None = None) -> None:
        super().__init__(params or AroonCrossoverParams())
        self.params: AroonCrossoverParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        up, down = ind.aroon(candles["high"], candles["low"], int(params.period))
        signals["aroon_up"] = up
        signals["aroon_down"] = down
        prev_up = up.shift(1)
        prev_down = down.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev_up <= prev_down) & (up > down)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev_up >= prev_down) & (up < down)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: Aroon up {up.loc[i]:.0f} down {down.loc[i]:.0f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["AroonCrossoverParams", "AroonCrossoverStrategy"]
