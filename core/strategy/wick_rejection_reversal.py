"""Enter when a long wick rejects and the close comes back inside the body zone.

Candle geometry, not a Bollinger touch and not ATR stretch.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class WickRejectionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    min_wick_frac: float = 0.6
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class WickRejectionReversalStrategy(Strategy):
    name = "wick_rejection_reversal"

    def __init__(self, params: WickRejectionParams | None = None) -> None:
        super().__init__(params or WickRejectionParams())
        self.params: WickRejectionParams = self.params
        self.min_bars = 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        open_ = candles["open"]
        close = candles["close"]
        high = candles["high"]
        low = candles["low"]
        bar_range = (high - low).replace(0, pd.NA)
        body_high = pd.concat([open_, close], axis=1).max(axis=1)
        body_low = pd.concat([open_, close], axis=1).min(axis=1)
        lower_wick = (body_low - low) / bar_range
        upper_wick = (high - body_high) / bar_range
        signals["lower_wick"] = lower_wick
        signals["upper_wick"] = upper_wick
        if params.side is SignalSide.LONG:
            entry = (lower_wick >= params.min_wick_frac) & (close >= body_low)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (upper_wick >= params.min_wick_frac) & (close <= body_high)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        wick = lower_wick if params.side is SignalSide.LONG else upper_wick
        signals.loc[entry, "score"] = wick.clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: wick rejection close {close.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["WickRejectionParams", "WickRejectionReversalStrategy"]
