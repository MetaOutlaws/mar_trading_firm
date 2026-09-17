"""Thrust-bar fail reversion — next bar reverts through the thrust mid.

Family G. Garwe/Munha stamp. Thrust bar is ``t-1`` (not a same-bar open
flush). Size uses the thrust high-low (not true range) vs Wilder ATR(20)
known *before* the signal bar so bar ``t`` cannot lift the size gate:

    (high[t-1] - low[t-1]) >= min_thrust_atr * ATR20

A thrust is directional (body + close vs mid), not a wide doji and not
outside-bar containment vs ``t-2``:

    UP:   close[t-1] > open[t-1] AND close[t-1] > mid[t-1]
    DOWN: close[t-1] < open[t-1] AND close[t-1] < mid[t-1]

The fail / reversion is bar ``t``: ``close[t]`` sits *strictly* inside
``(low[t-1], high[t-1])`` and has crossed back through that mid
(Quant-locked ``require_close_inside_thrust``). Side is the failed
thrust direction — SHORT is the priority edge:

- SHORT: UP thrust, then close[t] < mid
- LONG:  DOWN thrust, then close[t] > mid

A close on a rail or exactly on mid does not fire. No volume gate. No
ATR-compression overlay. The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority documented, not a SHORT-only grid)
    - Family id ``thrust_bar_fail_reversion`` only
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - Thrust = directional H-L bar at t-1 (close vs open AND close vs mid)
    - require_close_inside_thrust = True (strict inside)
    - Fail close must cross back through the thrust mid
    - Fill at t+1 open (engine convention)

Free search (1 only):

    - ``min_thrust_atr`` grid ``[1.0, 1.5]``
      (endpoints only — same sibling float-grid convention as
      ``outside_bar_fail_reversion.min_outside_atr`` /
      ``inside_bar_break_fail.min_mother_atr``)

OHLCV only. Causal: bars ``<= t``. No volume gate. No squeeze /
Donchian / engulf-open / London session overlay.

Not ``expansion_fail_fade`` (131 — ATR *true-range* expansion + weak-vol;
inclusive close-inside; side from expansion close vs mid, fail need not
cross mid).
Not ``range_compression_volume_thrust`` (102 — FOLLOW a squeeze then
volume thrust).
Not ``atr_open_flush_fade`` (138 — same-bar flush of *bar open*).
Not ``utc_day_open_flush_fade`` (139 — flush of UTC day-open).
Not ``outside_bar_fail_reversion`` (outside containment t-1 vs t-2, then
close-inside vs mid).
Not ``outside_bar_reversal`` (fires ON the outside bar with the close).
Not ``engulfing_fail_reversion`` (126 — two-bar body engulf, then fail
through the engulf *open*).
Not ``failed_range_break_reversion`` (119 — rolling N-bar Donchian).
Not ``failed_break_reclaim`` (130 — multi-bar wick probe).
Not ``ib_fail_reversion`` / ``inside_bar_break_fail`` / ``nr7_fail_reversion``.
Not ``candle_reject_reversal`` / ``body_efficiency_follow``.
Not ``lvn_fill_reject`` (family E). Do not recode family F
``inside_bar_break_fail``.
Do not recode spent families 118–150. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches min_thrust_atr only.
ATR_N_LOCKED = 20
# Quant-locked True: fail close must sit strictly inside the thrust H/L.
REQUIRE_CLOSE_INSIDE_THRUST_LOCKED = True
# Free-grid thrust-range floor. Endpoints only, matching sibling float grids.
MIN_THRUST_ATR_MIN = 1.0
MIN_THRUST_ATR_MAX = 1.5
MIN_THRUST_ATR_GRID = [1.0, 1.5]


@dataclass(frozen=True)
class ThrustBarFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Thrust-range floor in ATR units. Quant grid: [1.0, 1.5].
    min_thrust_atr: float = MIN_THRUST_ATR_MIN
    # Quant-locked True: fade only if close_t is strictly inside the thrust bar.
    require_close_inside_thrust: bool = REQUIRE_CLOSE_INSIDE_THRUST_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ThrustBarFailReversionStrategy(Strategy):
    name = "thrust_bar_fail_reversion"

    def __init__(self, params: ThrustBarFailReversionParams | None = None) -> None:
        super().__init__(params or ThrustBarFailReversionParams())
        self.params: ThrustBarFailReversionParams = self.params
        # ATR seed + prior close for TR context + thrust bar + the fail print.
        self.min_bars = ATR_N_LOCKED + 3

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
        # Searched size floor stays caller-set. Period / inside-lock stay locked.
        min_atr = float(params.min_thrust_atr)
        atr_n = ATR_N_LOCKED

        # Thrust is t-1. H-L range, not true range (that is expansion_fail_fade).
        thrust_high = high.shift(1)
        thrust_low = low.shift(1)
        thrust_open = open_.shift(1)
        thrust_close = close.shift(1)
        thrust_range = thrust_high - thrust_low
        thrust_mid = (thrust_high + thrust_low) / 2.0

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)
        thrust_atr = thrust_range / atr_safe
        sized = atr_ok & thrust_range.ge(min_atr * atr_known)

        # Directional thrust: body in the thrust direction AND close vs mid.
        # A wide doji / close-on-mid print is not a thrust.
        up_thrust = (
            thrust_open.notna()
            & thrust_close.notna()
            & thrust_mid.notna()
            & thrust_close.gt(thrust_open)
            & thrust_close.gt(thrust_mid)
        )
        down_thrust = (
            thrust_open.notna()
            & thrust_close.notna()
            & thrust_mid.notna()
            & thrust_close.lt(thrust_open)
            & thrust_close.lt(thrust_mid)
        )

        # Locked strict inside. A rail tag is not a fail-reversion, even if
        # a caller passes require_close_inside_thrust=False.
        close_inside = (
            thrust_high.notna()
            & thrust_low.notna()
            & close.gt(thrust_low)
            & close.lt(thrust_high)
        )
        # Reversion through mid: fail close must actually reverse the thrust.
        reverted_down = thrust_mid.notna() & close.lt(thrust_mid)
        reverted_up = thrust_mid.notna() & close.gt(thrust_mid)

        short_raw = sized & up_thrust & close_inside & reverted_down
        long_raw = sized & down_thrust & close_inside & reverted_up

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["thrust_high"] = thrust_high
        signals["thrust_low"] = thrust_low
        signals["thrust_open"] = thrust_open
        signals["thrust_close"] = thrust_close
        signals["thrust_mid"] = thrust_mid
        signals["thrust_range"] = thrust_range
        signals["thrust_atr"] = thrust_atr
        signals["sized_enough"] = sized.fillna(False)
        signals["up_thrust"] = up_thrust.fillna(False)
        signals["down_thrust"] = down_thrust.fillna(False)
        signals["close_inside_thrust"] = close_inside.fillna(False)
        signals["reverted_down"] = reverted_down.fillna(False)
        signals["reverted_up"] = reverted_up.fillna(False)

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
            half = (thrust_range / 2.0).replace(0, pd.NA)
            if params.side is SignalSide.LONG:
                score = ((close - thrust_mid) / half).clip(0.0, 1.0)
            else:
                score = ((thrust_mid - close) / half).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: thrust-bar fail-reversion close {close.loc[i]:.4f} "
                    f"inside ({thrust_low.loc[i]:.4f}, {thrust_high.loc[i]:.4f}) "
                    f"mid {thrust_mid.loc[i]:.4f} "
                    f"range {thrust_range.loc[i]:.4f}>={min_atr:.2f}×ATR "
                    f"{atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "MIN_THRUST_ATR_GRID",
    "MIN_THRUST_ATR_MAX",
    "MIN_THRUST_ATR_MIN",
    "REQUIRE_CLOSE_INSIDE_THRUST_LOCKED",
    "ThrustBarFailReversionParams",
    "ThrustBarFailReversionStrategy",
]
