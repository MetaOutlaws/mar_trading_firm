"""Break a 3-bar dry-up box on the first volume-confirmed thrust.

Require three consecutive bars with volume below the prior-20 mean (current
bar excluded from that mean). Then a thrust bar whose volume is above that
mean and whose close breaks the 3-bar high (LONG) or 3-bar low (SHORT).

Consecutive low-volume box then expansion break. Not
`range_compression_volume_thrust` (ATR-percentile squeeze), not
`nr7_breakout` (narrowest of 7), not `squeeze_momentum_break` (BB in Keltner).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class VolumeDryupRangeBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Consecutive dry bars that form the box. Walk-forward may search this.
    dry_bars: int = 3
    vol_lookback: int = 20
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class VolumeDryupRangeBreakStrategy(Strategy):
    name = "volume_dryup_range_break"

    def __init__(self, params: VolumeDryupRangeBreakParams | None = None) -> None:
        super().__init__(params or VolumeDryupRangeBreakParams())
        self.params: VolumeDryupRangeBreakParams = self.params
        self.min_bars = int(self.params.vol_lookback) + int(self.params.dry_bars) + 1

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
        dry_n = int(params.dry_bars)
        vol_mean = ind.prior_rolling_mean(volume, int(params.vol_lookback))
        dry = volume < vol_mean
        # The box is the prior `dry_n` bars, all quiet. This bar is the thrust.
        dry_run = dry.copy()
        for lag in range(1, dry_n + 1):
            if lag == 1:
                dry_run = dry.shift(1)
            else:
                dry_run = dry_run & dry.shift(lag)
        box_high = high.shift(1).rolling(dry_n, min_periods=dry_n).max()
        box_low = low.shift(1).rolling(dry_n, min_periods=dry_n).min()
        thrust = vol_mean.notna() & (volume > vol_mean)

        long_raw = dry_run & thrust & box_high.notna() & (close > box_high)
        short_raw = dry_run & thrust & box_low.notna() & (close < box_low)

        signals["vol_mean"] = vol_mean
        signals["box_high"] = box_high
        signals["box_low"] = box_low
        signals["dry_run"] = dry_run.fillna(False).astype("float64")

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (box_high - box_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - box_high) / width).clip(0.0, 1.0)
        else:
            score = ((box_low - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: dry-up break close {close.loc[i]:.4f} "
                    f"box {box_high.loc[i]:.4f}/{box_low.loc[i]:.4f} "
                    f"vol {volume.loc[i]:.1f}>{vol_mean.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["VolumeDryupRangeBreakParams", "VolumeDryupRangeBreakStrategy"]
