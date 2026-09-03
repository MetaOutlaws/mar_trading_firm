"""Fade a weak-volume 4h sweep of the prior UTC calendar day's high/low.

Calendar UTC day box, not floor pivots (`prior_day_pivot_breakout` is a
rejected breakout of P/R1/S1) and not the Asian 00:00–08:00 session box
(`session_liquidity_sweep`). A 4h bar that pokes the prior day's high or
low on volume below the 20-period volume MA fades toward that day's
session VWAP. Close-back-inside is not required — the filter is weak
volume, not a failed-sweep close.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SessionBoundaryVolumeFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Locked at 20. Brief: sweeping bar volume below the 20-period volume MA.
    vol_period: int = 20
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class SessionBoundaryVolumeFadeStrategy(Strategy):
    name = "session_boundary_volume_fade"

    def __init__(self, params: SessionBoundaryVolumeFadeParams | None = None) -> None:
        super().__init__(params or SessionBoundaryVolumeFadeParams())
        self.params: SessionBoundaryVolumeFadeParams = self.params
        # Prior UTC day plus a full volume-MA window.
        self.min_bars = int(self.params.vol_period) + 8

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
        vol_period = int(params.vol_period)

        # Causal: snapshot of yesterday's H/L on the first bar of today.
        prior_high, prior_low = ind.prior_utc_day_range(high, low)
        # Daily VWAP resets at UTC midnight — the fade target, not the entry tag.
        daily_vwap = ind.utc_session_vwap(high, low, close, volume)
        vol_ma = ind.sma(volume, vol_period)
        weak_volume = volume < vol_ma

        # Sweep = poke through the prior UTC day box. Not a close-back-inside
        # failed sweep (that is session_liquidity_sweep / monday_range).
        sweep_low = prior_low.notna() & (low < prior_low) & weak_volume
        sweep_high = prior_high.notna() & (high > prior_high) & weak_volume
        # Target is daily VWAP: only fade when price is on the sweep side of it.
        long_raw = sweep_low & daily_vwap.notna() & (close < daily_vwap)
        short_raw = sweep_high & daily_vwap.notna() & (close > daily_vwap)

        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["daily_vwap"] = daily_vwap
        signals["vol_ma"] = vol_ma

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One fade per UTC day. Calendar box, not a rolling Donchian.
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (prior_high - prior_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((daily_vwap - close) / width).clip(0.0, 1.0)
        else:
            score = ((close - daily_vwap) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: UTC-day box fade close {close.loc[i]:.4f} vs "
                    f"{prior_high.loc[i]:.4f}/{prior_low.loc[i]:.4f} "
                    f"vwap {daily_vwap.loc[i]:.4f} vol {volume.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["SessionBoundaryVolumeFadeParams", "SessionBoundaryVolumeFadeStrategy"]
