"""Body gap fail reversion — fade open-gap reclaim inside prior H–L.

Option B. Garwe LOCK + Brian YES. Live off. Do not set approved=true. No walk.
Fill t+1. SHORT: open>high[t-1]+min_gap*ATR20, close inside prior H–L.
LONG: mirror. Prior range>=min_prior*ATR20. ATR20 shift(1). FORBID follow
(neq Job 143). BOTH SHORT-pri. Free min_gap[0.10,0.25] min_prior[0.5,1.0].
No VP/VWAP/calendar/thrust. 0 book. Protect 12+56.
"""

from __future__ import annotations

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy
from core.strategy.body_gap_fail_reversion_params import (
    ATR_N_LOCKED,
    FORBID_FOLLOW_CONTINUATION_LOCKED,
    MIN_GAP_ATR_GRID,
    MIN_GAP_ATR_MAX,
    MIN_GAP_ATR_MIN,
    MIN_PRIOR_RANGE_ATR_GRID,
    MIN_PRIOR_RANGE_ATR_MAX,
    MIN_PRIOR_RANGE_ATR_MIN,
    OPTION_B_LOCKED,
    REQUIRE_CLOSE_RECLAIM_INSIDE_LOCKED,
    BodyGapFailReversionParams,
)


class BodyGapFailReversionStrategy(Strategy):
    name = "body_gap_fail_reversion"

    def __init__(self, params: BodyGapFailReversionParams | None = None) -> None:
        super().__init__(params or BodyGapFailReversionParams())
        self.params: BodyGapFailReversionParams = self.params
        self.min_bars = ATR_N_LOCKED + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        p = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals
        o, h, l, c = candles["open"], candles["high"], candles["low"], candles["close"]
        min_gap, min_prior = float(p.min_gap_atr), float(p.min_prior_range_atr)
        ph, pl = h.shift(1), l.shift(1)
        pr = ph - pl
        atr20 = ind.atr(h, l, c, ATR_N_LOCKED)
        ak = atr20.shift(1)
        ok = ak.gt(0)
        safe = ak.where(ok)
        up = ok & ph.notna() & o.gt(ph + min_gap * ak)
        dn = ok & pl.notna() & o.lt(pl - min_gap * ak)
        sized = ok & pr.gt(0) & pr.ge(min_prior * ak)
        inside = ph.notna() & pl.notna() & c.le(ph) & c.ge(pl)
        f_up, f_dn = up & c.gt(ph), dn & c.lt(pl)
        if not (REQUIRE_CLOSE_RECLAIM_INSIDE_LOCKED and FORBID_FOLLOW_CONTINUATION_LOCKED):
            raise RuntimeError("body gap fail reversion locks were edited")
        short_raw = sized & up & inside & ~f_up
        long_raw = sized & dn & inside & ~f_dn & ~short_raw.fillna(False)
        signals["atr"] = atr20
        signals["atr_known"] = ak
        signals["prior_high"] = ph
        signals["prior_low"] = pl
        signals["prior_range"] = pr
        signals["prior_range_atr"] = pr / safe
        signals["gap_up_size"] = o - ph
        signals["gap_down_size"] = pl - o
        signals["gap_up_atr"] = (o - ph) / safe
        signals["gap_down_atr"] = (pl - o) / safe
        signals["gap_up_open"] = up.fillna(False)
        signals["gap_down_open"] = dn.fillna(False)
        signals["prior_sized"] = sized.fillna(False)
        signals["close_inside"] = inside.fillna(False)
        signals["follow_up"] = f_up.fillna(False)
        signals["follow_down"] = f_dn.fillna(False)
        if p.side is SignalSide.SHORT:
            entry, sig, side = short_raw, -1, SignalSide.SHORT.value
            gsize, gatr = o - ph, (o - ph) / safe
        elif p.side is SignalSide.LONG:
            entry, sig, side = long_raw, 1, SignalSide.LONG.value
            gsize, gatr = pl - o, (pl - o) / safe
        else:
            entry = pd.Series(False, index=candles.index)
            sig, side = 0, SignalSide.FLAT.value
            gsize = pd.Series(pd.NA, index=candles.index, dtype="float64")
            gatr = gsize.copy()
        signals["gap_size"] = gsize
        signals["gap_atr"] = gatr
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if sig != 0:
            signals.loc[entry, "signal"] = sig
            signals.loc[entry, "side"] = side
            signals.loc[entry, "score"] = ((gatr - min_gap) / min_gap).clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and sig != 0:
            reasons.loc[entry] = [
                f"{side}: body-gap fail-reversion open {o.loc[i]:.4f} "
                f"gap {float(gsize.loc[i]):.4f} reclaim {c.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "FORBID_FOLLOW_CONTINUATION_LOCKED",
    "MIN_GAP_ATR_GRID",
    "MIN_GAP_ATR_MAX",
    "MIN_GAP_ATR_MIN",
    "MIN_PRIOR_RANGE_ATR_GRID",
    "MIN_PRIOR_RANGE_ATR_MAX",
    "MIN_PRIOR_RANGE_ATR_MIN",
    "OPTION_B_LOCKED",
    "REQUIRE_CLOSE_RECLAIM_INSIDE_LOCKED",
    "BodyGapFailReversionParams",
    "BodyGapFailReversionStrategy",
]
