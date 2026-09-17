"""Three-push exhaustion fail — three prior HH/LL, then fail + strong close.

Family J. FINAL AUTHORITATIVE stamp (Garwe + Marcus — Garwe geometry
SUPERSEDES looser Munha fail-to-extend OR). Job ~154 Option B
exploratory. Implement exactly.

Three prior pushes live on bars ``t-3, t-2, t-1``. Bar ``t`` is the
exhaustion print. Size is the two successive advances among those
three extremes vs Wilder ATR(20) known *before* the signal bar
(``atr.shift(1)``). Fail is *not* fail-to-extend alone: bar ``t`` must
also print a strong reverse close.

    SHORT:
        high[t-3] < high[t-2] < high[t-1]
        AND (high[t-2] - high[t-3]) >= min_push_atr * ATR20
        AND (high[t-1] - high[t-2]) >= min_push_atr * ATR20
        AND high[t] <= high[t-1]
        AND close[t] < open[t]
        AND close[t] < close[t-1]
    LONG (inverse):
        low[t-3] > low[t-2] > low[t-1]
        AND (low[t-3] - low[t-2]) >= min_push_atr * ATR20
        AND (low[t-2] - low[t-1]) >= min_push_atr * ATR20
        AND low[t] >= low[t-1]
        AND close[t] > open[t]
        AND close[t] > close[t-1]

BOTH sides honest, SHORT priority: when both raw conditions print on the
same bar, SHORT fires and LONG does not. The engine fills at ``t+1``
open. No volume gate. No session gate. No VP.

A push is a successive *bar* extreme, not a confirmed pivot and not a
lookback-N swing. The fail conjuncts are fail-new-extreme AND strong
close — not a same-bar wick-through that closes back, not a key
reversal (that family *breaks* t-1's extreme on bar t).

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority on two-sided bars)
    - Family id ``three_push_exhaustion_fail`` only
    - Exactly 3 prior pushes (bars t-3, t-2, t-1; n_pushes not searched)
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - Size gate is ``>=`` (an exact min_push_atr·ATR advance *is* a push)
    - Fail = no 4th extreme AND strong reverse close vs open and vs prior close
    - Fill at t+1 open (engine convention)
    - No volume / session / VP gate

Free search (1 only):

    - ``min_push_atr`` grid ``[0.15, 0.35]`` (endpoints only — same sibling
      float-grid convention as ``outside_bar_fail_reversion.min_outside_atr``
      / ``inside_bar_break_fail.min_mother_atr`` / ``key_reversal_bar.min_break_atr``.
      Do NOT use ``[0.3, 0.6]``. Do not invent interiors)

Not ``consecutive_bar_exhaustion`` (fade after N directional *closes*, no
ATR push floor, no fail-to-extend bar).
Not ``failed_higher_high`` (two consecutive *confirmed* swings).
Not ``swing_break_fail_reversion`` (family I — lookback-N wick-through then
close back through the swing).
Not ``swing_failure_reversal`` (confirmed N-bar pivots, any wick, no ATR
size floor).
Not ``key_reversal_bar`` (family H / Job 152 — bar t *breaks* t-1 extreme
then reverse body; this family fails to make a 4th extreme).
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
# Locked push count: bars t-3, t-2, t-1. Not searched.
N_PUSHES_LOCKED = 3
# Quant-locked True: fail close must reverse vs open and vs prior close.
REQUIRE_STRONG_CLOSE_LOCKED = True
# Free-grid push size in ATR units. Endpoints only. Do NOT use [0.3, 0.6].
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
    # Minimum successive-extreme advance in ATR units. Quant grid: [0.15, 0.35].
    min_push_atr: float = MIN_PUSH_ATR_MIN
    # Quant-locked True: fade only if bar t prints a strong reverse close.
    require_strong_close: bool = REQUIRE_STRONG_CLOSE_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ThreePushExhaustionFailStrategy(Strategy):
    name = "three_push_exhaustion_fail"

    def __init__(self, params: ThreePushExhaustionFailParams | None = None) -> None:
        super().__init__(params or ThreePushExhaustionFailParams())
        self.params: ThreePushExhaustionFailParams = self.params
        # ATR seed + exactly 3 prior push bars + the fail/strong-close print.
        self.min_bars = ATR_N_LOCKED + N_PUSHES_LOCKED + 1

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        open_ = candles["open"]
        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        # Searched push floor stays caller-set so the 0.15 vs 0.35 grid matters.
        # n_pushes / atr_n / strong-close stay locked even if a caller overrides.
        min_push = float(params.min_push_atr)
        atr_n = ATR_N_LOCKED
        n_pushes = N_PUSHES_LOCKED

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)

        high_t3 = high.shift(3)
        high_t2 = high.shift(2)
        high_t1 = high.shift(1)
        low_t3 = low.shift(3)
        low_t2 = low.shift(2)
        low_t1 = low.shift(1)
        prior_close = close.shift(1)

        # Two successive advances among the three prior extremes.
        # Garwe lock: size gate is ``>=`` — an exact min_push_atr·ATR step counts.
        push1_up = high_t2 - high_t3
        push2_up = high_t1 - high_t2
        push1_dn = low_t3 - low_t2
        push2_dn = low_t2 - low_t1
        rising = high_t3.notna() & high_t3.lt(high_t2) & high_t2.lt(high_t1)
        falling = low_t3.notna() & low_t3.gt(low_t2) & low_t2.gt(low_t1)
        sized_up1 = atr_ok & push1_up.ge(min_push * atr_known)
        sized_up2 = atr_ok & push2_up.ge(min_push * atr_known)
        sized_dn1 = atr_ok & push1_dn.ge(min_push * atr_known)
        sized_dn2 = atr_ok & push2_dn.ge(min_push * atr_known)
        three_up = rising & sized_up1 & sized_up2
        three_down = falling & sized_dn1 & sized_dn2

        # Fail new extreme (equal extreme is a fail). Key reversal *breaks* t-1.
        fail_extend_up = high_t1.notna() & ~high.gt(high_t1)
        fail_extend_down = low_t1.notna() & ~low.lt(low_t1)
        # Strong reverse close is locked. A caller cannot pass
        # require_strong_close=False to take a weak body.
        close_lt_open = close.lt(open_)
        close_gt_open = close.gt(open_)
        close_lt_prior = prior_close.notna() & close.lt(prior_close)
        close_gt_prior = prior_close.notna() & close.gt(prior_close)
        strong_short = close_lt_open & close_lt_prior
        strong_long = close_gt_open & close_gt_prior

        short_raw = three_up & fail_extend_up & strong_short
        long_raw = three_down & fail_extend_down & strong_long
        # SHORT priority: a two-sided fail is SHORT, not LONG.
        long_raw = long_raw & (~short_raw)

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["n_pushes"] = n_pushes
        signals["high_t3"] = high_t3
        signals["high_t2"] = high_t2
        signals["high_t1"] = high_t1
        signals["low_t3"] = low_t3
        signals["low_t2"] = low_t2
        signals["low_t1"] = low_t1
        signals["prior_high"] = high_t1
        signals["prior_low"] = low_t1
        signals["prior_close"] = prior_close
        signals["push1_up"] = push1_up
        signals["push2_up"] = push2_up
        signals["push1_dn"] = push1_dn
        signals["push2_dn"] = push2_dn
        signals["push1_up_atr"] = push1_up / atr_safe
        signals["push2_up_atr"] = push2_up / atr_safe
        signals["push1_dn_atr"] = push1_dn / atr_safe
        signals["push2_dn_atr"] = push2_dn / atr_safe
        signals["sized_up1"] = sized_up1.fillna(False)
        signals["sized_up2"] = sized_up2.fillna(False)
        signals["sized_dn1"] = sized_dn1.fillna(False)
        signals["sized_dn2"] = sized_dn2.fillna(False)
        signals["three_up"] = three_up.fillna(False)
        signals["three_down"] = three_down.fillna(False)
        signals["fail_extend_up"] = fail_extend_up.fillna(False)
        signals["fail_extend_down"] = fail_extend_down.fillna(False)
        signals["close_lt_open"] = close_lt_open.fillna(False)
        signals["close_gt_open"] = close_gt_open.fillna(False)
        signals["close_lt_prior"] = close_lt_prior.fillna(False)
        signals["close_gt_prior"] = close_gt_prior.fillna(False)
        signals["strong_short"] = strong_short.fillna(False)
        signals["strong_long"] = strong_long.fillna(False)

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
            # Stronger when the fail close sits further through prior close.
            if params.side is SignalSide.SHORT:
                score = ((prior_close - close) / atr_safe).clip(0.0, 1.0)
            else:
                score = ((close - prior_close) / atr_safe).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: three-push exhaustion-fail "
                    f"n={n_pushes} close {close.loc[i]:.4f} "
                    f"{'<' if params.side is SignalSide.SHORT else '>'} "
                    f"open {open_.loc[i]:.4f} vs prior close {prior_close.loc[i]:.4f} "
                    f"after 3rd {'HH' if params.side is SignalSide.SHORT else 'LL'} "
                    f"{high_t1.loc[i]:.4f}/{low_t1.loc[i]:.4f} "
                    f"push>={min_push:.2f}×ATR {atr_known.loc[i]:.4f}"
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
    "REQUIRE_STRONG_CLOSE_LOCKED",
    "ThreePushExhaustionFailParams",
    "ThreePushExhaustionFailStrategy",
]
