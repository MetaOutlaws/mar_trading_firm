"""Fade a failed UTC-day opening-range break that reverts back inside the ORB.

The opening range is the high/low of the first ``orb_bars`` *4h* bars of the
UTC day (Quant grid ``[1, 2]``). ``utc_opening_range`` publishes it only after
that window closes. A break is a *close* through that box, not a wick tag:

- SHORT: a prior same-day bar closed above ORB high, then close_t is back
  below that ORB high (within ``max_bars_since_break``).
- LONG: a prior same-day bar closed below ORB low, then close_t is back
  above that ORB low.

Quant-locked ``require_close_inside=True``: the fail close must still sit
inside the ORB. Free params are only ``orb_bars`` (grid ``[1, 2]``) and
``max_bars_since_break`` (grid ``[2, 4]``). No volume gate. OHLCV only.
Causal: bars ``<= t``. The engine fills at ``t+1`` open.

Not ``opening_range_breakout`` (follows the breakout; finished leftover).
Not ``utc_open_fail_reversion`` (same-bar wick fail of the first-4h box on
the second 4h only).
Not ``failed_range_break_reversion`` (rolling N-bar Donchian).
Not ``prior_day_extreme_reject`` (prior UTC calendar day H/L).
Not ``asia_range_london_reject`` (Asia 00:00–08:00 box / London wick reject).
Not ``nr7_fail_reversion`` (stays buffer) / ``nr7_breakout``.
Not ``range_compression_volume_thrust``.
Not H&S / ``asia_close_inventory_fade`` / Wyckoff.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Each orb_bar is one 4h UTC-day slot, independent of native tape width.
ORB_BAR_HOURS = 4.0


@dataclass(frozen=True)
class OrbFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # First N 4h bars of the UTC day. Quant grid: [1, 2].
    orb_bars: int = 1
    # Bars after the close-through in which the fail must print. Quant grid: [2, 4].
    max_bars_since_break: int = 4
    # Quant-locked True: fade only if close_t sits back inside the ORB.
    require_close_inside: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class OrbFailReversionStrategy(Strategy):
    name = "orb_fail_reversion"

    def __init__(self, params: OrbFailReversionParams | None = None) -> None:
        super().__init__(params or OrbFailReversionParams())
        self.params: OrbFailReversionParams = self.params
        orb_bars = max(1, int(self.params.orb_bars))
        max_bars = max(1, int(self.params.max_bars_since_break))
        # One completed UTC day of 4h bars plus room to observe a later fail.
        self.min_bars = max(8, orb_bars + max_bars + 1)

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
        orb_bars = max(1, int(params.orb_bars))
        max_bars = max(1, int(params.max_bars_since_break))
        close_inside = bool(params.require_close_inside)
        # First orb_bars 4h slots of the UTC day. Blank until the window closes.
        range_hours = float(orb_bars) * ORB_BAR_HOURS
        range_high, range_low, ready = ind.utc_opening_range(
            high, low, range_hours=range_hours
        )

        # Close-through of the published ORB. Held Donchian / ORB follow is
        # the other family. Same-bar wick-and-close-inside is utc_open_fail.
        broke_up = ready & range_high.notna() & (close > range_high)
        broke_down = ready & range_low.notna() & (close < range_low)

        day_key = ind.utc_day_key(candles.index)
        # Clock starts at the *first* same-day close-through, not the nearest
        # bar still outside. The ORB is fixed, so every stay-through bar is
        # also a close-through; nearest-break would make max_bars a no-op.
        idx = pd.Series(range(len(candles)), index=candles.index, dtype="float64")
        first_up = idx.where(broke_up).groupby(day_key).transform("min")
        first_dn = idx.where(broke_down).groupby(day_key).transform("min")
        up_lag = (idx - first_up).where(first_up.notna())
        dn_lag = (idx - first_dn).where(first_dn.notna())
        up_ok = up_lag.ge(1.0) & up_lag.le(float(max_bars))
        dn_ok = dn_lag.ge(1.0) & dn_lag.le(float(max_bars))

        # Back through the broken rail. Locked True: still inside the other rail.
        short_raw = up_ok & range_high.notna() & (close < range_high)
        long_raw = dn_ok & range_low.notna() & (close > range_low)
        if close_inside:
            short_raw = short_raw & range_low.notna() & (close >= range_low)
            long_raw = long_raw & range_high.notna() & (close <= range_high)

        signals["range_high"] = range_high
        signals["range_low"] = range_low
        signals["range_ready"] = ready.astype(float)
        signals["bars_since_up_break"] = up_lag
        signals["bars_since_down_break"] = dn_lag

        if params.side is SignalSide.LONG:
            raw = long_raw.fillna(False)
            signal_value, side_value = 1, SignalSide.LONG.value
            event_lag = dn_lag
        else:
            raw = short_raw.fillna(False)
            signal_value, side_value = -1, SignalSide.SHORT.value
            event_lag = up_lag

        # One fade per UTC day. Daily ORB, not a rolling Donchian event stream.
        entry = raw & raw.groupby(day_key).cumsum().eq(1)
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
                    f"{side_value}: ORB fail-reversion close {close.loc[i]:.4f} "
                    f"vs {range_high.loc[i]:.4f}/{range_low.loc[i]:.4f} "
                    f"after {int(event_lag.loc[i])} bar(s)"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ORB_BAR_HOURS",
    "OrbFailReversionParams",
    "OrbFailReversionStrategy",
]
