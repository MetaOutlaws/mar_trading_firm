"""Fade a quote-turnover climax whose close rejects the 20-bar extreme.

The bar's unused `turnover` (quote volume) must be a new 20-bar high versus
the prior 20. SHORT when that climax also breaks the prior-20 price high but
closes in the lower 20% of its own range. LONG when it breaks the prior-20
price low but closes in the upper 20%. Climax + rejection.

Not `volume_climax_fade` (RSI extreme + base-volume spike), not
`bar_vwap_inflow_surge` (follow a per-bar VWAP pulse), not
`up_down_turnover_imbalance` (up-bar vs down-bar turnover split).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class TurnoverClimaxRejectionFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    lookback: int = 20
    # Close must sit in this extreme fraction of the climax bar's range.
    reject_frac: float = 0.20
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class TurnoverClimaxRejectionFadeStrategy(Strategy):
    name = "turnover_climax_rejection_fade"

    def __init__(self, params: TurnoverClimaxRejectionFadeParams | None = None) -> None:
        super().__init__(params or TurnoverClimaxRejectionFadeParams())
        self.params: TurnoverClimaxRejectionFadeParams = self.params
        self.min_bars = int(self.params.lookback) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        if "turnover" not in candles.columns:
            raise ValueError(f"{self.name}: candles missing columns ['turnover']")
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        turnover = candles["turnover"].astype("float64")
        lookback = int(params.lookback)

        # Prior-20 only: this bar cannot be part of the extreme it is breaking.
        prior_high = high.shift(1).rolling(lookback, min_periods=lookback).max()
        prior_low = low.shift(1).rolling(lookback, min_periods=lookback).min()
        prior_to = turnover.shift(1).rolling(lookback, min_periods=lookback).max()
        climax = prior_to.notna() & (turnover > prior_to)

        width = (high - low).replace(0, pd.NA)
        close_frac = (close - low) / width
        reject = float(params.reject_frac)
        # Rejection: broke the extreme, closed the other way inside this bar.
        long_raw = climax & prior_low.notna() & (low < prior_low) & (close_frac >= (1.0 - reject))
        short_raw = climax & prior_high.notna() & (high > prior_high) & (close_frac <= reject)

        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["close_frac"] = close_frac
        signals["turnover"] = turnover
        signals["climax"] = climax.astype("float64")

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
        signals.loc[entry, "score"] = close_frac.fillna(0.0).clip(0.0, 1.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: turnover climax fade close {close.loc[i]:.4f} "
                    f"frac {float(close_frac.loc[i]):.2f} to {turnover.loc[i]:.1f} "
                    f"vs prior {prior_to.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "TurnoverClimaxRejectionFadeParams",
    "TurnoverClimaxRejectionFadeStrategy",
]
