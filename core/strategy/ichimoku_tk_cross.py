"""Trade Tenkan crossing Kijun. High-low midpoints, not EMAs, no displaced cloud."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class IchimokuTkCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    tenkan_period: int = 9
    kijun_period: int = 26
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class IchimokuTkCrossStrategy(Strategy):
    name = "ichimoku_tk_cross"

    def __init__(self, params: IchimokuTkCrossParams | None = None) -> None:
        super().__init__(params or IchimokuTkCrossParams())
        self.params: IchimokuTkCrossParams = self.params
        self.min_bars = int(self.params.kijun_period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        tenkan, kijun = ind.tenkan_kijun(
            candles["high"],
            candles["low"],
            tenkan_period=int(params.tenkan_period),
            kijun_period=int(params.kijun_period),
        )
        signals["tenkan"] = tenkan
        signals["kijun"] = kijun
        prev_t = tenkan.shift(1)
        prev_k = kijun.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev_t <= prev_k) & (tenkan > kijun)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev_t >= prev_k) & (tenkan < kijun)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: TK cross T {tenkan.loc[i]:.2f} K {kijun.loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["IchimokuTkCrossParams", "IchimokuTkCrossStrategy"]
