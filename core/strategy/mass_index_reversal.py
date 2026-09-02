"""Reverse after a Mass Index bulge. Range-ratio bulge, not Bollinger width."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class MassIndexReversalParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    ema_len: int = 9
    sum_len: int = 25
    bulge: float = 27.0
    setup: float = 26.5
    # 0 disables. 50 keeps longs above SMA (skips bear) and shorts below it.
    trend_sma: int = 0
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class MassIndexReversalStrategy(Strategy):
    name = "mass_index_reversal"

    def __init__(self, params: MassIndexReversalParams | None = None) -> None:
        super().__init__(params or MassIndexReversalParams())
        self.params: MassIndexReversalParams = self.params
        self.min_bars = (
            int(self.params.ema_len) * 2
            + int(self.params.sum_len)
            + 2
            + max(int(self.params.trend_sma), 0)
        )

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        mi = ind.mass_index(
            candles["high"], candles["low"], int(params.ema_len), int(params.sum_len)
        )
        signals["mass_index"] = mi
        # Bulge then reversal: MI recently printed the bulge and has now
        # crossed back below the setup — the drop can take more than one bar.
        recent_bulge = mi.shift(1).rolling(8, min_periods=1).max() >= params.bulge
        crossed_setup = (mi.shift(1) >= params.setup) & (mi < params.setup)
        bulge = recent_bulge & crossed_setup
        close = candles["close"]
        if params.side is SignalSide.LONG:
            entry = bulge & (close > close.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = bulge & (close < close.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        # Causal trend gate: SMA at t uses closes <= t. Skip counter-trend fades.
        if int(params.trend_sma) > 0:
            mid = ind.sma(close, int(params.trend_sma))
            aligned = close > mid if params.side is SignalSide.LONG else close < mid
            entry = entry & aligned.fillna(False)
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: MI {mi.loc[i]:.2f}" for i in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["MassIndexReversalParams", "MassIndexReversalStrategy"]
