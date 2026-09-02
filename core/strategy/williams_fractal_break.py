"""Break a confirmed Williams 5-bar fractal. Pivot confirmation, not a rolling Donchian."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class WilliamsFractalBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class WilliamsFractalBreakStrategy(Strategy):
    name = "williams_fractal_break"

    def __init__(self, params: WilliamsFractalBreakParams | None = None) -> None:
        super().__init__(params or WilliamsFractalBreakParams())
        self.params: WilliamsFractalBreakParams = self.params
        self.min_bars = 6

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        frac_high, frac_low = ind.williams_fractals(candles["high"], candles["low"])
        close = candles["close"]
        signals["fractal_high"] = frac_high
        signals["fractal_low"] = frac_low
        if params.side is SignalSide.LONG:
            entry = (close > frac_high) & (close.shift(1) <= frac_high.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (close < frac_low) & (close.shift(1) >= frac_low.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            level = frac_high if params.side is SignalSide.LONG else frac_low
            reasons.loc[entry] = [
                f"{side_value}: fractal break {level.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["WilliamsFractalBreakParams", "WilliamsFractalBreakStrategy"]
