"""Fade Twiggs Money Flow extremes. TR-buffered AD volume, not MFI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class TwiggsMoneyFlowFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 21
    os_level: float = -0.05
    ob_level: float = 0.05
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class TwiggsMoneyFlowFadeStrategy(Strategy):
    name = "twiggs_money_flow_fade"

    def __init__(self, params: TwiggsMoneyFlowFadeParams | None = None) -> None:
        super().__init__(params or TwiggsMoneyFlowFadeParams())
        self.params: TwiggsMoneyFlowFadeParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        tmf = ind.twiggs_money_flow(
            candles["high"], candles["low"], candles["close"], candles["volume"], int(params.period)
        )
        signals["tmf"] = tmf
        if params.side is SignalSide.LONG:
            entry = (tmf <= params.os_level) & (tmf > tmf.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (tmf >= params.ob_level) & (tmf < tmf.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: TMF {tmf.loc[i]:.3f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["TwiggsMoneyFlowFadeParams", "TwiggsMoneyFlowFadeStrategy"]
