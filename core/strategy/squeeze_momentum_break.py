"""Break after a BB-inside-Keltner squeeze, then linreg momentum. Not BB-width only."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SqueezeMomentumBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    bb_period: int = 20
    bb_k: float = 2.0
    kc_ema: int = 20
    kc_atr: int = 10
    kc_k: float = 1.5
    mom_period: int = 20
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.03


class SqueezeMomentumBreakStrategy(Strategy):
    name = "squeeze_momentum_break"

    def __init__(self, params: SqueezeMomentumBreakParams | None = None) -> None:
        super().__init__(params or SqueezeMomentumBreakParams())
        self.params: SqueezeMomentumBreakParams = self.params
        self.min_bars = (
            max(int(self.params.bb_period), int(self.params.kc_ema), int(self.params.mom_period))
            + 6
        )

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        squeezed = ind.squeeze_on(
            candles["high"],
            candles["low"],
            candles["close"],
            bb_period=int(params.bb_period),
            bb_k=float(params.bb_k),
            kc_ema=int(params.kc_ema),
            kc_atr=int(params.kc_atr),
            kc_k=float(params.kc_k),
        )
        mom = ind.squeeze_linreg_momentum(
            candles["high"], candles["low"], candles["close"], int(params.mom_period)
        )
        signals["squeeze"] = squeezed.astype("float64")
        signals["squeeze_mom"] = mom
        released = squeezed.shift(1).fillna(False) & ~squeezed.fillna(False)
        if params.side is SignalSide.LONG:
            entry = released & (mom > 0)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = released & (mom < 0)
            signal_value, side_value = -1, SignalSide.SHORT.value
        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: squeeze release mom {mom.loc[i]:.4f}"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["SqueezeMomentumBreakParams", "SqueezeMomentumBreakStrategy"]
