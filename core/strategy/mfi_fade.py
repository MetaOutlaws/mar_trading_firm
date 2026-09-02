"""Fade Money Flow Index extremes. Volume-weighted RSI, not close-only RSI."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class MfiFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    period: int = 14
    os_level: float = 20.0
    ob_level: float = 80.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class MfiFadeStrategy(Strategy):
    name = "mfi_fade"

    def __init__(self, params: MfiFadeParams | None = None) -> None:
        super().__init__(params or MfiFadeParams())
        self.params: MfiFadeParams = self.params
        self.min_bars = int(self.params.period) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        mfi = ind.money_flow_index(
            candles["high"],
            candles["low"],
            candles["close"],
            candles["volume"],
            int(params.period),
        )
        signals["mfi"] = mfi
        # Fade: buy when MFI turns up from oversold, sell when it turns down from overbought.
        if params.side is SignalSide.LONG:
            entry = (mfi <= params.os_level) & (mfi > mfi.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (mfi >= params.ob_level) & (mfi < mfi.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: MFI {mfi.loc[i]:.1f}" for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["MfiFadeParams", "MfiFadeStrategy"]
