"""Fade a failed London/NY sweep of the completed Asian session box.

Opposite of `asian_range_breakout` (which trades the break). This sleeve waits
until the 00:00–08:00 UTC high/low is published, then enters only if a later
London or NY bar pokes beyond that box by less than `max_sweep_pct` and closes
back inside. OHLCV session math only — not an order-book liquidity feed.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SessionLiquiditySweepParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    asia_start: float = 0.0
    asia_end: float = 8.0
    # London 08:00–16:00 plus NY 13:00–21:00 UTC, as one trade window.
    trade_start: float = 8.0
    trade_end: float = 21.0
    # Maximum excursion beyond the Asian boundary as a fraction of that level.
    max_sweep_pct: float = 0.01
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class SessionLiquiditySweepStrategy(Strategy):
    name = "session_liquidity_sweep"

    def __init__(self, params: SessionLiquiditySweepParams | None = None) -> None:
        super().__init__(params or SessionLiquiditySweepParams())
        self.params: SessionLiquiditySweepParams = self.params
        # Need a completed Asian window plus the first London bar.
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        range_high, range_low, asia_ready = ind.utc_session_range(
            candles["high"],
            candles["low"],
            start_hour=float(params.asia_start),
            end_hour=float(params.asia_end),
        )
        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        utc_index = candles.index
        if utc_index.tz is None:
            utc_index = utc_index.tz_localize("UTC")
        else:
            utc_index = utc_index.tz_convert("UTC")
        hours_into = (utc_index - utc_index.normalize()) / pd.Timedelta(hours=1)
        in_london_or_ny = pd.Series(
            (hours_into >= float(params.trade_start))
            & (hours_into < float(params.trade_end)),
            index=candles.index,
        )

        max_pct = float(params.max_sweep_pct)
        # Same-bar failed sweep: poke through, close back inside, stay under 1%.
        sweep_low = (
            asia_ready
            & in_london_or_ny
            & (low < range_low)
            & (close >= range_low)
            & (close <= range_high)
            & ((range_low - low) <= range_low.abs() * max_pct)
        )
        sweep_high = (
            asia_ready
            & in_london_or_ny
            & (high > range_high)
            & (close <= range_high)
            & (close >= range_low)
            & ((high - range_high) <= range_high.abs() * max_pct)
        )

        signals["range_high"] = range_high
        signals["range_low"] = range_low
        signals["asia_ready"] = asia_ready.astype("float64")

        if params.side is SignalSide.LONG:
            raw = sweep_low
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = sweep_high
            signal_value, side_value = -1, SignalSide.SHORT.value

        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (range_high - range_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - range_low) / width).clip(0.0, 1.0)
        else:
            score = ((range_high - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: Asian sweep fade close {close.loc[i]:.4f} vs "
                    f"{range_high.loc[i]:.4f}/{range_low.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["SessionLiquiditySweepParams", "SessionLiquiditySweepStrategy"]
