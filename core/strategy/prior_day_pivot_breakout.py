"""Break prior UTC-day pivot / R1 / S1 after that day has closed.

Classic floor-trader pivots from the prior day's H+L+C. Calendar-day
aggregation, not a rolling Donchian.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class PriorDayPivotParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class PriorDayPivotBreakoutStrategy(Strategy):
    name = "prior_day_pivot_breakout"

    def __init__(self, params: PriorDayPivotParams | None = None) -> None:
        super().__init__(params or PriorDayPivotParams())
        self.params: PriorDayPivotParams = self.params
        self.min_bars = 30

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        pivot, r1, s1 = ind.prior_day_floor_pivots(
            candles["high"], candles["low"], candles["close"]
        )
        close = candles["close"]
        signals["pivot"] = pivot
        signals["r1"] = r1
        signals["s1"] = s1
        if params.side is SignalSide.LONG:
            raw = r1.notna() & (close > r1)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = s1.notna() & (close < s1)
            signal_value, side_value = -1, SignalSide.SHORT.value
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: close {close.loc[i]:.4f} vs P/R1/S1 {pivot.loc[i]:.4f}/{r1.loc[i]:.4f}/{s1.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["PriorDayPivotParams", "PriorDayPivotBreakoutStrategy"]
