"""Swing-break fail reversion — sized break of a prior lookback swing, close back through.

Family I. CEO YES exploratory stamp (Job ~153). Prior swing is the rolling high/low of
the last ``swing_lookback`` bars *excluding* the signal bar (same prior-bar
Donchian geometry as ``wyckoff_spring_reclaim`` / ``failed_range_break_reversion``,
but the searched window is the short swing ``[3, 5]``, not 16/20):

    swing_high = max(high[t-swing_lookback : t])   # bars t-N .. t-1
    swing_low  = min(low[t-swing_lookback : t])

Bar ``t`` cannot lift its own swing. A fail is a same-bar *sized wick-through*
that then *closes back through* the broken swing level:

    SHORT: high[t] > swing_high + min_break_atr * ATR20
           AND close[t] < swing_high
    LONG:  low[t]  < swing_low  - min_break_atr * ATR20
           AND close[t] > swing_low

BOTH sides honest, SHORT priority: when both raw conditions print on the
same bar, SHORT fires and LONG does not. ATR is Wilder ATR(20) known
*before* the signal bar (``atr.shift(1)``) so bar ``t`` cannot lift its
own size gate. The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority on two-sided bars)
    - Family id ``swing_break_fail_reversion`` only
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - Swing = prior-bar rolling high/low over ``swing_lookback``
    - Fail = same-bar close back through the broken swing level
    - Fill at t+1 open (engine convention)

Free search (2 only):

    - ``swing_lookback`` grid ``[3, 5]`` (endpoints only)
    - ``min_break_atr`` grid ``[0.2, 0.5]`` (endpoints only — same sibling
      float-grid convention as ``outside_bar_fail_reversion.min_outside_atr``
      / ``inside_bar_break_fail.min_mother_atr``; do not invent interiors)

OHLCV only. Causal: bars ``<= t``. No volume gate. No max_bars_since_break.
No confirmed-pivot ``pivot_left``. No London / session lock.

Not ``swing_failure_reversal`` (confirmed N-bar pivots, any wick, no ATR
size floor).
Not ``failed_higher_high`` (two consecutive confirmed swings).
Not ``failed_range_break_reversion`` (119 — Donchian 16/20 close-through
then a later fail inside ``max_bars_since_break``).
Not ``failed_break_reclaim`` (130 — multi-bar wick probe of 16/20).
Not ``wyckoff_spring_reclaim`` (127 — 16/20 spring, no min_break_atr).
Not ``equal_high_low_restest_fade`` (two matched extremes).
Not ``williams_fractal_break`` (5-bar fractal close-through follow).
Not ``inside_bar_break_fail`` (family F — IB mother wick-fail).
Not ``thrust_bar_fail_reversion`` (family G / Job 151 — t-1 thrust then close inside prior).
Not ``key_reversal_bar`` (family H / Job 152 — t-1 extreme + reverse body vs prior close).
Not ``outside_bar_reversal`` / ``outside_bar_fail_reversion`` (both-rail containment).
Not ``ib_fail_reversion`` / ``nr7_fail_reversion``.
Not dead VP (``prior_poc_reclaim_fade`` / ``hvn_mean_revert`` /
``lvn_fill_reject`` / ``rolling_va_extreme_reject``). Not
``hvn_node_fade`` as an alias.
Not Job 133 ``bullish_rectangle_fail_reclaim`` (DEAD 0/12 — no-recode /
no-spawn). Not Job 144 ``keltner_channel_fade`` (0/12). Not
``utc_open_fail_reversion`` (0/12). Not ``measured_move_break`` (job 86 0/12).
Hold H&S / asia / wyckoff alone.
Do not recode spent families 118–152. Do not revive Job 133 rectangle.
Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches swing_lookback + min_break_atr only.
ATR_N_LOCKED = 20
# Free-grid prior-bar swing window. Endpoints only.
SWING_LOOKBACK_MIN = 3
SWING_LOOKBACK_MAX = 5
SWING_LOOKBACK_GRID = [3, 5]
# Free-grid break size in ATR units. Endpoints only.
MIN_BREAK_ATR_MIN = 0.2
MIN_BREAK_ATR_MAX = 0.5
MIN_BREAK_ATR_GRID = [0.2, 0.5]


@dataclass(frozen=True)
class SwingBreakFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Prior-bar swing window. Quant grid: [3, 5].
    swing_lookback: int = SWING_LOOKBACK_MIN
    # Minimum wick-through of the swing in ATR units. Quant grid: [0.2, 0.5].
    min_break_atr: float = MIN_BREAK_ATR_MIN
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class SwingBreakFailReversionStrategy(Strategy):
    name = "swing_break_fail_reversion"

    def __init__(self, params: SwingBreakFailReversionParams | None = None) -> None:
        super().__init__(params or SwingBreakFailReversionParams())
        self.params: SwingBreakFailReversionParams = self.params
        lookback = int(self.params.swing_lookback)
        lookback = min(SWING_LOOKBACK_MAX, max(SWING_LOOKBACK_MIN, lookback))
        # ATR seed + prior swing window + the fail/reversion print.
        self.min_bars = ATR_N_LOCKED + lookback + 1

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
        # Lookback stays inside the Quant grid even if a caller overrides.
        # Break size stays caller-set so the 0.2 vs 0.5 search grid matters.
        lookback = int(params.swing_lookback)
        lookback = min(SWING_LOOKBACK_MAX, max(SWING_LOOKBACK_MIN, lookback))
        min_break = float(params.min_break_atr)
        atr_n = ATR_N_LOCKED

        # Prior-bar swing. Current bar cannot lift or lower its own level.
        swing_high = high.shift(1).rolling(lookback, min_periods=lookback).max()
        swing_low = low.shift(1).rolling(lookback, min_periods=lookback).min()

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & swing_high.notna() & swing_low.notna()
        atr_safe = atr_known.replace(0, pd.NA)
        up_break_atr = (high - swing_high) / atr_safe
        dn_break_atr = (swing_low - low) / atr_safe

        # Munha + Marcus lock: size gate is strict `>` — a poke that lands
        # exactly on swing ± min_break_atr·ATR is not a break.
        broke_up = atr_ok & high.gt(swing_high + min_break * atr_known)
        broke_down = atr_ok & low.lt(swing_low - min_break * atr_known)
        # Close back *through* the broken level (strict). A rail tag is not a fail.
        closed_through_high = close.lt(swing_high)
        closed_through_low = close.gt(swing_low)
        short_raw = broke_up & closed_through_high
        long_raw = broke_down & closed_through_low
        # SHORT priority: a two-sided fail is SHORT, not LONG.
        long_raw = long_raw & (~short_raw)

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["swing_high"] = swing_high
        signals["swing_low"] = swing_low
        signals["swing_lookback"] = lookback
        signals["up_break_atr"] = up_break_atr
        signals["dn_break_atr"] = dn_break_atr
        signals["broke_up"] = broke_up.fillna(False)
        signals["broke_down"] = broke_down.fillna(False)
        signals["closed_through_high"] = closed_through_high.fillna(False)
        signals["closed_through_low"] = closed_through_low.fillna(False)

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
            # Stronger when the fail close sits further through the broken swing.
            if params.side is SignalSide.SHORT:
                score = ((swing_high - close) / atr_safe).clip(0.0, 1.0)
            else:
                score = ((close - swing_low) / atr_safe).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: swing-break fail-reversion close {close.loc[i]:.4f} "
                    f"through swing {swing_high.loc[i]:.4f}/{swing_low.loc[i]:.4f} "
                    f"lookback {lookback} break>{min_break:.2f}×ATR "
                    f"{atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "MIN_BREAK_ATR_GRID",
    "MIN_BREAK_ATR_MAX",
    "MIN_BREAK_ATR_MIN",
    "SWING_LOOKBACK_GRID",
    "SWING_LOOKBACK_MAX",
    "SWING_LOOKBACK_MIN",
    "SwingBreakFailReversionParams",
    "SwingBreakFailReversionStrategy",
]
