"""Impulse midpoint fail fade — two-bar impulse, then fade through the mid.

Option B paper sleeve. Garwe STAMP LOCK. Implement exactly. Live stays
off. Do not set approved=true. Do not start a walk from this module.

Impulse is bar ``t-1``. The fail, and the signal, is bar ``t``. The
engine fills at ``t+1`` open.

    range[t-1] = high[t-1] - low[t-1]
    range[t-1] >= min_range_atr * ATR(20)
    close location = (close[t-1] - low[t-1]) / range[t-1]

Bullish impulse: close location sits in the top ``extreme_frac`` of
the impulse bar (``close_frac >= 1 - extreme_frac``).
Bearish impulse: close location sits in the bottom ``extreme_frac``
(``close_frac <= extreme_frac``).

The next bar must close *through* the impulse midpoint
``(high[t-1] + low[t-1]) / 2`` (strict; a print on the mid is not a
fail). Fade the impulse:

    SHORT: bullish impulse, then close[t] < midpoint
    LONG:  bearish impulse, then close[t] > midpoint

ATR is Wilder ATR(20) known *before* the impulse bar
(``atr.shift(2)`` at the signal bar) so the wide impulse cannot lift
its own size gate. Range is high-low, not true range. No volume gate.
No session clock. The fail close may sit inside the impulse bar or
beyond the opposite rail — only the midpoint cross is required.

BOTH sides are honest. SHORT is the priority edge: if both raw masks
are true, SHORT fires and LONG does not. On the locked grid
(``extreme_frac`` < 0.5) the two impulse locations do not overlap, and
the two through-mid sides are exclusive.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority)
    - Family id ``impulse_midpoint_fail_fade`` only
    - ATR period = 20, known before the impulse bar
    - Fill at t+1 open (engine convention)
    - require_next_close_through_mid = True
    - option_b = True (paper SCORE/RETIRE; not an approval)

Free search (2 only), endpoints, no invented interiors:

    - ``min_range_atr`` grid ``[1.5, 2.0]``
    - ``extreme_frac`` grid ``[0.25, 0.35]``

Not Job 151 ``thrust_bar_fail_reversion`` (same-bar close back inside
the prior bar's high-low after a thrust). This family is two bars:
the impulse prints, then the *next* close goes through the impulse
midpoint.
Not ``expansion_fail_fade`` (true-range expansion, weak volume, next
close back *inside* the expansion bar).
Not ``candle_reject_reversal`` (same-bar hammer / hanging-man).
Not ``key_reversal_bar`` (same-bar break of the prior extreme plus a
reverse body).
Not ``outside_bar_fail_reversion`` (both-rail outside containment,
then a next close that stays inside the outside bar).
Not ``three_push_exhaustion_fail``.
Not the killed YES pack (ny cash open drive, UTC midnight gap,
failed higher-high, prior-week high break, three-bar play), ORB,
or Wyckoff. Do not modify sibling geometry. 0 book cells.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. The impulse is sized against ATR known before it.
ATR_N_LOCKED = 20
# Quant-locked True: the next close must pass the impulse midpoint.
REQUIRE_NEXT_CLOSE_THROUGH_MID_LOCKED = True
# Paper sleeve. Not an approval flag and not a searched param.
OPTION_B_LOCKED = True
# Free-grid impulse range floor. Endpoints only.
MIN_RANGE_ATR_MIN = 1.5
MIN_RANGE_ATR_MAX = 2.0
MIN_RANGE_ATR_GRID = [1.5, 2.0]
# Free-grid close-location extreme. Endpoints only. Smaller is stricter.
EXTREME_FRAC_MIN = 0.25
EXTREME_FRAC_MAX = 0.35
EXTREME_FRAC_GRID = [0.25, 0.35]


@dataclass(frozen=True)
class ImpulseMidpointFailFadeParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Impulse high-low floor in ATR units. Quant grid: [1.5, 2.0].
    min_range_atr: float = MIN_RANGE_ATR_MIN
    # Close must sit in this fraction of the impulse bar, at the
    # directional extreme. Quant grid: [0.25, 0.35].
    extreme_frac: float = EXTREME_FRAC_MIN
    # Quant-locked True: fade only when the next close goes through mid.
    require_next_close_through_mid: bool = REQUIRE_NEXT_CLOSE_THROUGH_MID_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ImpulseMidpointFailFadeStrategy(Strategy):
    name = "impulse_midpoint_fail_fade"

    def __init__(self, params: ImpulseMidpointFailFadeParams | None = None) -> None:
        super().__init__(params or ImpulseMidpointFailFadeParams())
        self.params: ImpulseMidpointFailFadeParams = self.params
        # ATR seed through the bar before the impulse, plus the impulse
        # bar, plus the fail bar that closes through the midpoint.
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
        # Searched floors stay caller-set. Period and the through-mid
        # lock stay locked even if a caller passes another value.
        min_range = float(params.min_range_atr)
        extreme = float(params.extreme_frac)
        atr_n = ATR_N_LOCKED

        # Impulse is the prior bar. The signal bar is the fail.
        impulse_high = high.shift(1)
        impulse_low = low.shift(1)
        impulse_close = close.shift(1)
        impulse_range = impulse_high - impulse_low
        impulse_mid = (impulse_high + impulse_low) / 2.0
        range_positive = impulse_range.gt(0)
        range_safe = impulse_range.where(range_positive)
        # Same close-location fraction as other extreme_frac sleeves:
        # 0 at the low, 1 at the high. Direction is which extreme holds
        # the impulse close — not a body-color filter.
        close_frac = (impulse_close - impulse_low) / range_safe
        bullish_impulse_loc = range_positive & close_frac.ge(1.0 - extreme)
        bearish_impulse_loc = range_positive & close_frac.le(extreme)

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the impulse. At signal bar t this is the ATR
        # printed on t-2, so bar t-1 cannot lift the range gate.
        atr_known = atr20.shift(2)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.where(atr_ok)
        range_atr = impulse_range / atr_safe
        sized = atr_ok & impulse_range.ge(min_range * atr_known)

        # Locked through-mid. A close sitting on the midpoint has not
        # gone through, even if a caller passes the flag False.
        through_down = impulse_mid.notna() & close.lt(impulse_mid)
        through_up = impulse_mid.notna() & close.gt(impulse_mid)

        short_raw = sized & bullish_impulse_loc & through_down
        long_raw = sized & bearish_impulse_loc & through_up
        # SHORT priority on any bar that would otherwise print both.
        long_raw = long_raw & ~short_raw

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["impulse_high"] = impulse_high
        signals["impulse_low"] = impulse_low
        signals["impulse_close"] = impulse_close
        signals["impulse_range"] = impulse_range
        signals["impulse_mid"] = impulse_mid
        signals["impulse_close_frac"] = close_frac
        signals["range_atr"] = range_atr
        signals["sized"] = sized.fillna(False)
        signals["bullish_impulse"] = bullish_impulse_loc.fillna(False)
        signals["bearish_impulse"] = bearish_impulse_loc.fillna(False)
        signals["through_down"] = through_down.fillna(False)
        signals["through_up"] = through_up.fillna(False)

        if params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
        elif params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the fail close has traveled further past mid,
            # scaled by half the impulse range.
            half = (impulse_range / 2.0).where(range_positive)
            if params.side is SignalSide.SHORT:
                score = ((impulse_mid - close) / half).clip(0.0, 1.0)
            else:
                score = ((close - impulse_mid) / half).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: impulse-midpoint fail-fade "
                    f"close {close.loc[i]:.4f} "
                    f"{'<' if params.side is SignalSide.SHORT else '>'} "
                    f"mid {impulse_mid.loc[i]:.4f} of "
                    f"[{impulse_low.loc[i]:.4f}, {impulse_high.loc[i]:.4f}] "
                    f"after {'bullish' if params.side is SignalSide.SHORT else 'bearish'} "
                    f"impulse close {impulse_close.loc[i]:.4f} "
                    f"frac {close_frac.loc[i]:.2f} "
                    f"range {impulse_range.loc[i]:.4f}>={min_range:.2f}×ATR "
                    f"{atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "EXTREME_FRAC_GRID",
    "EXTREME_FRAC_MAX",
    "EXTREME_FRAC_MIN",
    "MIN_RANGE_ATR_GRID",
    "MIN_RANGE_ATR_MAX",
    "MIN_RANGE_ATR_MIN",
    "OPTION_B_LOCKED",
    "REQUIRE_NEXT_CLOSE_THROUGH_MID_LOCKED",
    "ImpulseMidpointFailFadeParams",
    "ImpulseMidpointFailFadeStrategy",
]
