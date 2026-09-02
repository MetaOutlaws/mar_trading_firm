"""Fade the weekend gap versus Friday's UTC close.

Calendar weekend, not a rolling gap of N bars. Trade Monday back toward Friday.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class WeekendGapParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class WeekendGapFillStrategy(Strategy):
    name = "weekend_gap_fill"

    def __init__(self, params: WeekendGapParams | None = None) -> None:
        super().__init__(params or WeekendGapParams())
        self.params: WeekendGapParams = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        friday_close = ind.friday_utc_close(candles["close"])
        open_ = candles["open"]
        utc_index = ind._as_utc_index(candles.index)
        weekday = pd.Series(utc_index.dayofweek, index=candles.index)
        monday = weekday.eq(0)
        first_monday = monday & ~monday.shift(1, fill_value=False)
        signals["friday_close"] = friday_close
        if params.side is SignalSide.LONG:
            # Gap down: Monday open below Friday close, fade up toward Friday.
            entry = first_monday & friday_close.notna() & (open_ < friday_close)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = first_monday & friday_close.notna() & (open_ > friday_close)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        gap = ((open_ - friday_close).abs() / friday_close.replace(0, pd.NA)).clip(0.0, 1.0)
        signals.loc[entry, "score"] = gap.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: weekend gap open {open_.loc[i]:.4f} vs Friday {friday_close.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["WeekendGapParams", "WeekendGapFillStrategy"]
