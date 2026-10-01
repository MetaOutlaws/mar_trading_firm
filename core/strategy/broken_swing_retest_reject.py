"""Broken swing retest reject — continuation after close-break holds.

Option B. Garwe STAMP LOCK + Brian Inbox YES. Live off. Do not set
approved=true. No walk. Protect 12+56. Soft-watch Job 153.

Geometry (continuation-only; FORBID close-through = Job 153):

SHORT:
1) swing_high = max(high[t-1 .. t-swing_lookback]) — causal shift(1).rolling.
   Pivot lock named 3/3 in stamp; implemented as lookback max/min excluding t
   (no shared fractal helper in repo).
2) A prior bar CLOSE-breaks above that swing_high (close > swing_high).
3) Within retest_bars after that break, price retests FROM ABOVE (low tags
   the broken swing_high). No wick-through ATR size gate (neq 153 / neq 89).
4) Reject close stays on break side: close >= swing_high. STRICT forbid
   close < swing_high (that close-through is Job 153 territory — DARK here).
5) require_reject_close: close in upper half of the bar vs the retest low
   ((close - low) / (high - low) >= 0.5 when range > 0).

LONG: mirror — prior close broke below swing_low; retest from below within M;
close stays <= swing_low; forbid close > swing_low; close in lower half.

BOTH SHORT priority: if both raw sides print same bar, SHORT wins.
ATR20 Wilder known before signal (atr.shift(1)). Fill t+1 open (engine).
Free ≤2: swing_lookback {5, 8}, retest_bars {3, 6}.
No VP / session VWAP / calendar / wick-only unbroken pierce (=89).
Do NOT fork swing_break_fail_reversion.py (Job 153).
"""

from __future__ import annotations

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy
from core.strategy.broken_swing_retest_reject_params import (
    ATR_N_LOCKED,
    CONTINUATION_ONLY_LOCKED,
    FORBID_CLOSE_THROUGH_SWING_LOCKED,
    OPTION_B_LOCKED,
    PIVOT_33_LOCKED,
    REQUIRE_PRIOR_CLOSE_BREAK_LOCKED,
    REQUIRE_REJECT_CLOSE_LOCKED,
    RETEST_BARS_GRID,
    RETEST_BARS_MAX,
    RETEST_BARS_MIN,
    SWING_LOOKBACK_GRID,
    SWING_LOOKBACK_MAX,
    SWING_LOOKBACK_MIN,
    BrokenSwingRetestRejectParams,
)


