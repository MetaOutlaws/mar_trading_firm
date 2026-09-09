"""Displacement gap follow — trade *with* a same-bar gap that stays efficient.

Gap is adjacent-bar displacement, not a weekend / UTC-midnight / session box:

    LONG:  low[t] > high[t-1] AND close[t] > open[t]
    SHORT: high[t] < low[t-1] AND close[t] < open[t]

Size uses the *unfilled* gap vs Wilder ATR(20) known *before* the signal
bar so bar ``t`` cannot lift its own threshold:

    LONG gap  = low[t] - high[t-1]
    SHORT gap = low[t-1] - high[t]
    sized when gap >= min_gap_atr * ATR20

Body efficiency is bar-local occupancy of the high-low (not true range,
not Kaufman ER, not a two-bar body-efficiency pair):

    LONG:  (close - open) / (high - low) >= min_body_eff
    SHORT: (open - close) / (high - low) >= min_body_eff

Zero-range bars (high == low) never fire. The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - ATR period = 20
    - ATR known before the signal bar (shift 1)
    - gap-up / gap-down definition
    - follow the gap (not fade / fill it)
    - body efficiency uses high-low, not true range

Free search (2 only):

    - ``min_gap_atr`` grid ``[0.10, 0.25]``
    - ``min_body_eff`` grid ``[0.50, 0.70]``

OHLCV only. Causal: bars ``<= t``. No volume gate. No session / SMA /
Donchian / BB / inventory overlay.

Not ``weekend_gap_fill`` (Monday fade toward Friday UTC close).
Not ``utc_midnight_gap_fill`` (first-hour fade toward prior day close).
Not ``body_efficiency_follow`` (two consecutive efficient bars + volume;
no gap; efficiency is |body|/true_range).
Not ``open_in_prior_range_fail`` (gap *open* then close back *inside*
the prior bar — fade, not follow).
Not ``outside_bar_fail_reversion`` (142 — outside containment then
next-bar close-inside).
Not ``sma20_stretch_fade`` (141 — SMA20 wick stretch then reclaim).
Not ``bb_medium_bw_upper_reject`` (BB tag + medium-BW close-inside).
Not ``three_white_soldiers`` (140) / ``three_black_crows`` (134).
Not ``atr_open_flush_fade`` (138 — same-bar flush of *bar open*).
Not ``utc_day_open_flush_fade`` (139 — flush of UTC day-open).
Not ``failed_break_reclaim`` (130 — multi-bar wick probe then reclaim).
Not ``expansion_fail_fade`` (131 — ATR true-range expansion + weak-vol).
Not ``candle_reject_reversal`` (hammer / hanging-man same-bar geometry).
Not ``ib_fail_reversion`` (124) / ``nr7_fail_reversion`` (123).
Not ``engulfing_fail_reversion`` (126 — two-bar body engulf then fail).
Not ``asia_range_london_reject`` (121 — London tag of Asia H/L).
Not ``prior_day_extreme_reject`` (118 — prior UTC day H/L reject).
Not ``range_compression_volume_thrust`` (102 — squeeze then volume thrust).
Not ``london_close_inventory_fade`` (100) / ``ny_close_inventory_fade``
(banned/parked).
Do not recode spent families 118–142. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches min_gap_atr + min_body_eff only.
ATR_N_LOCKED = 20


@dataclass(frozen=True)
class DisplacementGapFollowParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Unfilled gap floor in ATR units. Quant grid: [0.10, 0.25].
    min_gap_atr: float = 0.10
    # Same-bar body / high-low floor. Quant grid: [0.50, 0.70].
    min_body_eff: float = 0.50
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class DisplacementGapFollowStrategy(Strategy):
    name = "displacement_gap_follow"

    def __init__(self, params: DisplacementGapFollowParams | None = None) -> None:
        super().__init__(params or DisplacementGapFollowParams())
        self.params: DisplacementGapFollowParams = self.params
        # ATR seed + the prior bar that defines the gap + the displacement print.
        self.min_bars = ATR_N_LOCKED + 2

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
        # Searched floors stay caller-set. Period stays locked even if overridden.
        min_gap = float(params.min_gap_atr)
        min_eff = float(params.min_body_eff)
        atr_n = ATR_N_LOCKED

        prior_high = high.shift(1)
        prior_low = low.shift(1)
        # Strict unfilled gap. A touch of the prior rail is not displacement.
        gap_up = prior_high.notna() & low.gt(prior_high)
        gap_down = prior_low.notna() & high.lt(prior_low)
        gap_up_size = low - prior_high
        gap_down_size = prior_low - high

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)
        sized_up = atr_ok & gap_up_size.ge(min_gap * atr_known)
        sized_down = atr_ok & gap_down_size.ge(min_gap * atr_known)

        # High-low occupancy, not true-range body_efficiency (that includes the gap).
        bar_range = high - low
        range_ok = bar_range.gt(0)
        range_safe = bar_range.replace(0, pd.NA)
        body_eff_long = (close - open_) / range_safe
        body_eff_short = (open_ - close) / range_safe
        efficient_long = range_ok & body_eff_long.ge(min_eff)
        efficient_short = range_ok & body_eff_short.ge(min_eff)

        bull = close.gt(open_)
        bear = close.lt(open_)
        long_raw = gap_up & bull & sized_up & efficient_long
        short_raw = gap_down & bear & sized_down & efficient_short

        # Diagnostic columns: gap vs prior rail, not a session / SMA / Donchian box.
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["gap_up"] = gap_up.fillna(False)
        signals["gap_down"] = gap_down.fillna(False)
        signals["gap_up_size"] = gap_up_size
        signals["gap_down_size"] = gap_down_size
        signals["gap_up_atr"] = gap_up_size / atr_safe
        signals["gap_down_atr"] = gap_down_size / atr_safe
        signals["bar_range"] = bar_range
        signals["body_eff_long"] = body_eff_long
        signals["body_eff_short"] = body_eff_short
        signals["sized_up"] = sized_up.fillna(False)
        signals["sized_down"] = sized_down.fillna(False)
        signals["efficient_long"] = efficient_long.fillna(False)
        signals["efficient_short"] = efficient_short.fillna(False)

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            gap_atr = gap_up_size / atr_safe
            body_eff = body_eff_long
            gap_size = gap_up_size
        elif params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            gap_atr = gap_down_size / atr_safe
            body_eff = body_eff_short
            gap_size = gap_down_size
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value
            gap_atr = pd.Series(pd.NA, index=candles.index, dtype="float64")
            body_eff = pd.Series(pd.NA, index=candles.index, dtype="float64")
            gap_size = pd.Series(pd.NA, index=candles.index, dtype="float64")

        signals["gap_size"] = gap_size
        signals["gap_atr"] = gap_atr
        signals["body_eff"] = body_eff
        signals["sized_enough"] = (sized_up if params.side is SignalSide.LONG else sized_down).fillna(
            False
        )
        signals["efficient_enough"] = (
            efficient_long if params.side is SignalSide.LONG else efficient_short
        ).fillna(False)

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the gap clears the floor by more, still efficient.
            excess = ((gap_atr - min_gap) / min_gap).clip(0.0, 1.0)
            signals.loc[entry, "score"] = excess.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: displacement-gap follow gap {float(gap_size.loc[i]):.4f} "
                    f"({float(gap_atr.loc[i]):.3f}×ATR {atr_known.loc[i]:.4f}) "
                    f">={min_gap:.2f} body_eff {float(body_eff.loc[i]):.3f}"
                    f">={min_eff:.2f} close {close.loc[i]:.4f} open {open_.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "DisplacementGapFollowParams",
    "DisplacementGapFollowStrategy",
]
