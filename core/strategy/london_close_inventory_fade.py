"""Fade an extreme London-close 4h bar on high volume, back to London VWAP.

The London-close bar is the bar covering 15:00–16:00 UTC (open-labeled 4h at
12:00, or the 15:00 hour on 1h). Fade when that close sits in the extreme
20% of the bar's range AND volume exceeds the prior-20 mean. Target is
London-session VWAP (08:00–16:00 UTC), not UTC-midnight VWAP.

Calendar London-close inventory — not `london_session_breakout` (break the
completed 08–16 box after 16:00), not `session_boundary_volume_fade` (prior
UTC day H/L on weak volume), not `monday_range_sweep_reversal`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class LondonCloseInventoryFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Extreme 20% of the close bar's own range. Locked in the walk-forward kit.
    extreme_frac: float = 0.20
    # Prior-N volume mean; current bar excluded.
    vol_lookback: int = 20
    london_start: float = 8.0
    london_end: float = 16.0
    close_hour: float = 15.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class LondonCloseInventoryFadeStrategy(Strategy):
    name = "london_close_inventory_fade"

    def __init__(self, params: LondonCloseInventoryFadeParams | None = None) -> None:
        super().__init__(params or LondonCloseInventoryFadeParams())
        self.params: LondonCloseInventoryFadeParams = self.params
        self.min_bars = int(self.params.vol_lookback) + 4

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
        bar_hours = ind.infer_bar_hours(candles.index)
        # The one bar whose interval contains 15:00 UTC — London cash close.
        london_close = ind.bar_covers_utc_hour(
            candles.index, params.close_hour, bar_hours=bar_hours
        )
        london_vwap = ind.utc_window_vwap(
            high,
            low,
            close,
            volume,
            start_hour=params.london_start,
            end_hour=params.london_end,
        )
        vol_mean = ind.prior_rolling_mean(volume, int(params.vol_lookback))
        heavy = volume > vol_mean

        width = (high - low).replace(0, pd.NA)
        close_frac = (close - low) / width
        extreme = float(params.extreme_frac)
        # Bottom 20% = inventory long fade toward VWAP; top 20% = short fade.
        extreme_low = close_frac <= extreme
        extreme_high = close_frac >= (1.0 - extreme)

        long_raw = (
            london_close
            & heavy
            & extreme_low
            & london_vwap.notna()
            & (close < london_vwap)
        )
        short_raw = (
            london_close
            & heavy
            & extreme_high
            & london_vwap.notna()
            & (close > london_vwap)
        )

        signals["london_vwap"] = london_vwap
        signals["vol_mean"] = vol_mean
        signals["close_frac"] = close_frac
        signals["london_close_bar"] = london_close.astype("float64")

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One inventory fade per UTC day, on the close bar only.
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        stretch = ((london_vwap - close).abs() / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = stretch.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: London-close fade {close.loc[i]:.4f} "
                    f"frac {float(close_frac.loc[i]):.2f} vwap {london_vwap.loc[i]:.4f} "
                    f"vol {volume.loc[i]:.1f}>{vol_mean.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["LondonCloseInventoryFadeParams", "LondonCloseInventoryFadeStrategy"]
