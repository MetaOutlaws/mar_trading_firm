"""Fade Ultimate Oscillator extremes. Three BP/TR windows, not RSI and not MFI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class UltimateOscillatorFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    short: int = 7
    mid: int = 14
    long: int = 28
    os_level: float = 30.0
    ob_level: float = 70.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class UltimateOscillatorFadeStrategy(Strategy):
    name = "ultimate_oscillator_fade"

    def __init__(self, params: UltimateOscillatorFadeParams | None = None) -> None:
        super().__init__(params or UltimateOscillatorFadeParams())
        self.params: UltimateOscillatorFadeParams = self.params
        self.min_bars = int(self.params.long) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        uo = ind.ultimate_oscillator(
            candles["high"],
            candles["low"],
            candles["close"],
            short=int(params.short),
            mid=int(params.mid),
            long=int(params.long),
        )
        signals["uo"] = uo
        if params.side is SignalSide.LONG:
            entry = (uo <= params.os_level) & (uo > uo.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (uo >= params.ob_level) & (uo < uo.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: UO {uo.loc[i]:.1f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["UltimateOscillatorFadeParams", "UltimateOscillatorFadeStrategy"]
