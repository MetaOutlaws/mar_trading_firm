"""Follow a volume-thrust bar that exits ATR compression.

Compression is 20-bar ATR in the bottom 30% of its 100-bar range (ATR
percentile only — not BB width, not BB-inside-Keltner). Trigger is a bar
with true range > 1.5× the prior ATR, close in the bar's direction, and
volume above the prior-20 mean. Trade with that close.

Not `squeeze_momentum_break` (BB inside Keltner + linreg), not `nr7_breakout`
(narrowest of 7), not `bb_squeeze_breakout` (BB-width then ATR channel).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class RangeCompressionVolumeThrustParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    atr_period: int = 20
    compress_lookback: int = 100
    # Bottom fraction of the 100-bar ATR range. Walk-forward may search this.
    compress_pct: float = 0.30
    # True range / prior ATR. Walk-forward may search this.
    thrust_mult: float = 1.5
    vol_lookback: int = 20
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class RangeCompressionVolumeThrustStrategy(Strategy):
    name = "range_compression_volume_thrust"

    def __init__(self, params: RangeCompressionVolumeThrustParams | None = None) -> None:
        super().__init__(params or RangeCompressionVolumeThrustParams())
        self.params: RangeCompressionVolumeThrustParams = self.params
        self.min_bars = int(self.params.compress_lookback) + 2

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
        open_ = candles["open"]
        volume = candles["volume"]

        atr20 = ind.atr(high, low, close, int(params.atr_period))
        # Prior ATR so the thrust bar cannot lift itself out of the squeeze.
        atr_prev = atr20.shift(1)
        lookback = int(params.compress_lookback)
        atr_min = atr_prev.rolling(lookback, min_periods=lookback).min()
        atr_max = atr_prev.rolling(lookback, min_periods=lookback).max()
        span = atr_max - atr_min
        threshold = atr_min + float(params.compress_pct) * span
        compressed = (span > 0) & atr_prev.notna() & (atr_prev <= threshold)

        tr = ind.true_range(high, low, close)
        expansion = atr_prev.notna() & (tr > float(params.thrust_mult) * atr_prev)
        vol_mean = ind.prior_rolling_mean(volume, int(params.vol_lookback))
        heavy = volume > vol_mean
        bull = close > open_
        bear = close < open_

        long_raw = compressed & expansion & heavy & bull
        short_raw = compressed & expansion & heavy & bear

        signals["atr"] = atr20
        signals["atr_prev"] = atr_prev
        signals["true_range"] = tr
        signals["vol_mean"] = vol_mean
        signals["compressed"] = compressed.astype("float64")

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
        thrust = (tr / atr_prev.replace(0, pd.NA)).clip(0.0, 4.0) / 4.0
        signals.loc[entry, "score"] = thrust.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: ATR-compress thrust TR {tr.loc[i]:.4f} "
                    f"> {params.thrust_mult:.2f}×ATR {atr_prev.loc[i]:.4f} "
                    f"vol {volume.loc[i]:.1f}>{vol_mean.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "RangeCompressionVolumeThrustParams",
    "RangeCompressionVolumeThrustStrategy",
]
