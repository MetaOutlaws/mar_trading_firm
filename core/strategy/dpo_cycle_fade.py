"""Fade causal DPO extremes. Detrended oscillator, not Bollinger mean-reversion."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class DpoCycleFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 20
    stretch_pct: float = 0.02
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class DpoCycleFadeStrategy(Strategy):
    name = "dpo_cycle_fade"

    def __init__(self, params: DpoCycleFadeParams | None = None) -> None:
        super().__init__(params or DpoCycleFadeParams())
        self.params: DpoCycleFadeParams = self.params
        # SMA(period) plus the causal lag of period/2+1 past bars.
        self.min_bars = int(self.params.period) + (int(self.params.period) // 2) + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        dpo = ind.causal_dpo(candles["close"], int(params.period))
        close = candles["close"].replace(0, pd.NA)
        rel = dpo / close
        signals["dpo"] = dpo
        signals["dpo_pct"] = rel
        stretch = abs(float(params.stretch_pct))
        if params.side is SignalSide.LONG:
            entry = (rel <= -stretch) & (dpo > dpo.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (rel >= stretch) & (dpo < dpo.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: DPO {dpo.loc[i]:.2f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["DpoCycleFadeParams", "DpoCycleFadeStrategy"]
