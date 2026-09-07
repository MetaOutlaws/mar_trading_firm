"""Fade a failed NR7 break that reverts back inside the NR7 bar's range.

NR7 is locked: the bar whose high-low range is the narrowest of the last 7
prints. ``nr7_setup`` publishes that bar's high/low on the following bar
(the canonical NR7-break bar). A break is a *close* through that box, not
a wick tag:

- SHORT: the setup bar closed above the NR7 high, then close_t is back
  below that same NR7 high (within ``max_bars_since_break``).
- LONG: the setup bar closed below the NR7 low, then close_t is back
  above that same NR7 low.

Quant-locked ``require_close_inside=True``: the fail close must still sit
inside the NR7 box. The only free param is ``max_bars_since_break``
(grid ``[1, 3]``). Lookback is not searched. No volume gate. OHLCV only.
Causal: bars ``<= t``. The engine fills at ``t+1`` open.

Not ``nr7_breakout`` (follows the breakout on the setup bar).
Not ``expansion_fail_fade`` (single ATR expansion bar — do not recode).
Not ``range_compression_volume_thrust`` (102 — successful thrust).
Not ``failed_range_break_reversion`` (119 — rolling N-bar Donchian).
Not ``orb_fail_reversion`` (121/122 — UTC-day ORB).
Not ``prior_day_extreme_reject`` (118) / ``asia_range_london_reject`` (120).
Not H&S / ``asia_close_inventory_fade`` / Wyckoff.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Classic NR7: narrowest range of the last 7 bars. Not a search param.
NR7_LOOKBACK = 7


@dataclass(frozen=True)
class Nr7FailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Bars after the NR7 close-through in which the fail must print. Quant grid: [1, 3].
    max_bars_since_break: int = 3
    # Quant-locked True: fade only if close_t sits back inside the NR7 box.
    require_close_inside: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class Nr7FailReversionStrategy(Strategy):
    name = "nr7_fail_reversion"

    def __init__(self, params: Nr7FailReversionParams | None = None) -> None:
        super().__init__(params or Nr7FailReversionParams())
        self.params: Nr7FailReversionParams = self.params
        max_bars = max(1, int(self.params.max_bars_since_break))
        # NR7 warmup plus the setup bar plus room to observe a later fail.
        self.min_bars = NR7_LOOKBACK + max_bars + 1

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

        # Locked NR7: published on the bar after the narrowest-of-7 print.
        nr_high, nr_low, setup = ind.nr7_setup(high, low, lookback=NR7_LOOKBACK)
        # Close-through of that one NR7 bar, not a rolling Donchian / ORB.
        # Held NR7 follow is nr7_breakout; we only fade a later fail.
        broke_up = setup & nr_high.notna() & (close > nr_high)
        broke_down = setup & nr_low.notna() & (close < nr_low)

        idx = pd.Series(range(len(candles)), index=candles.index, dtype="float64")
        up_lag = pd.Series(index=candles.index, dtype="float64")
        up_high = pd.Series(index=candles.index, dtype="float64")
        up_low = pd.Series(index=candles.index, dtype="float64")
        dn_lag = pd.Series(index=candles.index, dtype="float64")
        dn_high = pd.Series(index=candles.index, dtype="float64")
        dn_low = pd.Series(index=candles.index, dtype="float64")
        # Small max_bars (1..3). Nearest prior NR7 close-through wins.
        for lag in range(1, max_bars + 1):
            hit_up = broke_up.shift(lag).eq(True) & up_lag.isna()
            up_lag = up_lag.mask(hit_up, float(lag))
            up_high = up_high.mask(hit_up, nr_high.shift(lag))
            up_low = up_low.mask(hit_up, nr_low.shift(lag))
            hit_dn = broke_down.shift(lag).eq(True) & dn_lag.isna()
            dn_lag = dn_lag.mask(hit_dn, float(lag))
            dn_high = dn_high.mask(hit_dn, nr_high.shift(lag))
            dn_low = dn_low.mask(hit_dn, nr_low.shift(lag))

        # Back through the broken NR7 rail. Locked True: still inside the other rail.
        short_raw = up_high.notna() & (close < up_high)
        long_raw = dn_low.notna() & (close > dn_low)
        if close_inside:
            short_raw = short_raw & up_low.notna() & (close >= up_low)
            long_raw = long_raw & dn_high.notna() & (close <= dn_high)

        signals["nr7_high"] = nr_high
        signals["nr7_low"] = nr_low
        # Both rails of the NR7 box that broke, regardless of side.
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

        # One fade per failed NR7-break event, not every bar that stays inside.
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
                    f"{side_value}: NR7 fail-reversion close {close.loc[i]:.4f} "
                    f"vs broken {event_level.loc[i]:.4f} "
                    f"inside {other_level.loc[i]:.4f} "
                    f"after {int(event_lag.loc[i])} bar(s)"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "NR7_LOOKBACK",
    "Nr7FailReversionParams",
    "Nr7FailReversionStrategy",
]
