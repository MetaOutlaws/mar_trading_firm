"""Fade a rolling-VWAP ± σ band only inside a Bollinger-width squeeze.

Bands sit around the rolling 20 VWAP using the rolling stdev of close, not
around the SMA (`bollinger_mean_reversion` is a book-row BB fade). Entry
requires a 1h touch of the outer band AND BB width in the bottom 30% of
its 100-bar range. Target is the rolling VWAP.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class VwapVolatilityBandFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    vwap_period: int = 20
    # Multiplier on rolling stdev of close around the VWAP.
    band_k: float = 2.0
    bb_period: int = 20
    bb_k: float = 2.0
    # BB-width must sit in the bottom squeeze_pct of the last squeeze_lookback.
    squeeze_lookback: int = 100
    squeeze_pct: float = 0.30
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class VwapVolatilityBandFadeStrategy(Strategy):
    name = "vwap_volatility_band_fade"

    def __init__(self, params: VwapVolatilityBandFadeParams | None = None) -> None:
        super().__init__(params or VwapVolatilityBandFadeParams())
        self.params: VwapVolatilityBandFadeParams = self.params
        self.min_bars = int(self.params.squeeze_lookback) + int(self.params.vwap_period) + 2

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
        period = int(params.vwap_period)
        k = float(params.band_k)

        # Rolling typical-price VWAP, not a UTC session reset and not BB mid.
        vwap = ind.rolling_vwap(high, low, close, volume, period=period)
        # Stdev of close (same convention as Bollinger), bands around VWAP.
        stdev = close.astype("float64").rolling(window=period, min_periods=period).std(ddof=0)
        upper = vwap + k * stdev
        lower = vwap - k * stdev

        width = ind.bollinger_width(close, int(params.bb_period), float(params.bb_k))
        lookback = int(params.squeeze_lookback)
        # Inclusive 100-bar window ending at t. Require a real range so a
        # flat tape (width_max == width_min) is not a fake squeeze.
        width_min = width.rolling(lookback, min_periods=lookback).min()
        width_max = width.rolling(lookback, min_periods=lookback).max()
        span = width_max - width_min
        threshold = width_min + float(params.squeeze_pct) * span
        in_squeeze = (span > 0) & (width <= threshold)

        # Touch the outer VWAP band. Degenerate stdev=0 collapses to VWAP —
        # that is not a stretch, skip it.
        stretched = stdev > 0
        long_raw = in_squeeze & stretched & vwap.notna() & (low <= lower)
        short_raw = in_squeeze & stretched & vwap.notna() & (high >= upper)

        signals["rolling_vwap"] = vwap
        signals["vwap_upper"] = upper
        signals["vwap_lower"] = lower
        signals["bb_width"] = width

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
        band_width = (upper - lower).replace(0, pd.NA)
        stretch = ((vwap - close).abs() / band_width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = stretch.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: VWAP-band fade close {close.loc[i]:.4f} "
                    f"vwap {vwap.loc[i]:.4f} band "
                    f"{(lower if params.side is SignalSide.LONG else upper).loc[i]:.4f} "
                    f"bbw {width.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["VwapVolatilityBandFadeParams", "VwapVolatilityBandFadeStrategy"]
