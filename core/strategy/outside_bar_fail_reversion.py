"""Outside-bar fail reversion — next bar closes back inside the outside bar.

Outside bar is ``t-1`` vs ``t-2`` (range containment, not a body engulf):

    high[t-1] > high[t-2] AND low[t-1] < low[t-2]

Size uses the outside bar's high-low (not true range) vs Wilder ATR(20)
known *before* the signal bar so bar ``t`` cannot lift its own threshold:

    (high[t-1] - low[t-1]) >= min_outside_atr * ATR20

The fail / reversion is bar ``t``: ``close[t]`` sits *strictly* inside
``(low[t-1], high[t-1])`` (Quant-locked ``require_close_inside_outside``).
Side is the fail close vs the outside-bar midpoint — not the outside
bar's own close vs mid, and not a Donchian / IB / NR7 rail:

- LONG:  close[t] > mid of the outside bar
- SHORT: close[t] < mid of the outside bar

A close on a rail or exactly on mid does not fire. The engine fills at
``t+1`` open.

Quant-locked (not searched):

    - ATR period = 20
    - Outside definition (range containment t-1 vs t-2)
    - require_close_inside_outside = True (strict inside)
    - mid-side split (LONG above mid / SHORT below mid)

Free search (1 only):

    - ``min_outside_atr`` grid ``[0.8, 1.2]``

OHLCV only. Causal: bars ``<= t``. No volume gate. No session / SMA /
Donchian / engulf-open overlay.

Not ``outside_bar_reversal`` (fires ON the outside bar with the close).
Not ``engulfing_fail_reversion`` (126 — two-bar body engulf, then fail
through the engulf *open*).
Not ``failed_range_break_reversion`` (119 — rolling N-bar Donchian
close-through).
Not ``failed_break_reclaim`` (130 — multi-bar wick probe then reclaim).
Not ``expansion_fail_fade`` (131 — ATR true-range expansion + weak-vol;
side from the *expansion* close vs mid).
Not ``candle_reject_reversal`` (hammer / hanging-man same-bar geometry).
Not ``ib_fail_reversion`` (124 — London inside-bar mother).
Not ``nr7_fail_reversion`` (123 — narrowest-of-7 close-through fail).
Not ``atr_open_flush_fade`` (138 — same-bar flush of *bar open*).
Not ``utc_day_open_flush_fade`` (139 — flush of UTC day-open).
Not ``three_white_soldiers`` (140) / ``three_black_crows`` (134).
Not ``sma20_stretch_fade`` (141 — SMA20 wick stretch then reclaim).
Not ``london_close_inventory_fade`` (100) / ``ny_close_inventory_fade``
(banned/parked).
Do not recode spent families 118–141. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches min_outside_atr only.
ATR_N_LOCKED = 20
# Quant-locked True: fail close must sit strictly inside the outside H/L.
REQUIRE_CLOSE_INSIDE_OUTSIDE_LOCKED = True


@dataclass(frozen=True)
class OutsideBarFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Outside-bar range floor in ATR units. Quant grid: [0.8, 1.2].
    min_outside_atr: float = 0.8
    # Quant-locked True: fade only if close_t is strictly inside the outside bar.
    require_close_inside_outside: bool = REQUIRE_CLOSE_INSIDE_OUTSIDE_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class OutsideBarFailReversionStrategy(Strategy):
    name = "outside_bar_fail_reversion"

    def __init__(self, params: OutsideBarFailReversionParams | None = None) -> None:
        super().__init__(params or OutsideBarFailReversionParams())
        self.params: OutsideBarFailReversionParams = self.params
        # ATR seed + prior bar + outside bar + the fail/reversion print.
        self.min_bars = ATR_N_LOCKED + 3

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
        # Searched size floor stays caller-set. Period / inside-lock stay locked.
        min_atr = float(params.min_outside_atr)
        atr_n = ATR_N_LOCKED

        # Outside is t-1 vs t-2. Same definition as indicators.outside_bar at t-1.
        out_high = high.shift(1)
        out_low = low.shift(1)
        prior_high = high.shift(2)
        prior_low = low.shift(2)
        is_outside = out_high.gt(prior_high) & out_low.lt(prior_low)
        out_range = out_high - out_low
        out_mid = (out_high + out_low) / 2.0

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)
        outside_atr = out_range / atr_safe
        sized = atr_ok & out_range.ge(min_atr * atr_known)

        # Locked strict inside. A rail tag is not a fail-reversion, even if
        # a caller passes require_close_inside_outside=False.
        close_inside = (
            out_high.notna() & out_low.notna() & close.gt(out_low) & close.lt(out_high)
        )
        close_above_mid = out_mid.notna() & close.gt(out_mid)
        close_below_mid = out_mid.notna() & close.lt(out_mid)

        long_raw = is_outside & sized & close_inside & close_above_mid
        short_raw = is_outside & sized & close_inside & close_below_mid

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["outside"] = is_outside.fillna(False)
        signals["outside_high"] = out_high
        signals["outside_low"] = out_low
        signals["outside_mid"] = out_mid
        signals["outside_range"] = out_range
        signals["outside_atr"] = outside_atr
        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["sized_enough"] = sized.fillna(False)
        signals["close_inside_outside"] = close_inside.fillna(False)
        signals["close_above_mid"] = close_above_mid.fillna(False)
        signals["close_below_mid"] = close_below_mid.fillna(False)

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        elif params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the fail close sits further past mid, still inside.
            half = (out_range / 2.0).replace(0, pd.NA)
            if params.side is SignalSide.LONG:
                score = ((close - out_mid) / half).clip(0.0, 1.0)
            else:
                score = ((out_mid - close) / half).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: outside-bar fail-reversion close {close.loc[i]:.4f} "
                    f"inside ({out_low.loc[i]:.4f}, {out_high.loc[i]:.4f}) "
                    f"mid {out_mid.loc[i]:.4f} "
                    f"range {out_range.loc[i]:.4f}>={min_atr:.2f}×ATR {atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "REQUIRE_CLOSE_INSIDE_OUTSIDE_LOCKED",
    "OutsideBarFailReversionParams",
    "OutsideBarFailReversionStrategy",
]
