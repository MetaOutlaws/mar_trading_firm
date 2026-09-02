"""UTC opening-range breakout — session math the indicator library did not have.

Break the first N-hour high/low of the UTC day. The range is taken only from
completed opening-window bars; the engine fills at t+1 open. This is not a
rolling Donchian rename: the window is a calendar session, one shot per day.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class OpeningRangeParams(StrategyParams):
    """Parameters for the UTC opening-range breakout sleeve."""

    side: SignalSide = SignalSide.LONG
    # First N hours of the UTC day form the range. 1 = the 00:00 hour bar on 1h.
    range_hours: int = 1
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class OpeningRangeBreakoutStrategy(Strategy):
    """Break the completed UTC opening range; at most one entry per UTC day."""

    name = "opening_range_breakout"

    def __init__(self, params: OpeningRangeParams | None = None) -> None:
        super().__init__(params or OpeningRangeParams())
        self.params: OpeningRangeParams = self.params
        # One completed opening window plus a couple of post-window bars.
        # Bar size is unknown here; 12 covers 1h (range_hours=2) and 15m (1h window).
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)

        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        range_high, range_low, ready = ind.utc_opening_range(
            high, low, range_hours=float(params.range_hours)
        )

        signals["range_high"] = range_high
        signals["range_low"] = range_low
        signals["range_ready"] = ready.astype(float)

        if params.side is SignalSide.LONG:
            raw = (close > range_high) & ready
            side_value = SignalSide.LONG.value
            signal_value = 1
        else:
            raw = (close < range_low) & ready
            side_value = SignalSide.SHORT.value
            signal_value = -1

        raw = raw.fillna(False).astype(bool)
        # Classic ORB: first break of the day only. Later tags are not new tests.
        day_key = _utc_day_key(candles.index)
        first = raw.groupby(day_key).cumsum().eq(1)
        entry = raw & first
        entry.iloc[: self.min_bars] = False

        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = self._score(close, range_high, range_low)[entry]
        signals["reason"] = self._reasons(entry, close, range_high, range_low)
        return signals

    def _score(
        self,
        close: pd.Series,
        range_high: pd.Series,
        range_low: pd.Series,
    ) -> pd.Series:
        """How far the close has extended through the opening range. Roughly [0, 1]."""
        width = (range_high - range_low).replace(0, pd.NA)
        if self.params.side is SignalSide.LONG:
            extension = ((close - range_high) / width).clip(0.0, 1.0)
        else:
            extension = ((range_low - close) / width).clip(0.0, 1.0)
        return extension.fillna(0.0)

    def _reasons(
        self,
        entry: pd.Series,
        close: pd.Series,
        range_high: pd.Series,
        range_low: pd.Series,
    ) -> pd.Series:
        reasons = pd.Series("", index=entry.index, dtype="object")
        if not entry.any():
            return reasons
        side_label = "LONG" if self.params.side is SignalSide.LONG else "SHORT"
        fired = entry[entry].index
        reasons.loc[fired] = [
            (
                f"{side_label}: close {close.loc[stamp]:.4f} vs UTC opening range "
                f"{range_high.loc[stamp]:.4f}/{range_low.loc[stamp]:.4f}"
            )
            for stamp in fired
        ]
        return reasons


def _utc_day_key(index: pd.Index) -> pd.Series:
    """UTC calendar date per bar, for the one-shot-per-day groupby."""
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("opening-range signals need a DatetimeIndex")
    if index.tz is None:
        utc_index = index.tz_localize("UTC")
    else:
        utc_index = index.tz_convert("UTC")
    return pd.Series(utc_index.normalize(), index=index)


__all__ = ["OpeningRangeParams", "OpeningRangeBreakoutStrategy"]
