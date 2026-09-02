"""
ATR channel (Keltner) breakout — next coded family after rejected HTF pullback.

Enter long when close breaks above the prior bar's EMA + k·ATR; short when
close breaks below EMA − k·ATR. The channel uses *prior* completed ATR and
EMA (`shift(1)`), so the current bar cannot leak into its own breakout level.

This is the same breakout bet as Donchian, with volatility width instead of
an N-bar high, and only on a 4h clock — 15m/1h ATR breakouts already failed
as overtrading after costs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class AtrChannelParams(StrategyParams):
    """Parameters for the ATR channel breakout sleeve."""

    side: SignalSide = SignalSide.LONG
    ema_period: int = 20
    atr_period: int = 14
    atr_k: float = 2.0
    adx_period: int = 14
    # 0 disables the ADX filter so a first walk-forward can measure the raw rule.
    min_adx: float = 20.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class AtrChannelBreakoutStrategy(Strategy):
    """EMA ± k·ATR breakout with an optional ADX filter."""

    name = "atr_channel_breakout"

    def __init__(self, params: AtrChannelParams | None = None) -> None:
        super().__init__(params or AtrChannelParams())
        self.params: AtrChannelParams = self.params
        # Wilder ATR/ADX need a seed; add headroom beyond the EMA period.
        self.min_bars = max(self.params.ema_period + 5, self.params.atr_period + 40)

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

        mid = ind.ema(close, params.ema_period)
        atr_value = ind.atr(high, low, close, params.atr_period)
        # Prior-bar channel: exclude the current bar so a breakout is not
        # measured against an ATR/EMA that includes itself.
        upper = mid.shift(1) + params.atr_k * atr_value.shift(1)
        lower = mid.shift(1) - params.atr_k * atr_value.shift(1)
        adx_value, plus_di, minus_di = ind.adx(high, low, close, params.adx_period)

        signals["mid"] = mid
        signals["upper"] = upper
        signals["lower"] = lower
        signals["atr"] = atr_value
        signals["adx"] = adx_value
        signals["plus_di"] = plus_di
        signals["minus_di"] = minus_di

        adx_ok = adx_value >= params.min_adx if params.min_adx > 0 else True

        if params.side is SignalSide.LONG:
            entry = (close > upper) & adx_ok
            side_value = SignalSide.LONG.value
            signal_value = 1
        else:
            entry = (close < lower) & adx_ok
            side_value = SignalSide.SHORT.value
            signal_value = -1

        entry = entry.fillna(False).astype(bool)
        entry.iloc[: self.min_bars] = False

        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = self._score(close, upper, lower, adx_value)[entry]
        signals["reason"] = self._reasons(entry, close, upper, lower, adx_value)
        return signals

    def _score(
        self,
        close: pd.Series,
        upper: pd.Series,
        lower: pd.Series,
        adx_value: pd.Series,
    ) -> pd.Series:
        """How far through the channel, plus ADX conviction. Roughly [0, 2]."""
        width = (upper - lower).replace(0, pd.NA)
        if self.params.side is SignalSide.LONG:
            extension = ((close - upper) / width).clip(0.0, 1.0)
        else:
            extension = ((lower - close) / width).clip(0.0, 1.0)
        adx_component = ((adx_value - 20.0) / 20.0).clip(0.0, 1.0)
        return extension.fillna(0.0) + adx_component.fillna(0.0)

    def _reasons(
        self,
        entry: pd.Series,
        close: pd.Series,
        upper: pd.Series,
        lower: pd.Series,
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
                f"{upper.loc[stamp]:.4f}/{lower.loc[stamp]:.4f}, "
                f"ADX {adx_value.loc[stamp]:.1f}"
            )
            for stamp in fired
        ]
        return reasons


__all__ = ["AtrChannelParams", "AtrChannelBreakoutStrategy"]
