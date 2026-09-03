"""Fade a same-bar fail of an open that started outside the prior bar's range.

If this bar opens above the prior bar's high and closes back inside that
prior high-low, SHORT toward the prior-bar mid. If it opens below the prior
low and closes back inside, LONG toward the mid.

Adjacent-bar open/fail, not a UTC session box. Works on whatever candle
clock is passed (4h prior bar on a 4h tape).

Not `utc_open_fail_reversion` (UTC day's first-4h box, fade on the second
4h / 04:00–08:00). Not `ny_cash_open_drive` (13:00–14:00 UTC cash-open body).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class OpenInPriorRangeFailParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class OpenInPriorRangeFailStrategy(Strategy):
    name = "open_in_prior_range_fail"

    def __init__(self, params: OpenInPriorRangeFailParams | None = None) -> None:
        super().__init__(params or OpenInPriorRangeFailParams())
        self.params: OpenInPriorRangeFailParams = self.params
        # Need one prior bar so open-vs-prior-range is defined.
        self.min_bars = 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        open_ = candles["open"]
        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        # Prior bar only. Not a UTC 00:00–04:00 aggregate and not a session VWAP.
        prior_high = high.shift(1)
        prior_low = low.shift(1)
        prior_mid = (prior_high + prior_low) / 2.0
        width = (prior_high - prior_low).replace(0, pd.NA)
        has_range = width.gt(0)

        opened_above = has_range & (open_ > prior_high)
        opened_below = has_range & (open_ < prior_low)
        closed_inside = (close <= prior_high) & (close >= prior_low)

        # Same-bar fail: gapped (or opened) outside, close back inside the prior box.
        long_raw = opened_below & closed_inside
        short_raw = opened_above & closed_inside

        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["prior_mid"] = prior_mid

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        if params.side is SignalSide.LONG:
            score = ((close - prior_low) / width).clip(0.0, 1.0)
        else:
            score = ((prior_high - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: open {open_.loc[i]:.4f} outside prior "
                    f"{prior_high.loc[i]:.4f}/{prior_low.loc[i]:.4f} "
                    f"close {close.loc[i]:.4f} mid {prior_mid.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["OpenInPriorRangeFailParams", "OpenInPriorRangeFailStrategy"]
