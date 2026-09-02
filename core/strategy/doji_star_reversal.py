"""Fade after a doji that prints following a directional run.

Doji body/range plus run context. Not wick-rejection and not engulfing.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class DojiStarParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    run_bars: int = 3
    max_body_frac: float = 0.1
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class DojiStarReversalStrategy(Strategy):
    name = "doji_star_reversal"

    def __init__(self, params: DojiStarParams | None = None) -> None:
        super().__init__(params or DojiStarParams())
        self.params: DojiStarParams = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        close = candles["close"]
        doji = ind.doji_bar(
            candles["open"], candles["high"], candles["low"], close, max_body_frac=params.max_body_frac
        )
        # Run of `run_bars` closes ending at t-2, then doji at t-1, confirm at t.
        down_run = pd.Series(True, index=close.index)
        up_run = pd.Series(True, index=close.index)
        for step in range(params.run_bars):
            newer = close.shift(2 + step)
            older = close.shift(3 + step)
            down_run = down_run & (newer < older)
            up_run = up_run & (newer > older)
        star = doji.shift(1).eq(True)
        signals["doji"] = doji.astype(float)
        if params.side is SignalSide.LONG:
            entry = star & down_run & (close > candles["high"].shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = star & up_run & (close < candles["low"].shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: doji-star confirm close {close.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["DojiStarParams", "DojiStarReversalStrategy"]
