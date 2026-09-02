"""Trade a Chandelier Exit flip. ATR trail from HH/LL since side, not SAR."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ChandelierExitFlipParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 22
    atr_k: float = 3.0
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class ChandelierExitFlipStrategy(Strategy):
    name = "chandelier_exit_flip"

    def __init__(self, params: ChandelierExitFlipParams | None = None) -> None:
        super().__init__(params or ChandelierExitFlipParams())
        self.params: ChandelierExitFlipParams = self.params
        self.min_bars = int(self.params.period) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        trail, direction = ind.chandelier_direction(
            candles["high"],
            candles["low"],
            candles["close"],
            period=int(params.period),
            atr_k=float(params.atr_k),
        )
        signals["chandelier"] = trail
        signals["chandelier_dir"] = direction
        prev = direction.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev <= 0) & (direction > 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev >= 0) & (direction < 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: Chandelier flip" for _ in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["ChandelierExitFlipParams", "ChandelierExitFlipStrategy"]
