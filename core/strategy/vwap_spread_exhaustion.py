"""Fade an N-bar extreme of rolling-VWAP vs SMA, scaled by ATR.

spread = abs(rolling 20 VWAP − 20 SMA) / 20 ATR. When that spread is a
new N-bar high and volume is expanding, fade back to the rolling VWAP,
only in a low-ADX range. This is not `utc_session_vwap_reversion` (a
UTC-midnight session VWAP stretch). Rolling VWAP vs SMA dislocation.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class VwapSpreadExhaustionParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    vwap_period: int = 20
    sma_period: int = 20
    atr_period: int = 20
    # N-bar extreme of the ATR-normalized VWAP−SMA spread.
    extreme_lookback: int = 20
    adx_period: int = 14
    # Enter only when ADX is at or below this. 0 disables the chop filter.
    max_adx: float = 20.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class VwapSpreadExhaustionStrategy(Strategy):
    name = "vwap_spread_exhaustion"

    def __init__(self, params: VwapSpreadExhaustionParams | None = None) -> None:
        super().__init__(params or VwapSpreadExhaustionParams())
        self.params: VwapSpreadExhaustionParams = self.params
        # ADX needs extra bars after its period; keep warmup above both windows.
        self.min_bars = (
            max(
                int(self.params.vwap_period),
                int(self.params.sma_period),
                int(self.params.atr_period),
                int(self.params.extreme_lookback),
                int(self.params.adx_period),
            )
            + 40
        )

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
        lookback = int(params.extreme_lookback)

        # Rolling typical-price VWAP, not a UTC session reset.
        vwap = ind.rolling_vwap(
            high, low, close, volume, period=int(params.vwap_period)
        )
        sma_value = ind.sma(close, int(params.sma_period))
        atr_value = ind.atr(high, low, close, int(params.atr_period))
        spread = (vwap - sma_value).abs() / atr_value.replace(0, pd.NA)

        # New N-bar high of the spread. Prior N only — current print is the candidate.
        prior_spread_high = spread.shift(1).rolling(lookback, min_periods=lookback).max()
        is_extreme = spread > prior_spread_high
        # Expanding volume vs the trailing (current-excluded) 20-bar mean.
        vol_expanding = ind.volume_ratio(volume, period=int(params.vwap_period)) > 1.0

        adx_value, plus_di, minus_di = ind.adx(high, low, close, int(params.adx_period))
        chop_ok = True if params.max_adx <= 0 else adx_value <= params.max_adx

        ready = vwap.notna() & sma_value.notna() & atr_value.notna()
        long_raw = ready & is_extreme & vol_expanding & chop_ok & (close < vwap)
        short_raw = ready & is_extreme & vol_expanding & chop_ok & (close > vwap)

        signals["rolling_vwap"] = vwap
        signals["sma"] = sma_value
        signals["spread"] = spread
        signals["adx"] = adx_value
        signals["plus_di"] = plus_di
        signals["minus_di"] = minus_di

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
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: VWAP-SMA spread fade close {close.loc[i]:.4f} "
                    f"vwap {vwap.loc[i]:.4f} spread {spread.loc[i]:.3f} "
                    f"adx {adx_value.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["VwapSpreadExhaustionParams", "VwapSpreadExhaustionStrategy"]
