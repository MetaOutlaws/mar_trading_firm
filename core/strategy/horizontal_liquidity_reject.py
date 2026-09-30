"""Fade a wick that pierces a flat multi-touch liquidity band and closes back inside.

One 4h family, both directions, SHORT priority. The band is horizontal: in the
prior ``lookback`` bars, at least ``min_touches`` highs (resistance) or lows
(support) sit inside a strip ``touch_tol_atr * ATR(20)`` wide, anchored on
that window's extreme.

- SHORT: ``>= min_touches`` prior highs in ``[max_high - tol, max_high]``,
  this bar's high pierces strictly above ``max_high``, and the close prints
  back inside that strip.
- LONG is the mirror on prior lows.
- A bar that qualifies for both fades is SHORT, not LONG.

The pierce bar is not a touch. Touches are bars ``t-lookback .. t-1`` only.
ATR is the prior bar's ATR(20), so this bar's wick cannot widen the strip.
The engine fills at ``t+1`` open; this module emits the signal on bar ``t``.

Garwe stamp. Free search (2 only): ``lookback`` in ``{24, 48}``,
``min_touches`` in ``{3, 4}``.

Locked: ``touch_tol_atr=0.2``, ``atr_n=20``, ``require_wick_pierce=True``,
``require_close_inside_band=True``, ``no_session_clock=True``,
``min_touches_hard_min=3``. A caller cannot drop the touch floor to 2, turn
the wick or close-inside gate off, or widen the strip. There is no session
box and no UTC clock.

Not ``equal_high_low_restest_fade`` (Job 110). That family is exactly two
extremes within an ATR tolerance and a fail-to-close-through. Two matching
highs or lows, even with a wick back inside, do not fire here. This family
needs three or four touches on the flat band, a wick that trades through the
band, and a close that returns inside the strip. A close that only finishes
somewhere below the high (or above the low) is not inside the band.

Not ``bullish_rectangle_fail_reclaim`` (dual swing rails, close-outside then
reclaim). Not ``head_and_shoulders_neckline_break``. Not
``prior_day_extreme_reject`` / ``prior_week_extreme_reject`` (calendar
extremes). Not ``session_liquidity_sweep`` (session box — do not recode).

Option B. SCORE/RETIRE only. This module does not write approvals, does not
add a book cell, and does not start a walk-forward. Live stays off.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Wilder ATR window. Not searched. Known before the signal bar via shift(1).
ATR_PERIOD = 20
# Strip width as a multiple of that ATR. Not searched.
TOUCH_TOL_ATR = 0.2
# Dual-equal restest is two touches. This family cannot go below three.
MIN_TOUCHES_HARD_MIN = 3
# Endpoints only. Do not insert interiors.
LOOKBACK_GRID = [24, 48]
MIN_TOUCHES_GRID = [3, 4]
# Locked gates. generate_signals always applies these; param overrides do not.
REQUIRE_WICK_PIERCE = True
REQUIRE_CLOSE_INSIDE_BAND = True
NO_SESSION_CLOCK = True
OPTION_B = True


def effective_min_touches(requested: int) -> int:
    """Touch floor actually used. Values below 3 are raised to 3.

    A walk or a caller passing ``min_touches=2`` would otherwise recreate
    ``equal_high_low_restest_fade``. The hard minimum blocks that.
    """
    try:
        value = int(requested)
    except (TypeError, ValueError):
        return MIN_TOUCHES_HARD_MIN
    if value < MIN_TOUCHES_HARD_MIN:
        return MIN_TOUCHES_HARD_MIN
    return value


def horizontal_liquidity_band(
    high: pd.Series,
    low: pd.Series,
    tol: pd.Series,
    *,
    lookback: int,
) -> pd.DataFrame:
    """Flat resistance and support strips over the prior ``lookback`` bars.

    Bar ``t`` reads highs and lows on ``[t-lookback, t-1]`` only. ``tol`` at
    ``t`` must already be causal (the sleeve passes ``0.2 * ATR(20).shift(1)``).

    Resistance is anchored on the window max. A touch is a prior high inside
    ``[max_high - tol, max_high]``. Support is anchored on the window min, with
    touches inside ``[min_low, min_low + tol]``. The strip is one-sided: a
    resistance count does not require a matching support rail.
    """
    if lookback < 1:
        raise ValueError(f"lookback must be >= 1, got {lookback}")
    if not high.index.equals(low.index) or not high.index.equals(tol.index):
        raise ValueError("high, low, and tol must share an index")

    highs = high.to_numpy(dtype="float64", copy=False)
    lows = low.to_numpy(dtype="float64", copy=False)
    slack = tol.to_numpy(dtype="float64", copy=False)
    n = len(highs)
    res_high = np.full(n, np.nan)
    res_low = np.full(n, np.nan)
    sup_low = np.full(n, np.nan)
    sup_high = np.full(n, np.nan)
    n_high_touches = np.full(n, np.nan)
    n_low_touches = np.full(n, np.nan)

    for t in range(lookback, n):
        width = slack[t]
        if not np.isfinite(width) or width < 0.0:
            continue
        window_high = highs[t - lookback : t]
        window_low = lows[t - lookback : t]
        if window_high.size == 0 or not np.isfinite(window_high).any():
            continue
        if not np.isfinite(window_low).any():
            continue
        top = float(np.nanmax(window_high))
        bottom = float(np.nanmin(window_low))
        if not np.isfinite(top) or not np.isfinite(bottom):
            continue
        res_floor = top - width
        sup_ceiling = bottom + width
        # Prior extremes only. Equality with the anchor counts as a touch.
        # A high above the anchor cannot occur inside this window.
        high_hits = np.isfinite(window_high) & (window_high >= res_floor) & (window_high <= top)
        low_hits = np.isfinite(window_low) & (window_low >= bottom) & (window_low <= sup_ceiling)
        res_high[t] = top
        res_low[t] = res_floor
        sup_low[t] = bottom
        sup_high[t] = sup_ceiling
        n_high_touches[t] = float(high_hits.sum())
        n_low_touches[t] = float(low_hits.sum())

    return pd.DataFrame(
        {
            "res_high": res_high,
            "res_low": res_low,
            "sup_low": sup_low,
            "sup_high": sup_high,
            "n_high_touches": n_high_touches,
            "n_low_touches": n_low_touches,
        },
        index=high.index,
    )


@dataclass(frozen=True)
class HorizontalLiquidityRejectParams(StrategyParams):
    # SHORT-priority family. A two-sided bar is a short, not a long.
    side: SignalSide = SignalSide.SHORT
    # Prior bars that must hold the flat band. Grid: [24, 48].
    lookback: int = 24
    # Touches required on that band. Grid: [3, 4]. Values below 3 act as 3.
    min_touches: int = 3
    # Locked at 0.2. generate_signals reads TOUCH_TOL_ATR, not this field.
    touch_tol_atr: float = TOUCH_TOL_ATR
    # Locked True. A False override does not drop the wick gate.
    require_wick_pierce: bool = REQUIRE_WICK_PIERCE
    # Locked True. A False override does not accept a close outside the strip.
    require_close_inside_band: bool = REQUIRE_CLOSE_INSIDE_BAND
    # Locked True. There is no hour filter to turn on.
    no_session_clock: bool = NO_SESSION_CLOCK
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class HorizontalLiquidityRejectStrategy(Strategy):
    name = "horizontal_liquidity_reject"

    def __init__(self, params: HorizontalLiquidityRejectParams | None = None) -> None:
        super().__init__(params or HorizontalLiquidityRejectParams())
        self.params: HorizontalLiquidityRejectParams = self.params
        lookback = max(int(self.params.lookback), 1)
        # ATR(20) seed, the shift that publishes it before bar t, and the
        # lookback of prior touches. The pierce bar itself is extra.
        self.min_bars = lookback + ATR_PERIOD + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        lookback = int(params.lookback)
        if lookback < 1 or len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        # Prior-bar ATR(20). Period and the 0.2 multiple are module locks.
        # touch_tol_atr on the params object is not read, so a widened
        # override cannot pull a third near-miss into a two-touch cluster.
        atr = ind.atr(high, low, close, ATR_PERIOD).shift(1)
        tol = atr * TOUCH_TOL_ATR
        band = horizontal_liquidity_band(high, low, tol, lookback=lookback)
        need = effective_min_touches(params.min_touches)

        # Wick must trade strictly through the anchor. A tag of the anchor
        # without a pierce is not a reject. Close must finish inside the
        # strip, not merely back on the inner side of the anchor.
        pierced_high = high > band["res_high"]
        pierced_low = low < band["sup_low"]
        close_in_resistance = (close >= band["res_low"]) & (close <= band["res_high"])
        close_in_support = (close >= band["sup_low"]) & (close <= band["sup_high"])
        enough_highs = band["n_high_touches"] >= need
        enough_lows = band["n_low_touches"] >= need
        short_raw = (
            enough_highs
            & band["res_high"].notna()
            & tol.notna()
            & pierced_high
            & close_in_resistance
        )
        long_raw = (
            enough_lows
            & band["sup_low"].notna()
            & tol.notna()
            & pierced_low
            & close_in_support
        )
        # SHORT priority. Both gates stay on. There is no hour filter to apply.
        if not (REQUIRE_WICK_PIERCE and REQUIRE_CLOSE_INSIDE_BAND and NO_SESSION_CLOCK):
            raise RuntimeError("horizontal liquidity reject locks were edited")
        long_raw = long_raw & ~short_raw.fillna(False)

        signals["res_high"] = band["res_high"]
        signals["res_low"] = band["res_low"]
        signals["sup_low"] = band["sup_low"]
        signals["sup_high"] = band["sup_high"]
        signals["n_high_touches"] = band["n_high_touches"]
        signals["n_low_touches"] = band["n_low_touches"]
        signals["atr"] = atr
        signals["touch_tol"] = tol

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            anchor = band["sup_low"]
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            anchor = band["res_high"]

        entry = raw.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        atr_unit = atr.where(atr > 0.0)
        if params.side is SignalSide.LONG:
            score = (band["sup_low"] - low) / atr_unit
        else:
            score = (high - band["res_high"]) / atr_unit
        # A zero ATR (a perfectly flat band) has no pierce unit. Score stays 0.
        score = pd.to_numeric(score, errors="coerce").clip(0.0, 1.0).fillna(0.0)
        signals.loc[entry, "score"] = score.loc[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: horizontal liquidity reject close {close.loc[i]:.4f} "
                    f"vs anchor {anchor.loc[i]:.4f} "
                    f"touches H {band['n_high_touches'].loc[i]:.0f} "
                    f"L {band['n_low_touches'].loc[i]:.0f} "
                    f"tol {tol.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "LOOKBACK_GRID",
    "MIN_TOUCHES_GRID",
    "MIN_TOUCHES_HARD_MIN",
    "NO_SESSION_CLOCK",
    "OPTION_B",
    "REQUIRE_CLOSE_INSIDE_BAND",
    "REQUIRE_WICK_PIERCE",
    "TOUCH_TOL_ATR",
    "HorizontalLiquidityRejectParams",
    "HorizontalLiquidityRejectStrategy",
    "effective_min_touches",
    "horizontal_liquidity_band",
]
