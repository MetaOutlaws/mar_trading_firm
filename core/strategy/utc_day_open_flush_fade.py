"""Fade a flush of the UTC day-open, then reclaim through that open. BOTH sides.

UTC day-open is LOCKED: the open of the first 4h bar whose open time falls
in 00:00–03:59 UTC on that calendar day. The level is valid on that same
UTC day only — it does not carry into the next day.

SHORT: high extends ``>= k * ATR`` above day_open, then close sits back
*below* day_open (fade the up-flush).
LONG: low extends ``>= k * ATR`` below day_open, then close sits back
*above* day_open (fade the down-flush).

ATR is Wilder ``ATR(20)`` known *before* the signal bar so the flush
cannot lift its own threshold. Flush extreme and reclaim close live on
bar ``t``. The engine fills at ``t+1`` open.

This is not ``atr_open_flush_fade`` (138, RETIRED): that family fades a
same-bar flush of *that bar's own open* at any hour. This family fades a
flush of the *frozen UTC day-open* on the same calendar day, including
later 4h slots (04:00, 08:00, …).

Quant-locked (not searched):

    - ATR period = 20
    - UTC day-open = first 4h open in 00:00–03:59 UTC, same day only
    - SHORT = up-flush of day_open then close below; LONG = down-flush
      then close above

Free search (1 only):

    - ``k`` (flush distance in ATR units from day_open) grid ``[1.0, 1.5]``

OHLCV only. Causal: bars ``<= t``. No volume gate.

Not ``atr_open_flush_fade`` (138 — same-bar bar-open flush).
Not ``prior_day_extreme_reject`` / prior-week extremes.
Not ``prior_close_magnet_fade`` (stretch vs prior close).
Not ``ib_fail_reversion`` (London IB mother + later fail).
Not ``orb_fail_reversion`` (UTC-day ORB close-through then fail).
Not ``expansion_fail_fade`` (next-bar fail of a prior expansion).
Not ``london_close_inventory_fade`` / NY-close inventory.
Do not recode spent family 138.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window and UTC day-open slot. Walk-forward searches k only.
ATR_N_LOCKED = 20
DAY_OPEN_WINDOW_HOURS = ind.UTC_DAY_OPEN_WINDOW_HOURS


@dataclass(frozen=True)
class UtcDayOpenFlushFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Flush distance in ATR units from the UTC day-open. Quant grid: [1.0, 1.5].
    k: float = 1.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class UtcDayOpenFlushFadeStrategy(Strategy):
    name = "utc_day_open_flush_fade"

    def __init__(self, params: UtcDayOpenFlushFadeParams | None = None) -> None:
        super().__init__(params or UtcDayOpenFlushFadeParams())
        self.params: UtcDayOpenFlushFadeParams = self.params
        # ATR seed plus one bar so the threshold is the *prior* ATR print.
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
        # Locks stay locked even if a caller passes another atr_n.
        atr_n = ATR_N_LOCKED
        k = float(params.k)

        # Frozen UTC day-open for this calendar day only. Not bar open.
        day_open = ind.utc_day_open(open_, window_hours=DAY_OPEN_WINDOW_HOURS)
        atr20 = ind.atr(high, low, close, atr_n)
        # Prevailing ATR before this bar. The flush cannot inflate the hurdle.
        atr_prev = atr20.shift(1)
        atr_ok = atr_prev.gt(0) & day_open.notna()

        # Flush distance from the UTC day-open, in ATR units. Same UTC day only
        # because day_open is blank / reset on every other calendar day.
        up_flush_atr = (high - day_open) / atr_prev.replace(0, pd.NA)
        down_flush_atr = (day_open - low) / atr_prev.replace(0, pd.NA)
        up_flush = atr_ok & up_flush_atr.ge(k)
        down_flush = atr_ok & down_flush_atr.ge(k)
        # Fade: close back through the locked day-open, not the bar's own open.
        faded_below_day_open = close.lt(day_open)
        faded_above_day_open = close.gt(day_open)

        short_raw = up_flush & faded_below_day_open
        long_raw = down_flush & faded_above_day_open

        signals["atr"] = atr20
        signals["atr_prev"] = atr_prev
        signals["day_open"] = day_open
        signals["up_flush_atr"] = up_flush_atr
        signals["down_flush_atr"] = down_flush_atr
        signals["up_flush"] = up_flush.fillna(False)
        signals["down_flush"] = down_flush.fillna(False)
        signals["faded_below_day_open"] = faded_below_day_open.fillna(False)
        signals["faded_above_day_open"] = faded_above_day_open.fillna(False)

        if params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            flush_atr = up_flush_atr
        elif params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            flush_atr = down_flush_atr
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value
            flush_atr = pd.Series(pd.NA, index=candles.index, dtype="float64")

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the flush extends further past k*ATR.
            excess = ((flush_atr - k) / k).clip(0.0, 1.0)
            signals.loc[entry, "score"] = excess.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: utc-day-open flush fade open {day_open.loc[i]:.4f} "
                    f"close {close.loc[i]:.4f} high {high.loc[i]:.4f} "
                    f"low {low.loc[i]:.4f} flush {float(flush_atr.loc[i]):.3f} "
                    f"atr {atr_prev.loc[i]:.4f} k={k:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "DAY_OPEN_WINDOW_HOURS",
    "UtcDayOpenFlushFadeParams",
    "UtcDayOpenFlushFadeStrategy",
]
