"""Enter on an Awesome Oscillator saucer. Midpoint SMAs, not close MACD."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class AwesomeOscillatorSaucerParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class AwesomeOscillatorSaucerStrategy(Strategy):
    name = "awesome_oscillator_saucer"

    def __init__(self, params: AwesomeOscillatorSaucerParams | None = None) -> None:
        super().__init__(params or AwesomeOscillatorSaucerParams())
        self.params: AwesomeOscillatorSaucerParams = self.params
        self.min_bars = 36

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        ao = ind.awesome_oscillator(candles["high"], candles["low"])
        prev = ao.shift(1)
        prev2 = ao.shift(2)
        signals["ao"] = ao
        # Bullish saucer: AO above zero, two falling histogram bars, then a higher bar.
        # Bearish saucer: AO below zero, two rising bars, then a lower bar.
        if params.side is SignalSide.LONG:
            entry = (ao > 0) & (prev2 > prev) & (ao > prev)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (ao < 0) & (prev2 < prev) & (ao < prev)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: AO saucer {ao.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["AwesomeOscillatorSaucerParams", "AwesomeOscillatorSaucerStrategy"]
