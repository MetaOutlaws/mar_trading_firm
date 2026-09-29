"""Break the neckline of a 4h head-and-shoulders, or the inverse.

Garwe stamp. Option B exploratory. SCORE/RETIRE only. Not an approval.

SHORT is three swing highs (left shoulder → head → right shoulder)
with the head strictly above both shoulders and the shoulders inside
an ATR band, then a close through the neckline that joins the two
intervening swing lows. LONG is the inverse: three swing lows, head
strictly below both shoulders, close up through the neckline that
joins the two intervening swing highs.

The neckline is a line evaluated at bar ``t``, not the horizontal
min/max used by the two-touch double-top and double-bottom sleeves.
A signal at ``t`` uses bars ``<= t`` only. The engine fills at the
``t+1`` open.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority on two-sided bars)
    - Family id ``head_and_shoulders_neckline_break`` only
    - ATR period = 20 (Wilder, peer neckline convention at bar ``t``)
    - Pivot confirmation is symmetric: PIVOT_LEFT = PIVOT_RIGHT = 3
    - Close-through is strict (``close < neckline`` / ``close > neckline``)
    - One entry per completed pivot set
    - Fill at t+1 open (engine convention)

Free search (2 only), Garwe stamp — not an assumed grid:

    - ``lookback`` ``[40, 60]`` only. Not 24. Not 30. Not 50.
    - ``atr_tol`` ``[0.10, 0.15]``

Not ``double_top_neckline_break`` (two matched highs, one trough).
Not ``double_bottom_neckline_break`` (two matched lows, one peak).
Not ``equal_high_low_restest_fade`` (failed restest, no neckline break).
Not ``ascending_triangle_break`` (rising lows into a flat cap).
Do not modify sibling geometry. Do not set ``approved=true``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward does not search the period.
ATR_PERIOD = 20
# Symmetric swing confirmation. Right equals left; not a third free param.
PIVOT_LEFT = 3
PIVOT_RIGHT = 3
# Garwe free grid. Endpoints only. lookback 24 is not in this family.
LOOKBACK_MIN = 40
LOOKBACK_MAX = 60
LOOKBACK_GRID = [40, 60]
ATR_TOL_MIN = 0.10
ATR_TOL_MAX = 0.15
ATR_TOL_GRID = [0.10, 0.15]


@dataclass(frozen=True)
class HeadAndShouldersNecklineBreakParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    # Publication window that must contain the three pivots and both reactions.
    # Quant grid: [40, 60]. Not 24.
    lookback: int = LOOKBACK_MIN
    # |shoulder_left - shoulder_right| <= atr_tol * ATR(20).
    # Quant grid: [0.10, 0.15].
    atr_tol: float = ATR_TOL_MAX
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class HeadAndShouldersNecklineBreakStrategy(Strategy):
    name = "head_and_shoulders_neckline_break"

    def __init__(self, params: HeadAndShouldersNecklineBreakParams | None = None) -> None:
        super().__init__(params or HeadAndShouldersNecklineBreakParams())
        self.params: HeadAndShouldersNecklineBreakParams = self.params
        lookback = int(self.params.lookback)
        # ATR seed plus one confirmation window so a pivot can publish.
        self.min_bars = max(lookback, ATR_PERIOD) + PIVOT_LEFT + PIVOT_RIGHT + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals
        if PIVOT_LEFT != PIVOT_RIGHT:
            # Stamp locks a symmetric 3/3 window. Refuse a drifted constant.
            signals["reason"] = "pivot window is not symmetric"
            return signals

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        lookback = int(params.lookback)
        # Three-pivot geometry. Does not call the two-touch neckline helper.
        structure = ind.head_and_shoulders_structure(
            high, low, lookback=lookback, left=PIVOT_LEFT
        )
        atr = ind.atr(high, low, close, ATR_PERIOD)
        tol = float(params.atr_tol) * atr
        atr_ok = atr.gt(0)

        short_ls = structure["short_ls"]
        short_head = structure["short_head"]
        short_rs = structure["short_rs"]
        short_neck = structure["short_neckline"]
        long_ls = structure["long_ls"]
        long_head = structure["long_head"]
        long_rs = structure["long_rs"]
        long_neck = structure["long_neckline"]

        # Shoulders match inside the ATR band. Head-vs-shoulder is already
        # required by the structure helper (strict).
        short_shoulders = (short_ls - short_rs).abs() <= tol
        long_shoulders = (long_ls - long_rs).abs() <= tol
        short_pattern = (
            atr_ok
            & short_ls.notna()
            & short_head.notna()
            & short_rs.notna()
            & short_neck.notna()
            & short_shoulders.fillna(False)
        )
        long_pattern = (
            atr_ok
            & long_ls.notna()
            & long_head.notna()
            & long_rs.notna()
            & long_neck.notna()
            & long_shoulders.fillna(False)
        )

        prev_close = close.shift(1)
        # First close through the line. A bar that was already through while
        # the same pattern was active is not a new break. The bar the pattern
        # first becomes visible still qualifies (no prior pattern).
        short_prev = short_pattern.shift(1).fillna(False)
        long_prev = long_pattern.shift(1).fillna(False)
        short_was_above = (~short_prev) | prev_close.ge(short_neck.shift(1))
        long_was_below = (~long_prev) | prev_close.le(long_neck.shift(1))
        short_raw = short_pattern & close.lt(short_neck) & short_was_above.fillna(False)
        long_raw = long_pattern & close.gt(long_neck) & long_was_below.fillna(False)
        # SHORT priority: a bar that breaks both a top and an inverse is SHORT.
        long_raw = long_raw & (~short_raw)

        if params.side is SignalSide.SHORT:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            shoulder_l, head_px, shoulder_r = short_ls, short_head, short_rs
            neckline = short_neck
            bar_l = structure["short_ls_bar"]
            bar_h = structure["short_head_bar"]
            bar_r = structure["short_rs_bar"]
            react_l = structure["short_trough_left_bar"]
            react_r = structure["short_trough_right_bar"]
        elif params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            shoulder_l, head_px, shoulder_r = long_ls, long_head, long_rs
            neckline = long_neck
            bar_l = structure["long_ls_bar"]
            bar_h = structure["long_head_bar"]
            bar_r = structure["long_rs_bar"]
            react_l = structure["long_peak_left_bar"]
            react_r = structure["long_peak_right_bar"]
        else:
            raw = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value
            shoulder_l = head_px = shoulder_r = neckline = pd.Series(pd.NA, index=candles.index)
            bar_l = bar_h = bar_r = react_l = react_r = neckline

        signals["left_shoulder"] = shoulder_l
        signals["head"] = head_px
        signals["right_shoulder"] = shoulder_r
        signals["neckline"] = neckline
        signals["atr"] = atr
        signals["atr_tol_band"] = tol

        raw = raw.fillna(False)
        # One fire per pivot set so a hold beyond the neckline does not re-enter.
        key = (
            bar_l.astype(str)
            + "|"
            + bar_h.astype(str)
            + "|"
            + bar_r.astype(str)
            + "|"
            + react_l.astype(str)
            + "|"
            + react_r.astype(str)
        )
        entry = raw & raw.groupby(key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: head-and-shoulders "
                    f"{shoulder_l.loc[i]:.4f}/{head_px.loc[i]:.4f}/{shoulder_r.loc[i]:.4f} "
                    f"neck {neckline.loc[i]:.4f} close {close.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "ATR_TOL_GRID",
    "ATR_TOL_MAX",
    "ATR_TOL_MIN",
    "LOOKBACK_GRID",
    "LOOKBACK_MAX",
    "LOOKBACK_MIN",
    "PIVOT_LEFT",
    "PIVOT_RIGHT",
    "HeadAndShouldersNecklineBreakParams",
    "HeadAndShouldersNecklineBreakStrategy",
]
