"""Break the NR7 bar after the narrowest range of the last 7 prints.

Range-rank, not Bollinger width and not an N-bar Donchian channel.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class Nr7Params(StrategyParams):
    side: SignalSide = SignalSide.LONG
    lookback: int = 7
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class Nr7BreakoutStrategy(Strategy):
    name = "nr7_breakout"

    def __init__(self, params: Nr7Params | None = None) -> None:
        super().__init__(params or Nr7Params())
        self.params: Nr7Params = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        nr_high, nr_low, setup = ind.nr7_setup(
            candles["high"], candles["low"], lookback=params.lookback
        )
        close = candles["close"]
        signals["nr7_high"] = nr_high
        signals["nr7_low"] = nr_low
        if params.side is SignalSide.LONG:
            entry = setup & (close > nr_high)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = setup & (close < nr_low)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (nr_high - nr_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - nr_high) / width).clip(0.0, 1.0)
        else:
            score = ((nr_low - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: close {close.loc[i]:.4f} breaks NR7 {nr_high.loc[i]:.4f}/{nr_low.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["Nr7Params", "Nr7BreakoutStrategy"]
