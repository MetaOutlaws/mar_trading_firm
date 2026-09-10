"""Prior completed UTC-day VWAP stretch reject. 4h/4h BOTH.

VWAP is the session VWAP of the prior *completed* UTC day only
(00:00–24:00 UTC yesterday, typical-price volume/turnover weighted).
The forming / incomplete current day never contributes. This is not
developing ``utc_session_vwap``, not swing AVWAP, not rolling VWAP,
and not a VWAP-band / spread sleeve.

Same-bar wick stretch vs that locked prior-day VWAP, then reclaim
halfway back toward VWAP:

    SHORT: high[t] >= VWAP + k * ATR  AND  close[t] < VWAP + 0.5 * k * ATR
    LONG:  low[t]  <= VWAP - k * ATR  AND  close[t] > VWAP - 0.5 * k * ATR

ATR is Wilder ATR(20) known *before* the signal bar (``atr.shift(1)``) so
bar ``t`` cannot widen its own stretch band. The engine fills at ``t+1``
open.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH
    - Prior completed UTC-day session VWAP only (never a forming day)
    - ATR period = 20, known before the signal bar
    - Reject toward VWAP (halfway reclaim, frac = 0.5)
    - Fill at t+1 open

Free search (1 only):

    - ``k`` grid ``[1.0, 1.5]``

OHLCV + volume/turnover as available. Causal: bars ``<= t``.

Not ``utc_session_vwap_reversion`` (90 — developing UTC-day VWAP).
Not ``swing_anchored_vwap_pullback`` (94 — swing AVWAP).
Not ``vwap_spread_exhaustion`` (98 — rolling VWAP vs SMA spread).
Not ``vwap_volatility_band_fade`` (99 — rolling VWAP ± σ + BB squeeze).
Not inventory fades (london_close / ny_close).
Not ``prior_poc_reclaim_fade`` (Job 145 — single prior-day POC).
Not ``hvn_mean_revert`` (Job 146 — nearest-of-top-N HVN).
Not ``rolling_va_extreme_reject`` (rolling value-area).
Not ``sma20_stretch_fade`` (141 — SMA wick stretch + halfway reclaim).
Not ``keltner_channel_fade`` (Job 144 0/12 — do not revive).
Not ``prior_day_extreme_reject`` (118 — raw prior UTC day H/L).
Do not recode spent families 118–146. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches k only.
ATR_N_LOCKED = 20
# Reclaim line sits halfway from the k*ATR stretch back toward VWAP.
RECLAIM_FRAC_LOCKED = 0.5


@dataclass(frozen=True)
class PriorDayVwapRejectParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Stretch distance in ATR units from prior-day VWAP. Quant grid: [1.0, 1.5].
    k: float = 1.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class PriorDayVwapRejectStrategy(Strategy):
    name = "prior_day_vwap_reject"

    def __init__(self, params: PriorDayVwapRejectParams | None = None) -> None:
        super().__init__(params or PriorDayVwapRejectParams())
        self.params: PriorDayVwapRejectParams = self.params
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
        # Searched k stays caller-set. Period / reclaim frac stay locked
        # even if a caller tries to override atr_n on the params object.
        k = float(params.k)
        atr_n = ATR_N_LOCKED
        reclaim_frac = RECLAIM_FRAC_LOCKED

        # Prior completed UTC-day session VWAP. Forming day is excluded.
        vwap = ind.prior_utc_day_session_vwap(
            high, low, close, volume, turnover=turnover
        )
        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — the stretch wick cannot lift the band.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & vwap.notna()
        atr_safe = atr_known.replace(0, pd.NA)

        # Wick stretch from prior-day VWAP, in known-before ATR units.
        stretch_below_atr = (vwap - low) / atr_safe
        stretch_above_atr = (high - vwap) / atr_safe
        stretched_below = atr_ok & stretch_below_atr.ge(k)
        stretched_above = atr_ok & stretch_above_atr.ge(k)

        # Halfway back toward VWAP: 0.5 * k * ATR from the magnet.
        half = reclaim_frac * k * atr_known
        reclaimed_long = close.gt(vwap - half)
        reclaimed_short = close.lt(vwap + half)

        long_raw = stretched_below & reclaimed_long
        short_raw = stretched_above & reclaimed_short

        signals["vwap"] = vwap
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["stretch_below_atr"] = stretch_below_atr
        signals["stretch_above_atr"] = stretch_above_atr
        signals["stretched_below"] = stretched_below.fillna(False)
        signals["stretched_above"] = stretched_above.fillna(False)
        signals["reclaimed_toward_vwap_long"] = reclaimed_long.fillna(False)
        signals["reclaimed_toward_vwap_short"] = reclaimed_short.fillna(False)

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            stretch_atr = stretch_below_atr
        elif params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            stretch_atr = stretch_above_atr
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value
            stretch_atr = pd.Series(pd.NA, index=candles.index, dtype="float64")

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the wick extends further past k*ATR.
            excess = ((stretch_atr - k) / k).clip(0.0, 1.0)
            signals.loc[entry, "score"] = excess.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: prior-day VWAP reject vwap {vwap.loc[i]:.4f} "
                    f"close {close.loc[i]:.4f} high {high.loc[i]:.4f} "
                    f"low {low.loc[i]:.4f} stretch {float(stretch_atr.loc[i]):.3f} "
                    f"atr {atr_known.loc[i]:.4f} k={k:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "RECLAIM_FRAC_LOCKED",
    "PriorDayVwapRejectParams",
    "PriorDayVwapRejectStrategy",
]
