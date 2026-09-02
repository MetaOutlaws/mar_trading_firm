"""Fade the UTC-midnight gap back toward the prior day's close.

Gap is today's first-hour open versus the prior UTC day close. Not VWAP and
not opening-range break.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class MidnightGapParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class UtcMidnightGapFillStrategy(Strategy):
    name = "utc_midnight_gap_fill"

    def __init__(self, params: MidnightGapParams | None = None) -> None:
        super().__init__(params or MidnightGapParams())
        self.params: MidnightGapParams = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        prev_close = ind.prior_day_close(candles["close"])
        open_ = candles["open"]
        day = ind.utc_day_key(candles.index)
        first_of_day = day.ne(day.shift(1))
        signals["prior_close"] = prev_close
        if params.side is SignalSide.LONG:
            entry = first_of_day & prev_close.notna() & (open_ < prev_close)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = first_of_day & prev_close.notna() & (open_ > prev_close)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        gap = ((open_ - prev_close).abs() / prev_close.replace(0, pd.NA)).clip(0.0, 1.0)
        signals.loc[entry, "score"] = gap.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: midnight gap open {open_.loc[i]:.4f} vs prior close {prev_close.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["MidnightGapParams", "UtcMidnightGapFillStrategy"]
