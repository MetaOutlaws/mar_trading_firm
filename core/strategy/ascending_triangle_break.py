"""Break an ascending triangle (LONG) or its descending-triangle inverse (SHORT).

LONG: at least two rising swing lows (each low > the prior swing low) into a
flat swing-high cap (highs within `atr_tol` · ATR(20)), then `close_t` through
the cap AND `volume_t` > mean(volume_{t-20..t-1}).

SHORT: descending-triangle inverse — at least two falling swing highs into a
flat swing-low floor, then close through the floor on volume above the prior-20
mean.

Volume threshold is locked as the prior-20 mean. It is not a third free param.

Not `nr7_breakout`. Not `range_compression_volume_thrust` (job 102: ATR
compression then thrust, no triangle geometry). Not `inside_bar_breakout`.
Not `squeeze_momentum_break` (dead — do not recode).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# ATR period and the volume baseline are locked. Search lookback and atr_tol.
ATR_PERIOD = 20
VOL_LOOKBACK = 20
PIVOT_LEFT = 3


@dataclass(frozen=True)
class AscendingTriangleBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Publication window that must hold the rising lows and the flat cap.
    lookback: int = 40
    # Flat-cap / flat-floor band as a multiple of ATR(20).
    atr_tol: float = 0.15
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class AscendingTriangleBreakStrategy(Strategy):
    name = "ascending_triangle_break"

    def __init__(self, params: AscendingTriangleBreakParams | None = None) -> None:
        super().__init__(params or AscendingTriangleBreakParams())
        self.params: AscendingTriangleBreakParams = self.params
        lookback = int(self.params.lookback)
        self.min_bars = (
            max(lookback, ATR_PERIOD, VOL_LOOKBACK) + 2 * PIVOT_LEFT + 3
        )

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
        volume = candles["volume"]
        lookback = int(params.lookback)
        structure = ind.lookback_swing_structure(
            high, low, lookback=lookback, left=PIVOT_LEFT
        )
        atr = ind.atr(high, low, close, ATR_PERIOD)
        tol = float(params.atr_tol) * atr
        # Prior-20 mean excludes this bar. Not a searched third param.
        vol_mean = volume.shift(1).rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).mean()
        vol_ok = volume > vol_mean

        cap = structure["highs_max"]
        floor = structure["lows_min"]
        flat_cap = (
            structure["n_highs"].ge(2)
            & (structure["highs_max"] - structure["highs_min"] <= tol)
        )
        flat_floor = (
            structure["n_lows"].ge(2)
            & (structure["lows_max"] - structure["lows_min"] <= tol)
        )
        # Rising troughs into a horizontal resistance. Cap is the clustered high.
        ascending = (
            structure["lows_rising"]
            & structure["n_lows"].ge(2)
            & flat_cap
            & cap.notna()
        )
        # Falling peaks into a horizontal support. Floor is the clustered low.
        descending = (
            structure["highs_falling"]
            & structure["n_highs"].ge(2)
            & flat_floor
            & floor.notna()
        )

        prev_close = close.shift(1)
        long_raw = ascending & vol_ok & (prev_close <= cap) & (close > cap)
        short_raw = descending & vol_ok & (prev_close >= floor) & (close < floor)

        signals["cap"] = cap
        signals["floor"] = floor
        signals["vol_mean"] = vol_mean
        signals["atr_tol_band"] = tol
        signals["n_highs"] = structure["n_highs"]
        signals["n_lows"] = structure["n_lows"]

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            level = cap
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = floor

        raw = raw.fillna(False)
        key = (
            structure["n_highs"].astype(str)
            + "|"
            + structure["n_lows"].astype(str)
            + "|"
            + cap.astype(str)
            + "|"
            + floor.astype(str)
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
                    f"{side_value}: triangle break "
                    f"cap {cap.loc[i]:.4f} floor {floor.loc[i]:.4f} "
                    f"at {level.loc[i]:.4f} vol {volume.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "PIVOT_LEFT",
    "VOL_LOOKBACK",
    "AscendingTriangleBreakParams",
    "AscendingTriangleBreakStrategy",
]
