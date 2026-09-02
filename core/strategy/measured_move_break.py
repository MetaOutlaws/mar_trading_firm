"""AB=CD measured-move break of a completed impulse from causal confirmed swings.

Same causal impulse as fib_extension_break, different geometry. A completed
up-impulse is last_event == +1 (new confirmed swing high, ffilled). The
measured-move tag projects 100% of the impulse past its end:

    mm = end + 1.0 * (end - start) = 2 * end - start
    LONG:  mm = H + (H - L) = 2H - L
    SHORT: mm = L - (H - L) = 2L - H

not a Donchian channel and not H + 0.618 * R (that is fib_extension_break).
LONG waits for close through that measured move and through the impulse end.
SHORT is the mirror (last_event == -1). Invalidation is close back through
the impulse end (H longs, L shorts) on the same impulse.

Ratio is locked at 1.0. This family does not search or trade 1.618 or 0.618.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# AB=CD projection. Not a searched 1.618 / 0.618 (those are other families).
MM_RATIO = 1.0


@dataclass(frozen=True)
class MeasuredMoveBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    pivot_left: int = 3
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class MeasuredMoveBreakStrategy(Strategy):
    name = "measured_move_break"

    def __init__(self, params: MeasuredMoveBreakParams | None = None) -> None:
        super().__init__(params or MeasuredMoveBreakParams())
        self.params: MeasuredMoveBreakParams = self.params
        left = int(self.params.pivot_left)
        # Two full confirmation windows so origin and end can both publish.
        self.min_bars = 2 * (2 * left + 1) + 5

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

        # Impulse from two confirmed swings, not a rolling Donchian window.
        # Up: origin L = swing_low, end H = swing_high, require H > L.
        # Down: origin H = swing_high, end L = swing_low, require L < H.
        rng = swing_high - swing_low
        # mm = end + 1.0*(end-start) = 2*end - start. Locked; not 1.618/0.618.
        long_mm = swing_high + MM_RATIO * rng  # 2H - L
        short_mm = swing_low - MM_RATIO * rng  # 2L - H

        up_ready = last_event.eq(1.0) & swing_high.notna() & swing_low.notna() & (rng > 0)
        down_ready = last_event.eq(-1.0) & swing_high.notna() & swing_low.notna() & (rng > 0)

        # Invalidation latches per impulse. A new confirmed swing high (longs)
        # or swing low (shorts) is a new impulse end, so the latch resets.

        signals["swing_high"] = swing_high
        signals["swing_low"] = swing_low
        signals["mm"] = long_mm if params.side is SignalSide.LONG else short_mm
        signals["last_event"] = last_event.fillna(0.0)

        if params.side is SignalSide.LONG:
            # Break the measured move and the impulse end. Invalidation is
            # close back through H after a break on this impulse.
            era = high_changed.astype("int64").cumsum()
            broke = up_ready & (close > long_mm) & (close > swing_high)
            had_break = broke.groupby(era).cummax()
            invalidated = (had_break.shift(1).fillna(False) & (close <= swing_high)).groupby(
                era
            ).cummax()
            entry = broke & ~invalidated
            signal_value, side_value = 1, SignalSide.LONG.value
            level = long_mm
            end = swing_high
        else:
            era = low_changed.astype("int64").cumsum()
            broke = down_ready & (close < short_mm) & (close < swing_low)
            had_break = broke.groupby(era).cummax()
            invalidated = (had_break.shift(1).fillna(False) & (close >= swing_low)).groupby(
                era
            ).cummax()
            entry = broke & ~invalidated
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = short_mm
            end = swing_low

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: measured-move break of "
                    f"{swing_high.loc[i]:.4f}/{swing_low.loc[i]:.4f} "
                    f"at {level.loc[i]:.4f} end {end.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["MeasuredMoveBreakParams", "MeasuredMoveBreakStrategy"]
