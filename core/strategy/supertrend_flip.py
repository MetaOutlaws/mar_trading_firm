"""Enter on a SuperTrend flip. Trailing ATR stop, not an EMA channel break."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SupertrendFlipParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    atr_period: int = 10
    multiplier: float = 3.0
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class SupertrendFlipStrategy(Strategy):
    name = "supertrend_flip"

    def __init__(self, params: SupertrendFlipParams | None = None) -> None:
        super().__init__(params or SupertrendFlipParams())
        self.params: SupertrendFlipParams = self.params
        self.min_bars = int(self.params.atr_period) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        direction = ind.supertrend_direction(
            candles["high"],
            candles["low"],
            candles["close"],
            period=int(params.atr_period),
            multiplier=float(params.multiplier),
        )
        signals["supertrend"] = direction
        flipped = direction.ne(direction.shift(1)) & direction.ne(0)
        if params.side is SignalSide.LONG:
            entry = flipped & direction.eq(1)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = flipped & direction.eq(-1)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: supertrend flip {int(direction.loc[i])}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["SupertrendFlipParams", "SupertrendFlipStrategy"]
