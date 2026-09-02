"""0.618 bounce of a completed impulse from causal confirmed swings.

A completed up-impulse is a confirmed swing high whose last event sits after
a distinct confirmed swing low. The 0.618 tag is

    swing_high - ratio * (swing_high - swing_low)

not a Donchian channel, not a floor pivot, and not a round-number grid.
LONG waits for price to tag that level, close back above it, and leave the
origin low intact. SHORT is the mirror (last event is the swing low).

Search ratios are 0.500 / 0.618 / 0.786. An optional 0.15·ATR buffer
widens the tag and the origin. This family does not trade 1.272 / 1.618
extensions.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class FibRetracementBounceParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    pivot_left: int = 3
    # 0.500 / 0.618 / 0.786 retracement of the completed impulse.
    fib_ratio: float = 0.618
    atr_period: int = 14
    # 0 disables the buffer. 0.15 is 0.15 * ATR around the tag / origin.
    atr_buffer: float = 0.15
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class FibRetracementBounceStrategy(Strategy):
    name = "fib_retracement_bounce"

    def __init__(self, params: FibRetracementBounceParams | None = None) -> None:
        super().__init__(params or FibRetracementBounceParams())
        self.params: FibRetracementBounceParams = self.params
        left = int(self.params.pivot_left)
        self.min_bars = 2 * (2 * left + 1) + int(self.params.atr_period) + 5

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
        swing_high, swing_low = ind.confirmed_swings(
            high, low, left=int(params.pivot_left)
        )
        atr_value = ind.atr(high, low, close, int(params.atr_period))
        buffer = float(params.atr_buffer) * atr_value.fillna(0.0)

        # Last event = whichever confirmed swing last changed. A distinct
        # opposite swing must already exist so the impulse is complete.
        high_changed = swing_high.notna() & swing_high.ne(swing_high.shift(1))
        low_changed = swing_low.notna() & swing_low.ne(swing_low.shift(1))
        pos = pd.Series(range(len(candles)), index=candles.index, dtype="float64")
        high_at = pos.where(high_changed).ffill()
        low_at = pos.where(low_changed).ffill()
        last_is_high = high_at.notna() & low_at.notna() & (high_at > low_at)
        last_is_low = high_at.notna() & low_at.notna() & (low_at > high_at)

        impulse = swing_high - swing_low
        ratio = float(params.fib_ratio)
        # Retrace of the completed impulse, not an extension past the origin.
        long_level = swing_high - ratio * impulse
        short_level = swing_low + ratio * impulse

        # Origin intact: extrema since this swing published have not taken
        # out the opposite pivot (the impulse start).
        high_era = high_changed.astype("int64").cumsum()
        low_era = low_changed.astype("int64").cumsum()
        run_min = low.groupby(high_era).cummin()
        run_max = high.groupby(low_era).cummax()
        long_origin_ok = run_min > (swing_low - buffer)
        short_origin_ok = run_max < (swing_high + buffer)

        distinct = (
            swing_high.notna()
            & swing_low.notna()
            & (impulse > 0)
            & swing_high.ne(swing_low)
        )

        signals["swing_high"] = swing_high
        signals["swing_low"] = swing_low
        signals["fib_level"] = long_level if params.side is SignalSide.LONG else short_level
        signals["atr"] = atr_value
        signals["last_event"] = 0.0
        signals.loc[last_is_high, "last_event"] = 1.0
        signals.loc[last_is_low, "last_event"] = -1.0

        if params.side is SignalSide.LONG:
            tagged = (low <= long_level + buffer) & (high >= long_level - buffer)
            close_back = close > long_level
            entry = (
                last_is_high
                & distinct
                & tagged
                & close_back
                & long_origin_ok
            )
            signal_value, side_value = 1, SignalSide.LONG.value
            level = long_level
        else:
            tagged = (high >= short_level - buffer) & (low <= short_level + buffer)
            close_back = close < short_level
            entry = (
                last_is_low
                & distinct
                & tagged
                & close_back
                & short_origin_ok
            )
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = short_level

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: {ratio:.3f} bounce of "
                    f"{swing_high.loc[i]:.4f}/{swing_low.loc[i]:.4f} "
                    f"at {level.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["FibRetracementBounceParams", "FibRetracementBounceStrategy"]
