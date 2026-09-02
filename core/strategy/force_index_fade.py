"""Fade an extreme Elder Force Index. Signed volume, not RSI."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ForceIndexFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 13
    z_lookback: int = 40
    z_stretch: float = 1.5
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ForceIndexFadeStrategy(Strategy):
    name = "force_index_fade"

    def __init__(self, params: ForceIndexFadeParams | None = None) -> None:
        super().__init__(params or ForceIndexFadeParams())
        self.params: ForceIndexFadeParams = self.params
        self.min_bars = int(self.params.period) + int(self.params.z_lookback) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        force = ind.force_index(
            candles["close"], candles["volume"], int(params.period)
        )
        # Z-score vs prior bars only so the current print cannot shrink its own stretch.
        lookback = int(params.z_lookback)
        past = force.shift(1)
        mean = past.rolling(lookback, min_periods=lookback).mean()
        std = past.rolling(lookback, min_periods=lookback).std()
        z = (force - mean) / std.replace(0, np.nan)
        signals["force_index"] = force
        signals["force_z"] = z
        stretch = abs(float(params.z_stretch))
        if params.side is SignalSide.LONG:
            entry = (z <= -stretch) & (force > force.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (z >= stretch) & (force < force.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: Force z {z.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["ForceIndexFadeParams", "ForceIndexFadeStrategy"]
