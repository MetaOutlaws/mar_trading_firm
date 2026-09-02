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

The walk-forward kit searches only 1.618 so fold CV cannot blame two
ratios. 1.272 stays as the inner zone start for display, not a searched
grid value. This family does not trade the 0.618 bounce.

skip_bull / skip_bear default False so the approved BTC SHORT path is
unchanged unless a near-miss overlay freezes them. When a flag is on,
SHORT skips bull bars and LONG skips bear bars. Prefer a `regime` column
on the candle frame when a causal series is already there. The validator's
quarterly BTC labels are not attached (they use the whole quarter's
return and would leak future bars). Fallback is close versus a causal
200-bar SMA: above = local bull, below = local bear.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Local bull/bear stand-in when candles have no causal `regime` column.
REGIME_SMA = 200


def _as_flag(value: object) -> bool:
    """Coerce a kit / JSON overlay into a boolean without treating 'false' as True."""
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _bar_regime(candles: pd.DataFrame, close: pd.Series) -> pd.Series:
    """Per-bar bull/bear/chop label with no lookahead.

    ``regime`` on the frame wins (tests or a harness that already attached a
    causal series). Otherwise close vs SMA(200) at t uses closes <= t only.
    Unwarmed SMA rows stay empty so skip_* does not invent a regime.
    """
    if "regime" in candles.columns:
        return candles["regime"].astype("string").str.lower().fillna("")
    mid = ind.sma(close, REGIME_SMA)
    labels = pd.Series("", index=close.index, dtype="object")
    labels = labels.mask(close > mid, "bull")
    labels = labels.mask(close < mid, "bear")
    return labels.fillna("")


@dataclass(frozen=True)
class FibExtensionBreakParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    pivot_left: int = 3
    # Walk-forward searches only 1.618. 1.272 remains the inner zone start.
    # 1.618 => end + 0.618 * range; 1.272 => end + 0.272 * range (display).
    fib_ratio: float = 1.618
    # Near-miss overlay may freeze these. Defaults keep the approved BTC path.
    skip_bull: bool = False
    skip_bear: bool = False
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
            # Break 1.618 (or a caller-set ratio) and the impulse end.
            # Invalidation is close back through H after a break on this impulse.
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

        # Regime skip is opt-in. Unknown / unwarmed bars are not bull or bear.
        regime = _bar_regime(candles, close)
        signals["regime"] = regime
        if params.side is SignalSide.SHORT and _as_flag(params.skip_bull):
            entry = entry & ~regime.eq("bull")
        if params.side is SignalSide.LONG and _as_flag(params.skip_bear):
            entry = entry & ~regime.eq("bear")

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
