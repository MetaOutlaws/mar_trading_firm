"""Fade Chaikin Money Flow extremes. Windowed CLV volume ratio, not an EMA of ADL."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ChaikinMoneyFlowFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 20
    os_level: float = -0.05
    ob_level: float = 0.05
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ChaikinMoneyFlowFadeStrategy(Strategy):
    name = "chaikin_money_flow_fade"

    def __init__(self, params: ChaikinMoneyFlowFadeParams | None = None) -> None:
        super().__init__(params or ChaikinMoneyFlowFadeParams())
        self.params: ChaikinMoneyFlowFadeParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        cmf = ind.chaikin_money_flow(
            candles["high"],
            candles["low"],
            candles["close"],
            candles["volume"],
            int(params.period),
        )
        signals["cmf"] = cmf
        if params.side is SignalSide.LONG:
            entry = (cmf <= params.os_level) & (cmf > cmf.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (cmf >= params.ob_level) & (cmf < cmf.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: CMF {cmf.loc[i]:.3f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["ChaikinMoneyFlowFadeParams", "ChaikinMoneyFlowFadeStrategy"]
