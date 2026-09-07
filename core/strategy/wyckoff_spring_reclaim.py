"""Wyckoff spring / failed-breakdown reclaim (upthrust is the short mirror).

Identify a recent range low over ``lookback`` prior bars (Donchian min of
lows ending at t-1 — the current bar cannot set its own spring level).
A SPRING is a liquidity grab: price *trades* below that low, then *closes*
back above it within ``hold_bars``:

- ``hold_bars=1``: same-bar wick spring (low_t < range_low, close_t > range_low).
- ``hold_bars=2``: same-bar spring, or a grab that did not reclaim on the
  grab bar and then close_t back above that frozen level on the next bar.

LONG on the reclaim close (failed breakdown). SHORT is the upthrust:
trade above a prior-lookback range high, then close back below within
``hold_bars``.

This is not a close-through fade of a rolling channel
(``failed_range_break_reversion`` — 119 — requires a prior *close* through,
then a fail 2–3 bars later). A same-bar wick spring never prints a
close-through. OHLCV only. No volume gate. Causal: bars ``<= t``.
The engine fills at ``t+1`` open.

Free params (max 2): ``lookback`` grid ``[16, 20]`` and ``hold_bars``
grid ``[1, 2]``.

Not ``failed_range_break_reversion`` (119 — close-through then later fail).
Not ``prior_day_extreme_reject`` (118 — prior UTC day H/L).
Not ``asia_range_london_reject`` (120 — Asia box / London reject).
Not ``orb_fail_reversion`` / ``nr7_fail_reversion`` / ``ib_fail_reversion``.
Not ``converging_wedge_break`` / ``engulfing_fail_reversion``.
Not ``equal_high_low_restest_fade`` (two matched extremes).
Not ``swing_failure_reversal`` (confirmed N-bar pivots).
Not H&S / ``asia_close_inventory_fade`` / ``prior_close_magnet_fade``.
Do not recode the 118–126 spent families.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class WyckoffSpringReclaimParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Prior-bar range window. Quant grid: [16, 20].
    lookback: int = 20
    # Bars in the spring window, including the grab bar. Quant grid: [1, 2].
    hold_bars: int = 2
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class WyckoffSpringReclaimStrategy(Strategy):
    name = "wyckoff_spring_reclaim"

    def __init__(self, params: WyckoffSpringReclaimParams | None = None) -> None:
        super().__init__(params or WyckoffSpringReclaimParams())
        self.params: WyckoffSpringReclaimParams = self.params
        lookback = max(2, int(self.params.lookback))
        hold_bars = max(1, int(self.params.hold_bars))
        # Range warmup plus room for a same-bar or next-bar reclaim.
        self.min_bars = lookback + hold_bars + 1

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
        lookback = max(2, int(params.lookback))
        hold_bars = max(1, int(params.hold_bars))

        # Prior-bar range. Current wick cannot lift or lower its own level.
        swing_high = high.shift(1).rolling(lookback, min_periods=lookback).max()
        swing_low = low.shift(1).rolling(lookback, min_periods=lookback).min()
        # Grab = trade through the range extreme (wick / liquidity), not a close-through.
        grab_down = swing_low.notna() & (low < swing_low)
        grab_up = swing_high.notna() & (high > swing_high)

        long_lag = pd.Series(index=candles.index, dtype="float64")
        long_level = pd.Series(index=candles.index, dtype="float64")
        short_lag = pd.Series(index=candles.index, dtype="float64")
        short_level = pd.Series(index=candles.index, dtype="float64")

        # lag=0: same-bar wick spring / upthrust. Later lags reuse the grab's frozen level.
        for lag in range(0, hold_bars):
            if lag == 0:
                hit_long = grab_down & (close > swing_low)
                hit_short = grab_up & (close < swing_high)
                lvl_long = swing_low
                lvl_short = swing_high
            else:
                # Grab at t-lag that did not already reclaim on that bar.
                prior_down = grab_down.shift(lag).eq(True)
                prior_up = grab_up.shift(lag).eq(True)
                prior_low = swing_low.shift(lag)
                prior_high = swing_high.shift(lag)
                already_long = close.shift(lag) > swing_low.shift(lag)
                already_short = close.shift(lag) < swing_high.shift(lag)
                hit_long = (
                    prior_down
                    & ~already_long.fillna(False)
                    & prior_low.notna()
                    & (close > prior_low)
                )
                hit_short = (
                    prior_up
                    & ~already_short.fillna(False)
                    & prior_high.notna()
                    & (close < prior_high)
                )
                lvl_long = prior_low
                lvl_short = prior_high
            take_long = hit_long.fillna(False) & long_lag.isna()
            long_lag = long_lag.mask(take_long, float(lag))
            long_level = long_level.mask(take_long, lvl_long)
            take_short = hit_short.fillna(False) & short_lag.isna()
            short_lag = short_lag.mask(take_short, float(lag))
            short_level = short_level.mask(take_short, lvl_short)

        signals["swing_high"] = swing_high
        signals["swing_low"] = swing_low
        signals["spring_level"] = long_level.fillna(short_level)
        signals["bars_since_grab"] = long_lag.fillna(short_lag)

        if params.side is SignalSide.LONG:
            raw = long_lag.notna()
            signal_value, side_value = 1, SignalSide.LONG.value
            event_lag, event_level, other_level = long_lag, long_level, swing_high
        else:
            raw = short_lag.notna()
            signal_value, side_value = -1, SignalSide.SHORT.value
            event_lag, event_level, other_level = short_lag, short_level, swing_low

        # One reclaim per grab event, not every bar that stays through the level.
        idx = pd.Series(range(len(candles)), index=candles.index, dtype="float64")
        orphan = -1.0 - idx
        event_id = (idx - event_lag).where(event_lag.notna(), orphan)
        entry = raw.fillna(False) & raw.groupby(event_id).cumsum().eq(1)
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
                    f"{side_value}: wyckoff spring reclaim close {close.loc[i]:.4f} "
                    f"through {event_level.loc[i]:.4f} "
                    f"after {int(event_lag.loc[i])} bar(s) since grab"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "WyckoffSpringReclaimParams",
    "WyckoffSpringReclaimStrategy",
]
