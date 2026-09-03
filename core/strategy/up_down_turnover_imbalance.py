"""Follow-the-money: up-bar vs down-bar turnover imbalance.

An up-bar is close > prior close; a down-bar is close < prior close.
Imbalance is the rolling share of quote volume (turnover) that printed
on those two sets of bars:

    up_to   = turnover on up-bars, else 0
    down_to = turnover on down-bars, else 0
    imb     = (sum_N up_to - sum_N down_to) / (sum_N up_to + sum_N down_to)

LONG when imb > k; SHORT when imb < -k. This follows the money, it does
not fade it, and it is not a close-only oscillator (RSI/CCI of close).
Bybit already ships unused `turnover` beside base `volume`. The sleeve
reads that column; it does not cumsum into an OBV ledger, does not use
per-bar VWAP, and does not invent taker/CVD/netflow columns.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class UpDownTurnoverImbalanceParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    lookback: int = 20
    # Share of quote volume on the dominant side. 0.30 ≈ a 65/35 split.
    imbalance_k: float = 0.30
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class UpDownTurnoverImbalanceStrategy(Strategy):
    name = "up_down_turnover_imbalance"

    def __init__(self, params: UpDownTurnoverImbalanceParams | None = None) -> None:
        super().__init__(params or UpDownTurnoverImbalanceParams())
        self.params: UpDownTurnoverImbalanceParams = self.params
        self.min_bars = int(self.params.lookback) + 5

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        if "turnover" not in candles.columns:
            raise ValueError(f"{self.name}: candles missing columns ['turnover']")
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        close = candles["close"].astype("float64")
        turnover = candles["turnover"].astype("float64")
        # Up/down by close vs prior close, not close vs open (that is the
        # signed-range family) and not a close-only oscillator.
        up_bar = close > close.shift(1)
        down_bar = close < close.shift(1)
        up_to = turnover.where(up_bar, 0.0)
        down_to = turnover.where(down_bar, 0.0)

        lookback = int(params.lookback)
        up_sum = up_to.rolling(lookback, min_periods=lookback).sum()
        down_sum = down_to.rolling(lookback, min_periods=lookback).sum()
        total = up_sum + down_sum
        # Rolling share, not a cumulative ledger (that would be OBV).
        imbalance = (up_sum - down_sum) / total.replace(0.0, pd.NA)

        signals["up_turnover"] = up_sum
        signals["down_turnover"] = down_sum
        signals["imbalance"] = imbalance

        threshold = float(params.imbalance_k)
        if params.side is SignalSide.LONG:
            raw = imbalance > threshold
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = imbalance < -threshold
            signal_value, side_value = -1, SignalSide.SHORT.value

        entry = raw.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: up/down turnover imb {imbalance.loc[i]:.2f} "
                    f"up {up_sum.loc[i]:.1f} down {down_sum.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["UpDownTurnoverImbalanceParams", "UpDownTurnoverImbalanceStrategy"]
