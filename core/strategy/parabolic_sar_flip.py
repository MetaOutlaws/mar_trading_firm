"""Trade a Parabolic SAR flip. Accelerating stop, not SuperTrend ATR bands."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ParabolicSarFlipParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    af_start: float = 0.02
    af_step: float = 0.02
    af_max: float = 0.20
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class ParabolicSarFlipStrategy(Strategy):
    name = "parabolic_sar_flip"

    def __init__(self, params: ParabolicSarFlipParams | None = None) -> None:
        super().__init__(params or ParabolicSarFlipParams())
        self.params: ParabolicSarFlipParams = self.params
        self.min_bars = 5

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        sar, direction = ind.parabolic_sar_direction(
            candles["high"],
            candles["low"],
            af_start=float(params.af_start),
            af_step=float(params.af_step),
            af_max=float(params.af_max),
        )
        signals["sar"] = sar
        signals["sar_dir"] = direction
        prev = direction.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev <= 0) & (direction > 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev >= 0) & (direction < 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: SAR flip" for _ in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["ParabolicSarFlipParams", "ParabolicSarFlipStrategy"]
