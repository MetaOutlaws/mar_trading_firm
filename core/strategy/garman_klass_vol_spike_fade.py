"""Garman-Klass OHLC vol spike fade -- fade a GK z-spike bar.

Option B. Garwe STAMP LOCK. Live off. Do not set approved=true. No walk.
Protect 12+56. Soft-watch Job 172 EXPLICIT.

Geometry (!= Job 172 amihud_illiquidity_spike_fade):

172 = Amihud |ret|/turnover (or volume*close) z-spike; fade spike-bar body.
This = Garman-Klass OHLC vol estimator z-spike; fade spike-bar body.
      NO volume/turnover in signal. NO wick_frac. NO Donchian. NO compression.
      Soft-watch 172 EXPLICIT at SCORE (do not collapse to |ret|/turnover).

hl_t = ln(high_t / low_t)   (floor eps for nonpositive ratios)
co_t = ln(close_t / open_t) (floor eps for nonpositive ratios)
gk_t = 0.5 * hl^2 - (2*ln(2) - 1) * co^2  (floor eps if needed)
z_t  = (gk_t - mean(gk, prior lookback)) / std(gk, prior lookback)
       causal: mean/std of PRIOR lookback bars only (shift exclude t)

SHORT: z_t >= z_min AND close_t > open_t  (fade up-bar spike)
LONG:  z_t >= z_min AND close_t < open_t  (fade down-bar spike)

BOTH SHORT priority on two-sided bars.
Fill t+1 open (engine). Free <=2: lookback {20, 40}, z_min {2.0, 2.5}.
FORBID volume-in-signal / wick_frac / Donchian / compression /
extreme_frac / next-thru-mid / CLV. No VP / session VWAP.
Do NOT fork amihud_illiquidity_spike_fade, high_vol_wick_reject,
donchian_n_fail_reversion, atr_compression_break_fail,
impulse_midpoint_fail_fade, two_bar_run_mid_fail.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy.base import SignalSide, Strategy
from core.strategy.garman_klass_vol_spike_fade_params import (
    CAUSAL_Z_PRIOR_LOOKBACK_LOCKED,
    EPS_LOCKED,
    FADE_SPIKE_BAR_BODY_LOCKED,
    FORBID_CLV_LOCKED,
    FORBID_COMPRESSION_LOCKED,
    FORBID_DONCHIAN_LOCKED,
    FORBID_EXTREME_FRAC_LOCKED,
    FORBID_NEXT_THRU_MID_LOCKED,
    FORBID_VOLUME_IN_SIGNAL_LOCKED,
    FORBID_WICK_FRAC_LOCKED,
    LOOKBACK_GRID,
    LOOKBACK_MAX,
    LOOKBACK_MIN,
    OHLC_ONLY_GARMAN_KLASS_LOCKED,
    OPTION_B_LOCKED,
    Z_MIN_GRID,
    Z_MIN_MAX,
    Z_MIN_MIN,
    GarmanKlassVolSpikeFadeParams,
)

_LN2 = float(np.log(2.0))
_GK_CO_COEF = 2.0 * _LN2 - 1.0  # 2*ln(2) - 1


def _garman_klass(o: pd.Series, h: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    """Garman-Klass estimator from O/H/L/C only. Never touches volume."""
    # Floor nonpositive ratios at eps before ln.
    hl_ratio = (h / l).clip(lower=EPS_LOCKED)
    co_ratio = (c / o).clip(lower=EPS_LOCKED)
    hl = np.log(hl_ratio)
    co = np.log(co_ratio)
    gk = 0.5 * hl.pow(2) - _GK_CO_COEF * co.pow(2)
    return gk.clip(lower=EPS_LOCKED)


class GarmanKlassVolSpikeFadeStrategy(Strategy):
    name = "garman_klass_vol_spike_fade"

    def __init__(self, params: GarmanKlassVolSpikeFadeParams | None = None) -> None:
        super().__init__(params or GarmanKlassVolSpikeFadeParams())
        self.params: GarmanKlassVolSpikeFadeParams = self.params
        # Lookback window after shift + signal bar.
        self.min_bars = int(self.params.lookback) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        p = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        if not (
            FADE_SPIKE_BAR_BODY_LOCKED
            and CAUSAL_Z_PRIOR_LOOKBACK_LOCKED
            and FORBID_EXTREME_FRAC_LOCKED
            and FORBID_NEXT_THRU_MID_LOCKED
            and FORBID_CLV_LOCKED
            and FORBID_VOLUME_IN_SIGNAL_LOCKED
            and FORBID_WICK_FRAC_LOCKED
            and FORBID_DONCHIAN_LOCKED
            and FORBID_COMPRESSION_LOCKED
            and OHLC_ONLY_GARMAN_KLASS_LOCKED
            and OPTION_B_LOCKED
        ):
            raise RuntimeError("garman_klass_vol_spike_fade locks were edited")

        # OHLC only -- never read volume/turnover/quote_volume in signal path.
        o = candles["open"].astype("float64")
        h = candles["high"].astype("float64")
        l = candles["low"].astype("float64")
        c = candles["close"].astype("float64")

        lookback = int(p.lookback)
        lookback = min(LOOKBACK_MAX, max(LOOKBACK_MIN, lookback))
        z_min = float(p.z_min)
        z_min = min(Z_MIN_MAX, max(Z_MIN_MIN, z_min))

        gk = _garman_klass(o, h, l, c)

        # Causal z: mean/std of PRIOR lookback bars only (exclude t via shift).
        prior = gk.shift(1)
        mean_prior = prior.rolling(lookback, min_periods=lookback).mean()
        std_prior = prior.rolling(lookback, min_periods=lookback).std(ddof=0)
        std_ok = std_prior.notna() & std_prior.gt(0)
        z = (gk - mean_prior) / std_prior.where(std_ok)

        spike = z.notna() & z.ge(z_min)
        up_bar = c.gt(o)
        down_bar = c.lt(o)

        # SHORT priority if both (mutually exclusive via body, but keep ~short).
        short_raw = spike & up_bar
        long_raw = spike & down_bar & ~short_raw.fillna(False)

        signals["gk"] = gk
        signals["gk_mean_prior"] = mean_prior
        signals["gk_std_prior"] = std_prior
        signals["z"] = z
        signals["spike"] = spike.fillna(False)
        signals["up_bar"] = up_bar.fillna(False)
        signals["down_bar"] = down_bar.fillna(False)

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
            # Score: how far z clears z_min, clipped.
            over = ((z - z_min) / z_min).clip(0.0, 1.0)
            signals.loc[entry, "score"] = over.fillna(0.0)[entry]

        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and sig != 0:
            reasons.loc[entry] = [
                (
                    f"{side}: gk z-spike fade z={float(z.loc[i]):.3f}>="
                    f"{z_min:.2f} gk={float(gk.loc[i]):.6g} "
                    f"{'up' if p.side is SignalSide.SHORT else 'down'}-bar "
                    f"c={float(c.loc[i]):.4f} o={float(o.loc[i]):.4f} "
                    f"lookback={lookback}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "GarmanKlassVolSpikeFadeParams",
    "GarmanKlassVolSpikeFadeStrategy",
    "CAUSAL_Z_PRIOR_LOOKBACK_LOCKED",
    "EPS_LOCKED",
    "FADE_SPIKE_BAR_BODY_LOCKED",
    "FORBID_CLV_LOCKED",
    "FORBID_COMPRESSION_LOCKED",
    "FORBID_DONCHIAN_LOCKED",
    "FORBID_EXTREME_FRAC_LOCKED",
    "FORBID_NEXT_THRU_MID_LOCKED",
    "FORBID_VOLUME_IN_SIGNAL_LOCKED",
    "FORBID_WICK_FRAC_LOCKED",
    "LOOKBACK_GRID",
    "LOOKBACK_MAX",
    "LOOKBACK_MIN",
    "OHLC_ONLY_GARMAN_KLASS_LOCKED",
    "OPTION_B_LOCKED",
    "Z_MIN_GRID",
    "Z_MIN_MAX",
    "Z_MIN_MIN",
    "_garman_klass",
]
