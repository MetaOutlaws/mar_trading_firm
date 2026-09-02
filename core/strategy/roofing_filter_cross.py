"""Trade the roofing filter crossing zero. HP then SuperSmoother, not a decycler."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class RoofingFilterCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    hp_period: int = 48
    lp_period: int = 10
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class RoofingFilterCrossStrategy(Strategy):
    name = "roofing_filter_cross"

    def __init__(self, params: RoofingFilterCrossParams | None = None) -> None:
        super().__init__(params or RoofingFilterCrossParams())
        self.params: RoofingFilterCrossParams = self.params
        self.min_bars = int(self.params.hp_period) + int(self.params.lp_period) + 4

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        osc = ind.ehlers_roofing_filter(
            candles["close"], int(params.hp_period), int(params.lp_period)
        )
        signals["roofing"] = osc
        prev = osc.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev <= 0) & (osc > 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev >= 0) & (osc < 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: roofing {osc.loc[i]:.4f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["RoofingFilterCrossParams", "RoofingFilterCrossStrategy"]
