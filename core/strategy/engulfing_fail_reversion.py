"""Fade a failed engulfing continuation that closes back through the engulf open.

After a two-bar *body* engulf (``engulfing_direction``), the setup is that
bar — not a rolling N-bar channel and not a UTC-day ORB. A continuation
tries to leave the engulf extremes; this sleeve fades when that attempt
fails with a *close* back through the engulfing bar's open:

- SHORT: a bullish engulf, then a later bar trades through that engulf
  high, then close_t is back through the engulf *open* (within
  ``max_bars_since_engulf``).
- LONG: a bearish engulf, then a later bar trades through that engulf
  low, then close_t is back through the engulf *open*.

A wick that tags the open but does not close through it is not a fail.
Quant-locked ``require_close_inside=True``: the fail close must still sit
inside the engulf high/low. Body-efficiency is locked OFF (not searched,
not applied). The only free param is ``max_bars_since_engulf``
(grid ``[1, 2]``). No volume gate. OHLCV only. Causal: bars ``<= t``.
The engine fills at ``t+1`` open.

The clock starts at the engulf, not at the break:

- 1 bar after the engulf: wick-through of the continuation extreme on
  that bar, close back through the open (a held close-through does not
  fire).
- 2 bars after the engulf: a prior close-through of the extreme, then a
  later close through the open, or the same-bar close-through-open fail.

Not ``engulfing_reversal`` (fires ON the engulf bar, with the engulf).
Not ``failed_range_break_reversion`` (119 — rolling N-bar Donchian).
Not ``orb_fail_reversion`` (121 — UTC-day ORB).
Not ``nr7_fail_reversion`` (123 — narrowest-of-7).
Not ``ib_fail_reversion`` (124 — London inside-bar mother).
Not ``body_efficiency_follow`` (body/TR occupancy; locked off here).
Not ``asia_range_london_reject`` / ``prior_day_extreme_reject``.
Not ``converging_wedge_break`` (125 — both-rails wedge).
Not H&S / ``asia_close_inventory_fade`` / Wyckoff.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class EngulfingFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Bars after the engulfing print in which the fail must print. Quant grid: [1, 2].
    max_bars_since_engulf: int = 2
    # Quant-locked True: fade only if close_t still sits inside the engulf H/L.
    require_close_inside: bool = True
    # Quant-locked OFF. Not a free param. Do not gate on body / true-range.
    min_efficiency: float = 0.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class EngulfingFailReversionStrategy(Strategy):
    name = "engulfing_fail_reversion"

    def __init__(self, params: EngulfingFailReversionParams | None = None) -> None:
        super().__init__(params or EngulfingFailReversionParams())
        self.params: EngulfingFailReversionParams = self.params
        max_bars = max(1, int(self.params.max_bars_since_engulf))
        # Two-bar engulf plus room to observe a later fail.
        self.min_bars = max(8, 2 + max_bars)

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
        open_ = candles["open"]
        max_bars = max(1, int(params.max_bars_since_engulf))
        close_inside = bool(params.require_close_inside)
        # Locked off: min_efficiency stays 0 and is never a search key.

        # Body engulf on the setup bar. Fail rail is that bar's open.
        direction = ind.engulfing_direction(open_, close)
        bull_engulf = direction.eq(1)
        bear_engulf = direction.eq(-1)

        idx = pd.Series(range(len(candles)), index=candles.index, dtype="float64")
        bull_lag = pd.Series(index=candles.index, dtype="float64")
        bull_high = pd.Series(index=candles.index, dtype="float64")
        bull_low = pd.Series(index=candles.index, dtype="float64")
        bull_open = pd.Series(index=candles.index, dtype="float64")
        bear_lag = pd.Series(index=candles.index, dtype="float64")
        bear_high = pd.Series(index=candles.index, dtype="float64")
        bear_low = pd.Series(index=candles.index, dtype="float64")
        bear_open = pd.Series(index=candles.index, dtype="float64")
        # Small max_bars (1..2). Nearest prior engulf of that side wins.
        for lag in range(1, max_bars + 1):
            hit_bull = bull_engulf.shift(lag).eq(True) & bull_lag.isna()
            bull_lag = bull_lag.mask(hit_bull, float(lag))
            bull_high = bull_high.mask(hit_bull, high.shift(lag))
            bull_low = bull_low.mask(hit_bull, low.shift(lag))
            bull_open = bull_open.mask(hit_bull, open_.shift(lag))
            hit_bear = bear_engulf.shift(lag).eq(True) & bear_lag.isna()
            bear_lag = bear_lag.mask(hit_bear, float(lag))
            bear_high = bear_high.mask(hit_bear, high.shift(lag))
            bear_low = bear_low.mask(hit_bear, low.shift(lag))
            bear_open = bear_open.mask(hit_bear, open_.shift(lag))

        # Post-engulf window is the last `lag` bars (engulf itself is excluded).
        # Continuation break = trade through the extreme in that window.
        bull_win_high = pd.Series(index=candles.index, dtype="float64")
        bear_win_low = pd.Series(index=candles.index, dtype="float64")
        for lag in range(1, max_bars + 1):
            win_high = high.rolling(lag, min_periods=lag).max()
            win_low = low.rolling(lag, min_periods=lag).min()
            bull_win_high = bull_win_high.mask(bull_lag.eq(float(lag)), win_high)
            bear_win_low = bear_win_low.mask(bear_lag.eq(float(lag)), win_low)

        broke_up = bull_high.notna() & bull_win_high.gt(bull_high)
        broke_down = bear_low.notna() & bear_win_low.lt(bear_low)

        # Fail is a *close* back through the engulf open, not a wick tag.
        short_raw = broke_up & bull_open.notna() & (close < bull_open)
        long_raw = broke_down & bear_open.notna() & (close > bear_open)
        if close_inside:
            short_raw = short_raw & bull_low.notna() & (close >= bull_low)
            long_raw = long_raw & bear_high.notna() & (close <= bear_high)

        signals["engulfing"] = direction
        signals["engulf_high"] = bull_high.fillna(bear_high)
        signals["engulf_low"] = bull_low.fillna(bear_low)
        signals["engulf_open"] = bull_open.fillna(bear_open)
        signals["bars_since_engulf"] = bull_lag.fillna(bear_lag)

        if params.side is SignalSide.LONG:
            raw = long_raw.fillna(False)
            signal_value, side_value = 1, SignalSide.LONG.value
            event_lag, event_level, other_level = bear_lag, bear_open, bear_high
        else:
            raw = short_raw.fillna(False)
            signal_value, side_value = -1, SignalSide.SHORT.value
            event_lag, event_level, other_level = bull_lag, bull_open, bull_low

        # One fade per engulf event, not every bar that stays through the open.
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
                    f"{side_value}: engulf fail-reversion close {close.loc[i]:.4f} "
                    f"through open {event_level.loc[i]:.4f} "
                    f"inside {other_level.loc[i]:.4f} "
                    f"after {int(event_lag.loc[i])} bar(s) since engulf"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "EngulfingFailReversionParams",
    "EngulfingFailReversionStrategy",
]
