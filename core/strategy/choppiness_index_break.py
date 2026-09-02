"""Break after Choppiness Index compresses. Range-efficiency log ratio, not BB width."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ChoppinessIndexBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 14
    chop_level: float = 61.8
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class ChoppinessIndexBreakStrategy(Strategy):
    name = "choppiness_index_break"

    def __init__(self, params: ChoppinessIndexBreakParams | None = None) -> None:
        super().__init__(params or ChoppinessIndexBreakParams())
        self.params: ChoppinessIndexBreakParams = self.params
        self.min_bars = int(self.params.period) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        period = int(params.period)
        ci = ind.choppiness_index(candles["high"], candles["low"], candles["close"], period)
        signals["ci"] = ci
        compressed = ci.shift(1) >= params.chop_level
        if params.side is SignalSide.LONG:
            prior_high = candles["high"].shift(1).rolling(period, min_periods=period).max()
            entry = compressed & (candles["close"] > prior_high)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            prior_low = candles["low"].shift(1).rolling(period, min_periods=period).min()
            entry = compressed & (candles["close"] < prior_low)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: CI {ci.loc[i]:.1f} break" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["ChoppinessIndexBreakParams", "ChoppinessIndexBreakStrategy"]
