"""Break the mother bar after a full inside bar.

Two-bar structure: bar t-1 sits inside bar t-2, then bar t closes through that
mother range. Not N-bar Donchian.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class InsideBarParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class InsideBarBreakoutStrategy(Strategy):
    name = "inside_bar_breakout"

    def __init__(self, params: InsideBarParams | None = None) -> None:
        super().__init__(params or InsideBarParams())
        self.params: InsideBarParams = self.params
        self.min_bars = 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        mother_high, mother_low, inside = ind.inside_bar_mother(
            candles["high"], candles["low"]
        )
        close = candles["close"]
        signals["mother_high"] = mother_high
        signals["mother_low"] = mother_low
        if params.side is SignalSide.LONG:
            entry = inside & (close > mother_high)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = inside & (close < mother_low)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (mother_high - mother_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - mother_high) / width).clip(0.0, 1.0)
        else:
            score = ((mother_low - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: close {close.loc[i]:.4f} breaks mother {mother_high.loc[i]:.4f}/{mother_low.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["InsideBarParams", "InsideBarBreakoutStrategy"]
