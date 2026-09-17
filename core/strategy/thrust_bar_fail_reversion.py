"""Thrust-bar fail reversion — close back inside prior after a thrust break.

Family G. Munha stamp (Brian YES already live). Sibling fail-reversion
geometry: a *thrust break* of the immediate prior bar, then the next bar
fails and closes back *inside that prior range*. Not a close-inside of
the thrust bar itself, and not a mid-cross of the thrust.

Prior range is bar ``t-2``. Thrust / break is bar ``t-1``. Fail is bar
``t`` (next bar only; ``max_bars_since_break`` is not a free param).

Thrust size uses the break bar's high-low (not true range) vs Wilder
ATR(20) known *before* the signal bar so bar ``t`` cannot lift the gate:

    (high[t-1] - low[t-1]) >= min_thrust_atr * ATR20

Break is a *close-through* of the prior bar (sibling convention — not a
wick tag):

    UP:   close[t-1] > high[t-2]
    DOWN: close[t-1] < low[t-2]

Fail / reversion is close back inside the *prior* range (Quant-locked
``require_close_inside``), same rail rules as NR7 / IB / ORB /
failed-range fail-reversion:

    SHORT: UP break, then close[t] < prior_high AND close[t] >= prior_low
    LONG:  DOWN break, then close[t] > prior_low AND close[t] <= prior_high

A close on the broken rail has not come back through. SHORT is the
priority edge; LONG is the honest mirror. No volume gate. No rolling
Donchian lookback. The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority documented, not a SHORT-only grid)
    - Family id ``thrust_bar_fail_reversion`` only
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - Prior = immediate previous bar (t-2), not a rolling N-bar channel
    - Break = close-through of that prior (not a wick)
    - Fail = next bar only, close back inside the prior range
    - require_close_inside = True
    - Fill at t+1 open (engine convention)

Free search (1 only):

    - ``min_thrust_atr`` grid ``[1.0, 1.5]``
      (endpoints only — same sibling float-grid convention as
      ``outside_bar_fail_reversion.min_outside_atr`` /
      ``inside_bar_break_fail.min_mother_atr``)

OHLCV only. Causal: bars ``<= t``. No volume gate. No squeeze /
Donchian lookback / engulf-open / London session overlay.

Not ``failed_range_break_reversion`` (119 — rolling N-bar Donchian
close-through, searched lookback + max_bars_since_break).
Not ``nr7_fail_reversion`` (123 — narrowest-of-7 box).
Not ``ib_fail_reversion`` (124 — London IB mother, later fail).
Not ``orb_fail_reversion`` (121 — UTC-day ORB).
Not ``outside_bar_fail_reversion`` (outside containment t-1 vs t-2, then
close-inside the *outside* bar vs mid).
Not ``inside_bar_break_fail`` (family F — same-bar wick-fail of an IB mother).
Not ``expansion_fail_fade`` (131 — ATR true-range expansion + weak-vol;
fail close-inside the *expansion* bar).
Not ``range_compression_volume_thrust`` (102 — FOLLOW a squeeze thrust).
Not ``atr_open_flush_fade`` (138 — same-bar flush of *bar open*).
Not ``utc_day_open_flush_fade`` (139).
Not ``engulfing_fail_reversion`` (126).
Not ``failed_break_reclaim`` (130).
Not ``lvn_fill_reject`` (family E). Do not recode family F.
Do not recode spent families 118–150. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches min_thrust_atr only.
ATR_N_LOCKED = 20
# Quant-locked True: fail close must sit back inside the *prior* range.
REQUIRE_CLOSE_INSIDE_LOCKED = True
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
    # Quant-locked True: fade only if close_t sits back inside the prior bar.
    require_close_inside: bool = REQUIRE_CLOSE_INSIDE_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ThrustBarFailReversionStrategy(Strategy):
    name = "thrust_bar_fail_reversion"

    def __init__(self, params: ThrustBarFailReversionParams | None = None) -> None:
        super().__init__(params or ThrustBarFailReversionParams())
        self.params: ThrustBarFailReversionParams = self.params
        # ATR seed + prior bar + thrust/break bar + the fail/reversion print.
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
        min_atr = float(params.min_thrust_atr)
        atr_n = ATR_N_LOCKED

        # Prior range is the bar immediately before the thrust. Not Donchian.
        prior_high = high.shift(2)
        prior_low = low.shift(2)
        thrust_high = high.shift(1)
        thrust_low = low.shift(1)
        thrust_close = close.shift(1)
        thrust_range = thrust_high - thrust_low

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)
        thrust_atr = thrust_range / atr_safe
        sized = atr_ok & thrust_range.ge(min_atr * atr_known)

        # Close-through of the prior bar. A wick tag is not a thrust break.
        broke_up = (
            prior_high.notna() & thrust_close.notna() & thrust_close.gt(prior_high)
        )
        broke_down = (
            prior_low.notna() & thrust_close.notna() & thrust_close.lt(prior_low)
        )

        # Locked inside-prior. A rail tag of the broken rail is not a fail,
        # even if a caller passes require_close_inside=False. Other rail is
        # inclusive, matching NR7 / IB / ORB / failed-range fail-reversion.
        close_inside_prior = (
            prior_high.notna()
            & prior_low.notna()
            & close.lt(prior_high)
            & close.gt(prior_low)
        )
        # Back through the broken rail, still inside the other rail.
        short_raw = (
            sized
            & broke_up
            & close.lt(prior_high)
            & close.ge(prior_low)
            & close_inside_prior
        )
        long_raw = (
            sized
            & broke_down
            & close.gt(prior_low)
            & close.le(prior_high)
            & close_inside_prior
        )

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["thrust_high"] = thrust_high
        signals["thrust_low"] = thrust_low
        signals["thrust_close"] = thrust_close
        signals["thrust_range"] = thrust_range
        signals["thrust_atr"] = thrust_atr
        signals["sized_enough"] = sized.fillna(False)
        signals["broke_up"] = broke_up.fillna(False)
        signals["broke_down"] = broke_down.fillna(False)
        signals["close_inside_prior"] = close_inside_prior.fillna(False)

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
            # Stronger when the fail close sits further past the broken rail.
            width = (prior_high - prior_low).replace(0, pd.NA)
            if params.side is SignalSide.LONG:
                score = ((close - prior_low) / width).clip(0.0, 1.0)
            else:
                score = ((prior_high - close) / width).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: thrust-bar fail-reversion close {close.loc[i]:.4f} "
                    f"inside prior ({prior_low.loc[i]:.4f}, {prior_high.loc[i]:.4f}) "
                    f"after thrust close {thrust_close.loc[i]:.4f} "
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
    "REQUIRE_CLOSE_INSIDE_LOCKED",
    "ThrustBarFailReversionParams",
    "ThrustBarFailReversionStrategy",
]
