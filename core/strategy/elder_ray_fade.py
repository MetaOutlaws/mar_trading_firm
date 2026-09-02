"""Fade extreme Elder Ray Bear/Bull Power. Bar extremes vs EMA, not signed volume."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ElderRayFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 13
    z_lookback: int = 40
    z_stretch: float = 1.5
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ElderRayFadeStrategy(Strategy):
    name = "elder_ray_fade"

    def __init__(self, params: ElderRayFadeParams | None = None) -> None:
        super().__init__(params or ElderRayFadeParams())
        self.params: ElderRayFadeParams = self.params
        self.min_bars = int(self.params.period) + int(self.params.z_lookback) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        bull, bear = ind.elder_ray(
            candles["high"], candles["low"], candles["close"], int(params.period)
        )
        window = int(params.z_lookback)
        signals["bull_power"] = bull
        signals["bear_power"] = bear
        if params.side is SignalSide.LONG:
            prev = bear.shift(1)
            trough = prev <= prev.rolling(window, min_periods=window).min()
            entry = trough & (bear > prev) & (prev < 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            prev = bull.shift(1)
            peak = prev >= prev.rolling(window, min_periods=window).max()
            entry = peak & (bull < prev) & (prev > 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: Elder Ray fade" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["ElderRayFadeParams", "ElderRayFadeStrategy"]
