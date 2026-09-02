"""
Donchian channel breakout — the next coded family after rejected rsi_trend.

Classic CTA rule: go long when close breaks the prior N-bar high, short when
close breaks the prior N-bar low. The channel is computed on *prior* bars
(`shift(1)`), so the current bar cannot leak into its own breakout level.

ADX is an optional trend-strength filter. 0 disables it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class DonchianParams(StrategyParams):
    """Parameters for the Donchian breakout sleeve."""

    side: SignalSide = SignalSide.LONG
    lookback: int = 20
    adx_period: int = 14
    # 0 disables the ADX filter so a first walk-forward can measure the raw rule.
    min_adx: float = 20.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class DonchianBreakoutStrategy(Strategy):
    """N-bar channel breakout with an optional ADX filter."""

    name = "donchian_breakout"

    def __init__(self, params: DonchianParams | None = None) -> None:
        super().__init__(params or DonchianParams())
        self.params: DonchianParams = self.params
        # ADX needs a Wilder seed; add headroom beyond the channel lookback.
        self.min_bars = max(self.params.lookback + 5, self.params.adx_period + 40)

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

        # Prior-bar channel: exclude the current bar so a breakout is not
        # measured against a high/low that includes itself.
        channel_high = high.shift(1).rolling(params.lookback, min_periods=params.lookback).max()
        channel_low = low.shift(1).rolling(params.lookback, min_periods=params.lookback).min()
        adx_value, plus_di, minus_di = ind.adx(high, low, close, params.adx_period)

        signals["channel_high"] = channel_high
        signals["channel_low"] = channel_low
        signals["adx"] = adx_value
        signals["plus_di"] = plus_di
        signals["minus_di"] = minus_di

        adx_ok = adx_value >= params.min_adx if params.min_adx > 0 else True

        if params.side is SignalSide.LONG:
            entry = (close > channel_high) & adx_ok
            side_value = SignalSide.LONG.value
            signal_value = 1
        else:
            entry = (close < channel_low) & adx_ok
            side_value = SignalSide.SHORT.value
            signal_value = -1

        entry = entry.fillna(False).astype(bool)
        entry.iloc[: self.min_bars] = False

        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = self._score(close, channel_high, channel_low, adx_value)[entry]
        signals["reason"] = self._reasons(entry, close, channel_high, channel_low, adx_value)
        return signals

    def _score(
        self,
        close: pd.Series,
        channel_high: pd.Series,
        channel_low: pd.Series,
        adx_value: pd.Series,
    ) -> pd.Series:
        """How far through the channel, plus ADX conviction. Roughly [0, 2]."""
        params = self.params
        width = (channel_high - channel_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            extension = ((close - channel_high) / width).clip(0.0, 1.0)
        else:
            extension = ((channel_low - close) / width).clip(0.0, 1.0)
        adx_component = ((adx_value - 20.0) / 20.0).clip(0.0, 1.0)
        return (extension.fillna(0.0) + adx_component.fillna(0.0))

    def _reasons(
        self,
        entry: pd.Series,
        close: pd.Series,
        channel_high: pd.Series,
        channel_low: pd.Series,
        adx_value: pd.Series,
    ) -> pd.Series:
        reasons = pd.Series("", index=entry.index, dtype="object")
        if not entry.any():
            return reasons
        side_label = "LONG" if self.params.side is SignalSide.LONG else "SHORT"
        fired = entry[entry].index
        reasons.loc[fired] = [
            (
                f"{side_label}: close {close.loc[stamp]:.4f} vs channel "
                f"{channel_high.loc[stamp]:.4f}/{channel_low.loc[stamp]:.4f}, "
                f"ADX {adx_value.loc[stamp]:.1f}"
            )
            for stamp in fired
        ]
        return reasons


__all__ = ["DonchianParams", "DonchianBreakoutStrategy"]
