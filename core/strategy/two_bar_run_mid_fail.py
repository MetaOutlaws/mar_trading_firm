"""Two-bar run mid fail — fade through TWO-BAR envelope mid after a run.

Option B. Garwe STAMP LOCK + Brian Inbox YES. Live off. Do not set
approved=true. No walk. Protect 12+56. Soft-watch Job 165.

Geometry (≠ Job 165 impulse_midpoint_fail_fade):

165 = ONE impulse bar + extreme_frac on that bar + next through THAT bar mid.
This = TWO same-color consecutive closes; envelope mid of both bars; NO
extreme_frac. Soft-watch 165 EXPLICIT at SCORE (overlap risk).

SHORT:
1) close[t-2] > open[t-2] AND close[t-1] > open[t-1] AND close[t-1] > close[t-2]
2) H = max(high[t-2], high[t-1]); L = min(low[t-2], low[t-1])
3) (H - L) >= min_range_atr * ATR20_known  (atr.shift(1) causal)
4) signal: close[t] < (H + L) / 2   — TWO-BAR envelope mid, NOT single-bar mid

LONG inverse:
1) two down closes (close < open) consecutive + close[t-1] < close[t-2]
2) same H/L envelope of t-2,t-1; sized by min_range_atr * ATR
3) close[t] > (H + L) / 2

BOTH SHORT priority on two-sided bars.
Fill t+1 open (engine). Free ≤2 (only one free): min_range_atr {1.0, 1.5}.
FORBID extreme_frac param. FORBID single-bar mid as signal level.
No VP / session VWAP / gap-open edge.
Do NOT fork impulse_midpoint_fail_fade.py (Job 165).
"""

from __future__ import annotations

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy
from core.strategy.two_bar_run_mid_fail_params import (
    ATR_N_LOCKED,
    FORBID_EXTREME_FRAC_LOCKED,
    FORBID_SINGLE_BAR_MID_LOCKED,
    MIN_RANGE_ATR_GRID,
    MIN_RANGE_ATR_MAX,
    MIN_RANGE_ATR_MIN,
    OPTION_B_LOCKED,
    REQUIRE_MONOTONIC_RUN_LOCKED,
    REQUIRE_TWO_BAR_ENVELOPE_MID_LOCKED,
    REQUIRE_TWO_SAME_COLOR_LOCKED,
    TwoBarRunMidFailParams,
)


class TwoBarRunMidFailStrategy(Strategy):
    name = "two_bar_run_mid_fail"

    def __init__(self, params: TwoBarRunMidFailParams | None = None) -> None:
        super().__init__(params or TwoBarRunMidFailParams())
        self.params: TwoBarRunMidFailParams = self.params
        # ATR seed + two run bars + signal bar.
        self.min_bars = ATR_N_LOCKED + 3

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        p = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        if not (
            REQUIRE_TWO_SAME_COLOR_LOCKED
            and REQUIRE_MONOTONIC_RUN_LOCKED
            and REQUIRE_TWO_BAR_ENVELOPE_MID_LOCKED
            and FORBID_EXTREME_FRAC_LOCKED
            and FORBID_SINGLE_BAR_MID_LOCKED
            and OPTION_B_LOCKED
        ):
            raise RuntimeError("two_bar_run_mid_fail locks were edited")

        o = candles["open"]
        h = candles["high"]
        l = candles["low"]
        c = candles["close"]

        min_range = float(p.min_range_atr)
        min_range = min(MIN_RANGE_ATR_MAX, max(MIN_RANGE_ATR_MIN, min_range))

        # Run bars: t-2 and t-1. Signal is bar t.
        o2, h2, l2, c2 = o.shift(2), h.shift(2), l.shift(2), c.shift(2)
        o1, h1, l1, c1 = o.shift(1), h.shift(1), l.shift(1), c.shift(1)

        # TWO same-color consecutive closes + monotonic.
        bull_run = c2.gt(o2) & c1.gt(o1) & c1.gt(c2)
        bear_run = c2.lt(o2) & c1.lt(o1) & c1.lt(c2)

        # TWO-BAR envelope (not single-bar mid).
        env_high = pd.concat([h2, h1], axis=1).max(axis=1)
        env_low = pd.concat([l2, l1], axis=1).min(axis=1)
        env_range = env_high - env_low
        env_mid = (env_high + env_low) / 2.0

        atr20 = ind.atr(h, l, c, ATR_N_LOCKED)
        # Locked causal: atr.shift(1) known before signal close.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & env_high.notna() & env_low.notna()
        atr_safe = atr_known.where(atr_ok)
        sized = atr_ok & env_range.gt(0) & env_range.ge(min_range * atr_known)

        # Close through TWO-BAR envelope mid (strict). FORBID single-bar mid.
        through_down = env_mid.notna() & c.lt(env_mid)
        through_up = env_mid.notna() & c.gt(env_mid)

        short_raw = sized & bull_run & through_down
        long_raw = sized & bear_run & through_up & ~short_raw.fillna(False)

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["run_open_t2"] = o2
        signals["run_close_t2"] = c2
        signals["run_open_t1"] = o1
        signals["run_close_t1"] = c1
        signals["env_high"] = env_high
        signals["env_low"] = env_low
        signals["env_range"] = env_range
        signals["env_mid"] = env_mid
        signals["env_range_atr"] = env_range / atr_safe
        signals["bull_run"] = bull_run.fillna(False)
        signals["bear_run"] = bear_run.fillna(False)
        signals["sized"] = sized.fillna(False)
        signals["through_down"] = through_down.fillna(False)
        signals["through_up"] = through_up.fillna(False)

        if p.side is SignalSide.SHORT:
            entry, sig, side = short_raw, -1, SignalSide.SHORT.value
        elif p.side is SignalSide.LONG:
            entry, sig, side = long_raw, 1, SignalSide.LONG.value
        else:
            entry = pd.Series(False, index=candles.index)
            sig, side = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if sig != 0:
            signals.loc[entry, "signal"] = sig
            signals.loc[entry, "side"] = side
            half = (env_range / 2.0).where(env_range.gt(0))
            if p.side is SignalSide.SHORT:
                score = ((env_mid - c) / half).clip(0.0, 1.0)
            else:
                score = ((c - env_mid) / half).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]

        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and sig != 0:
            reasons.loc[entry] = [
                (
                    f"{side}: two-bar-run mid-fail close {c.loc[i]:.4f} "
                    f"{'<' if p.side is SignalSide.SHORT else '>'} "
                    f"env_mid {float(env_mid.loc[i]):.4f} of "
                    f"[{float(env_low.loc[i]):.4f}, {float(env_high.loc[i]):.4f}] "
                    f"after {'bull' if p.side is SignalSide.SHORT else 'bear'} "
                    f"run c2={float(c2.loc[i]):.4f} c1={float(c1.loc[i]):.4f} "
                    f"range {float(env_range.loc[i]):.4f}>={min_range:.2f}×ATR "
                    f"{float(atr_known.loc[i]):.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "FORBID_EXTREME_FRAC_LOCKED",
    "FORBID_SINGLE_BAR_MID_LOCKED",
    "MIN_RANGE_ATR_GRID",
    "MIN_RANGE_ATR_MAX",
    "MIN_RANGE_ATR_MIN",
    "OPTION_B_LOCKED",
    "REQUIRE_MONOTONIC_RUN_LOCKED",
    "REQUIRE_TWO_BAR_ENVELOPE_MID_LOCKED",
    "REQUIRE_TWO_SAME_COLOR_LOCKED",
    "TwoBarRunMidFailParams",
    "TwoBarRunMidFailStrategy",
]
