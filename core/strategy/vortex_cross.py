"""Trade +VI crossing -VI. Vortex ratio, not ADX and not SuperTrend."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class VortexCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 14
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class VortexCrossStrategy(Strategy):
    name = "vortex_cross"

    def __init__(self, params: VortexCrossParams | None = None) -> None:
        super().__init__(params or VortexCrossParams())
        self.params: VortexCrossParams = self.params
        self.min_bars = int(self.params.period) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        plus_vi, minus_vi = ind.vortex(
            candles["high"], candles["low"], candles["close"], int(params.period)
        )
        signals["plus_vi"] = plus_vi
        signals["minus_vi"] = minus_vi
        prev_plus = plus_vi.shift(1)
        prev_minus = minus_vi.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev_plus <= prev_minus) & (plus_vi > minus_vi)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev_plus >= prev_minus) & (plus_vi < minus_vi)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: +VI {plus_vi.loc[i]:.2f} -VI {minus_vi.loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["VortexCrossParams", "VortexCrossStrategy"]
