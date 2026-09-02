"""
4h trend, 1h pullback — higher-timeframe regime, slower entry than 15m/1h breakouts.

15m and 1h raw breakouts overtraded after costs. This sleeve keeps the
directional bet (trade with the trend) but:
* measures the trend on completed 4h bars (EMA + ADX),
* enters on a 1h pullback to the 1h EMA, not a breakout.

Walk-forward and paper both feed 1h candles. The 4h series is resampled
inside `generate_signals` from those same bars. Only a *completed* 4h bar
is used, so an in-progress 4h candle cannot leak into a 1h signal.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class TrendPullbackHtfParams(StrategyParams):
    """Parameters for the 4h-trend / 1h-pullback sleeve."""

    side: SignalSide = SignalSide.LONG
    # 4h trend EMAs (computed on resampled bars).
    trend_ema_fast: int = 20
    trend_ema_slow: int = 50
    adx_period: int = 14
    # 1h pullback EMA.
    pullback_ema: int = 20
    htf_minutes: int = 240
    # 0 disables the 4h ADX filter so a first walk-forward can measure the raw rule.
    min_adx: float = 20.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


def _htf_ohlcv(candles: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Resample entry-clock bars to the higher timeframe."""
    hours = max(int(minutes) // 60, 1)
    htf = candles.resample(f"{hours}h").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return htf.dropna(how="any")


def _completed_htf(series: pd.Series, index: pd.Index) -> pd.Series:
    """Map HTF values onto the entry clock using only finished HTF bars.

    `shift(1)` drops the current (possibly incomplete) HTF bar, then `ffill`
    carries the last completed value forward onto each 1h timestamp.
    """
    return series.shift(1).reindex(index, method="ffill")


class TrendPullbackHtfStrategy(Strategy):
    """4h EMA/ADX regime + 1h pullback to the fast 1h EMA."""

    name = "trend_pullback_htf"

    def __init__(self, params: TrendPullbackHtfParams | None = None) -> None:
        super().__init__(params or TrendPullbackHtfParams())
        self.params: TrendPullbackHtfParams = self.params
        htf_bars = max(self.params.trend_ema_slow + 10, self.params.adx_period + 40)
        ratio = max(self.params.htf_minutes // 60, 1)
        self.min_bars = htf_bars * ratio + self.params.pullback_ema + 10

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        htf = _htf_ohlcv(candles, params.htf_minutes)
        if len(htf) < params.trend_ema_slow + 5:
            signals["reason"] = "insufficient higher-timeframe history"
            return signals

        htf_fast = ind.ema(htf["close"], params.trend_ema_fast)
        htf_slow = ind.ema(htf["close"], params.trend_ema_slow)
        htf_adx, htf_plus, htf_minus = ind.adx(
            htf["high"], htf["low"], htf["close"], params.adx_period
        )
        regime_long = _completed_htf(htf_fast > htf_slow, candles.index)
        regime_short = _completed_htf(htf_fast < htf_slow, candles.index)
        adx_1h = _completed_htf(htf_adx, candles.index)
        plus_1h = _completed_htf(htf_plus, candles.index)
        minus_1h = _completed_htf(htf_minus, candles.index)
        trend_fast_1h = _completed_htf(htf_fast, candles.index)
        trend_slow_1h = _completed_htf(htf_slow, candles.index)

        close = candles["close"]
        high = candles["high"]
        low = candles["low"]
        pullback = ind.ema(close, params.pullback_ema)
        adx_ok = True if params.min_adx <= 0 else adx_1h >= params.min_adx
        was_above = close.shift(1) > pullback.shift(1)
        was_below = close.shift(1) < pullback.shift(1)
        tagged = low <= pullback
        spiked = high >= pullback

        signals["htf_ema_fast"] = trend_fast_1h
        signals["htf_ema_slow"] = trend_slow_1h
        signals["pullback_ema"] = pullback
        signals["adx"] = adx_1h
        signals["plus_di"] = plus_1h
        signals["minus_di"] = minus_1h

        if params.side is SignalSide.LONG:
            entry = regime_long & adx_ok & was_above & tagged & (close >= pullback)
            side_value = SignalSide.LONG.value
            signal_value = 1
        else:
            entry = regime_short & adx_ok & was_below & spiked & (close <= pullback)
            side_value = SignalSide.SHORT.value
            signal_value = -1

        entry = entry.fillna(False).astype(bool)
        entry.iloc[: self.min_bars] = False

        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        dist = (close - pullback).abs() / pullback.replace(0, pd.NA)
        adx_component = ((adx_1h - 20.0) / 20.0).clip(0.0, 1.0)
        signals.loc[entry, "score"] = (
            adx_component.fillna(0.0) + (1.0 - dist.clip(0.0, 1.0).fillna(1.0))
        )[entry]
        signals["reason"] = self._reasons(entry, close, pullback, adx_1h)
        return signals

    def _reasons(
        self,
        entry: pd.Series,
        close: pd.Series,
        pullback: pd.Series,
        adx_value: pd.Series,
    ) -> pd.Series:
        reasons = pd.Series("", index=entry.index, dtype="object")
        if not entry.any():
            return reasons
        side_label = "LONG" if self.params.side is SignalSide.LONG else "SHORT"
        fired = entry[entry].index
        reasons.loc[fired] = [
            (
                f"{side_label} 4h-trend 1h-pullback close={close.loc[ts]:.4f} "
                f"ema={pullback.loc[ts]:.4f} adx4h={adx_value.loc[ts]:.1f}"
            )
            for ts in fired
        ]
        return reasons
