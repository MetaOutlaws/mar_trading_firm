"""Break the rest bar of a 3-bar play.

Trend bar, narrow rest inside it, then a break of the rest in the trend
direction. Not a two-bar inside-bar and not Donchian.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ThreeBarPlayParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ThreeBarPlayStrategy(Strategy):
    name = "three_bar_play"

    def __init__(self, params: ThreeBarPlayParams | None = None) -> None:
        super().__init__(params or ThreeBarPlayParams())
        self.params: ThreeBarPlayParams = self.params
        self.min_bars = 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        rest_high, rest_low, direction = ind.three_bar_play_setup(
            candles["open"], candles["high"], candles["low"], candles["close"]
        )
        close = candles["close"]
        signals["rest_high"] = rest_high
        signals["rest_low"] = rest_low
        if params.side is SignalSide.LONG:
            entry = direction.eq(1) & (close > rest_high)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = direction.eq(-1) & (close < rest_low)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (rest_high - rest_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - rest_high) / width).clip(0.0, 1.0)
        else:
            score = ((rest_low - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: 3-bar play break rest {rest_high.loc[i]:.4f}/{rest_low.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["ThreeBarPlayParams", "ThreeBarPlayStrategy"]
