"""Break the completed London (08:00–16:00 UTC) session range.

Published only after 16:00. Not the Asian 00–08 box and not a 1-hour ORB.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class LondonRangeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    start_hour: float = 8.0
    end_hour: float = 16.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class LondonSessionBreakoutStrategy(Strategy):
    name = "london_session_breakout"

    def __init__(self, params: LondonRangeParams | None = None) -> None:
        super().__init__(params or LondonRangeParams())
        self.params: LondonRangeParams = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        range_high, range_low, ready = ind.utc_session_range(
            candles["high"],
            candles["low"],
            start_hour=params.start_hour,
            end_hour=params.end_hour,
        )
        close = candles["close"]
        signals["range_high"] = range_high
        signals["range_low"] = range_low
        if params.side is SignalSide.LONG:
            raw = ready & (close > range_high)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = ready & (close < range_low)
            signal_value, side_value = -1, SignalSide.SHORT.value
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (range_high - range_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - range_high) / width).clip(0.0, 1.0)
        else:
            score = ((range_low - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: close {close.loc[i]:.4f} vs London range "
                    f"{range_high.loc[i]:.4f}/{range_low.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["LondonRangeParams", "LondonSessionBreakoutStrategy"]
