"""Break the prior completed UTC week's high or low.

Weekly calendar box, published only after Sunday closes. Not prior-day
pivots and not a rolling Donchian.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class PriorWeekParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class PriorWeekHighBreakStrategy(Strategy):
    name = "prior_week_high_break"

    def __init__(self, params: PriorWeekParams | None = None) -> None:
        super().__init__(params or PriorWeekParams())
        self.params: PriorWeekParams = self.params
        self.min_bars = 40

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        week_high, week_low = ind.prior_utc_week_range(candles["high"], candles["low"])
        close = candles["close"]
        signals["week_high"] = week_high
        signals["week_low"] = week_low
        if params.side is SignalSide.LONG:
            raw = week_high.notna() & (close > week_high)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = week_low.notna() & (close < week_low)
            signal_value, side_value = -1, SignalSide.SHORT.value
        utc_index = candles.index.tz_convert("UTC") if candles.index.tz is not None else candles.index
        naive = utc_index.tz_localize(None) if getattr(utc_index, "tz", None) is not None else utc_index
        week_key = pd.Series(pd.DatetimeIndex(naive).to_period("W-SUN").astype(str), index=candles.index)
        entry = raw.fillna(False) & raw.groupby(week_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (week_high - week_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - week_high) / width).clip(0.0, 1.0)
        else:
            score = ((week_low - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: close {close.loc[i]:.4f} vs prior week {week_high.loc[i]:.4f}/{week_low.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["PriorWeekParams", "PriorWeekHighBreakStrategy"]
