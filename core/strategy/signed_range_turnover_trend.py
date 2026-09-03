"""Direction plus participation: signed range times turnover.

    signed_range = close - open
    pulse        = signed_range * turnover
    trend        = sum_N pulse / (prior-N mean|pulse| * N)

The current bar is excluded from the |pulse| baseline so a print cannot
shrink its own stretch. LONG when trend > k; SHORT when trend < -k.

This is not an EMA of close and not ADX/+DI. Qstick is an SMA of bodies
with no participation; Force Index is Δclose * base volume. This family
multiplies the bar's signed range by unused quote turnover and follows
the rolling sum of that product. Do not invent taker/CVD/netflow columns.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SignedRangeTurnoverTrendParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    lookback: int = 20
    # Rolling sum of pulse vs prior typical |pulse|. 1.0 = one typical window.
    trend_k: float = 1.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class SignedRangeTurnoverTrendStrategy(Strategy):
    name = "signed_range_turnover_trend"

    def __init__(self, params: SignedRangeTurnoverTrendParams | None = None) -> None:
        super().__init__(params or SignedRangeTurnoverTrendParams())
        self.params: SignedRangeTurnoverTrendParams = self.params
        # Two windows: the sum, and the prior-|pulse| baseline.
        self.min_bars = 2 * int(self.params.lookback) + 5

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        if "turnover" not in candles.columns:
            raise ValueError(f"{self.name}: candles missing columns ['turnover']")
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        open_ = candles["open"].astype("float64")
        close = candles["close"].astype("float64")
        turnover = candles["turnover"].astype("float64")
        # Signed range is the body, not close-to-close (Force) and not
        # (close-open)/(high-low) (Balance of Power). Participation is
        # quote turnover, not base volume.
        signed_range = close - open_
        pulse = signed_range * turnover
        lookback = int(params.lookback)
        window_sum = pulse.rolling(lookback, min_periods=lookback).sum()
        # Prior-N |pulse| mean; shift(1) drops the current print.
        baseline = (
            pulse.abs()
            .shift(1)
            .rolling(lookback, min_periods=lookback)
            .mean()
        )
        typical = baseline * lookback
        trend = window_sum / typical.replace(0.0, pd.NA)

        signals["signed_range"] = signed_range
        signals["pulse"] = pulse
        signals["trend"] = trend

        threshold = float(params.trend_k)
        if params.side is SignalSide.LONG:
            raw = trend > threshold
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = trend < -threshold
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
                    f"{side_value}: signed-range turnover trend {trend.loc[i]:.2f} "
                    f"pulse {pulse.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["SignedRangeTurnoverTrendParams", "SignedRangeTurnoverTrendStrategy"]
