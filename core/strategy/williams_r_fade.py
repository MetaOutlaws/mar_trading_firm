"""Fade Williams %R extremes. Inverted range oscillator, not RSI and not Stochastic %K."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class WilliamsRFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 14
    os_level: float = -80.0
    ob_level: float = -20.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class WilliamsRFadeStrategy(Strategy):
    name = "williams_r_fade"

    def __init__(self, params: WilliamsRFadeParams | None = None) -> None:
        super().__init__(params or WilliamsRFadeParams())
        self.params: WilliamsRFadeParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        wr = ind.williams_r(
            candles["high"], candles["low"], candles["close"], int(params.period)
        )
        signals["williams_r"] = wr
        # Fade: buy when %R turns up from oversold, sell when it turns down from overbought.
        if params.side is SignalSide.LONG:
            entry = (wr <= params.os_level) & (wr > wr.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (wr >= params.ob_level) & (wr < wr.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: Williams %R {wr.loc[i]:.1f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["WilliamsRFadeParams", "WilliamsRFadeStrategy"]
