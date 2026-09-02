"""Trade RVI crossing its signal. Body/range oscillator, not Qstick of close-open alone."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class RelativeVigorCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 10
    signal: int = 4
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class RelativeVigorCrossStrategy(Strategy):
    name = "relative_vigor_cross"

    def __init__(self, params: RelativeVigorCrossParams | None = None) -> None:
        super().__init__(params or RelativeVigorCrossParams())
        self.params: RelativeVigorCrossParams = self.params
        self.min_bars = int(self.params.period) + int(self.params.signal) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        line, sig = ind.relative_vigor(
            candles["open"],
            candles["high"],
            candles["low"],
            candles["close"],
            period=int(params.period),
            signal=int(params.signal),
        )
        signals["rvi"] = line
        signals["rvi_signal"] = sig
        prev_line = line.shift(1)
        prev_sig = sig.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev_line <= prev_sig) & (line > sig)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev_line >= prev_sig) & (line < sig)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: RVI {line.loc[i]:.3f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["RelativeVigorCrossParams", "RelativeVigorCrossStrategy"]
