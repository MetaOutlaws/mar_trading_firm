"""
Bollinger fade in chop — mean-reversion when ADX says the market is not trending.

Opposite bet from Donchian: buy a 4h stretch below the lower band, sell a
stretch above the upper band, only when ADX is weak. Hard stop and target
come from StrategyParams so costs still apply.

`max_adx` of 0 disables the chop filter so a first walk-forward can measure
the raw band fade.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class BollingerMrParams(StrategyParams):
    """Parameters for the Bollinger fade sleeve."""

    side: SignalSide = SignalSide.LONG
    bb_period: int = 20
    band_k: float = 2.0
    adx_period: int = 14
    # Enter only when ADX is at or below this. 0 disables the filter.
    max_adx: float = 20.0
    take_profit_pct: float = 0.03
    stop_loss_pct: float = 0.02


class BollingerMeanReversionStrategy(Strategy):
    """Fade a Bollinger stretch, optionally only in a low-ADX regime."""

    name = "bollinger_mean_reversion"

    def __init__(self, params: BollingerMrParams | None = None) -> None:
        super().__init__(params or BollingerMrParams())
        self.params: BollingerMrParams = self.params
        self.min_bars = max(self.params.bb_period + 5, self.params.adx_period + 40)

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
        mid, upper, lower = ind.bollinger_bands(close, params.bb_period, params.band_k)
        adx_value, plus_di, minus_di = ind.adx(high, low, close, params.adx_period)
        chop_ok = True if params.max_adx <= 0 else adx_value <= params.max_adx

        signals["bb_mid"] = mid
        signals["bb_upper"] = upper
        signals["bb_lower"] = lower
        signals["adx"] = adx_value
        signals["plus_di"] = plus_di
        signals["minus_di"] = minus_di

        if params.side is SignalSide.LONG:
            entry = chop_ok & (close <= lower)
            side_value = SignalSide.LONG.value
            signal_value = 1
        else:
            entry = chop_ok & (close >= upper)
            side_value = SignalSide.SHORT.value
            signal_value = -1

        entry = entry.fillna(False).astype(bool)
        entry.iloc[: self.min_bars] = False

        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (upper - lower).replace(0, pd.NA)
        stretch = ((mid - close).abs() / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = stretch.fillna(0.0)[entry]
        signals["reason"] = self._reasons(entry, close, lower, upper, adx_value)
        return signals

    def _reasons(
        self,
        entry: pd.Series,
        close: pd.Series,
        lower: pd.Series,
        upper: pd.Series,
        adx_value: pd.Series,
    ) -> pd.Series:
        reasons = pd.Series("", index=entry.index, dtype="object")
        if not entry.any():
            return reasons
        side_label = "LONG" if self.params.side is SignalSide.LONG else "SHORT"
        band = lower if self.params.side is SignalSide.LONG else upper
        fired = entry[entry].index
        reasons.loc[fired] = [
            (
                f"{side_label} Bollinger fade close={close.loc[ts]:.4f} "
                f"band={band.loc[ts]:.4f} adx={adx_value.loc[ts]:.1f}"
            )
            for ts in fired
        ]
        return reasons
