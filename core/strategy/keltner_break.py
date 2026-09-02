"""Break a Keltner band. EMA of typical ± ATR, not Bollinger and not SuperTrend."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class KeltnerBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    ema_period: int = 20
    atr_period: int = 10
    atr_k: float = 1.5
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class KeltnerBreakStrategy(Strategy):
    name = "keltner_break"

    def __init__(self, params: KeltnerBreakParams | None = None) -> None:
        super().__init__(params or KeltnerBreakParams())
        self.params: KeltnerBreakParams = self.params
        self.min_bars = max(int(self.params.ema_period), int(self.params.atr_period)) + 6

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        mid, upper, lower = ind.keltner_channel(
            candles["high"],
            candles["low"],
            candles["close"],
            int(params.ema_period),
            int(params.atr_period),
            float(params.atr_k),
        )
        close = candles["close"]
        signals["keltner_mid"] = mid
        signals["keltner_upper"] = upper
        signals["keltner_lower"] = lower
        # Prior-bar envelope so a close is measured against a band that does
        # not include this bar's ATR (distinct from SuperTrend's ratcheted HL2).
        prior_upper = upper.shift(1)
        prior_lower = lower.shift(1)
        if params.side is SignalSide.LONG:
            entry = (close > prior_upper) & (close.shift(1) <= prior_upper.shift(1))
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (close < prior_lower) & (close.shift(1) >= prior_lower.shift(1))
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            band = prior_upper if params.side is SignalSide.LONG else prior_lower
            reasons.loc[entry] = [
                f"{side_value}: Keltner break {close.loc[i]:.2f} vs {band.loc[i]:.2f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["KeltnerBreakParams", "KeltnerBreakStrategy"]
