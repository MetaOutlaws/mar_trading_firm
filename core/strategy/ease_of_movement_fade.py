"""Fade extreme Ease of Movement. Midpoint/volume box, not Force Index."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class EaseOfMovementFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 14
    lookback: int = 40
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class EaseOfMovementFadeStrategy(Strategy):
    name = "ease_of_movement_fade"

    def __init__(self, params: EaseOfMovementFadeParams | None = None) -> None:
        super().__init__(params or EaseOfMovementFadeParams())
        self.params: EaseOfMovementFadeParams = self.params
        self.min_bars = int(self.params.period) + int(self.params.lookback) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        eom = ind.ease_of_movement(
            candles["high"], candles["low"], candles["volume"], int(params.period)
        )
        signals["eom"] = eom
        window = int(params.lookback)
        if params.side is SignalSide.LONG:
            prev = eom.shift(1)
            trough = prev <= prev.rolling(window, min_periods=window).min()
            entry = trough & (eom > prev) & (prev < 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            prev = eom.shift(1)
            peak = prev >= prev.rolling(window, min_periods=window).max()
            entry = peak & (eom < prev) & (prev > 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: EOM fade" for _ in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["EaseOfMovementFadeParams", "EaseOfMovementFadeStrategy"]
