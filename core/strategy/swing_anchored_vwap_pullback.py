"""Pullback to VWAP anchored on a confirmed-swing impulse origin.

Same last-event impulse as fib_extension_break: +1 new confirmed swing
high (up-impulse ready), -1 new confirmed swing low (down-impulse ready),
then ffill. AVWAP is the turnover/volume VWAP from the origin swing
publish bar to t — not a session VWAP, not a 0.618 fib tag, and not a
1.618 extension break.

    LONG:  origin = last swing_low publish, avwap = Σturnover / Σvolume
    SHORT: origin = last swing_high publish

LONG waits for an up-impulse whose end sits above AVWAP, a tag
(low <= avwap), and a close back above AVWAP with the origin intact.
SHORT is the mirror. Invalidation is close back through the origin on
the same impulse. Volume-weighted continuation of the same swing engine,
not fib_retracement_bounce and not fib_extension_break.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class SwingAnchoredVwapPullbackParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Same swing window as fib_extension_break / measured_move_break.
    pivot_left: int = 3
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class SwingAnchoredVwapPullbackStrategy(Strategy):
    name = "swing_anchored_vwap_pullback"

    def __init__(self, params: SwingAnchoredVwapPullbackParams | None = None) -> None:
        super().__init__(params or SwingAnchoredVwapPullbackParams())
        self.params: SwingAnchoredVwapPullbackParams = self.params
        left = int(self.params.pivot_left)
        # Two full confirmation windows so origin and end can both publish.
        self.min_bars = 2 * (2 * left + 1) + 5

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
        volume = candles["volume"].astype("float64")
        turnover = candles["turnover"].astype("float64")
        # Causal: bars <= t only. confirmed_swings already shifts past the
        # right-hand confirmation window so bar t never sees future pivots.
        swing_high, swing_low = ind.confirmed_swings(
            high, low, left=int(params.pivot_left)
        )

        # Last event: +1 new swing high, -1 new swing low, then ffill.
        # Up-impulse is complete when last_event == +1; down when -1.
        high_changed = swing_high.notna() & swing_high.ne(swing_high.shift(1))
        low_changed = swing_low.notna() & swing_low.ne(swing_low.shift(1))
        event = pd.Series(float("nan"), index=candles.index, dtype="float64")
        event = event.mask(low_changed, -1.0)
        event = event.mask(high_changed, 1.0)
        last_event = event.ffill()

        # AVWAP resets when the origin swing publishes a new price.
        # Long origin = swing_low era; short origin = swing_high era.
        long_era = low_changed.astype("int64").cumsum()
        short_era = high_changed.astype("int64").cumsum()
        long_avwap = turnover.groupby(long_era).cumsum() / volume.groupby(
            long_era
        ).cumsum().replace(0.0, pd.NA)
        short_avwap = turnover.groupby(short_era).cumsum() / volume.groupby(
            short_era
        ).cumsum().replace(0.0, pd.NA)

        rng = swing_high - swing_low
        up_ready = (
            last_event.eq(1.0)
            & swing_high.notna()
            & swing_low.notna()
            & (rng > 0)
            & (swing_high > long_avwap)
        )
        down_ready = (
            last_event.eq(-1.0)
            & swing_high.notna()
            & swing_low.notna()
            & (rng > 0)
            & (swing_low < short_avwap)
        )

        signals["swing_high"] = swing_high
        signals["swing_low"] = swing_low
        signals["last_event"] = last_event.fillna(0.0)

        if params.side is SignalSide.LONG:
            # Tag AVWAP from above and close back through it. Invalidation
            # is close back through the origin low on this impulse.
            avwap = long_avwap
            era = long_era
            tagged = up_ready & (low <= avwap) & (close > avwap) & (close > swing_low)
            invalidated = (close <= swing_low).groupby(era).cummax()
            entry = tagged & ~invalidated
            signal_value, side_value = 1, SignalSide.LONG.value
            origin = swing_low
        else:
            avwap = short_avwap
            era = short_era
            tagged = down_ready & (high >= avwap) & (close < avwap) & (close < swing_high)
            invalidated = (close >= swing_high).groupby(era).cummax()
            entry = tagged & ~invalidated
            signal_value, side_value = -1, SignalSide.SHORT.value
            origin = swing_high

        signals["avwap"] = avwap

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: swing-anchored VWAP pullback "
                    f"{swing_high.loc[i]:.4f}/{swing_low.loc[i]:.4f} "
                    f"avwap {avwap.loc[i]:.4f} origin {origin.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["SwingAnchoredVwapPullbackParams", "SwingAnchoredVwapPullbackStrategy"]
