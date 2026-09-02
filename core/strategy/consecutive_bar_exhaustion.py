"""Fade after N consecutive closes in one direction.

Run-length of directional closes is the signal, not RSI and not volume climax.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class ConsecutiveBarParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    run_length: int = 5
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ConsecutiveBarExhaustionStrategy(Strategy):
    name = "consecutive_bar_exhaustion"

    def __init__(self, params: ConsecutiveBarParams | None = None) -> None:
        super().__init__(params or ConsecutiveBarParams())
        self.params: ConsecutiveBarParams = self.params
        self.min_bars = 12

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        close = candles["close"]
        up = close > close.shift(1)
        down = close < close.shift(1)
        # Reset the run when direction flips. cumsum of the reset, then count within group.
        up_group = (~up.fillna(False)).cumsum()
        down_group = (~down.fillna(False)).cumsum()
        up_run = up.fillna(False).astype(int).groupby(up_group).cumsum()
        down_run = down.fillna(False).astype(int).groupby(down_group).cumsum()
        signals["up_run"] = up_run
        signals["down_run"] = down_run
        # Fade: after N up closes, short; after N down closes, long.
        if params.side is SignalSide.LONG:
            entry = down_run >= params.run_length
            signal_value, side_value = 1, SignalSide.LONG.value
            run = down_run
        else:
            entry = up_run >= params.run_length
            signal_value, side_value = -1, SignalSide.SHORT.value
            run = up_run
        # One shot at the moment the run first hits N, not every extra bar.
        entry = entry.fillna(False) & (run == params.run_length)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                f"{side_value}: fade {int(run.loc[i])} consecutive closes"
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["ConsecutiveBarParams", "ConsecutiveBarExhaustionStrategy"]
