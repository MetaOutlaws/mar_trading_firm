"""Trade a confirmed double-bottom neckline break (and its invalidation).

In `lookback`, find two swing lows whose prices differ by at most
`atr_tol` · ATR(20) and an intervening swing high (the neckline). LONG when
`close_t` crosses above that neckline. SHORT when the second low is in place
and `close_t` crosses below it (pattern invalidation).

This waits for a close through the intervening high. It is not a failed
equal-high/low restest fade, not a single-swing failure, and not a double-top
neckline break of two highs.

Not `equal_high_low_restest_fade` (job 110: fade a failed restest, no neckline).
Not `swing_failure_reversal`. Not `monday_range_sweep_reversal`.
Not `failed_higher_high`. Not a rename of `double_top_neckline_break`.
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
class DoubleBottomNecklineBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Publication window that must contain both troughs and the neckline high.
    lookback: int = 40
    # |low_1 - low_2| <= atr_tol * ATR(20). Classic "equal bottoms" band.
    atr_tol: float = 0.15
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class DoubleBottomNecklineBreakStrategy(Strategy):
    name = "double_bottom_neckline_break"

    def __init__(self, params: DoubleBottomNecklineBreakParams | None = None) -> None:
        super().__init__(params or DoubleBottomNecklineBreakParams())
        self.params: DoubleBottomNecklineBreakParams = self.params
        lookback = int(self.params.lookback)
        # Two confirmation windows plus ATR so both troughs can publish.
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
        # Causal structure: published swings in [t-lookback+1, t] only.
        structure = ind.lookback_swing_structure(
            high, low, lookback=lookback, left=PIVOT_LEFT
        )
        atr = ind.atr(high, low, close, ATR_PERIOD)
        tol = float(params.atr_tol) * atr

        first_low = structure["prev_low"]
        second_low = structure["last_low"]
        neckline = structure["double_bottom_neckline"]
        # Two troughs match inside the ATR band and sit under the intervening peak.
        lows_match = (first_low - second_low).abs() <= tol
        neck_above = (neckline > first_low) & (neckline > second_low)
        pattern = (
            structure["n_lows"].ge(2)
            & first_low.notna()
            & second_low.notna()
            & neckline.notna()
            & lows_match
            & neck_above
        )

        prev_close = close.shift(1)
        # LONG: confirmed close through the intervening high, not a restest fade.
        long_raw = pattern & (prev_close <= neckline) & (close > neckline)
        # SHORT: second trough is in place and price loses it. Not two-high geometry.
        short_raw = pattern & (prev_close >= second_low) & (close < second_low)

        signals["first_low"] = first_low
        signals["second_low"] = second_low
        signals["neckline"] = neckline
        signals["atr_tol_band"] = tol

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            level = neckline
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = second_low

        raw = raw.fillna(False)
        # One fire per trough-pair + neckline so a hold above the neck does not re-enter.
        key = (
            first_low.astype(str)
            + "|"
            + second_low.astype(str)
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
                    f"{side_value}: double-bottom "
                    f"{first_low.loc[i]:.4f}/{second_low.loc[i]:.4f} "
                    f"neck {neckline.loc[i]:.4f} vs {level.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "PIVOT_LEFT",
    "DoubleBottomNecklineBreakParams",
    "DoubleBottomNecklineBreakStrategy",
]
