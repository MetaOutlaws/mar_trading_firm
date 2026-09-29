"""Break an expanding megaphone (broadening formation).

One pattern, both directions. Swing highs print higher highs on a rising
upper rail (slope > 0) and swing lows print lower lows on a falling lower
rail (slope < 0). LONG when ``close_t`` breaks above the upper rail. SHORT
when ``close_t`` breaks below the lower rail. A wick through the rail
without the close does not fire.

The expanding-rail fit lives in this module. It does not call the
converging-wedge rail fitter or the ascending-triangle swing structure.
Rails are this file's own OLS through the last ``min_touches`` 3/3 swing
highs and swing lows in ``lookback``. Each of those swings must sit within
one ATR(20) of its rail. That ATR is the touch tolerance only: it is not a
break-size filter, not a free parameter, and not a volume-profile input.

Garwe stamp. Free params (walk grid, not started from this coding change):
``lookback`` in ``{32, 48}``, ``min_touches`` in ``{3, 4}``.

Locked: expanding rails (upper slope > 0, lower slope < 0), break on the
close, ATR(20) for touch tolerance only, swing pivots 3/3 (three bars each
side), fill at ``t+1`` open (the engine fills the next bar; this file emits
the signal on bar ``t``), no volume gate, no session gate, no volume profile.

Not ``converging_wedge_break`` (Job 125 — both rails slope the same way and
converge; do not recode it). Not ``ascending_triangle_break`` (flat cap).
Not ``failed_range_break_reversion`` / ``double_top_neckline_break``. Not
``round_number_fade`` / ``consecutive_bar_exhaustion`` / ``mass_index_reversal``.
Not head-and-shoulders (coded separately).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Garwe stamp: swing detection is a 3/3 pivot (three bars left, three bars
# right). Not searched. The window is symmetric, so one width of 3 is 3/3.
# Owned by this module. Not the wedge rail helper and not the triangle structure.
PIVOT_LEFT = 3
PIVOT_RIGHT = 3
# Locked ATR window. Used only as the distance a swing may sit off its rail.
ATR_PERIOD = 20
# One ATR(20). Not searched — the break itself is a raw close through the rail.
TOUCH_TOL_ATR = 1.0
# Searched grids. Endpoints only; do not insert interiors.
LOOKBACK_GRID = [32, 48]
MIN_TOUCHES_GRID = [3, 4]


def publish_broadening_swings(
    high: pd.Series, low: pd.Series
) -> tuple[pd.Series, pd.Series]:
    """3/3 swing high and swing low, published only after the window has closed.

    The candidate is three bars back. It is a swing when it is the extreme of
    ``[t-6, t]`` (three bars each side). Publication is one bar later, so bar
    ``t`` never reads a future print. This detector belongs to the megaphone
    sleeve. It is not a call into the wedge rails or the triangle structure.
    """
    if not high.index.equals(low.index):
        raise ValueError("high and low must share an index")
    if PIVOT_LEFT != 3 or PIVOT_RIGHT != 3 or PIVOT_LEFT != PIVOT_RIGHT:
        raise ValueError("Garwe lock: broadening swings are pivot 3/3")
    left = PIVOT_LEFT
    window = 2 * left + 1
    roll_high = high.rolling(window=window, min_periods=window).max()
    roll_low = low.rolling(window=window, min_periods=window).min()
    pivot_high = high.shift(left).where(high.shift(left) >= roll_high)
    pivot_low = low.shift(left).where(low.shift(left) <= roll_low)
    # Publish on the bar after confirmation. No lookahead.
    return pivot_high.shift(1), pivot_low.shift(1)


def broadening_formation_rails(
    high: pd.Series,
    low: pd.Series,
    *,
    lookback: int,
    min_touches: int = 3,
    touch_tol: pd.Series | None = None,
) -> pd.DataFrame:
    """OLS rails of an expanding megaphone (higher highs and lower lows).

    Fits the last ``min_touches`` 3/3 swing highs and swing lows whose
    publication bar is inside ``lookback``. ``x`` is the original pivot bar.
    Upper slope must be positive and lower slope must be negative, and the
    rails must still be open (upper above lower). Every fitted swing must sit
    within ``touch_tol`` of its rail. The sleeve passes ATR(20), already
    shifted so bar ``t`` does not use its own range.

    This function does not call the converging-wedge rail fitter or the
    ascending-triangle swing structure.
    """
    if lookback < 2:
        raise ValueError(f"lookback must be >= 2, got {lookback}")
    if min_touches < 2:
        raise ValueError(f"min_touches must be >= 2, got {min_touches}")
    if not high.index.equals(low.index):
        raise ValueError("high and low must share an index")
    if touch_tol is not None and not touch_tol.index.equals(high.index):
        raise ValueError("touch_tol must share the high/low index")
    pub_high, pub_low = publish_broadening_swings(high, low)
    n = len(high)
    high_events: list[tuple[int, int, float]] = []
    low_events: list[tuple[int, int, float]] = []
    hi_start = 0
    lo_start = 0
    pub_h = pub_high.to_numpy(dtype="float64", copy=False)
    pub_l = pub_low.to_numpy(dtype="float64", copy=False)
    tol_arr = None if touch_tol is None else touch_tol.to_numpy(dtype="float64", copy=False)
    # Publication is confirmation (left bars) plus one extra shift.
    pivot_lag = PIVOT_LEFT + 1

    n_highs = np.full(n, np.nan)
    n_lows = np.full(n, np.nan)
    n_high_touches = np.full(n, np.nan)
    n_low_touches = np.full(n, np.nan)
    upper_slope = np.full(n, np.nan)
    lower_slope = np.full(n, np.nan)
    upper_rail = np.full(n, np.nan)
    lower_rail = np.full(n, np.nan)
    high_residual = np.full(n, np.nan)
    low_residual = np.full(n, np.nan)
    highs_rising = np.zeros(n, dtype="bool")
    lows_falling = np.zeros(n, dtype="bool")
    broadening = np.zeros(n, dtype="bool")

    def _ols(points: list[tuple[int, int, float]]) -> tuple[float, float]:
        """Slope and intercept of price versus the original pivot bar."""
        xs = [float(orig) for orig, _pub, _price in points]
        ys = [price for _orig, _pub, price in points]
        k = float(len(points))
        sx = float(sum(xs))
        sy = float(sum(ys))
        sxy = float(sum(x * y for x, y in zip(xs, ys)))
        sx2 = float(sum(x * x for x in xs))
        den = k * sx2 - sx * sx
        if den == 0.0:
            return np.nan, np.nan
        slope = (k * sxy - sx * sy) / den
        intercept = (sy - slope * sx) / k
        return float(slope), float(intercept)

    def _touch_stats(
        points: list[tuple[int, int, float]], slope: float, intercept: float, tol: float
    ) -> tuple[int, float]:
        """How many fitted swings lie within ``tol`` of the rail, and the worst gap."""
        worst = 0.0
        hits = 0
        for orig, _pub, price in points:
            gap = abs(price - (intercept + slope * float(orig)))
            worst = max(worst, gap)
            # A perfectly straight rail leaves a float-dust residual.
            if gap <= tol + 1e-9:
                hits += 1
        return hits, worst

    for t in range(n):
        if not np.isnan(pub_h[t]):
            high_events.append((t - pivot_lag, t, float(pub_h[t])))
        if not np.isnan(pub_l[t]):
            low_events.append((t - pivot_lag, t, float(pub_l[t])))
        window_start = t - lookback + 1
        while hi_start < len(high_events) and high_events[hi_start][1] < window_start:
            hi_start += 1
        while lo_start < len(low_events) and low_events[lo_start][1] < window_start:
            lo_start += 1
        hs = high_events[hi_start:]
        ls = low_events[lo_start:]
        n_highs[t] = float(len(hs))
        n_lows[t] = float(len(ls))
        if len(hs) < min_touches or len(ls) < min_touches:
            continue
        hs_fit = hs[-min_touches:]
        ls_fit = ls[-min_touches:]
        h_prices = [p for _, _, p in hs_fit]
        l_prices = [p for _, _, p in ls_fit]
        # Higher highs and lower lows on the swings that define the rails.
        hh = all(h_prices[k] > h_prices[k - 1] for k in range(1, len(h_prices)))
        ll = all(l_prices[k] < l_prices[k - 1] for k in range(1, len(l_prices)))
        highs_rising[t] = hh
        lows_falling[t] = ll
        u_s, u_b = _ols(hs_fit)
        l_s, l_b = _ols(ls_fit)
        if np.isnan(u_s) or np.isnan(l_s):
            continue
        u_rail = u_b + u_s * float(t)
        l_rail = l_b + l_s * float(t)
        upper_slope[t] = u_s
        lower_slope[t] = l_s
        upper_rail[t] = u_rail
        lower_rail[t] = l_rail
        tol = 0.0 if tol_arr is None else float(tol_arr[t])
        finite_tol = tol if np.isfinite(tol) else -1.0
        h_hits, h_res = _touch_stats(hs_fit, u_s, u_b, finite_tol)
        l_hits, l_res = _touch_stats(ls_fit, l_s, l_b, finite_tol)
        n_high_touches[t] = float(h_hits)
        n_low_touches[t] = float(l_hits)
        high_residual[t] = h_res
        low_residual[t] = l_res
        tol_ok = np.isfinite(tol) and tol >= 0.0 and h_hits >= min_touches and l_hits >= min_touches
        # Expanding megaphone only. Both slopes the same sign is a different pattern.
        broadening[t] = bool(
            hh and ll and u_s > 0.0 and l_s < 0.0 and u_rail > l_rail and tol_ok
        )

    return pd.DataFrame(
        {
            "n_highs": n_highs,
            "n_lows": n_lows,
            "n_high_touches": n_high_touches,
            "n_low_touches": n_low_touches,
            "upper_slope": upper_slope,
            "lower_slope": lower_slope,
            "upper_rail": upper_rail,
            "lower_rail": lower_rail,
            "high_residual": high_residual,
            "low_residual": low_residual,
            "highs_rising": highs_rising,
            "lows_falling": lows_falling,
            "broadening": broadening,
        },
        index=high.index,
    )


@dataclass(frozen=True)
class BroadeningFormationBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Publication window that must hold the last min_touches swings per rail.
    lookback: int = 48
    # How many recent swing highs / lows must define each expanding rail.
    min_touches: int = 3
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class BroadeningFormationBreakStrategy(Strategy):
    name = "broadening_formation_break"

    def __init__(self, params: BroadeningFormationBreakParams | None = None) -> None:
        super().__init__(params or BroadeningFormationBreakParams())
        self.params: BroadeningFormationBreakParams = self.params
        lookback = int(self.params.lookback)
        # 3/3 is one symmetric window. A 2/2 fractal is not a touch.
        if PIVOT_LEFT != 3 or PIVOT_RIGHT != 3 or PIVOT_LEFT != PIVOT_RIGHT:
            raise ValueError("Garwe lock: broadening swings are pivot 3/3")
        # Lookback, pivot confirmation on both sides, and the ATR(20) seed.
        self.min_bars = lookback + 2 * PIVOT_LEFT + ATR_PERIOD + 3

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
        lookback = int(params.lookback)
        min_touches = int(params.min_touches)
        # ATR known before the signal bar. The break bar's own range must not
        # loosen the touch test that qualifies the rails.
        # ATR(20) only. The rail fit is this module, not a wedge or triangle helper.
        atr_known = ind.atr(high, low, close, ATR_PERIOD).shift(1)
        touch_tol = atr_known * TOUCH_TOL_ATR
        rails = broadening_formation_rails(
            high,
            low,
            lookback=lookback,
            min_touches=min_touches,
            touch_tol=touch_tol,
        )
        prev_close = close.shift(1)
        formed = rails["broadening"].fillna(False)
        # First close through the rail. A held breakout (already through on
        # this bar's rail) does not fire again. Wicks do not count.
        long_raw = (
            formed
            & rails["upper_rail"].notna()
            & (prev_close <= rails["upper_rail"])
            & (close > rails["upper_rail"])
        )
        short_raw = (
            formed
            & rails["lower_rail"].notna()
            & (prev_close >= rails["lower_rail"])
            & (close < rails["lower_rail"])
        )

        signals["upper_rail"] = rails["upper_rail"]
        signals["lower_rail"] = rails["lower_rail"]
        signals["upper_slope"] = rails["upper_slope"]
        signals["lower_slope"] = rails["lower_slope"]
        signals["n_highs"] = rails["n_highs"]
        signals["n_lows"] = rails["n_lows"]
        signals["n_high_touches"] = rails["n_high_touches"]
        signals["n_low_touches"] = rails["n_low_touches"]
        signals["high_residual"] = rails["high_residual"]
        signals["low_residual"] = rails["low_residual"]
        signals["atr_touch_tol"] = touch_tol

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            level = rails["upper_rail"]
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = rails["lower_rail"]

        raw = raw.fillna(False)
        # One entry per megaphone identity (touch counts + rail slopes).
        key = (
            rails["n_highs"].astype(str)
            + "|"
            + rails["n_lows"].astype(str)
            + "|"
            + rails["upper_slope"].round(8).astype(str)
            + "|"
            + rails["lower_slope"].round(8).astype(str)
        )
        entry = raw & raw.groupby(key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (rails["upper_rail"] - rails["lower_rail"]).abs().replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - rails["upper_rail"]) / width).clip(0.0, 1.0)
        else:
            score = ((rails["lower_rail"] - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: broadening-formation break "
                    f"close {close.loc[i]:.4f} vs rail {level.loc[i]:.4f} "
                    f"u_slope {rails['upper_slope'].loc[i]:.4f} "
                    f"l_slope {rails['lower_slope'].loc[i]:.4f} "
                    f"touch_tol {touch_tol.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "LOOKBACK_GRID",
    "MIN_TOUCHES_GRID",
    "PIVOT_LEFT",
    "PIVOT_RIGHT",
    "TOUCH_TOL_ATR",
    "BroadeningFormationBreakParams",
    "BroadeningFormationBreakStrategy",
    "broadening_formation_rails",
    "publish_broadening_swings",
]