class BrokenSwingRetestRejectStrategy(Strategy):
    name = "broken_swing_retest_reject"

    def __init__(self, params: BrokenSwingRetestRejectParams | None = None) -> None:
        super().__init__(params or BrokenSwingRetestRejectParams())
        self.params: BrokenSwingRetestRejectParams = self.params
        lookback = int(self.params.swing_lookback)
        lookback = min(SWING_LOOKBACK_MAX, max(SWING_LOOKBACK_MIN, lookback))
        retest = int(self.params.retest_bars)
        retest = min(RETEST_BARS_MAX, max(RETEST_BARS_MIN, retest))
        # ATR seed + swing window + room for a delayed retest after close-break.
        self.min_bars = ATR_N_LOCKED + lookback + retest + 1

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        p = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        if not (
            REQUIRE_REJECT_CLOSE_LOCKED
            and CONTINUATION_ONLY_LOCKED
            and FORBID_CLOSE_THROUGH_SWING_LOCKED
            and REQUIRE_PRIOR_CLOSE_BREAK_LOCKED
            and PIVOT_33_LOCKED
            and OPTION_B_LOCKED
        ):
            raise RuntimeError("broken_swing_retest_reject locks were edited")

        h = candles["high"]
        l = candles["low"]
        c = candles["close"]

        lookback = int(p.swing_lookback)
        lookback = min(SWING_LOOKBACK_MAX, max(SWING_LOOKBACK_MIN, lookback))
        retest_m = int(p.retest_bars)
        retest_m = min(RETEST_BARS_MAX, max(RETEST_BARS_MIN, retest_m))

        # Causal swing: bars t-1 .. t-lookback only (signal bar excluded).
        swing_high = h.shift(1).rolling(lookback, min_periods=lookback).max()
        swing_low = l.shift(1).rolling(lookback, min_periods=lookback).min()

        atr20 = ind.atr(h, l, c, ATR_N_LOCKED)
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & swing_high.notna() & swing_low.notna()
        atr_safe = atr_known.where(atr_ok)

        # Prior CLOSE-break of the swing (not wick-only; not same-bar fail).
        close_broke_up = atr_ok & c.gt(swing_high)
        close_broke_down = atr_ok & c.lt(swing_low)

        up_lag = pd.Series(index=candles.index, dtype="float64")
        up_level = pd.Series(index=candles.index, dtype="float64")
        dn_lag = pd.Series(index=candles.index, dtype="float64")
        dn_level = pd.Series(index=candles.index, dtype="float64")
        for lag in range(1, retest_m + 1):
            hit_up = close_broke_up.shift(lag).eq(True) & up_lag.isna()
            up_lag = up_lag.mask(hit_up, float(lag))
            up_level = up_level.mask(hit_up, swing_high.shift(lag))
            hit_dn = close_broke_down.shift(lag).eq(True) & dn_lag.isna()
            dn_lag = dn_lag.mask(hit_dn, float(lag))
            dn_level = dn_level.mask(hit_dn, swing_low.shift(lag))

        bar_range = (h - l).replace(0, pd.NA)
        upper_half = bar_range.notna() & ((c - l) / bar_range).ge(0.5)
        lower_half = bar_range.notna() & ((h - c) / bar_range).ge(0.5)

        # Retest from above: low tags broken swing_high; close stays >= (forbid through).
        retest_up = up_level.notna() & l.le(up_level)
        stay_above = up_level.notna() & c.ge(up_level)
        close_through_high = up_level.notna() & c.lt(up_level)
        reject_short_char = upper_half  # require_reject_close rule
        short_raw = (
            atr_ok
            & retest_up
            & stay_above
            & ~close_through_high.fillna(False)
            & reject_short_char.fillna(False)
        )

        # Retest from below: high tags broken swing_low; close stays <=.
        retest_dn = dn_level.notna() & h.ge(dn_level)
        stay_below = dn_level.notna() & c.le(dn_level)
        close_through_low = dn_level.notna() & c.gt(dn_level)
        reject_long_char = lower_half
        long_raw = (
            atr_ok
            & retest_dn
            & stay_below
            & ~close_through_low.fillna(False)
            & reject_long_char.fillna(False)
            & ~short_raw.fillna(False)  # BOTH SHORT priority
        )

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["swing_high"] = swing_high
        signals["swing_low"] = swing_low
        signals["swing_lookback"] = lookback
        signals["retest_bars"] = retest_m
        signals["broken_swing_high"] = up_level
        signals["broken_swing_low"] = dn_level
        signals["bars_since_up_close_break"] = up_lag
        signals["bars_since_down_close_break"] = dn_lag
        signals["close_broke_up"] = close_broke_up.fillna(False)
        signals["close_broke_down"] = close_broke_down.fillna(False)
        signals["retest_up"] = retest_up.fillna(False)
        signals["retest_down"] = retest_dn.fillna(False)
        signals["stay_above"] = stay_above.fillna(False)
        signals["stay_below"] = stay_below.fillna(False)
        signals["close_through_high"] = close_through_high.fillna(False)
        signals["close_through_low"] = close_through_low.fillna(False)
        signals["reject_upper_half"] = upper_half.fillna(False)
        signals["reject_lower_half"] = lower_half.fillna(False)

        if p.side is SignalSide.SHORT:
            entry, sig, side = short_raw, -1, SignalSide.SHORT.value
            level = up_level
        elif p.side is SignalSide.LONG:
            entry, sig, side = long_raw, 1, SignalSide.LONG.value
            level = dn_level
        else:
            entry = pd.Series(False, index=candles.index)
            sig, side = 0, SignalSide.FLAT.value
            level = pd.Series(float("nan"), index=candles.index, dtype="float64")

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if sig != 0:
            signals.loc[entry, "signal"] = sig
            signals.loc[entry, "side"] = side
            if p.side is SignalSide.SHORT:
                score = ((c - level) / atr_safe).clip(0.0, 1.0)
            else:
                score = ((level - c) / atr_safe).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]

        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and sig != 0:
            reasons.loc[entry] = [
                (
                    f"{side}: broken-swing retest-reject close {c.loc[i]:.4f} "
                    f"holds broken {float(level.loc[i]):.4f} "
                    f"lookback {lookback} retest_bars {retest_m} "
                    f"atr_known {float(atr_known.loc[i]):.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "CONTINUATION_ONLY_LOCKED",
    "FORBID_CLOSE_THROUGH_SWING_LOCKED",
    "OPTION_B_LOCKED",
    "PIVOT_33_LOCKED",
    "REQUIRE_PRIOR_CLOSE_BREAK_LOCKED",
    "REQUIRE_REJECT_CLOSE_LOCKED",
    "RETEST_BARS_GRID",
    "RETEST_BARS_MAX",
    "RETEST_BARS_MIN",
    "SWING_LOOKBACK_GRID",
    "SWING_LOOKBACK_MAX",
    "SWING_LOOKBACK_MIN",
    "BrokenSwingRetestRejectParams",
    "BrokenSwingRetestRejectStrategy",
]
