"""Three-push exhaustion fail — three sized successive extremes, then fail to extend.

Family J. FINAL AUTHORITATIVE stamp (Brian), Job ~154 Option B exploratory.
Implement exactly. Three successive *pushes* live on bars ``t-3, t-2, t-1``.
Bar ``t`` is the fail-to-extend print (not a fourth push):

    SHORT: three successive higher-highs, each sized vs ATR20
           high[t-3] > high[t-4] AND (high[t-3]-high[t-4]) > min_push_atr·ATR
           high[t-2] > high[t-3] AND (high[t-2]-high[t-3]) > min_push_atr·ATR
           high[t-1] > high[t-2] AND (high[t-1]-high[t-2]) > min_push_atr·ATR
           AND high[t] <= high[t-1]          # fail to make a 4th higher high
           AND t-4 was not also a sized HH   # exact n_pushes=3, not 4+
    LONG:  three successive lower-lows, each sized vs ATR20 (mirror)
           low[t-3] < low[t-4] AND (low[t-4]-low[t-3]) > min_push_atr·ATR
           low[t-2] < low[t-3] AND (low[t-3]-low[t-2]) > min_push_atr·ATR
           low[t-1] < low[t-2] AND (low[t-2]-low[t-1]) > min_push_atr·ATR
           AND low[t] >= low[t-1]            # fail to make a 4th lower low
           AND t-4 was not also a sized LL

BOTH sides honest, SHORT priority: when both raw conditions print on the
same bar, SHORT fires and LONG does not. ATR is Wilder ATR(20) known
*before* the signal bar (``atr.shift(1)``) so bar ``t`` cannot lift the
size gate. All three push sizes are measured against that same known-before
ATR. The engine fills at ``t+1`` open. No volume gate. No session gate.

A push is a *successive bar extreme*, not a confirmed pivot and not a
lookback-N swing. Fail-to-extend is "did not print a 4th extreme" — not a
same-bar wick-through that closes back, not a reverse-body key reversal.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority on two-sided bars)
    - Family id ``three_push_exhaustion_fail`` only
    - n_pushes = 3 (exact run ending at t-1; 2 or 4+ do not fire)
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - Fail = bar t does not extend the 3rd push extreme
    - Size gate is strict ``>`` (an exact min_push_atr·ATR step is not a push)
    - Fill at t+1 open (engine convention)
    - No volume / session gate

Free search (1 only):

    - ``min_push_atr`` grid ``[0.15, 0.35]`` (endpoints only — same sibling
      float-grid convention as ``outside_bar_fail_reversion.min_outside_atr``
      / ``inside_bar_break_fail.min_mother_atr`` / ``key_reversal_bar.min_break_atr``;
      do not invent interiors)

Not ``consecutive_bar_exhaustion`` (fade after N directional *closes*, no
ATR push floor, no fail-to-extend bar).
Not ``failed_higher_high`` (two consecutive *confirmed* swings).
Not ``swing_break_fail_reversion`` (family I — lookback-N wick-through then
close back through the swing).
Not ``swing_failure_reversal`` (confirmed N-bar pivots, any wick, no ATR
size floor).
Not ``key_reversal_bar`` (family H / Job 152 — single t vs t-1 extreme +
reverse body).
Not ``thrust_bar_fail_reversion`` (family G / Job 151 — t-1 thrust then
close inside prior).
Not ``inside_bar_break_fail`` (family F — IB mother wick-fail).
Not ``outside_bar_reversal`` / ``outside_bar_fail_reversion`` (both-rail
containment).
Not ``expansion_fail_fade``. Not ``candle_reject_reversal``.
Not ``three_white_soldiers`` / ``three_black_crows`` / ``three_bar_play``.
Not ``failed_range_break_reversion`` (119). Not ``failed_break_reclaim``
(130). Not ``wyckoff_spring_reclaim`` (127).
Not dead VP (``prior_poc_reclaim_fade`` / ``hvn_mean_revert`` /
``lvn_fill_reject`` / ``rolling_va_extreme_reject``).
Not Job 133 ``bullish_rectangle_fail_reclaim`` (DEAD 0/12 — no-recode /
no-spawn). Not Job 144 ``keltner_channel_fade`` (0/12). Not
``utc_open_fail_reversion`` (0/12).
Hold H&S / asia / wyckoff alone.
Do not recode spent families 118–153. Do not revive Job 133 rectangle.
Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches min_push_atr only.
ATR_N_LOCKED = 20
# Locked push count. Three successive extremes, then fail. Not searched.
N_PUSHES_LOCKED = 3
# Free-grid push size in ATR units. Endpoints only.
MIN_PUSH_ATR_MIN = 0.15
MIN_PUSH_ATR_MAX = 0.35
MIN_PUSH_ATR_GRID = [0.15, 0.35]


@dataclass(frozen=True)
class ThreePushExhaustionFailParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Successive-push count. Quant-locked at 3 — not a free search param.
    n_pushes: int = N_PUSHES_LOCKED
    # Minimum successive-extreme size in ATR units. Quant grid: [0.15, 0.35].
    min_push_atr: float = MIN_PUSH_ATR_MIN
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ThreePushExhaustionFailStrategy(Strategy):
    name = "three_push_exhaustion_fail"

    def __init__(self, params: ThreePushExhaustionFailParams | None = None) -> None:
        super().__init__(params or ThreePushExhaustionFailParams())
        self.params: ThreePushExhaustionFailParams = self.params
        # ATR seed + 3 pushes + baseline t-4 + exact-3 predecessor t-5 + fail t.
        self.min_bars = ATR_N_LOCKED + N_PUSHES_LOCKED + 3

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
        # Searched push floor stays caller-set so the 0.15 vs 0.35 grid matters.
        # n_pushes / atr_n stay locked even if a caller overrides the dataclass.
        min_push = float(params.min_push_atr)
        atr_n = ATR_N_LOCKED
        n_pushes = N_PUSHES_LOCKED

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)

        # Pushes live on t-3, t-2, t-1. Each step is vs the prior bar's extreme.
        # Size uses the same known-before ATR at t (causal at the signal bar).
        hh1 = high.shift(3) - high.shift(4)
        hh2 = high.shift(2) - high.shift(3)
        hh3 = high.shift(1) - high.shift(2)
        # Predecessor at t-4: a sized HH here would make the run 4+, not 3.
        hh0 = high.shift(4) - high.shift(5)
        ll1 = low.shift(4) - low.shift(3)
        ll2 = low.shift(3) - low.shift(2)
        ll3 = low.shift(2) - low.shift(1)
        ll0 = low.shift(5) - low.shift(4)

        # Munha + Marcus lock (same as family I): size gate is strict `>`.
        # A step that lands exactly on min_push_atr·ATR is not a push.
        sized_hh1 = atr_ok & hh1.gt(min_push * atr_known)
        sized_hh2 = atr_ok & hh2.gt(min_push * atr_known)
        sized_hh3 = atr_ok & hh3.gt(min_push * atr_known)
        sized_hh0 = atr_ok & hh0.gt(min_push * atr_known)
        sized_ll1 = atr_ok & ll1.gt(min_push * atr_known)
        sized_ll2 = atr_ok & ll2.gt(min_push * atr_known)
        sized_ll3 = atr_ok & ll3.gt(min_push * atr_known)
        sized_ll0 = atr_ok & ll0.gt(min_push * atr_known)

        three_up = sized_hh1 & sized_hh2 & sized_hh3
        three_down = sized_ll1 & sized_ll2 & sized_ll3
        # Exact n_pushes=3: the bar before the first push was not a sized push.
        exact_three_up = three_up & (~sized_hh0)
        exact_three_down = three_down & (~sized_ll0)

        prior_high = high.shift(1)
        prior_low = low.shift(1)
        # Fail-to-extend: bar t does not print a 4th higher high / lower low.
        # An equal extreme is a fail (did not extend). A 4th push is not.
        fail_extend_up = prior_high.notna() & ~high.gt(prior_high)
        fail_extend_down = prior_low.notna() & ~low.lt(prior_low)

        short_raw = exact_three_up & fail_extend_up
        long_raw = exact_three_down & fail_extend_down
        # SHORT priority: a two-sided fail is SHORT, not LONG.
        long_raw = long_raw & (~short_raw)

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["n_pushes"] = n_pushes
        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["hh1"] = hh1
        signals["hh2"] = hh2
        signals["hh3"] = hh3
        signals["ll1"] = ll1
        signals["ll2"] = ll2
        signals["ll3"] = ll3
        signals["push1_up_atr"] = hh1 / atr_safe
        signals["push2_up_atr"] = hh2 / atr_safe
        signals["push3_up_atr"] = hh3 / atr_safe
        signals["push1_dn_atr"] = ll1 / atr_safe
        signals["push2_dn_atr"] = ll2 / atr_safe
        signals["push3_dn_atr"] = ll3 / atr_safe
        signals["sized_hh1"] = sized_hh1.fillna(False)
        signals["sized_hh2"] = sized_hh2.fillna(False)
        signals["sized_hh3"] = sized_hh3.fillna(False)
        signals["sized_ll1"] = sized_ll1.fillna(False)
        signals["sized_ll2"] = sized_ll2.fillna(False)
        signals["sized_ll3"] = sized_ll3.fillna(False)
        signals["three_up"] = three_up.fillna(False)
        signals["three_down"] = three_down.fillna(False)
        signals["exact_three_up"] = exact_three_up.fillna(False)
        signals["exact_three_down"] = exact_three_down.fillna(False)
        signals["fail_extend_up"] = fail_extend_up.fillna(False)
        signals["fail_extend_down"] = fail_extend_down.fillna(False)

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
            # Stronger when the fail sits further from extending the 3rd push.
            if params.side is SignalSide.SHORT:
                score = ((prior_high - high) / atr_safe).clip(0.0, 1.0)
            else:
                score = ((low - prior_low) / atr_safe).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: three-push exhaustion-fail "
                    f"n={n_pushes} close {close.loc[i]:.4f} "
                    f"after 3rd {'HH' if params.side is SignalSide.SHORT else 'LL'} "
                    f"{prior_high.loc[i]:.4f}/{prior_low.loc[i]:.4f} "
                    f"push>{min_push:.2f}×ATR {atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "MIN_PUSH_ATR_GRID",
    "MIN_PUSH_ATR_MAX",
    "MIN_PUSH_ATR_MIN",
    "N_PUSHES_LOCKED",
    "ThreePushExhaustionFailParams",
    "ThreePushExhaustionFailStrategy",
]
