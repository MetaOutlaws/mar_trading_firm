"""Fade a 20-bar price extreme that ATR-normalized volume force does not confirm.

Distinct from `force_index_fade` (z-score of EMA(Δclose*volume)) and from
`volume_price_trend_break` (percent-change volume channel break). This sleeve
accumulates signed volume scaled by close-to-close change / ATR, then fades a
new price high/low when that ledger fails to confirm, only in a low-ADX chop.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class VolumeForceDivergenceParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    lookback: int = 20
    atr_period: int = 14
    adx_period: int = 14
    # Enter only when ADX is at or below this. 0 disables the chop filter.
    max_adx: float = 20.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class VolumeForceDivergenceStrategy(Strategy):
    name = "volume_force_divergence"

    def __init__(self, params: VolumeForceDivergenceParams | None = None) -> None:
        super().__init__(params or VolumeForceDivergenceParams())
        self.params: VolumeForceDivergenceParams = self.params
        # ADX needs extra bars after its period; keep warmup above both windows.
        self.min_bars = (
            max(int(self.params.lookback), int(self.params.atr_period), int(self.params.adx_period))
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
        lookback = int(params.lookback)

        # Cumulative ATR-normalized force. Current bar is included; that is
        # the confirmation print, not a future leak.
        vf = ind.cumulative_volume_force(
            high, low, close, volume, atr_period=int(params.atr_period)
        )
        adx_value, plus_di, minus_di = ind.adx(high, low, close, int(params.adx_period))
        chop_ok = True if params.max_adx <= 0 else adx_value <= params.max_adx

        # Prior N bars only — the current print is the candidate extreme.
        prior_price_high = high.shift(1).rolling(lookback, min_periods=lookback).max()
        prior_price_low = low.shift(1).rolling(lookback, min_periods=lookback).min()
        prior_vf_high = vf.shift(1).rolling(lookback, min_periods=lookback).max()
        prior_vf_low = vf.shift(1).rolling(lookback, min_periods=lookback).min()

        price_new_high = high > prior_price_high
        price_new_low = low < prior_price_low
        vf_lower_high = vf < prior_vf_high
        vf_higher_low = vf > prior_vf_low

        signals["volume_force"] = vf
        signals["adx"] = adx_value
        signals["plus_di"] = plus_di
        signals["minus_di"] = minus_di

        if params.side is SignalSide.LONG:
            # Bullish divergence: new price low, force makes a higher low.
            entry = chop_ok & price_new_low & vf_higher_low
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            # Bearish divergence: new price high, force makes a lower high.
            entry = chop_ok & price_new_high & vf_lower_high
            signal_value, side_value = -1, SignalSide.SHORT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: VF divergence px {close.loc[i]:.2f} vf {vf.loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["VolumeForceDivergenceParams", "VolumeForceDivergenceStrategy"]
