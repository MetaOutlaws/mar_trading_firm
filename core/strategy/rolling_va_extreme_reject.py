"""Rolling volume-profile value-area extreme reject. 4h/4h BOTH.

Value area is the rolling volume-profile VA on the walk clock: the prior
``lookback`` bars only (excluding the signal bar). Histogram binning is
the same locked definition as ``prior_poc_reclaim_fade`` / ``hvn_mean_revert``:
20 equal-width price bins across that window's [low, high]; each bar's
volume is spread uniformly across overlapping bins. VA grows one bin at a
time from the POC until accumulated volume >= ``va_frac`` of total volume.
VAH / VAL are the outer edges of that value area (see
``indicators.volume_profile_value_area`` / ``rolling_volume_value_area``).

Fade the extremes (chop / mean-reversion — not a breakout). Garwe stamp
signal rules (exact):

    SHORT: high[t] >= VAH - touch_tol_atr * ATR  AND  VAL < close[t] < VAH
    LONG:  low[t]  <= VAL + touch_tol_atr * ATR  AND  VAL < close[t] < VAH

``require_close_inside_va`` is locked True: close must sit strictly inside
(VAL, VAH) after the tag. ATR is Wilder ATR(20) known *before* the signal
bar (``atr.shift(1)``) so bar ``t`` cannot widen its own tag band. The
engine fills at ``t+1`` open.

Quant-locked (not searched) — Garwe stamp:

    - Clock 4h/4h, side BOTH
    - Family id ``rolling_va_extreme_reject`` only
    - Rolling VA on the walk clock (prior lookback bars, never a
      prior-completed-UTC-day profile)
    - Same 20-bin occupancy histogram as prior_poc / HVN
    - ``require_close_inside_va`` = True
    - ATR period = 20, known before the signal bar
    - Fill at t+1 open

Free search (3 only) — Garwe stamp, do not widen or rename:

    - ``lookback`` grid ``[20, 48]``
    - ``touch_tol_atr`` grid ``[0.0, 0.10]`` (ATR multiples)
    - ``va_frac`` grid ``[0.68, 0.70]``

OHLCV + volume/turnover as available. Causal: bars ``<= t``.

Not ``prior_poc_reclaim_fade`` (Job 145 — single prior-day POC).
Not ``hvn_mean_revert`` (Job 146 — nearest-of-top-N prior-day HVN).
Not ``prior_day_vwap_reject`` / ``session_vwap_band_fade`` /
    ``utc_session_vwap_reversion`` / ``vwap_volatility_band_fade``.
Not ``session_volume_profile_reversal`` (skip-list — do not code).
Not ``prior_day_extreme_reject`` (118 — raw prior UTC day H/L).
Not ``sma20_stretch_fade`` / ``keltner_channel_fade``.
Not asia / inventory fades.
Do not recode spent families 118–146. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches lookback + touch_tol_atr + va_frac.
ATR_N_LOCKED = 20
# Locked histogram bins. Same definition as prior_poc / HVN.
POC_BINS_LOCKED = ind.POC_BINS_LOCKED
# Garwe stamp free-grid bounds. Clamped even if a caller tries to override.
LOOKBACK_MIN = 20
LOOKBACK_MAX = 48
TOUCH_TOL_MIN = 0.0
TOUCH_TOL_MAX = 0.10
VA_FRAC_MIN = 0.68
VA_FRAC_MAX = 0.70
# Quant-locked True: fade only if close rejects back inside the VA.
REQUIRE_CLOSE_INSIDE_VA_LOCKED = True


@dataclass(frozen=True)
class RollingVaExtremeRejectParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Prior-bar rolling profile length. Garwe grid: [20, 48].
    lookback: int = LOOKBACK_MIN
    # Tag slack as a multiple of prior-bar ATR. Garwe grid: [0.0, 0.10].
    touch_tol_atr: float = TOUCH_TOL_MIN
    # Value-area fraction of window volume. Garwe grid: [0.68, 0.70].
    va_frac: float = VA_FRAC_MIN
    # Quant-locked True: require close strictly inside (VAL, VAH).
    require_close_inside_va: bool = REQUIRE_CLOSE_INSIDE_VA_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class RollingVaExtremeRejectStrategy(Strategy):
    name = "rolling_va_extreme_reject"

    def __init__(self, params: RollingVaExtremeRejectParams | None = None) -> None:
        super().__init__(params or RollingVaExtremeRejectParams())
        self.params: RollingVaExtremeRejectParams = self.params
        lookback = min(LOOKBACK_MAX, max(LOOKBACK_MIN, int(self.params.lookback)))
        # Rolling window plus ATR(20) warmup and the known-before shift.
        self.min_bars = max(lookback, ATR_N_LOCKED) + 8

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
        # Searched knobs stay caller-set but stay inside the Garwe grid.
        # Period / bin count / close-inside stay locked even if overridden.
        lookback = min(LOOKBACK_MAX, max(LOOKBACK_MIN, int(params.lookback)))
        touch_k = min(TOUCH_TOL_MAX, max(TOUCH_TOL_MIN, float(params.touch_tol_atr)))
        va_frac = min(VA_FRAC_MAX, max(VA_FRAC_MIN, float(params.va_frac)))
        atr_n = ATR_N_LOCKED
        close_inside = REQUIRE_CLOSE_INSIDE_VA_LOCKED

        profile = ind.rolling_volume_value_area(
            high,
            low,
            volume,
            lookback=lookback,
            va_frac=va_frac,
            n_bins=POC_BINS_LOCKED,
            turnover=turnover,
        )
        vah = profile["vah"]
        val = profile["val"]
        poc = profile["poc"]
        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — the tag wick cannot lift the band.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & vah.notna() & val.notna() & vah.gt(val)
        touch = touch_k * atr_known.fillna(0.0)

        tagged_vah = atr_ok & high.ge(vah - touch)
        tagged_val = atr_ok & low.le(val + touch)
        # Garwe lock: close must sit strictly inside VA after the tag.
        inside_va = bool(close_inside) & atr_ok & close.gt(val) & close.lt(vah)
        short_raw = tagged_vah & inside_va
        long_raw = tagged_val & inside_va

        signals["vah"] = vah
        signals["val"] = val
        signals["poc"] = poc
        signals["lookback"] = lookback
        signals["va_frac"] = va_frac
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["touch"] = touch
        signals["tagged_vah"] = tagged_vah.fillna(False)
        signals["tagged_val"] = tagged_val.fillna(False)
        signals["closed_inside_va"] = inside_va.fillna(False)

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
                depth = ((high - vah) / atr_safe).clip(0.0, 1.0)
            else:
                depth = ((val - low) / atr_safe).clip(0.0, 1.0)
            signals.loc[entry, "score"] = depth.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: rolling-VA extreme-reject close {close.loc[i]:.4f} "
                    f"vah {vah.loc[i]:.4f} val {val.loc[i]:.4f} "
                    f"lookback={lookback} va_frac={va_frac:.2f} "
                    f"touch {touch.loc[i]:.4f} atr {atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "LOOKBACK_MAX",
    "LOOKBACK_MIN",
    "POC_BINS_LOCKED",
    "REQUIRE_CLOSE_INSIDE_VA_LOCKED",
    "TOUCH_TOL_MAX",
    "TOUCH_TOL_MIN",
    "VA_FRAC_MAX",
    "VA_FRAC_MIN",
    "RollingVaExtremeRejectParams",
    "RollingVaExtremeRejectStrategy",
]
