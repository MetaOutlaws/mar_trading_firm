"""Reverse in the close direction of an outside bar.

This bar's range fully contains the prior bar. Opposite of inside-bar breakout.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class OutsideBarParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class OutsideBarReversalStrategy(Strategy):
    name = "outside_bar_reversal"

    def __init__(self, params: OutsideBarParams | None = None) -> None:
        super().__init__(params or OutsideBarParams())
        self.params: OutsideBarParams = self.params
        self.min_bars = 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        outside = ind.outside_bar(candles["high"], candles["low"])
        close = candles["close"]
        open_ = candles["open"]
        signals["outside"] = outside.astype(float)
        if params.side is SignalSide.LONG:
            entry = outside & (close > open_)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = outside & (close < open_)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: outside bar close {close.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["OutsideBarParams", "OutsideBarReversalStrategy"]
