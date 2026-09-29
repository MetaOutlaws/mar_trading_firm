"""Classic morning-star LONG / evening-star SHORT as one 4h BOTH family.

Option B exploratory. SCORE/RETIRE only. Not an approval. Do not set
``approved=true``. Live stays off. Walk-forward is not started from
this coding change.

Three closed bars, signal on bar ``t``, engine fills at ``t+1`` open.
Bars ``<= t`` only. No volume profile. No session gate. The star does
not have to be a doji — a small real body is enough.

Morning LONG (all of these):

    - bar ``t-2`` is bearish and its body is at least
      ``min_body_atr · ATR(20)``
    - bar ``t-1`` (the star) has ``|close-open| / range <= max_star_body_frac``
      and more than half of that range sits strictly below the ``t-2`` body
    - bar ``t`` is bullish, its body is at least ``min_body_atr · ATR(20)``,
      and its close is at or above the midpoint of the ``t-2`` body

Evening SHORT is the mirror: bullish ``t-2``, star range mostly above
that body, bearish ``t`` closing at or below the ``t-2`` midpoint.

ATR is Wilder ATR(20) known *before* the bar it sizes
(``atr.shift(1)``). Bar ``t-2`` is sized by ATR known before ``t-2``.
Bar ``t`` is sized by ATR known before ``t``, so neither candle can
lift its own threshold. A caller-supplied ``atr_n`` is ignored.

"Mostly outside" is locked at strictly more than half the star range
on the gap side of the prior real body. It is not a free parameter
and it is not a doji test.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (each instance emits only its own side)
    - Family id ``morning_evening_star_reversal`` only
    - Three-bar star structure (``t-2``, ``t-1``, ``t``)
    - ATR period = 20
    - No doji-only requirement (a spinning-top star qualifies)
    - Fill at t+1 open (engine convention; this module does not shift)
    - No volume profile, no session gate

Free search (2 only):

    - ``min_body_atr`` grid ``[0.6, 1.0]``
    - ``max_star_body_frac`` grid ``[0.30, 0.40]``
      (endpoints only — do not invent interiors)

Hard constraint: the signal is the full three-candle star and nothing
less. It does not collapse to a doji-only confirm (Job 158
``doji_star_reversal`` is a separate family) and it does not collapse
to a two-bar body engulf (``engulfing_reversal`` /
``engulfing_fail_reversion``). Dropping the sized ``t-2`` body, the
small outside star, or the sized ``t`` close-through-midpoint leaves
the bar flat.

Not ``doji_star_reversal`` (Job 158 — doji after a close run, then a
confirm beyond the doji extreme; no ATR-sized first body and no
midpoint reclaim). Not ``three_black_crows`` /
``three_white_soldiers`` (three same-color soldiers). Not
``engulfing_fail_reversion`` (body engulf, then a later close back
through the engulf open). Not ``candle_reject_reversal`` (hammer /
hanging-man wick fractions on one bar). Do not modify those files.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches the two free knobs only.
ATR_N_LOCKED = 20
# Star window is exactly the three bars t-2, t-1, t. Not searched.
N_BARS_LOCKED = 3
# More than half the star range must sit outside the prior real body.
# Equality is not "mostly". Not a free search param.
MOSTLY_OUTSIDE_FRAC_LOCKED = 0.5
# A doji is allowed but not required. There is no 0.10 body cap.
# Job 158 doji_star_reversal owns doji-only. This flag must stay False;
# generate_signals fail-closes if it is flipped, rather than dropping
# the other two candles.
DOJI_ONLY_REQUIRED = False
# Free-grid endpoints. Do not insert interiors.
MIN_BODY_ATR_GRID = [0.6, 1.0]
MAX_STAR_BODY_FRAC_GRID = [0.30, 0.40]


@dataclass(frozen=True)
class MorningEveningStarReversalParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — generate_signals ignores
    # any other value so the sleeve cannot become ATR(14).
    atr_n: int = ATR_N_LOCKED
    # Real-body floor for bars t-2 and t, in ATR(20) units.
    # Quant grid: [0.6, 1.0].
    min_body_atr: float = 0.6
    # Star body share of its own high-low range. Quant grid: [0.30, 0.40].
    # This is a ceiling, not a doji requirement.
    max_star_body_frac: float = 0.40
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class MorningEveningStarReversalStrategy(Strategy):
    name = "morning_evening_star_reversal"

    def __init__(self, params: MorningEveningStarReversalParams | None = None) -> None:
        super().__init__(params or MorningEveningStarReversalParams())
        self.params: MorningEveningStarReversalParams = self.params
        # ATR(20) seed, the shift that publishes ATR before the bar, and
        # the two bars behind t that complete the star.
        self.min_bars = ATR_N_LOCKED + N_BARS_LOCKED

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
        # Searched knobs stay caller-set. Period, bar count, and the
        # mostly-outside fraction stay locked even if a caller tries
        # to override atr_n.
        min_body = float(params.min_body_atr)
        max_star_frac = float(params.max_star_body_frac)
        atr_n = ATR_N_LOCKED

        body = (close - open_).abs()
        bar_range = (high - low).replace(0, pd.NA)
        body_high = pd.concat([open_, close], axis=1).max(axis=1)
        body_low = pd.concat([open_, close], axis=1).min(axis=1)

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before each bar. Bar t cannot widen the gate it
        # must clear, and bar t-2 is judged on the ATR that existed
        # before that candle printed.
        atr_known = atr20.shift(1)

        body_t2 = body.shift(2)
        open_t2 = open_.shift(2)
        close_t2 = close.shift(2)
        body_high_t2 = body_high.shift(2)
        body_low_t2 = body_low.shift(2)
        mid_t2 = (open_t2 + close_t2) / 2.0
        atr_t2 = atr_known.shift(2)
        sized_t2 = atr_t2.gt(0) & body_t2.ge(min_body * atr_t2)
        bearish_t2 = close_t2.lt(open_t2) & sized_t2
        bullish_t2 = close_t2.gt(open_t2) & sized_t2

        # Star is bar t-1. Zero-range stars never qualify (frac is undefined).
        star_high = high.shift(1)
        star_low = low.shift(1)
        star_range = bar_range.shift(1)
        star_body = body.shift(1)
        star_body_frac = star_body / star_range
        small_star = star_range.notna() & star_body_frac.le(max_star_frac)

        # Portion of the star range that sits strictly outside the t-2
        # real body, on the gap side. "Mostly" is a strict majority.
        below_len = (
            pd.concat([star_high, body_low_t2], axis=1).min(axis=1) - star_low
        ).clip(lower=0.0)
        above_len = (
            star_high - pd.concat([star_low, body_high_t2], axis=1).max(axis=1)
        ).clip(lower=0.0)
        below_frac = below_len / star_range
        above_frac = above_len / star_range
        mostly_below = star_range.notna() & below_frac.gt(MOSTLY_OUTSIDE_FRAC_LOCKED)
        mostly_above = star_range.notna() & above_frac.gt(MOSTLY_OUTSIDE_FRAC_LOCKED)

        atr_ok = atr_known.gt(0)
        sized_t = atr_ok & body.ge(min_body * atr_known)
        bullish_t = close.gt(open_) & sized_t
        bearish_t = close.lt(open_) & sized_t
        close_ge_mid = mid_t2.notna() & close.ge(mid_t2)
        close_le_mid = mid_t2.notna() & close.le(mid_t2)

        # Full three-candle star only. A doji cap or a 2-bar window
        # fail-closes instead of replacing this geometry. small_star is
        # a ceiling (max_star_body_frac), not a doji requirement, so a
        # spinning top with body frac 0.25 still qualifies.
        three_candle = (N_BARS_LOCKED == 3) and (not DOJI_ONLY_REQUIRED)
        morning = (
            three_candle
            & bearish_t2
            & small_star
            & mostly_below
            & bullish_t
            & close_ge_mid
        )
        evening = (
            three_candle
            & bullish_t2
            & small_star
            & mostly_above
            & bearish_t
            & close_le_mid
        )

        atr_safe = atr_known.replace(0, pd.NA)
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["body"] = body
        signals["body_atr"] = body / atr_safe
        signals["body_t2"] = body_t2
        signals["body_t2_atr"] = body_t2 / atr_t2.replace(0, pd.NA)
        signals["star_body_frac"] = star_body_frac
        signals["star_below_frac"] = below_frac
        signals["star_above_frac"] = above_frac
        signals["prior_body_mid"] = mid_t2
        signals["small_star"] = small_star.fillna(False)
        signals["mostly_below"] = mostly_below.fillna(False)
        signals["mostly_above"] = mostly_above.fillna(False)
        signals["morning_star"] = morning.fillna(False)
        signals["evening_star"] = evening.fillna(False)

        if params.side is SignalSide.LONG:
            entry = morning
            signal_value, side_value = 1, SignalSide.LONG.value
        elif params.side is SignalSide.SHORT:
            entry = evening
            signal_value, side_value = -1, SignalSide.SHORT.value
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the confirm close pushes further through the
            # t-2 midpoint, in ATR units known before bar t.
            if params.side is SignalSide.LONG:
                depth = (close - mid_t2) / atr_safe
            else:
                depth = (mid_t2 - close) / atr_safe
            signals.loc[entry, "score"] = depth.clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            gap_frac = below_frac if params.side is SignalSide.LONG else above_frac
            reasons.loc[entry] = [
                (
                    f"{side_value}: "
                    f"{'morning' if params.side is SignalSide.LONG else 'evening'}"
                    f"-star close {close.loc[i]:.4f} "
                    f"{'>=' if params.side is SignalSide.LONG else '<='} "
                    f"t-2 mid {mid_t2.loc[i]:.4f} "
                    f"body {body.loc[i]:.4f}>={min_body:.2f}×ATR "
                    f"{atr_known.loc[i]:.4f} "
                    f"star_frac {star_body_frac.loc[i]:.3f}<={max_star_frac:.2f} "
                    f"outside {gap_frac.loc[i]:.3f}>{MOSTLY_OUTSIDE_FRAC_LOCKED:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "DOJI_ONLY_REQUIRED",
    "MAX_STAR_BODY_FRAC_GRID",
    "MIN_BODY_ATR_GRID",
    "MOSTLY_OUTSIDE_FRAC_LOCKED",
    "N_BARS_LOCKED",
    "MorningEveningStarReversalParams",
    "MorningEveningStarReversalStrategy",
]
