"""Fade a failed Monday London/NY sweep of the completed UTC weekend box.

Weekend is Saturday 00:00 through Sunday 23:59 UTC — a calendar window, not
the dead Asian 00:00–08:00 session box (`session_liquidity_sweep`). After
Sunday closes, a Monday London or NY bar that pokes beyond that box by less
than `max_sweep_pct` and closes back inside fades toward the weekend mid.
OHLCV calendar math only — no order-book feed.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class MondayRangeSweepReversalParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # London 08:00–16:00 plus NY 13:00–21:00 UTC, as one Monday trade window.
    trade_start: float = 8.0
    trade_end: float = 21.0
    # Maximum excursion beyond the weekend boundary as a fraction of that level.
    max_sweep_pct: float = 0.015
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class MondayRangeSweepReversalStrategy(Strategy):
    name = "monday_range_sweep_reversal"

    def __init__(self, params: MondayRangeSweepReversalParams | None = None) -> None:
        super().__init__(params or MondayRangeSweepReversalParams())
        self.params: MondayRangeSweepReversalParams = self.params
        # Need a completed Sat–Sun box plus the first Monday London bar.
        self.min_bars = 16

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        # Causal: weekend box uses bars <= t only. Saturday never sees Sunday.
        range_high, range_low, weekend_ready = ind.weekend_utc_range(
            candles["high"], candles["low"]
        )
        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        utc_index = ind._as_utc_index(candles.index)
        hours_into = (utc_index - utc_index.normalize()) / pd.Timedelta(hours=1)
        in_london_or_ny = pd.Series(
            (hours_into >= float(params.trade_start))
            & (hours_into < float(params.trade_end)),
            index=candles.index,
        )

        max_pct = float(params.max_sweep_pct)
        # Same-bar failed sweep: poke through, close back inside, stay under 1.5%.
        sweep_low = (
            weekend_ready
            & in_london_or_ny
            & (low < range_low)
            & (close >= range_low)
            & (close <= range_high)
            & ((range_low - low) <= range_low.abs() * max_pct)
        )
        sweep_high = (
            weekend_ready
            & in_london_or_ny
            & (high > range_high)
            & (close <= range_high)
            & (close >= range_low)
            & ((high - range_high) <= range_high.abs() * max_pct)
        )

        weekend_mid = (range_high + range_low) / 2.0
        signals["range_high"] = range_high
        signals["range_low"] = range_low
        signals["weekend_mid"] = weekend_mid
        signals["weekend_ready"] = weekend_ready.astype("float64")

        if params.side is SignalSide.LONG:
            raw = sweep_low
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = sweep_high
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One fade per Monday. Calendar day, not a rolling session box.
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (range_high - range_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - range_low) / width).clip(0.0, 1.0)
        else:
            score = ((range_high - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: weekend sweep fade close {close.loc[i]:.4f} vs "
                    f"{range_high.loc[i]:.4f}/{range_low.loc[i]:.4f} "
                    f"mid {weekend_mid.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["MondayRangeSweepReversalParams", "MondayRangeSweepReversalStrategy"]
