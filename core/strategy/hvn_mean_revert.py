"""Prior-day HVN mean-revert. 4h/4h BOTH.

HVN set is the top ``lookback_nodes`` volume nodes from the prior
*completed* UTC-day volume profile only (00:00–24:00 UTC yesterday). The
forming / incomplete current day never contributes. Histogram binning is
the same locked definition as ``prior_poc_reclaim_fade``: 20 equal-width
price bins across that day's [low, high]; each bar's volume is spread
uniformly across overlapping bins; a node is a bin midpoint (see
``indicators.volume_profile_hvn_nodes`` / ``prior_utc_day_volume_hvns``).

The signal uses the *nearest* of that top-N set to the bar extreme
(SHORT → high[t], LONG → low[t]). ``lookback_nodes=1`` is the POC
(highest-volume bin) — same node as ``prior_poc_reclaim_fade``, but this
family also searches N>1 so a secondary HVN can fire when POC does not.

    SHORT: high[t] >= HVN - touch_tol_atr * ATR  AND  close[t] < HVN
    LONG:  low[t]  <= HVN + touch_tol_atr * ATR  AND  close[t] > HVN

ATR is Wilder ATR(20) known *before* the signal bar (``atr.shift(1)``) so
bar ``t`` cannot widen its own tag band. The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH
    - Family id ``hvn_mean_revert`` only (not ``hvn_node_fade``)
    - Prior completed UTC-day volume profile (never a forming day)
    - Same 20-bin occupancy histogram as prior_poc
    - Nearest-of-top-N HVN to the bar extreme
    - ATR period = 20, known before the signal bar
    - Fill at t+1 open

Free search (2 only):

    - ``lookback_nodes`` grid ``[1, 3]``
    - ``touch_tol_atr`` grid ``[0.0, 0.15]``

Withdrawn — do not code: ``leave_atr``, bar-lookback ``[20, 48]``,
``hvn_node_fade`` as an alternate family name.

OHLCV + volume/turnover as available. Causal: bars ``<= t``.

Not ``prior_poc_reclaim_fade`` (Job 145 — single prior-day POC only).
Not ``prior_day_vwap_reject`` / ``session_vwap_band_fade``.
Not ``session_volume_profile_reversal`` (skip-list — do not code).
Not ``asia_range_london_reject`` / london_close / ny_close inventory fades.
Not ``sma20_stretch_fade`` / ``keltner_channel_fade``.
Not ``prior_day_extreme_reject`` (118 — raw prior UTC day H/L).
Not ``rolling_va_extreme_reject`` (rolling value-area).
Do not recode spent families 118–145. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches lookback_nodes + touch_tol_atr.
ATR_N_LOCKED = 20
# Locked histogram bins. Same definition as prior_poc_reclaim_fade.
POC_BINS_LOCKED = ind.POC_BINS_LOCKED
# Free-grid HVN count. Clamped even if a caller tries to override.
LOOKBACK_NODES_MIN = 1
LOOKBACK_NODES_MAX = ind.HVN_LOOKBACK_NODES_MAX


@dataclass(frozen=True)
class HvnMeanRevertParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Top-N prior-day HVN nodes. Quant grid: [1, 3].
    lookback_nodes: int = LOOKBACK_NODES_MIN
    # Tag slack as a multiple of prior-bar ATR. Quant grid: [0.0, 0.15].
    touch_tol_atr: float = 0.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class HvnMeanRevertStrategy(Strategy):
    name = "hvn_mean_revert"

    def __init__(self, params: HvnMeanRevertParams | None = None) -> None:
        super().__init__(params or HvnMeanRevertParams())
        self.params: HvnMeanRevertParams = self.params
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
        # Searched knobs stay caller-set but stay inside the Quant grid.
        # Period / bin count stay locked even if atr_n is overridden.
        n_nodes = int(params.lookback_nodes)
        n_nodes = min(LOOKBACK_NODES_MAX, max(LOOKBACK_NODES_MIN, n_nodes))
        touch_k = float(params.touch_tol_atr)
        atr_n = ATR_N_LOCKED

        # Prior completed UTC-day HVN set. Forming day is excluded.
        # Always compute top-3 so lookback_nodes>1 can pick a secondary node
        # from the same frozen histogram as lookback_nodes=1 (POC).
        hvn_nodes = ind.prior_utc_day_volume_hvns(
            high,
            low,
            volume,
            n_bins=POC_BINS_LOCKED,
            top_n=LOOKBACK_NODES_MAX,
            turnover=turnover,
        )
        # SHORT uses the bar high; LONG uses the bar low. Nearest of top-N.
        if params.side is SignalSide.SHORT:
            extreme = high
        elif params.side is SignalSide.LONG:
            extreme = low
        else:
            extreme = close
        hvn = ind.nearest_hvn_to_extreme(
            hvn_nodes, extreme, lookback_nodes=n_nodes
        )
        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — the tag wick cannot lift the band.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & hvn.notna()
        touch = touch_k * atr_known.fillna(0.0)

        tagged_from_below = atr_ok & high.ge(hvn - touch)
        tagged_from_above = atr_ok & low.le(hvn + touch)
        closed_below = close.lt(hvn)
        closed_above = close.gt(hvn)
        short_raw = tagged_from_below & closed_below
        long_raw = tagged_from_above & closed_above

        signals["hvn"] = hvn
        signals["hvn_1"] = hvn_nodes["hvn_1"]
        signals["hvn_2"] = hvn_nodes["hvn_2"]
        signals["hvn_3"] = hvn_nodes["hvn_3"]
        signals["lookback_nodes"] = n_nodes
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["touch"] = touch
        signals["tagged_from_below"] = tagged_from_below.fillna(False)
        signals["tagged_from_above"] = tagged_from_above.fillna(False)
        signals["closed_below_hvn"] = closed_below.fillna(False)
        signals["closed_above_hvn"] = closed_above.fillna(False)

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
                depth = ((high - hvn) / atr_safe).clip(0.0, 1.0)
            else:
                depth = ((hvn - low) / atr_safe).clip(0.0, 1.0)
            signals.loc[entry, "score"] = depth.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: prior-HVN mean-revert close {close.loc[i]:.4f} "
                    f"hvn {hvn.loc[i]:.4f} n={n_nodes} touch {touch.loc[i]:.4f} "
                    f"atr {atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "LOOKBACK_NODES_MAX",
    "LOOKBACK_NODES_MIN",
    "POC_BINS_LOCKED",
    "HvnMeanRevertParams",
    "HvnMeanRevertStrategy",
]
