"""Fade a close back inside an N-bar range after a break that fails to hold.

Range high/low is the lookback window excluding the current bar (Donchian
prior-bar channel). A break is a *close* through that channel, not a wick
tag and not a UTC calendar-day extreme:

- SHORT: a prior bar closed above its range_high, then close_t is back
  below that same range_high, still inside the broken range
  (Quant-locked ``require_close_inside=True``).
- LONG: a prior bar closed below its range_low, then close_t is back
  above that same range_low, still inside the broken range.

The break must be within ``max_bars_since_break`` (default 3). Free params
are only ``lookback`` (grid ``[16, 20]``) and ``max_bars_since_break``
(grid ``[2, 3]``). No volume gate. OHLCV only. Causal: bars ``<= t``.
The engine fills at ``t+1`` open.

Not ``range_compression_volume_thrust`` (successful ATR-compress thrust).
Not ``expansion_fail_fade`` (single ATR expansion bar — do not recode).
Not ``nr7_breakout`` / a volume-dry NR7 fail.
Not ``opening_range_breakout`` / UTC-open fail.
Not ``ascending_triangle_break`` / H&S neckline confirmed breaks.
Not ``prior_day_extreme_reject`` (prior UTC day H/L).
Not ``donchian_breakout`` (follows a held channel break on the break bar).
Do not recode ``asia_close_inventory_fade``, ``wyckoff_spring_reclaim``,
or the Garwe buffer three.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class FailedRangeBreakReversionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Prior-bar Donchian window. Quant grid: [16, 20].
    lookback: int = 20
    # Bars after the close-through in which the fail must print. Quant grid: [2, 3].
    max_bars_since_break: int = 3
    # Quant-locked True: fade only if close_t sits back inside the broken range.
    require_close_inside: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class FailedRangeBreakReversionStrategy(Strategy):
    name = "failed_range_break_reversion"

    def __init__(self, params: FailedRangeBreakReversionParams | None = None) -> None:
        super().__init__(params or FailedRangeBreakReversionParams())
        self.params: FailedRangeBreakReversionParams = self.params
        lookback = max(1, int(self.params.lookback))
        max_bars = max(1, int(self.params.max_bars_since_break))
        # Channel warmup plus room to observe a later fail.
        self.min_bars = lookback + max_bars + 1

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
        lookback = max(1, int(params.lookback))
        max_bars = max(1, int(params.max_bars_since_break))
        close_inside = bool(params.require_close_inside)

        # Prior-bar N-window. Current bar cannot lift its own break level.
        range_high = high.shift(1).rolling(lookback, min_periods=lookback).max()
        range_low = low.shift(1).rolling(lookback, min_periods=lookback).min()
        # Close-through, not a wick tag. Held Donchian follow is the other family.
        broke_up = range_high.notna() & (close > range_high)
        broke_down = range_low.notna() & (close < range_low)

        idx = pd.Series(range(len(candles)), index=candles.index, dtype="float64")
        up_lag = pd.Series(index=candles.index, dtype="float64")
        up_high = pd.Series(index=candles.index, dtype="float64")
        up_low = pd.Series(index=candles.index, dtype="float64")
        dn_lag = pd.Series(index=candles.index, dtype="float64")
        dn_high = pd.Series(index=candles.index, dtype="float64")
        dn_low = pd.Series(index=candles.index, dtype="float64")
        # Small max_bars (2 or 3). Nearest prior close-through wins.
        for lag in range(1, max_bars + 1):
            hit_up = broke_up.shift(lag).eq(True) & up_lag.isna()
            up_lag = up_lag.mask(hit_up, float(lag))
            up_high = up_high.mask(hit_up, range_high.shift(lag))
            up_low = up_low.mask(hit_up, range_low.shift(lag))
            hit_dn = broke_down.shift(lag).eq(True) & dn_lag.isna()
            dn_lag = dn_lag.mask(hit_dn, float(lag))
            dn_high = dn_high.mask(hit_dn, range_high.shift(lag))
            dn_low = dn_low.mask(hit_dn, range_low.shift(lag))

        # Back through the broken rail. Locked True: still inside the other rail.
        short_raw = up_high.notna() & (close < up_high)
        long_raw = dn_low.notna() & (close > dn_low)
        if close_inside:
            short_raw = short_raw & up_low.notna() & (close >= up_low)
            long_raw = long_raw & dn_high.notna() & (close <= dn_high)

        signals["range_high"] = range_high
        signals["range_low"] = range_low
        signals["break_high"] = up_high
        signals["break_low"] = dn_low
        signals["bars_since_up_break"] = up_lag
        signals["bars_since_down_break"] = dn_lag

        if params.side is SignalSide.LONG:
            raw = long_raw.fillna(False)
            signal_value, side_value = 1, SignalSide.LONG.value
            event_lag, event_level, other_level = dn_lag, dn_low, dn_high
        else:
            raw = short_raw.fillna(False)
            signal_value, side_value = -1, SignalSide.SHORT.value
            event_lag, event_level, other_level = up_lag, up_high, up_low

        # One fade per failed-break event, not every bar that stays inside.
        orphan = -1.0 - idx
        event_id = (idx - event_lag).where(event_lag.notna(), orphan)
        entry = raw & raw.groupby(event_id).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (other_level - event_level).abs().replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - event_level) / width).clip(0.0, 1.0)
        else:
            score = ((event_level - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: failed range-break reversion close {close.loc[i]:.4f} "
                    f"vs broken {event_level.loc[i]:.4f} "
                    f"inside {other_level.loc[i]:.4f} "
                    f"after {int(event_lag.loc[i])} bar(s)"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "FailedRangeBreakReversionParams",
    "FailedRangeBreakReversionStrategy",
]
