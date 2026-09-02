"""Fade a failed break of the last confirmed swing high or low.

Swing pivots are confirmed only after the right-hand window has closed.
A failure is a wick through that swing with the close back inside.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SwingFailureParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    pivot_left: int = 3
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class SwingFailureReversalStrategy(Strategy):
    name = "swing_failure_reversal"

    def __init__(self, params: SwingFailureParams | None = None) -> None:
        super().__init__(params or SwingFailureParams())
        self.params: SwingFailureParams = self.params
        self.min_bars = 20

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        swing_high, swing_low = ind.confirmed_swings(
            candles["high"], candles["low"], left=params.pivot_left
        )
        close = candles["close"]
        high = candles["high"]
        low = candles["low"]
        signals["swing_high"] = swing_high
        signals["swing_low"] = swing_low
        if params.side is SignalSide.LONG:
            entry = swing_low.notna() & (low < swing_low) & (close > swing_low)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = swing_high.notna() & (high > swing_high) & (close < swing_high)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        if params.side is SignalSide.LONG:
            depth = ((swing_low - low) / swing_low.replace(0, pd.NA)).clip(0.0, 1.0)
        else:
            depth = ((high - swing_high) / swing_high.replace(0, pd.NA)).clip(0.0, 1.0)
        signals.loc[entry, "score"] = depth.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: failed break of swing {swing_high.loc[i]:.4f}/{swing_low.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["SwingFailureParams", "SwingFailureReversalStrategy"]
