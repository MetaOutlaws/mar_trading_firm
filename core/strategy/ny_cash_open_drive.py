"""Trade in the direction of the US cash-open hour after that hour closes.

The 13:00–14:00 UTC (08:00–09:00 ET) bar is the drive. Published only after
14:00. Not ORB and not Donchian.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class NyCashOpenParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class NyCashOpenDriveStrategy(Strategy):
    name = "ny_cash_open_drive"

    def __init__(self, params: NyCashOpenParams | None = None) -> None:
        super().__init__(params or NyCashOpenParams())
        self.params: NyCashOpenParams = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        direction, ready = ind.ny_cash_open_drive(candles["open"], candles["close"])
        signals["drive_dir"] = direction
        if params.side is SignalSide.LONG:
            raw = ready & direction.eq(1)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = ready & direction.eq(-1)
            signal_value, side_value = -1, SignalSide.SHORT.value
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: NY cash-open drive {int(direction.loc[i])}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["NyCashOpenParams", "NyCashOpenDriveStrategy"]
