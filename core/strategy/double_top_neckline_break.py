"""Trade a confirmed double-top neckline break (and its invalidation).

In `lookback`, find two swing highs whose prices differ by at most
`atr_tol` · ATR(20) and an intervening swing low (the neckline). SHORT when
`close_t` crosses below that neckline. LONG when the second high is in place
and `close_t` crosses above it (pattern invalidation).

High-high-neckline geometry. This is not a sign-flipped copy of a
double-bottom file: the pattern is two peaks and the trough between them.

Not `equal_high_low_restest_fade` (job 110: fade a failed restest, no neckline).
Not `swing_failure_reversal`. Not `failed_higher_high`.
Not a rename of `double_bottom_neckline_break`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# ATR period is locked. Walk-forward searches lookback and atr_tol.
ATR_PERIOD = 20
# Swing confirmation window is locked so it is not a third free param.
PIVOT_LEFT = 3


@dataclass(frozen=True)
class DoubleTopNecklineBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Publication window that must contain both peaks and the neckline low.
    lookback: int = 40
    # |high_1 - high_2| <= atr_tol * ATR(20). Classic "equal tops" band.
    atr_tol: float = 0.15
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class DoubleTopNecklineBreakStrategy(Strategy):
    name = "double_top_neckline_break"

    def __init__(self, params: DoubleTopNecklineBreakParams | None = None) -> None:
        super().__init__(params or DoubleTopNecklineBreakParams())
        self.params: DoubleTopNecklineBreakParams = self.params
        lookback = int(self.params.lookback)
        # Two confirmation windows plus ATR so both peaks can publish.
        self.min_bars = max(lookback, ATR_PERIOD) + 2 * PIVOT_LEFT + 3

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
        # Peaks first: structure columns are high/high/neckline-low, not flipped lows.
        structure = ind.lookback_swing_structure(
            high, low, lookback=lookback, left=PIVOT_LEFT
        )
        atr = ind.atr(high, low, close, ATR_PERIOD)
        tol = float(params.atr_tol) * atr

        first_high = structure["prev_high"]
        second_high = structure["last_high"]
        neckline = structure["double_top_neckline"]
        # Two peaks match inside the ATR band and sit above the intervening trough.
        highs_match = (first_high - second_high).abs() <= tol
        neck_below = (neckline < first_high) & (neckline < second_high)
        pattern = (
            structure["n_highs"].ge(2)
            & first_high.notna()
            & second_high.notna()
            & neckline.notna()
            & highs_match
            & neck_below
        )

        prev_close = close.shift(1)
        # SHORT: confirmed close through the intervening low, not a restest fade.
        short_raw = pattern & (prev_close >= neckline) & (close < neckline)
        # LONG: second peak is in place and price reclaims it. Not two-low geometry.
        long_raw = pattern & (prev_close <= second_high) & (close > second_high)

        signals["first_high"] = first_high
        signals["second_high"] = second_high
        signals["neckline"] = neckline
        signals["atr_tol_band"] = tol

        if params.side is SignalSide.SHORT:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = neckline
        else:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            level = second_high

        raw = raw.fillna(False)
        # One fire per peak-pair + neckline so a hold below the neck does not re-enter.
        key = (
            first_high.astype(str)
            + "|"
            + second_high.astype(str)
            + "|"
            + neckline.astype(str)
        )
        entry = raw & raw.groupby(key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: double-top "
                    f"{first_high.loc[i]:.4f}/{second_high.loc[i]:.4f} "
                    f"neck {neckline.loc[i]:.4f} vs {level.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "PIVOT_LEFT",
    "DoubleTopNecklineBreakParams",
    "DoubleTopNecklineBreakStrategy",
]
