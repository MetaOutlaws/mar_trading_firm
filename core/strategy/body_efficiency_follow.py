"""Follow two consecutive high body-efficiency bars in the same direction.

A bar is efficient when |close-open| / true_range >= `min_efficiency` (0.7).
Trade with that close direction when the second bar's volume is at least the
first's. Follow, not fade.

Not `three_bar_play` (trend + narrow rest + break of rest). Not
`engulfing_reversal` (current body swallows prior, reverse). Not
`consecutive_bar_exhaustion` (fade after N closes). Not Kaufman ER.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class BodyEfficiencyFollowParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # |close-open| / true_range floor. Walk-forward may search this.
    min_efficiency: float = 0.7
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class BodyEfficiencyFollowStrategy(Strategy):
    name = "body_efficiency_follow"

    def __init__(self, params: BodyEfficiencyFollowParams | None = None) -> None:
        super().__init__(params or BodyEfficiencyFollowParams())
        self.params: BodyEfficiencyFollowParams = self.params
        self.min_bars = 4

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        open_ = candles["open"]
        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        volume = candles["volume"]
        # Bar-local body / true range. Current bar cannot lift a prior bar's score.
        eff = ind.body_efficiency(open_, high, low, close)
        min_eff = float(params.min_efficiency)
        efficient = eff >= min_eff
        # Body direction (close vs open), not close-vs-prior-close run length.
        bull = close > open_
        bear = close < open_
        pair = efficient & efficient.shift(1)
        same_up = bull & bull.shift(1)
        same_down = bear & bear.shift(1)
        # Second bar participates at least as much as the first.
        vol_ok = volume >= volume.shift(1)

        long_raw = pair & same_up & vol_ok
        short_raw = pair & same_down & vol_ok

        signals["efficiency"] = eff
        signals["prev_efficiency"] = eff.shift(1)
        signals["prev_volume"] = volume.shift(1)

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
        signals.loc[entry, "score"] = eff.clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: two efficient bodies {eff.shift(1).loc[i]:.2f}/"
                    f"{eff.loc[i]:.2f} vol {volume.shift(1).loc[i]:.1f}->{volume.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["BodyEfficiencyFollowParams", "BodyEfficiencyFollowStrategy"]
