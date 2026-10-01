"""Amihud illiquidity spike fade — fade a |ret|/turnover z-spike bar.

Option B. Garwe STAMP LOCK. Live off. Do not set approved=true. No walk.
Protect 12+56. Soft-watch Job 103 EXPLICIT.

Geometry (≠ Job 103 turnover_climax_rejection_fade):

103 = turnover NEW 20-bar high + break prior-20 H/L + close reject_frac
      inside the climax bar.
This = Amihud |ret|/turnover (or volume*close) z-spike vs prior lookback;
      fade the spike-bar body direction. NO prior H/L break. NO reject_frac.
      Soft-watch 103 EXPLICIT at SCORE (do not collapse to climax+reject).

Amihud_t = abs(close_t/close_{t-1}-1) / max(turnover_t or volume_t*close_t, eps)
z_t      = (amihud_t - mean(amihud, prior lookback)) / std(amihud, prior lookback)
           causal: mean/std of PRIOR lookback bars only (shift exclude t)

SHORT: z_t >= z_min AND close_t > open_t  (fade up-bar spike)
LONG:  z_t >= z_min AND close_t < open_t  (fade down-bar spike)

BOTH SHORT priority on two-sided bars.
Fill t+1 open (engine). Free ≤2: lookback {20, 40}, z_min {2.0, 2.5}.
FORBID extreme_frac / next-thru-mid / CLV params.
No VP / session VWAP. Prefer existing turnover/quote_volume column; else
volume*close. No new quote feed.
Do NOT fork turnover_climax_rejection_fade, up_down_turnover_imbalance,
volume_imbalance_delta_reversal, volume_dryup_range_break,
bar_vwap_inflow_surge, impulse_midpoint_fail_fade, two_bar_run_mid_fail.
"""

from __future__ import annotations

import pandas as pd

from core.strategy.base import SignalSide, Strategy
from core.strategy.amihud_illiquidity_spike_fade_params import (
    CAUSAL_Z_PRIOR_LOOKBACK_LOCKED,
    EPS_LOCKED,
    FADE_SPIKE_BAR_BODY_LOCKED,
    FORBID_CLV_LOCKED,
    FORBID_EXTREME_FRAC_LOCKED,
    FORBID_NEXT_THRU_MID_LOCKED,
    LOOKBACK_GRID,
    LOOKBACK_MAX,
    LOOKBACK_MIN,
    OPTION_B_LOCKED,
    USE_EXISTING_TURNOVER_OR_VOLUME_X_CLOSE_LOCKED,
    Z_MIN_GRID,
    Z_MIN_MAX,
    Z_MIN_MIN,
    AmihudIlliquiditySpikeFadeParams,
)


def _quote_proxy(candles: pd.DataFrame) -> pd.Series:
    """Prefer turnover/quote_volume if present; else volume*close. No new feed."""
    close = candles["close"].astype("float64")
    volume = candles["volume"].astype("float64")
    for col in ("turnover", "quote_volume", "quoteVolume"):
        if col in candles.columns:
            return candles[col].astype("float64")
    return volume * close


class AmihudIlliquiditySpikeFadeStrategy(Strategy):
    name = "amihud_illiquidity_spike_fade"

    def __init__(self, params: AmihudIlliquiditySpikeFadeParams | None = None) -> None:
        super().__init__(params or AmihudIlliquiditySpikeFadeParams())
        self.params: AmihudIlliquiditySpikeFadeParams = self.params
        # Prior close for ret + lookback window after shift + signal bar.
        self.min_bars = int(self.params.lookback) + 3

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
            and OPTION_B_LOCKED
            and USE_EXISTING_TURNOVER_OR_VOLUME_X_CLOSE_LOCKED
        ):
            raise RuntimeError("amihud_illiquidity_spike_fade locks were edited")

        o = candles["open"].astype("float64")
        c = candles["close"].astype("float64")

        lookback = int(p.lookback)
        lookback = min(LOOKBACK_MAX, max(LOOKBACK_MIN, lookback))
        z_min = float(p.z_min)
        z_min = min(Z_MIN_MAX, max(Z_MIN_MIN, z_min))

        # Amihud: |ret| / max(quote proxy, eps).
        ret = c / c.shift(1) - 1.0
        quote = _quote_proxy(candles)
        denom = quote.clip(lower=EPS_LOCKED)
        amihud = ret.abs() / denom

        # Causal z: mean/std of PRIOR lookback bars only (exclude t via shift).
        prior = amihud.shift(1)
        mean_prior = prior.rolling(lookback, min_periods=lookback).mean()
        std_prior = prior.rolling(lookback, min_periods=lookback).std(ddof=0)
        std_ok = std_prior.notna() & std_prior.gt(0)
        z = (amihud - mean_prior) / std_prior.where(std_ok)

        spike = z.notna() & z.ge(z_min)
        up_bar = c.gt(o)
        down_bar = c.lt(o)

        short_raw = spike & up_bar
        long_raw = spike & down_bar & ~short_raw.fillna(False)

        signals["ret"] = ret
        signals["quote_proxy"] = quote
        signals["amihud"] = amihud
        signals["amihud_mean_prior"] = mean_prior
        signals["amihud_std_prior"] = std_prior
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
                    f"{side}: amihud z-spike fade z={float(z.loc[i]):.3f}>="
                    f"{z_min:.2f} |ret|={float(abs(ret.loc[i])):.6f} "
                    f"quote={float(quote.loc[i]):.4f} "
                    f"{'up' if p.side is SignalSide.SHORT else 'down'}-bar "
                    f"c={float(c.loc[i]):.4f} o={float(o.loc[i]):.4f} "
                    f"lookback={lookback}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "AmihudIlliquiditySpikeFadeParams",
    "AmihudIlliquiditySpikeFadeStrategy",
    "CAUSAL_Z_PRIOR_LOOKBACK_LOCKED",
    "EPS_LOCKED",
    "FADE_SPIKE_BAR_BODY_LOCKED",
    "FORBID_CLV_LOCKED",
    "FORBID_EXTREME_FRAC_LOCKED",
    "FORBID_NEXT_THRU_MID_LOCKED",
    "LOOKBACK_GRID",
    "LOOKBACK_MAX",
    "LOOKBACK_MIN",
    "OPTION_B_LOCKED",
    "USE_EXISTING_TURNOVER_OR_VOLUME_X_CLOSE_LOCKED",
    "Z_MIN_GRID",
    "Z_MIN_MAX",
    "Z_MIN_MIN",
    "_quote_proxy",
]
