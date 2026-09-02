"""Break the VPT channel. Percent-change volume ledger, not sign-only OBV."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class VolumePriceTrendBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    lookback: int = 20
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class VolumePriceTrendBreakStrategy(Strategy):
    name = "volume_price_trend_break"

    def __init__(self, params: VolumePriceTrendBreakParams | None = None) -> None:
        super().__init__(params or VolumePriceTrendBreakParams())
        self.params: VolumePriceTrendBreakParams = self.params
        self.min_bars = int(self.params.lookback) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        vpt = ind.volume_price_trend(candles["close"], candles["volume"])
        lookback = int(params.lookback)
        prior_high = vpt.shift(1).rolling(lookback, min_periods=lookback).max()
        prior_low = vpt.shift(1).rolling(lookback, min_periods=lookback).min()
        signals["vpt"] = vpt
        if params.side is SignalSide.LONG:
            entry = vpt > prior_high
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = vpt < prior_low
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: VPT break {vpt.loc[i]:.0f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["VolumePriceTrendBreakParams", "VolumePriceTrendBreakStrategy"]
