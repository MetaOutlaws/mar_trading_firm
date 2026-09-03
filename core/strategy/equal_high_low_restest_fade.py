"""Fade a failed restest of a rolling equal high or equal low.

If two prior highs (lows) inside `lookback` match within `tol_atr` · ATR,
that clustered level is the equal high (low). This bar trades through the
level and closes back on the inside: SHORT a failed equal-high restest,
LONG a failed equal-low restest.

Family id is `restest` as spelled, not `retest`.

Not `monday_range_sweep_reversal` (weekend Sat–Sun box, Monday London/NY).
Not `session_liquidity_sweep` (dead Asian-box sweep — do not recode).
Not `failed_higher_high` (confirmed two-swing structure).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# ATR period is locked. Walk-forward searches lookback and tol_atr.
ATR_PERIOD = 14


@dataclass(frozen=True)
class EqualHighLowRestestFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Prior bars that must contain two matching highs or lows.
    lookback: int = 12
    # Match tolerance as a multiple of prior-bar ATR. Small tick/ATR band.
    tol_atr: float = 0.15
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class EqualHighLowRestestFadeStrategy(Strategy):
    name = "equal_high_low_restest_fade"

    def __init__(self, params: EqualHighLowRestestFadeParams | None = None) -> None:
        super().__init__(params or EqualHighLowRestestFadeParams())
        self.params: EqualHighLowRestestFadeParams = self.params
        self.min_bars = max(int(self.params.lookback), ATR_PERIOD) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        lookback = int(params.lookback)
        # Prior-bar ATR so this bar's poke cannot widen the equal-level band.
        atr = ind.atr(high, low, close, ATR_PERIOD).shift(1)
        tol = float(params.tol_atr) * atr

        # Equal structure is on bars t-lookback..t-1 only. This bar is the restest.
        prior_high = high.shift(1)
        prior_low = low.shift(1)
        equal_high = prior_high.rolling(lookback, min_periods=lookback).max()
        equal_low = prior_low.rolling(lookback, min_periods=lookback).min()
        second_high = ind.rolling_second_max(prior_high, lookback)
        second_low = ind.rolling_second_min(prior_low, lookback)
        matched_high = (equal_high - second_high) <= tol
        matched_low = (second_low - equal_low) <= tol

        # Trade through the clustered level, close back inside (not a held break).
        short_raw = matched_high & (high > equal_high) & (close < equal_high)
        long_raw = matched_low & (low < equal_low) & (close > equal_low)

        signals["equal_high"] = equal_high
        signals["equal_low"] = equal_low
        signals["second_high"] = second_high
        signals["second_low"] = second_low
        signals["tol"] = tol

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
        if params.side is SignalSide.LONG:
            score = ((equal_low - low) / atr.replace(0, pd.NA)).clip(0.0, 1.0)
        else:
            score = ((high - equal_high) / atr.replace(0, pd.NA)).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: failed restest of "
                    f"{equal_high.loc[i]:.4f}/{equal_low.loc[i]:.4f} "
                    f"close {close.loc[i]:.4f} tol {tol.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "EqualHighLowRestestFadeParams",
    "EqualHighLowRestestFadeStrategy",
]
