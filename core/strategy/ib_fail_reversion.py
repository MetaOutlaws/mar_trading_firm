"""Fade a failed London inside-bar break that reverts back inside the mother.

The mother is locked as the first London 4h bar of the UTC day (desk London
window 08:00–16:00 UTC; the open-labeled 08:00–12:00 print). Bar t-1 is an
inside bar when its range sits strictly inside that mother. A break is a
*close* through the mother high/low on the first bar after the inside print,
not a wick tag:

- SHORT: the setup bar closed above the mother high, then close_t is back
  below that same mother high (within ``max_bars_since_break``).
- LONG: the setup bar closed below the mother low, then close_t is back
  above that same mother low.

Quant-locked ``require_close_inside=True``: the fail close must still sit
inside the mother. The only free param is ``max_bars_since_break``
(grid ``[2, 4]``). London window and first-4h mother are not searched.
No volume gate. OHLCV only. Causal: bars ``<= t``. The engine fills at
``t+1`` open.

Mother+inside geometry only (``inside_bar_mother``). Not a rolling N-bar
channel, not NR7, not a UTC-day ORB, and not an Asia-box London tag.

Not ``nr7_fail_reversion`` (123 — narrowest-of-7).
Not ``failed_range_break_reversion`` (119 — rolling N-bar Donchian).
Not ``orb_fail_reversion`` (121 — UTC-day ORB).
Not ``asia_range_london_reject`` (120 — Asia H/L London tag).
Not ``prior_day_extreme_reject`` / ``prior_week_high_break``.
Not ``inside_bar_breakout`` (follows the breakout).
Not ``engulfing_reversal``.
Not H&S / ``asia_close_inventory_fade`` / Wyckoff.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Desk London window. First 4h bar is the open-labeled 08:00 print.
# Not searched — Quant lock. 07:00 is asia_range_london_reject only.
LONDON_START_HOUR = 8.0
LONDON_END_HOUR = 16.0
LONDON_FIRST_BAR_HOURS = 4.0


def _first_london_4h_bar(index: pd.Index) -> pd.Series:
    """True on the open-labeled first London 4h bar (08:00 UTC).

    Desk London is 08:00–16:00. On the 4h clock that first print is the
    08:00–12:00 bar. Hour is read from the index only, so this is causal.
    """
    utc_index = index
    if not isinstance(utc_index, pd.DatetimeIndex):
        raise ValueError("ib_fail_reversion needs a DatetimeIndex")
    if utc_index.tz is None:
        utc_index = utc_index.tz_localize("UTC")
    else:
        utc_index = utc_index.tz_convert("UTC")
    hours_into = (utc_index - utc_index.normalize()) / pd.Timedelta(hours=1)
    return pd.Series(hours_into == float(LONDON_START_HOUR), index=index)


@dataclass(frozen=True)
class IbFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Bars after the mother close-through in which the fail must print. Quant grid: [2, 4].
    max_bars_since_break: int = 4
    # Quant-locked True: fade only if close_t sits back inside the mother.
    require_close_inside: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class IbFailReversionStrategy(Strategy):
    name = "ib_fail_reversion"

    def __init__(self, params: IbFailReversionParams | None = None) -> None:
        super().__init__(params or IbFailReversionParams())
        self.params: IbFailReversionParams = self.params
        max_bars = max(1, int(self.params.max_bars_since_break))
        # Mother + inside + setup bar plus room to observe a later fail.
        self.min_bars = max(8, 3 + max_bars)

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
        max_bars = max(1, int(params.max_bars_since_break))
        close_inside = bool(params.require_close_inside)

        # Classic two-bar IB: t-1 sits inside t-2. Published on the break bar.
        mother_high, mother_low, inside = ind.inside_bar_mother(high, low)
        # Lock: the mother (t-2) must be the first London 4h bar.
        london_mother = _first_london_4h_bar(candles.index).shift(2).eq(True)
        setup = inside & london_mother & mother_high.notna() & mother_low.notna()
        # Close-through of that one mother, not a rolling Donchian / ORB / NR7.
        # Held IB follow is inside_bar_breakout; we only fade a later fail.
        broke_up = setup & (close > mother_high)
        broke_down = setup & (close < mother_low)

        idx = pd.Series(range(len(candles)), index=candles.index, dtype="float64")
        up_lag = pd.Series(index=candles.index, dtype="float64")
        up_high = pd.Series(index=candles.index, dtype="float64")
        up_low = pd.Series(index=candles.index, dtype="float64")
        dn_lag = pd.Series(index=candles.index, dtype="float64")
        dn_high = pd.Series(index=candles.index, dtype="float64")
        dn_low = pd.Series(index=candles.index, dtype="float64")
        # Small max_bars (2..4). Nearest prior London-IB close-through wins.
        for lag in range(1, max_bars + 1):
            hit_up = broke_up.shift(lag).eq(True) & up_lag.isna()
            up_lag = up_lag.mask(hit_up, float(lag))
            up_high = up_high.mask(hit_up, mother_high.shift(lag))
            up_low = up_low.mask(hit_up, mother_low.shift(lag))
            hit_dn = broke_down.shift(lag).eq(True) & dn_lag.isna()
            dn_lag = dn_lag.mask(hit_dn, float(lag))
            dn_high = dn_high.mask(hit_dn, mother_high.shift(lag))
            dn_low = dn_low.mask(hit_dn, mother_low.shift(lag))

        # Back through the broken mother rail. Locked True: still inside the other rail.
        short_raw = up_high.notna() & (close < up_high)
        long_raw = dn_low.notna() & (close > dn_low)
        if close_inside:
            short_raw = short_raw & up_low.notna() & (close >= up_low)
            long_raw = long_raw & dn_high.notna() & (close <= dn_high)

        signals["mother_high"] = mother_high
        signals["mother_low"] = mother_low
        signals["london_mother"] = london_mother.astype("float64")
        # Both rails of the mother that broke, regardless of side.
        signals["break_high"] = up_high.fillna(dn_high)
        signals["break_low"] = up_low.fillna(dn_low)
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

        # One fade per failed London-IB event, not every bar that stays inside.
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
                    f"{side_value}: IB fail-reversion close {close.loc[i]:.4f} "
                    f"vs broken {event_level.loc[i]:.4f} "
                    f"inside {other_level.loc[i]:.4f} "
                    f"after {int(event_lag.loc[i])} bar(s)"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "LONDON_START_HOUR",
    "LONDON_END_HOUR",
    "LONDON_FIRST_BAR_HOURS",
    "IbFailReversionParams",
    "IbFailReversionStrategy",
]
