"""Fade stretch away from the UTC-day TWAP (equal weight per bar).

TWAP resets at midnight and ignores volume. Not session VWAP.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class UtcSessionTwapParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    stretch_pct: float = 0.005
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class UtcSessionTwapReversionStrategy(Strategy):
    name = "utc_session_twap_reversion"

    def __init__(self, params: UtcSessionTwapParams | None = None) -> None:
        super().__init__(params or UtcSessionTwapParams())
        self.params: UtcSessionTwapParams = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        twap = ind.utc_session_twap(candles["close"])
        close = candles["close"]
        signals["twap"] = twap
        ready = twap.notna()
        if params.side is SignalSide.LONG:
            raw = ready & (close < twap * (1.0 - params.stretch_pct))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = ready & (close > twap * (1.0 + params.stretch_pct))
            signal_value, side_value = -1, SignalSide.SHORT.value
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (twap * params.stretch_pct).replace(0, pd.NA)
        extension = ((twap - close).abs() / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = extension.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: close {close.loc[i]:.4f} vs UTC TWAP {twap.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["UtcSessionTwapParams", "UtcSessionTwapReversionStrategy"]
