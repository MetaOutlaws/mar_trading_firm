"""Follow persistent close location (CLV) without a new 20-bar extreme.

CLV = (close-low)/(high-low). LONG when the lookback mean CLV is at or
above `clv_threshold` and this close is not a 20-bar high. SHORT when the
mean is at or below (1 - clv_threshold) and this close is not a 20-bar low.

Auction location persistence across bars. A doji at the high has CLV near 1
and body efficiency near 0.

Not `body_efficiency_follow` (body occupancy / true range). Not
`wick_rejection_reversal` (single-bar wick geometry). Not turnover, not
session/VWAP, not week-open.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked anti-breakout window. Walk-forward searches lookback and clv_threshold.
EXTREME_BARS = 20


@dataclass(frozen=True)
class CloseLocationPersistenceParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Bars in the mean-CLV window, including the current bar.
    lookback: int = 8
    # LONG floor. SHORT uses 1 - clv_threshold so the two sides stay mirrors.
    clv_threshold: float = 0.75
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class CloseLocationPersistenceStrategy(Strategy):
    name = "close_location_persistence"

    def __init__(self, params: CloseLocationPersistenceParams | None = None) -> None:
        super().__init__(params or CloseLocationPersistenceParams())
        self.params: CloseLocationPersistenceParams = self.params
        self.min_bars = max(int(self.params.lookback), EXTREME_BARS) + 1

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
        lookback = int(params.lookback)
        threshold = float(params.clv_threshold)
        # Bar-local CLV, then a causal lookback mean. Current bar is in the mean.
        clv = ind.close_location_value(high, low, close)
        mean_clv = ind.mean_close_location(high, low, close, lookback)
        # 20-bar extreme includes this close: persistence, not a Donchian break.
        close_high = close.rolling(EXTREME_BARS, min_periods=EXTREME_BARS).max()
        close_low = close.rolling(EXTREME_BARS, min_periods=EXTREME_BARS).min()
        not_high = close < close_high
        not_low = close > close_low

        long_raw = mean_clv.ge(threshold) & not_high
        short_raw = mean_clv.le(1.0 - threshold) & not_low

        signals["clv"] = clv
        signals["mean_clv"] = mean_clv
        signals["close_high"] = close_high
        signals["close_low"] = close_low

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
        if params.side is SignalSide.LONG:
            score = mean_clv.clip(0.0, 1.0)
        else:
            score = (1.0 - mean_clv).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: mean CLV {mean_clv.loc[i]:.2f} "
                    f"close {close.loc[i]:.4f} vs 20-bar "
                    f"{close_high.loc[i]:.4f}/{close_low.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "CloseLocationPersistenceParams",
    "CloseLocationPersistenceStrategy",
    "EXTREME_BARS",
]
