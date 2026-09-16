"""Prior-day LVN fill-reject. 4h/4h BOTH.

LVN is the low-volume node from the prior *completed* UTC-day volume
profile only (00:00–24:00 UTC yesterday). The forming / incomplete current
day never contributes. Histogram binning is the same locked definition as
``prior_poc_reclaim_fade`` / ``hvn_mean_revert``: 20 equal-width price bins
across that day's [low, high]; each bar's volume is spread uniformly across
overlapping bins; LVN = midpoint of the lowest-positive-volume bin (see
``indicators.volume_profile_lvn`` / ``prior_utc_day_volume_lvn``).
Zero-weight bins are skipped; exact volume ties take the lowest-price min.

Price fills into that prior-day LVN within ``touch_tol_atr * ATR20``, then
rejects (closes back on the fade side of LVN). SHORT rejects down from
LVN; LONG rejects up from LVN:

    SHORT: high[t] >= LVN - touch_tol_atr * ATR  AND  close[t] < LVN
    LONG:  low[t]  <= LVN + touch_tol_atr * ATR  AND  close[t] > LVN

ATR is Wilder ATR(20) known *before* the signal bar (``atr.shift(1)``) so
bar ``t`` cannot widen its own tag band. The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH
    - Family id ``lvn_fill_reject`` only
    - Prior completed UTC-day volume-profile LVN (never a forming day)
    - Same 20-bin occupancy histogram as prior_poc / HVN
    - ATR period = 20, known before the signal bar
    - Fill at t+1 open

Free search (1 only):

    - ``touch_tol_atr`` grid ``[0.0, 0.05, 0.10, 0.15]``
      (endpoints 0.0 and 0.15 plus 0.05-step interiors, matching how
      sibling single-float grids list discrete search points)

OHLCV + volume/turnover as available. Causal: bars ``<= t``.

Not ``prior_poc_reclaim_fade`` (Job 145 — single prior-day POC).
Not ``hvn_mean_revert`` (Job 146 — nearest-of-top-N prior-day HVN).
Not ``prior_day_vwap_reject`` / ``session_vwap_band_fade``.
Not ``rolling_va_extreme_reject`` (Job ~148 — rolling walk-clock VA).
Not ``session_volume_profile_reversal`` (skip-list — do not code).
Not ``asia_range_london_reject`` / london_close / ny_close inventory fades.
Not ``sma20_stretch_fade`` / ``keltner_channel_fade``.
Not ``prior_day_extreme_reject`` (118 — raw prior UTC day H/L).
Not ``inside_bar_break_fail`` (family F — do not code in this sleeve).
Do not recode spent families 118–148. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches touch_tol_atr only.
ATR_N_LOCKED = 20
# Locked histogram bins. Same definition as prior_poc_reclaim_fade.
POC_BINS_LOCKED = ind.POC_BINS_LOCKED
# Free-grid tag slack. Endpoints 0.0 / 0.15 plus 0.05-step interiors.
TOUCH_TOL_MIN = 0.0
TOUCH_TOL_MAX = 0.15
TOUCH_TOL_GRID = [0.0, 0.05, 0.10, 0.15]


@dataclass(frozen=True)
class LvnFillRejectParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Tag slack as a multiple of prior-bar ATR. Quant grid:
    # [0.0, 0.05, 0.10, 0.15].
    touch_tol_atr: float = TOUCH_TOL_MIN
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class LvnFillRejectStrategy(Strategy):
    name = "lvn_fill_reject"

    def __init__(self, params: LvnFillRejectParams | None = None) -> None:
        super().__init__(params or LvnFillRejectParams())
        self.params: LvnFillRejectParams = self.params
        # One completed UTC day plus ATR(20) warmup and the known-before shift.
        self.min_bars = ATR_N_LOCKED + 8

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
        volume = candles["volume"]
        turnover = candles["turnover"] if "turnover" in candles.columns else None
        # Searched tag slack stays caller-set. Period / bin count stay locked
        # even if a caller tries to override atr_n on the params object.
        touch_k = float(params.touch_tol_atr)
        atr_n = ATR_N_LOCKED

        # Prior completed UTC-day volume-profile LVN. Forming day is excluded.
        lvn = ind.prior_utc_day_volume_lvn(
            high,
            low,
            volume,
            n_bins=POC_BINS_LOCKED,
            turnover=turnover,
        )
        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — the tag wick cannot lift the band.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & lvn.notna()
        touch = touch_k * atr_known.fillna(0.0)

        # Tag = fill into LVN within touch slack. Reject = close strictly
        # back on the fade side of LVN (SHORT below / LONG above).
        tagged_from_below = atr_ok & high.ge(lvn - touch)
        tagged_from_above = atr_ok & low.le(lvn + touch)
        closed_below = close.lt(lvn)
        closed_above = close.gt(lvn)
        short_raw = tagged_from_below & closed_below
        long_raw = tagged_from_above & closed_above

        signals["lvn"] = lvn
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["touch"] = touch
        signals["tagged_from_below"] = tagged_from_below.fillna(False)
        signals["tagged_from_above"] = tagged_from_above.fillna(False)
        signals["closed_below_lvn"] = closed_below.fillna(False)
        signals["closed_above_lvn"] = closed_above.fillna(False)

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
            atr_safe = atr_known.replace(0, pd.NA)
            if params.side is SignalSide.SHORT:
                depth = ((high - lvn) / atr_safe).clip(0.0, 1.0)
            else:
                depth = ((lvn - low) / atr_safe).clip(0.0, 1.0)
            signals.loc[entry, "score"] = depth.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: prior-LVN fill-reject close {close.loc[i]:.4f} "
                    f"lvn {lvn.loc[i]:.4f} touch {touch.loc[i]:.4f} "
                    f"atr {atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "POC_BINS_LOCKED",
    "TOUCH_TOL_GRID",
    "TOUCH_TOL_MAX",
    "TOUCH_TOL_MIN",
    "LvnFillRejectParams",
    "LvnFillRejectStrategy",
]
