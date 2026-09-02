"""Trade in the direction of a Hull MA turn. HMA weighting, not EMA/SMA."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class HullMaTrendParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 16
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class HullMaTrendStrategy(Strategy):
    name = "hull_ma_trend"

    def __init__(self, params: HullMaTrendParams | None = None) -> None:
        super().__init__(params or HullMaTrendParams())
        self.params: HullMaTrendParams = self.params
        # HMA needs n + sqrt(n) WMA seeds before a turn is defined.
        self.min_bars = int(self.params.period) + 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        hma = ind.hull_ma(candles["close"], int(params.period))
        signals["hma"] = hma
        prev = hma.shift(1)
        prev2 = hma.shift(2)
        if params.side is SignalSide.LONG:
            entry = (prev2 >= prev) & (hma > prev)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev2 <= prev) & (hma < prev)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: HMA {hma.loc[i]:.2f} turn" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["HullMaTrendParams", "HullMaTrendStrategy"]
