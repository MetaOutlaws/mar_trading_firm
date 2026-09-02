"""Fade Connors RSI extremes. RSI + streak RSI + ROC rank, not a single Wilder RSI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ConnorsRsiFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    rsi_len: int = 3
    streak_len: int = 2
    rank_len: int = 100
    os_level: float = 10.0
    ob_level: float = 90.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ConnorsRsiFadeStrategy(Strategy):
    name = "connors_rsi_fade"

    def __init__(self, params: ConnorsRsiFadeParams | None = None) -> None:
        super().__init__(params or ConnorsRsiFadeParams())
        self.params: ConnorsRsiFadeParams = self.params
        self.min_bars = int(self.params.rank_len) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        crsi = ind.connors_rsi(
            candles["close"],
            rsi_len=int(params.rsi_len),
            streak_len=int(params.streak_len),
            rank_len=int(params.rank_len),
        )
        signals["connors_rsi"] = crsi
        if params.side is SignalSide.LONG:
            entry = (crsi <= params.os_level) & (crsi > crsi.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (crsi >= params.ob_level) & (crsi < crsi.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: CRSI {crsi.loc[i]:.1f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["ConnorsRsiFadeParams", "ConnorsRsiFadeStrategy"]
