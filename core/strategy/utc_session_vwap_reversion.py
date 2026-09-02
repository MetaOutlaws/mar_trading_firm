"""UTC-day VWAP fade — cumulative volume math the templates do not have.

VWAP resets at each UTC midnight from typical-price * volume. Fade a close
that stretches away from that session VWAP. Not a rolling SMA and not Bollinger.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class UtcSessionVwapParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    stretch_pct: float = 0.005
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class UtcSessionVwapReversionStrategy(Strategy):
    name = "utc_session_vwap_reversion"

    def __init__(self, params: UtcSessionVwapParams | None = None) -> None:
        super().__init__(params or UtcSessionVwapParams())
        self.params: UtcSessionVwapParams = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        vwap = ind.utc_session_vwap(
            candles["high"], candles["low"], candles["close"], candles["volume"]
        )
        close = candles["close"]
        signals["vwap"] = vwap
        ready = vwap.notna()
        if params.side is SignalSide.LONG:
            raw = ready & (close < vwap * (1.0 - params.stretch_pct))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = ready & (close > vwap * (1.0 + params.stretch_pct))
            signal_value, side_value = -1, SignalSide.SHORT.value

        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (vwap * params.stretch_pct).replace(0, pd.NA)
        extension = ((vwap - close).abs() / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = extension.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: close {close.loc[i]:.4f} vs UTC VWAP {vwap.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["UtcSessionVwapParams", "UtcSessionVwapReversionStrategy"]
