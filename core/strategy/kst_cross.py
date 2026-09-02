"""Trade KST crossing its signal line. Stacked ROC composite, not MACD and not PPO."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class KstCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    signal: int = 9
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class KstCrossStrategy(Strategy):
    name = "kst_cross"

    def __init__(self, params: KstCrossParams | None = None) -> None:
        super().__init__(params or KstCrossParams())
        self.params: KstCrossParams = self.params
        # Longest ROC (30) + its SMA (15) + signal SMA.
        self.min_bars = 30 + 15 + int(self.params.signal) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        line, sig = ind.kst(candles["close"], signal=int(params.signal))
        signals["kst"] = line
        signals["kst_signal"] = sig
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
                f"{side_value}: KST {line.loc[i]:.2f} sig {sig.loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["KstCrossParams", "KstCrossStrategy"]
