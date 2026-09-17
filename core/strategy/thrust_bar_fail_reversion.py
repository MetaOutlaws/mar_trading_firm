"""Thrust-bar fail reversion — sized high/low break of prior, close back inside.

Family G. AUTHORITATIVE Munha/Garwe stamp (Brian YES live — lock exactly).
Same-bar geometry. Not a clone of family F ``inside_bar_break_fail``,
``outside_bar_fail_reversion``, ``expansion_fail_fade``,
``candle_reject_reversal``, or a dead VP cluster.

Prior range is bar ``t-1``. Thrust and fail live on bar ``t`` (same bar;
``max_bars_since_break`` is not a free param). Fill is engine ``t+1`` open.

Thrust (k = ``min_thrust_atr``) is range vs Wilder ATR(20) known *before*
the signal bar so bar ``t`` cannot lift the gate, AND a high/low break of
the immediate prior bar (a wick counts; close-through is not required):

    (high[t] - low[t]) >= min_thrust_atr * ATR20
    AND (high[t] > prior_high  XOR  low[t] < prior_low)

Exclusive one-sided: both rails is outside-bar territory, not this family.

Fail / reversion is close back inside the *prior* bar (Quant-locked
``require_close_inside``):

    SHORT: broke prior high only, then prior_low < close[t] < prior_high
    LONG:  broke prior low only,  then prior_low < close[t] < prior_high

A close on a rail has not come back inside. SHORT is the priority edge;
LONG is the honest mirror. No volume gate. No rolling Donchian lookback.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority documented, not a SHORT-only grid)
    - Family id ``thrust_bar_fail_reversion`` only
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - Prior = immediate previous bar (t-1), not a rolling N-bar channel
    - Break = high[t] > prior_high or low[t] < prior_low (wick counts)
    - Fail = same bar, close back inside the prior range
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
Not ``outside_bar_fail_reversion`` (both-rail containment t-1 vs t-2, then
next-bar close-inside the *outside* bar vs mid).
Not ``inside_bar_break_fail`` (family F — IB mother, then same-bar wick-fail
of the *mother*; size is mother range, not thrust range).
Not ``expansion_fail_fade`` (131 — ATR true-range expansion + weak-vol;
fail close-inside the *expansion* bar).
Not ``candle_reject_reversal`` (hammer / hanging-man wick fractions).
Not ``range_compression_volume_thrust`` (102 — FOLLOW a squeeze thrust).
Not ``atr_open_flush_fade`` (138 — same-bar flush of *bar open*).
Not ``utc_day_open_flush_fade`` (139).
Not ``engulfing_fail_reversion`` (126).
Not ``failed_break_reclaim`` (130).
Not VP cluster (``prior_poc_reclaim_fade`` / ``hvn_mean_revert`` /
``lvn_fill_reject`` / rolling VA / VWAP). Do not recode family F.
Do not recode spent families 118–150. Do not modify sibling geometry.
Hold H&S / asia / wyckoff families alone. No DOGE/DOT/NEAR/LDO universe adds.
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
        # ATR seed + prior bar + the same-bar thrust/fail print.
        self.min_bars = ATR_N_LOCKED + 2

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

        # Prior is the bar immediately before the thrust. Not Donchian. Not IB mother.
        prior_high = high.shift(1)
        prior_low = low.shift(1)
        # Thrust *is* the signal bar. Range and rails are published on t.
        thrust_high = high
        thrust_low = low
        thrust_close = close
        thrust_range = thrust_high - thrust_low

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the thrust/signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)
        thrust_atr = thrust_range / atr_safe
        sized = atr_ok & thrust_range.ge(min_atr * atr_known)

        # High/low break of the prior bar. A wick tag is a thrust break.
        broke_up = prior_high.notna() & thrust_high.gt(prior_high)
        broke_down = prior_low.notna() & thrust_low.lt(prior_low)
        # Exclusive one-sided — both rails is outside_bar_fail_reversion territory.
        one_sided_up = broke_up & ~broke_down
        one_sided_down = broke_down & ~broke_up

        # Locked inside-prior. A rail tag is not a fail, even if a caller
        # passes require_close_inside=False.
        close_inside_prior = (
            prior_high.notna()
            & prior_low.notna()
            & close.lt(prior_high)
            & close.gt(prior_low)
        )
        short_raw = sized & one_sided_up & close_inside_prior
        long_raw = sized & one_sided_down & close_inside_prior

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
                    f"after {'high' if signal_value < 0 else 'low'} break "
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
