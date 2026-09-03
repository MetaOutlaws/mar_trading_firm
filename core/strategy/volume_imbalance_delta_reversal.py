"""Fade a 20-bar high/low when that bar's buy/sell volume share is exhausted.

Bar-level imbalance, not a cumulative force ledger (`volume_force_divergence`
is dead). Buying share is (close-low)/(high-low) on the sweep bar only. A new
20-bar high whose buying volume is under `exhaust_share` of total fades short
toward the 20-EMA; a new 20-bar low whose selling volume is under that share
fades long. No taker/CVD/netflow columns — OHLCV close-location only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class VolumeImbalanceDeltaReversalParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    lookback: int = 20
    ema_period: int = 20
    # Buying share below this at a new high (or selling share at a new low).
    exhaust_share: float = 0.20
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class VolumeImbalanceDeltaReversalStrategy(Strategy):
    name = "volume_imbalance_delta_reversal"

    def __init__(self, params: VolumeImbalanceDeltaReversalParams | None = None) -> None:
        super().__init__(params or VolumeImbalanceDeltaReversalParams())
        self.params: VolumeImbalanceDeltaReversalParams = self.params
        self.min_bars = int(self.params.lookback) + int(self.params.ema_period) + 2

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
        exhaust = float(params.exhaust_share)

        # One-bar buy share. Do not cumsum — that would be A/D / volume force.
        buy_share = ind.bar_buy_share(high, low, close)
        sell_share = 1.0 - buy_share
        ema_value = ind.ema(close, int(params.ema_period))

        # Prior N bars only — the current print is the candidate extreme.
        prior_high = high.shift(1).rolling(lookback, min_periods=lookback).max()
        prior_low = low.shift(1).rolling(lookback, min_periods=lookback).min()
        new_high = high > prior_high
        new_low = low < prior_low

        signals["buy_share"] = buy_share
        signals["sell_share"] = sell_share
        signals["ema"] = ema_value
        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low

        if params.side is SignalSide.LONG:
            # Sweep a new low; sellers are < exhaust_share of this bar's volume.
            entry = new_low & (sell_share < exhaust)
            signal_value, side_value = 1, SignalSide.LONG.value
            share = sell_share
        else:
            # Sweep a new high; buyers are < exhaust_share of this bar's volume.
            entry = new_high & (buy_share < exhaust)
            signal_value, side_value = -1, SignalSide.SHORT.value
            share = buy_share

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0 - share.clip(0.0, 1.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: bar imbalance fade px {close.loc[i]:.2f} "
                    f"buy {buy_share.loc[i]:.2f} ema {ema_value.loc[i]:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "VolumeImbalanceDeltaReversalParams",
    "VolumeImbalanceDeltaReversalStrategy",
]
