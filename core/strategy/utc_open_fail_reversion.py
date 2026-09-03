"""Fade a failed break of the UTC day's first 4h box on the second 4h bar.

00:00–04:00 UTC sets the box (published only after that window closes). The
next 4h (04:00–08:00) must trade through the box and close back inside; fade
toward the first-4h mid. On 4h that is the 04:00 bar; on 1h it is the 07:00
bar using the slot's aggregated high/low.

Not `utc_midnight_gap_fill` (first-bar open vs prior close), not
`asian_range_breakout` (break the completed 00–08 box after 08:00), not
`session_liquidity_sweep` (Asian box failed-sweep with a 1% cap).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class UtcOpenFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # First UTC 4h box. Locked — this family is the fail of that box, not ORB hours.
    box_hours: float = 4.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class UtcOpenFailReversionStrategy(Strategy):
    name = "utc_open_fail_reversion"

    def __init__(self, params: UtcOpenFailReversionParams | None = None) -> None:
        super().__init__(params or UtcOpenFailReversionParams())
        self.params: UtcOpenFailReversionParams = self.params
        self.min_bars = 10

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
        box_hours = float(params.box_hours)
        # Causal first-4h box: blank during 00:00–04:00, published from 04:00.
        box_high, box_low, box_ready = ind.utc_opening_range(
            high, low, range_hours=box_hours
        )
        bar_hours = ind.infer_bar_hours(candles.index)
        # Last bar of 04:00–08:00 — the completed second 4h, not a 08:00 Asian break.
        second_done = ind.last_bar_of_utc_slot(
            candles.index,
            slot_start=box_hours,
            slot_end=2.0 * box_hours,
            bar_hours=bar_hours,
        )

        utc_index = ind._as_utc_index(candles.index)
        day = utc_index.normalize()
        hours_into = (utc_index - day) / pd.Timedelta(hours=1)
        in_second = (hours_into >= box_hours) & (hours_into < (2.0 * box_hours))
        day_key = ind.utc_day_key(candles.index)
        # Running H/L of the second 4h only. Cummax is causal (bars <= t).
        slot_high = high.where(in_second).groupby(day_key).cummax()
        slot_low = low.where(in_second).groupby(day_key).cummin()

        closed_inside = box_ready & (close <= box_high) & (close >= box_low)
        # Trade through then close back inside: a fail, not a held breakout.
        fail_low = second_done & closed_inside & (slot_low < box_low)
        fail_high = second_done & closed_inside & (slot_high > box_high)
        box_mid = (box_high + box_low) / 2.0

        signals["box_high"] = box_high
        signals["box_low"] = box_low
        signals["box_mid"] = box_mid
        signals["slot_high"] = slot_high
        signals["slot_low"] = slot_low

        if params.side is SignalSide.LONG:
            raw = fail_low
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = fail_high
            signal_value, side_value = -1, SignalSide.SHORT.value

        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (box_high - box_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - box_low) / width).clip(0.0, 1.0)
        else:
            score = ((box_high - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: UTC first-4h fail close {close.loc[i]:.4f} "
                    f"box {box_high.loc[i]:.4f}/{box_low.loc[i]:.4f} "
                    f"mid {box_mid.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["UtcOpenFailReversionParams", "UtcOpenFailReversionStrategy"]
