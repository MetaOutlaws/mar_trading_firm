"""Prior-day volume-profile POC reclaim fade. 4h/4h BOTH.

POC is the volume-profile point of control from the prior *completed* UTC
day only (00:00–24:00 UTC yesterday). The forming / incomplete current day
never contributes. Histogram binning is locked: 20 equal-width price bins
across that day's [low, high]; each bar's volume is spread uniformly across
overlapping bins; POC = midpoint of the highest-volume bin (see
``indicators.volume_profile_poc`` / ``prior_utc_day_volume_poc``).

Same-bar tag then reclaim toward value on the far side of POC:

    SHORT: high[t] >= POC - touch_tol_atr * ATR  AND  close[t] < POC
    LONG:  low[t]  <= POC + touch_tol_atr * ATR  AND  close[t] > POC

ATR is Wilder ATR(20) known *before* the signal bar (``atr.shift(1)``) so
bar ``t`` cannot widen its own tag band. No k-stretch geometry (not SMA/POC
distance stretch). The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH
    - Prior completed UTC-day volume-profile POC (never a forming day)
    - POC binning: 20 equal-width bins, volume histogram, bin midpoint
    - ATR period = 20, known before the signal bar
    - Reclaim = close strictly through POC (SHORT below / LONG above)
    - No k-stretch

Free search (1 only):

    - ``touch_tol_atr`` grid ``[0.0, 0.10]``

OHLCV + volume/turnover as available. Causal: bars ``<= t``.

Not ``prior_day_extreme_reject`` (118 — raw prior UTC day H/L).
Not ``sma20_stretch_fade`` (141 — SMA wick stretch + halfway reclaim).
Not ``keltner_channel_fade`` (Job 144 0/12 — do not revive).
Not ``keltner_break`` (close-through typical-price Keltner).
Not ``bb_medium_bw_upper_reject`` (BB + medium-BW).
Not ``outside_bar_fail_reversion`` (142 — outside containment then close-inside).
Not ``asia_range_london_reject`` (London tag of Asia H/L).
Not inventory fades (london_close / ny_close).
Not ``hvn_mean_revert`` / ``rolling_va_extreme_reject`` (rolling VA / HVN).
Not ``prior_day_vwap_reject`` / ``session_vwap_band_fade`` /
    ``utc_session_vwap_reversion`` / ``vwap_volatility_band_fade`` (VWAP, not POC).
Not ``displacement_gap_follow`` (PARKED — adjacent-bar gap follow).
Not ``week_open_reclaim`` / ``orb_fail_reversion``.
Do not recode spent families 118–144. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches touch_tol_atr only.
ATR_N_LOCKED = 20
# Locked histogram bins. Not a free search param.
POC_BINS_LOCKED = ind.POC_BINS_LOCKED


@dataclass(frozen=True)
class PriorPocReclaimFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Tag slack as a multiple of prior-bar ATR. Quant grid: [0.0, 0.10].
    touch_tol_atr: float = 0.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class PriorPocReclaimFadeStrategy(Strategy):
    name = "prior_poc_reclaim_fade"

    def __init__(self, params: PriorPocReclaimFadeParams | None = None) -> None:
        super().__init__(params or PriorPocReclaimFadeParams())
        self.params: PriorPocReclaimFadeParams = self.params
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

        # Prior completed UTC-day volume-profile POC. Forming day is excluded.
        poc = ind.prior_utc_day_volume_poc(
            high,
            low,
            volume,
            n_bins=POC_BINS_LOCKED,
            turnover=turnover,
        )
        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — the tag wick cannot lift the band.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & poc.notna()
        touch = touch_k * atr_known.fillna(0.0)

        # Tag = trade to (or through) POC within touch slack. Reclaim = close
        # strictly through POC toward value on the far side. No k-stretch.
        tagged_from_below = atr_ok & high.ge(poc - touch)
        tagged_from_above = atr_ok & low.le(poc + touch)
        closed_below = close.lt(poc)
        closed_above = close.gt(poc)
        short_raw = tagged_from_below & closed_below
        long_raw = tagged_from_above & closed_above

        signals["poc"] = poc
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["touch"] = touch
        signals["tagged_from_below"] = tagged_from_below.fillna(False)
        signals["tagged_from_above"] = tagged_from_above.fillna(False)
        signals["closed_below_poc"] = closed_below.fillna(False)
        signals["closed_above_poc"] = closed_above.fillna(False)

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
                depth = ((high - poc) / atr_safe).clip(0.0, 1.0)
            else:
                depth = ((poc - low) / atr_safe).clip(0.0, 1.0)
            signals.loc[entry, "score"] = depth.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: prior-POC reclaim-fade close {close.loc[i]:.4f} "
                    f"poc {poc.loc[i]:.4f} touch {touch.loc[i]:.4f} "
                    f"atr {atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "POC_BINS_LOCKED",
    "PriorPocReclaimFadeParams",
    "PriorPocReclaimFadeStrategy",
]
