"""Trade a Heikin-Ashi color flip. Averaged bars, not raw candle direction."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class HeikinAshiTrendParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class HeikinAshiTrendStrategy(Strategy):
    name = "heikin_ashi_trend"

    def __init__(self, params: HeikinAshiTrendParams | None = None) -> None:
        super().__init__(params or HeikinAshiTrendParams())
        self.params: HeikinAshiTrendParams = self.params
        self.min_bars = 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        ha = ind.heikin_ashi(
            candles["open"], candles["high"], candles["low"], candles["close"]
        )
        bull = ha["ha_close"] > ha["ha_open"]
        bear = ha["ha_close"] < ha["ha_open"]
        signals["ha_open"] = ha["ha_open"]
        signals["ha_close"] = ha["ha_close"]
        # First bar of a new HA color after the opposite color. Uses t and t-1 only.
        if params.side is SignalSide.LONG:
            entry = bull & bear.shift(1).fillna(False)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = bear & bull.shift(1).fillna(False)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: HA flip close {ha['ha_close'].loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["HeikinAshiTrendParams", "HeikinAshiTrendStrategy"]
