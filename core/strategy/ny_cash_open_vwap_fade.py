"""NY cash-open VWAP fade — stretch from the 13:00 UTC anchor, then reclaim.

Garwe stamp. Option B exploratory. SCORE/RETIRE only. Not an approval.

US cash open (13:00 UTC) starts a new fair-value clock. A 4h bar that
wicks at least ``k`` ATR(20) away from the cash-open VWAP and closes
back inside the halfway band is a fade toward that VWAP. Hold is the
engine's standard percent TP/SL plus fees. This is not drive
continuation and not a UTC-midnight VWAP.

    Anchor: first bar of the UTC day with hour_utc in [13, 16]
            (on 4h that is the 16:00 bar — hour 12 is outside the window)
    VWAP:   running HLC3×volume from that bar through the rest of the day
    SHORT:  (high - VWAP) >= k·ATR20  AND  close < VWAP + 0.5·k·ATR20
    LONG:   (VWAP - low)  >= k·ATR20  AND  close > VWAP - 0.5·k·ATR20

BOTH sides honest, SHORT priority: a bar that prints both fades is
SHORT, not LONG. At most one entry per UTC day per side. The engine
fills at ``t+1`` open. No signal on bars before 13:00 UTC (VWAP is NaN
until the anchor).

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority on two-sided bars)
    - Family id ``ny_cash_open_vwap_fade`` only
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - A caller-supplied ``atr_n`` is ignored so the sleeve cannot become ATR14
    - Halfway reclaim (frac = 0.5); strict close back inside the band
    - NY cash-open anchor only (not UTC 00:00, not a swing pivot,
      not a prior-day frozen VWAP)
    - One entry per UTC calendar day per side
    - Fill at t+1 open (engine convention)
    - Desk research pairs are the standard six majors
      (BTC/ETH/BNB/XRP/SOL/AVAX); this module does not narrow them
    - Exits are the shared walk-forward TP/SL kit plus fees.
      ``k`` is the only family free param. TP is not frozen at 0.05
      and ``stop_loss_pct`` is not a family search axis.

Free search (1 only):

    - ``k`` grid ``[1.0, 1.5]`` (endpoints only — do not insert 1.25).
      Unit is ATR(20) distance from the cash-open VWAP. Not a
      standard-deviation band and not a fraction of the VWAP.

Not ``ny_cash_open_drive`` (trade the cash-open hour's direction).
Not ``utc_session_vwap_reversion`` (VWAP from UTC midnight).
Not ``prior_day_vwap_reject`` (yesterday's finished VWAP, frozen).
Not ``swing_anchored_vwap_pullback`` (Job 94, dead).
Not ``up_down_turnover_imbalance`` / ``signed_range_turnover_trend``
(Jobs 92–93, dead).
Not ``bar_vwap_inflow_surge`` (per-bar VWAP pulse, dead).
Not a wick-fail template (inside-bar / thrust / key-reversal /
swing-break).
Job 154 ``three_push_exhaustion_fail`` is RETIRE 0/12. Do not revive it.
Not Job 133 ``bullish_rectangle_fail_reclaim``.
Protect book stays Research 12 + Overrides 56. This module does not
write approvals.
Do not modify sibling geometry. Do not set ``approved=true``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches k only. Never ATR(14).
ATR_N_LOCKED = 20
# Reclaim line sits halfway from the k·ATR stretch back toward VWAP.
RECLAIM_FRAC_LOCKED = 0.5
# Free-grid stretch in ATR(20) units. Endpoints only. Do not insert 1.25.
K_MIN = 1.0
K_MAX = 1.5
K_GRID = [1.0, 1.5]
# One signal per UTC calendar day on each side instance.
ONE_ENTRY_PER_UTC_DAY_LOCKED = True


@dataclass(frozen=True)
class NyCashOpenVwapFadeParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    # generate_signals ignores any other value so ATR14 cannot be selected.
    atr_n: int = ATR_N_LOCKED
    # Stretch distance in ATR(20) units from the NY cash-open VWAP.
    # Quant grid: [1.0, 1.5]. Not 1.25. Not a percent stretch.
    k: float = K_MIN
    # Shared desk defaults. The walk searches the standard kit
    # [0.03, 0.05] × [0.02, 0.03]. Neither value is frozen, and
    # stop_loss_pct is not a family free axis.
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class NyCashOpenVwapFadeStrategy(Strategy):
    name = "ny_cash_open_vwap_fade"

    def __init__(self, params: NyCashOpenVwapFadeParams | None = None) -> None:
        super().__init__(params or NyCashOpenVwapFadeParams())
        self.params: NyCashOpenVwapFadeParams = self.params
        # ATR(20) seed plus the shift that publishes ATR known before bar t.
        self.min_bars = ATR_N_LOCKED + 1

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
        # Searched k stays caller-set. Period and reclaim frac stay locked
        # even if a caller passes atr_n=14 on the params object.
        k = float(params.k)
        atr_n = ATR_N_LOCKED
        reclaim_frac = RECLAIM_FRAC_LOCKED

        # Cash-open VWAP. Pre-13:00 bars are NaN; the cumsum resets each day.
        is_anchor, in_session, hour = ind.ny_cash_open_session(candles.index)
        vwap = ind.ny_cash_open_vwap(high, low, close, volume)
        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — the stretch wick cannot lift the band.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & vwap.notna() & in_session & hour.ge(ind.NY_CASH_OPEN_HOUR)
        atr_safe = atr_known.replace(0, pd.NA)

        # Wick stretch from the developing cash-open VWAP, in known-before ATR.
        stretch_below_atr = (vwap - low) / atr_safe
        stretch_above_atr = (high - vwap) / atr_safe
        stretched_below = atr_ok & stretch_below_atr.ge(k)
        stretched_above = atr_ok & stretch_above_atr.ge(k)

        # Halfway back toward VWAP. Equality is not a reclaim (strict close).
        half = reclaim_frac * k * atr_known
        reclaimed_long = close.gt(vwap - half)
        reclaimed_short = close.lt(vwap + half)

        long_raw = stretched_below & reclaimed_long
        short_raw = stretched_above & reclaimed_short
        # SHORT priority: a two-sided fade is SHORT, not LONG.
        long_raw = long_raw & (~short_raw)

        signals["vwap"] = vwap
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["hour_utc"] = hour
        signals["is_anchor"] = is_anchor
        signals["in_session"] = in_session
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
        if ONE_ENTRY_PER_UTC_DAY_LOCKED and signal_value != 0:
            # First qualifying bar of the UTC day only. The other side is a
            # separate strategy instance, so this is one entry per side.
            day_key = ind.utc_day_key(candles.index)
            entry = entry & entry.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the wick extends further past k·ATR.
            excess = ((stretch_atr - k) / k).clip(0.0, 1.0)
            signals.loc[entry, "score"] = excess.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: NY cash-open VWAP reclaim vwap {vwap.loc[i]:.4f} "
                    f"close {close.loc[i]:.4f} high {high.loc[i]:.4f} "
                    f"low {low.loc[i]:.4f} stretch {float(stretch_atr.loc[i]):.3f} "
                    f"atr20 {atr_known.loc[i]:.4f} k={k:.2f} "
                    f"hour {float(hour.loc[i]):.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "K_GRID",
    "K_MAX",
    "K_MIN",
    "ONE_ENTRY_PER_UTC_DAY_LOCKED",
    "RECLAIM_FRAC_LOCKED",
    "NyCashOpenVwapFadeParams",
    "NyCashOpenVwapFadeStrategy",
]
