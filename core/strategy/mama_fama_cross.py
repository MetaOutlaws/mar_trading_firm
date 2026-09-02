"""Trade MAMA crossing FAMA. Hilbert-period adaptive MA, not a fixed EMA."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class MamaFamaCrossParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    fastlimit: float = 0.5
    slowlimit: float = 0.05
    # 0 disables. 50 keeps longs above SMA and shorts below it.
    trend_sma: int = 0
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class MamaFamaCrossStrategy(Strategy):
    name = "mama_fama_cross"

    def __init__(self, params: MamaFamaCrossParams | None = None) -> None:
        super().__init__(params or MamaFamaCrossParams())
        self.params: MamaFamaCrossParams = self.params
        self.min_bars = 12 + max(int(self.params.trend_sma), 0)

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        mama, fama = ind.mama_fama(
            candles["close"],
            fastlimit=float(params.fastlimit),
            slowlimit=float(params.slowlimit),
        )
        signals["mama"] = mama
        signals["fama"] = fama
        prev_m = mama.shift(1)
        prev_f = fama.shift(1)
        if params.side is SignalSide.LONG:
            entry = (prev_m <= prev_f) & (mama > fama)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = (prev_m >= prev_f) & (mama < fama)
            signal_value, side_value = -1, SignalSide.SHORT.value
        if int(params.trend_sma) > 0:
            mid = ind.sma(candles["close"], int(params.trend_sma))
            aligned = (
                candles["close"] > mid
                if params.side is SignalSide.LONG
                else candles["close"] < mid
            )
            entry = entry & aligned.fillna(False)
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [f"{side_value}: MAMA/FAMA" for _ in entry[entry].index]
        signals["reason"] = reasons
        return signals


__all__ = ["MamaFamaCrossParams", "MamaFamaCrossStrategy"]
