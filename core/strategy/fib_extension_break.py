"""1.618 extension break of a completed impulse from causal confirmed swings.

Follow-on to the 0.618 retracement bounce, not a clone. A completed
up-impulse is last_event == +1 (new confirmed swing high, ffilled). The
1.618 tag is

    swing_high + 0.618 * (swing_high - swing_low)
    == swing_low + 1.618 * (swing_high - swing_low)

not a Donchian channel and not a 0.618 retracement bounce. LONG waits for
close through that extension and through the impulse end. SHORT is the
mirror (last_event == -1). Invalidation is close back through the impulse
end (H longs, L shorts) on the same impulse.

Search ratios are 1.272 / 1.618. The inner 1.272 is a zone start in this
family, not a second sleeve. This family does not trade the 0.618 bounce.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class FibExtensionBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    pivot_left: int = 3
    # 1.272 / 1.618 extension of the completed impulse (from origin).
    # 1.618 => end + 0.618 * range; 1.272 => end + 0.272 * range (zone start).
    fib_ratio: float = 1.618
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class FibExtensionBreakStrategy(Strategy):
    name = "fib_extension_break"

    def __init__(self, params: FibExtensionBreakParams | None = None) -> None:
        super().__init__(params or FibExtensionBreakParams())
        self.params: FibExtensionBreakParams = self.params
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
        ratio = float(params.fib_ratio)
        addon = ratio - 1.0
        # Up: ext = H + 0.618*R == L + 1.618*R. Inner 1.272 = H + 0.272*R.
        long_ext = swing_high + addon * rng
        short_ext = swing_low - addon * rng
        long_inner = swing_high + 0.272 * rng
        short_inner = swing_low - 0.272 * rng

        up_ready = last_event.eq(1.0) & swing_high.notna() & swing_low.notna() & (rng > 0)
        down_ready = last_event.eq(-1.0) & swing_high.notna() & swing_low.notna() & (rng > 0)

        # Invalidation latches per impulse. A new confirmed swing high (longs)
        # or swing low (shorts) is a new impulse end, so the latch resets.

        signals["swing_high"] = swing_high
        signals["swing_low"] = swing_low
        signals["fib_ext"] = long_ext if params.side is SignalSide.LONG else short_ext
        signals["fib_inner"] = long_inner if params.side is SignalSide.LONG else short_inner
        signals["last_event"] = last_event.fillna(0.0)

        if params.side is SignalSide.LONG:
            # Break 1.618 (or 1.272) and the impulse end. Invalidation is
            # close back through H after a break on this impulse.
            era = high_changed.astype("int64").cumsum()
            broke = up_ready & (close > long_ext) & (close > swing_high)
            had_break = broke.groupby(era).cummax()
            invalidated = (had_break.shift(1).fillna(False) & (close <= swing_high)).groupby(
                era
            ).cummax()
            entry = broke & ~invalidated
            signal_value, side_value = 1, SignalSide.LONG.value
            level = long_ext
            end = swing_high
        else:
            era = low_changed.astype("int64").cumsum()
            broke = down_ready & (close < short_ext) & (close < swing_low)
            had_break = broke.groupby(era).cummax()
            invalidated = (had_break.shift(1).fillna(False) & (close >= swing_low)).groupby(
                era
            ).cummax()
            entry = broke & ~invalidated
            signal_value, side_value = -1, SignalSide.SHORT.value
            level = short_ext
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
                    f"{side_value}: {ratio:.3f} extension break of "
                    f"{swing_high.loc[i]:.4f}/{swing_low.loc[i]:.4f} "
                    f"at {level.loc[i]:.4f} end {end.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["FibExtensionBreakParams", "FibExtensionBreakStrategy"]
