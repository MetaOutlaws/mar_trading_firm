"""Reclaim this week's UTC Monday 00:00 open after a wrong-side excursion.

Anchor is the first 4h open of the ISO week (Monday 00:00 UTC). After at
least `min_wrong_closes` closes on the wrong side of that open this week,
trade the reclaim: LONG when close crosses back above with volume above the
prior-20 mean; SHORT when close crosses back below.

Not `monday_range_sweep_reversal` (weekend H/L fade on Monday London/NY).
Not `swing_anchored_vwap_pullback` (AVWAP of confirmed swings). Not
`prior_week_high_break` (break last week's high/low).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class WeekOpenReclaimParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wrong-side closes this ISO week before the reclaim. Walk-forward may search.
    min_wrong_closes: int = 3
    vol_lookback: int = 20
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class WeekOpenReclaimStrategy(Strategy):
    name = "week_open_reclaim"

    def __init__(self, params: WeekOpenReclaimParams | None = None) -> None:
        super().__init__(params or WeekOpenReclaimParams())
        self.params: WeekOpenReclaimParams = self.params
        self.min_bars = int(self.params.vol_lookback) + int(self.params.min_wrong_closes) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        close = candles["close"]
        volume = candles["volume"]
        # Monday 00:00 open only. Mid-week starts stay NaN until Monday prints.
        week_open = ind.iso_week_open(candles["open"])
        week_key = ind.iso_week_key(candles.index)
        vol_mean = ind.prior_rolling_mean(volume, int(params.vol_lookback))
        heavy = vol_mean.notna() & (volume > vol_mean)
        min_wrong = int(params.min_wrong_closes)

        below = close < week_open
        above = close > week_open
        # This-week count. On a reclaim bar the current print is not on the
        # wrong side, so cumsum equals the prior wrong-side closes this week.
        below_count = below.groupby(week_key).cumsum()
        above_count = above.groupby(week_key).cumsum()
        prev_close = close.shift(1)
        # Cross back through the frozen Monday open, not a weekend H/L fade.
        cross_above = week_open.notna() & (close > week_open) & (prev_close <= week_open)
        cross_below = week_open.notna() & (close < week_open) & (prev_close >= week_open)

        long_raw = cross_above & (below_count >= min_wrong) & heavy
        short_raw = cross_below & (above_count >= min_wrong) & heavy

        signals["week_open"] = week_open
        signals["below_count"] = below_count.astype("float64")
        signals["above_count"] = above_count.astype("float64")
        signals["vol_mean"] = vol_mean

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One reclaim per ISO week. Calendar week, not a rolling Donchian.
        entry = raw.fillna(False) & raw.groupby(week_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        dist = (close - week_open).abs()
        signals.loc[entry, "score"] = dist.clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: week-open reclaim close {close.loc[i]:.4f} "
                    f"vs open {week_open.loc[i]:.4f} vol {volume.loc[i]:.1f}"
                    f">{vol_mean.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["WeekOpenReclaimParams", "WeekOpenReclaimStrategy"]
