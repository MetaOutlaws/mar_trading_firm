"""Trade DEMA crossing a slow DEMA. Two DEMAs, not ZLEMA versus a raw EMA."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class DemaCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    fast: int = 10
    slow: int = 20
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class DemaCrossStrategy(Strategy):
    name = "dema_cross"

    def __init__(self, params: DemaCrossParams | None = None) -> None:
        super().__init__(params or DemaCrossParams())
        self.params: DemaCrossParams = self.params
        self.min_bars = int(self.params.slow) * 2 + 4

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        fast = ind.dema(candles["close"], int(params.fast))
        slow = ind.dema(candles["close"], int(params.slow))
        signals["fast_dema"] = fast
        signals["slow_dema"] = slow
        prev_fast = fast.shift(1)
        prev_slow = slow.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev_fast <= prev_slow) & (fast > slow)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev_fast >= prev_slow) & (fast < slow)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: DEMA {fast.loc[i]:.2f} vs {slow.loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["DemaCrossParams", "DemaCrossStrategy"]
