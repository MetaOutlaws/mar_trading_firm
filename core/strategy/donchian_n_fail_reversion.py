"""Donchian N fail reversion — same-bar wick pierce then close inside channel.

Option B. Garwe STAMP LOCK + Brian Inbox YES. Live off. Do not set
approved=true. No walk. Protect 12+56. Soft-watch Jobs 119 + 167 EXPLICIT.

Geometry (≠ Job 119 failed_range_break_reversion; ≠ Job 167 horizontal):

119 = prior CLOSE outside rolling range, then later reclaim within max_bars.
This = SAME-bar wick pierce of causal prior-N Donchian + close back inside
      + body confirms. Soft-watch 119 EXPLICIT at SCORE.

167 = min_touches≥3 flat band — no touch count here. Soft-watch 167 EXPLICIT.

Donchian exclude-t (causal):
  DHigh = max(high, t-n..t-1)   via high.shift(1).rolling(n).max()
  DLow  = min(low,  t-n..t-1)   via low.shift(1).rolling(n).min()

SHORT: high_t > DHigh + pierce_tol_atr*ATR20_known
       AND close_t < DHigh AND close_t < open_t
LONG:  low_t  < DLow  - pierce_tol_atr*ATR20_known
       AND close_t > DLow  AND close_t > open_t

BOTH SHORT priority on two-sided bars.
Fill t+1 open (engine). Free ≤2: n {10, 20}, pierce_tol_atr {0.0, 0.10}.
Locked: ATR20 atr.shift(1) causal; require wick pierce + close inside.
FORBID multi-touch flat band / next-thru-mid / extreme_frac / CLV.
No VP / session VWAP.
Do NOT fork failed_range_break_reversion, horizontal_liquidity_reject,
donchian_breakout, thrust_bar_fail_reversion, swing_failure_reversal,
candle_reject_reversal, wick_rejection_reversal.
"""

from __future__ import annotations

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy
from core.strategy.donchian_n_fail_reversion_params import (
    ATR_N_LOCKED,
    DONCHIAN_EXCLUDE_T_LOCKED,
    FORBID_CLV_LOCKED,
    FORBID_EXTREME_FRAC_LOCKED,
    FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED,
    FORBID_NEXT_THRU_MID_LOCKED,
    N_GRID,
    N_MAX,
    N_MIN,
    OPTION_B_LOCKED,
    PIERCE_TOL_ATR_GRID,
    PIERCE_TOL_ATR_MAX,
    PIERCE_TOL_ATR_MIN,
    REQUIRE_WICK_PIERCE_CLOSE_INSIDE_LOCKED,
    DonchianNFailReversionParams,
)


class DonchianNFailReversionStrategy(Strategy):
    name = "donchian_n_fail_reversion"

    def __init__(self, params: DonchianNFailReversionParams | None = None) -> None:
        super().__init__(params or DonchianNFailReversionParams())
        self.params: DonchianNFailReversionParams = self.params
        # ATR seed + Donchian window + signal bar.
        n = max(N_MIN, int(self.params.n))
        self.min_bars = max(ATR_N_LOCKED, n) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        p = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        if not (
            DONCHIAN_EXCLUDE_T_LOCKED
            and REQUIRE_WICK_PIERCE_CLOSE_INSIDE_LOCKED
            and FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED
            and FORBID_NEXT_THRU_MID_LOCKED
            and FORBID_EXTREME_FRAC_LOCKED
            and FORBID_CLV_LOCKED
            and OPTION_B_LOCKED
        ):
            raise RuntimeError("donchian_n_fail_reversion locks were edited")

        o = candles["open"].astype("float64")
        h = candles["high"].astype("float64")
        l = candles["low"].astype("float64")
        c = candles["close"].astype("float64")

        n = int(p.n)
        n = min(N_MAX, max(N_MIN, n))
        pierce = float(p.pierce_tol_atr)
        pierce = min(PIERCE_TOL_ATR_MAX, max(PIERCE_TOL_ATR_MIN, pierce))

        # Causal Donchian exclude-t: prior n bars only (shift(1).rolling(n)).
        d_high = h.shift(1).rolling(n, min_periods=n).max()
        d_low = l.shift(1).rolling(n, min_periods=n).min()

        atr20 = ind.atr(h, l, c, ATR_N_LOCKED)
        # Locked causal: atr.shift(1) known before signal close.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & d_high.notna() & d_low.notna()
        atr_safe = atr_known.where(atr_ok)
        thresh = pierce * atr_known

        # Wick pierce beyond Donchian + same-bar close inside + body confirm.
        pierce_up = atr_ok & h.gt(d_high + thresh)
        pierce_dn = atr_ok & l.lt(d_low - thresh)
        close_below_dhigh = c.lt(d_high)
        close_above_dlow = c.gt(d_low)
        bear_body = c.lt(o)
        bull_body = c.gt(o)

        short_raw = pierce_up & close_below_dhigh & bear_body
        long_raw = pierce_dn & close_above_dlow & bull_body & ~short_raw.fillna(False)

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["d_high"] = d_high
        signals["d_low"] = d_low
        signals["pierce_thresh"] = thresh
        signals["pierce_up"] = pierce_up.fillna(False)
        signals["pierce_dn"] = pierce_dn.fillna(False)
        signals["close_below_dhigh"] = close_below_dhigh.fillna(False)
        signals["close_above_dlow"] = close_above_dlow.fillna(False)
        signals["bear_body"] = bear_body.fillna(False)
        signals["bull_body"] = bull_body.fillna(False)

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
            # Score: pierce depth in ATR units, clipped.
            if p.side is SignalSide.SHORT:
                depth = (h - d_high - thresh) / atr_safe
            else:
                depth = (d_low - thresh - l) / atr_safe
            signals.loc[entry, "score"] = depth.clip(0.0, 1.0).fillna(0.0)[entry]

        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and sig != 0:
            reasons.loc[entry] = [
                (
                    f"{side}: donchian-n fail-reversion "
                    f"{'pierce_up h=' + f'{float(h.loc[i]):.4f}' if p.side is SignalSide.SHORT else 'pierce_dn l=' + f'{float(l.loc[i]):.4f}'} "
                    f"DHigh={float(d_high.loc[i]):.4f} DLow={float(d_low.loc[i]):.4f} "
                    f"close={float(c.loc[i]):.4f} open={float(o.loc[i]):.4f} "
                    f"n={n} pierce_tol={pierce:.2f} ATR={float(atr_known.loc[i]):.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "DONCHIAN_EXCLUDE_T_LOCKED",
    "FORBID_CLV_LOCKED",
    "FORBID_EXTREME_FRAC_LOCKED",
    "FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED",
    "FORBID_NEXT_THRU_MID_LOCKED",
    "N_GRID",
    "N_MAX",
    "N_MIN",
    "OPTION_B_LOCKED",
    "PIERCE_TOL_ATR_GRID",
    "PIERCE_TOL_ATR_MAX",
    "PIERCE_TOL_ATR_MIN",
    "REQUIRE_WICK_PIERCE_CLOSE_INSIDE_LOCKED",
    "DonchianNFailReversionParams",
    "DonchianNFailReversionStrategy",
]
