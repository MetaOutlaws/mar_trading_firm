"""Inside-bar break-fail — wick through the mother, close back inside.

Family F. Munhamutapa CHAIR stamp. Classic two-bar inside-bar mother (``inside_bar_mother``): bar
t-1 sits *strictly* inside bar t-2, published on bar t (the first bar that
may break the mother). This is a same-bar *rejection / fail-through*:

    SHORT: high[t] > mother_high  AND  mother_low < close[t] < mother_high
    LONG:  low[t]  < mother_low   AND  mother_low < close[t] < mother_high

A two-sided wick (both rails) does not fire. A close on a rail is not
inside. A close *through* the mother is ``inside_bar_breakout`` (follow),
not this fade.

Mother size uses the mother high-low (not true range) vs Wilder ATR(20)
known *before* the signal bar so bar t cannot lift its own threshold:

    (mother_high - mother_low) >= min_mother_atr * ATR20

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH
    - Family id ``inside_bar_break_fail`` only
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - Mother = inside-bar mother context (any bar, not a London session lock)
    - require_close_inside_mother = True (strict inside)
    - Fill at t+1 open (engine convention)

Free search (1 only):

    - ``min_mother_atr`` grid ``[0.8, 1.2]``
      (endpoints only — same sibling float-grid convention as
      ``outside_bar_fail_reversion.min_outside_atr``)

OHLCV only. Causal: bars ``<= t``. No volume gate. No London IB open
window. No ``max_bars_since_break``.

Not ``ib_fail_reversion`` (124 — London first-4h-open-in-07:00–11:00
mother, close-through, then a *later* bar fails inside
``max_bars_since_break``).
Not ``inside_bar_breakout`` (follows the close-through).
Not ``nr7_fail_reversion`` (123 — narrowest-of-7 close-through fail).
Not ``outside_bar_fail_reversion`` (outside containment then next-bar
close-inside vs mid).
Not ``failed_range_break_reversion`` (119 — rolling N-bar Donchian).
Not ``failed_break_reclaim`` (130 — multi-bar wick probe).
Not ``engulfing_fail_reversion`` (126 — body engulf then fail through
engulf open).
Not ``expansion_fail_fade`` / ``candle_reject_reversal``.
Not ``lvn_fill_reject`` (family E — prior-day LVN fill-reject).
Not ``swing_break_fail_reversion`` (family I — prior-lookback swing
wick-fail; do not code in this sleeve).
Do not recode spent families 118–149. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches min_mother_atr only.
ATR_N_LOCKED = 20
# Quant-locked True: fail close must sit strictly inside the mother.
REQUIRE_CLOSE_INSIDE_MOTHER_LOCKED = True
# Free-grid mother-range floor. Endpoints only, matching sibling [0.8, 1.2].
MIN_MOTHER_ATR_MIN = 0.8
MIN_MOTHER_ATR_MAX = 1.2
MIN_MOTHER_ATR_GRID = [0.8, 1.2]


@dataclass(frozen=True)
class InsideBarBreakFailParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Mother-range floor in ATR units. Quant grid: [0.8, 1.2].
    min_mother_atr: float = MIN_MOTHER_ATR_MIN
    # Quant-locked True: fade only if close_t is strictly inside the mother.
    require_close_inside_mother: bool = REQUIRE_CLOSE_INSIDE_MOTHER_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class InsideBarBreakFailStrategy(Strategy):
    name = "inside_bar_break_fail"

    def __init__(self, params: InsideBarBreakFailParams | None = None) -> None:
        super().__init__(params or InsideBarBreakFailParams())
        self.params: InsideBarBreakFailParams = self.params
        # ATR seed + mother + inside bar + the fail/reject print.
        self.min_bars = ATR_N_LOCKED + 3

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
        # Searched size floor stays caller-set. Period / inside-lock stay locked.
        min_atr = float(params.min_mother_atr)
        atr_n = ATR_N_LOCKED

        # Classic two-bar IB: t-1 sits inside t-2. Published on the break bar.
        mother_high, mother_low, inside = ind.inside_bar_mother(high, low)
        mother_range = mother_high - mother_low
        mother_mid = (mother_high + mother_low) / 2.0

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)
        mother_atr = mother_range / atr_safe
        sized = atr_ok & mother_range.ge(min_atr * atr_known)

        # Locked strict inside. A rail tag is not a fail, even if a caller
        # passes require_close_inside_mother=False.
        close_inside = (
            mother_high.notna()
            & mother_low.notna()
            & close.gt(mother_low)
            & close.lt(mother_high)
        )
        # Wick-through of one mother rail. Two-sided outside-the-mother is
        # not this family (and is closer to an outside bar of the mother).
        broke_up = mother_high.notna() & high.gt(mother_high)
        broke_down = mother_low.notna() & low.lt(mother_low)

        short_raw = (
            inside & sized & close_inside & broke_up & (~broke_down)
        )
        long_raw = (
            inside & sized & close_inside & broke_down & (~broke_up)
        )

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["inside"] = inside.fillna(False)
        signals["mother_high"] = mother_high
        signals["mother_low"] = mother_low
        signals["mother_mid"] = mother_mid
        signals["mother_range"] = mother_range
        signals["mother_atr"] = mother_atr
        signals["sized_enough"] = sized.fillna(False)
        signals["close_inside_mother"] = close_inside.fillna(False)
        signals["broke_up"] = broke_up.fillna(False)
        signals["broke_down"] = broke_down.fillna(False)

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        elif params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the fail close sits further from the broken rail.
            width = mother_range.replace(0, pd.NA)
            if params.side is SignalSide.LONG:
                score = ((close - mother_low) / width).clip(0.0, 1.0)
            else:
                score = ((mother_high - close) / width).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: inside-bar break-fail close {close.loc[i]:.4f} "
                    f"inside ({mother_low.loc[i]:.4f}, {mother_high.loc[i]:.4f}) "
                    f"range {mother_range.loc[i]:.4f}>={min_atr:.2f}×ATR "
                    f"{atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "MIN_MOTHER_ATR_GRID",
    "MIN_MOTHER_ATR_MAX",
    "MIN_MOTHER_ATR_MIN",
    "REQUIRE_CLOSE_INSIDE_MOTHER_LOCKED",
    "InsideBarBreakFailParams",
    "InsideBarBreakFailStrategy",
]
