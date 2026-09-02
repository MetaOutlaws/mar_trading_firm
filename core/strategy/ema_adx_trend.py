"""
EMA trend + ADX pullback — enter with the trend after a dip to the fast EMA.

This is the catalog family after rejected Donchian. Same directional bet
(trade with strength), different trigger: Donchian bought the breakout;
this waits for a pullback to the fast EMA while ADX says the trend is real.

LONG: fast EMA above slow EMA, ADX at or above the floor, yesterday's close
was above the fast EMA, today's low tags it, close finishes back above.
SHORT: the inverse.

The channel is computed on the current bar's close (no future bars). The
engine still fills at the next bar's open, same as every other sleeve.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class EmaAdxParams(StrategyParams):
    """Parameters for the EMA + ADX pullback sleeve."""

    side: SignalSide = SignalSide.LONG
    ema_fast: int = 20
    ema_slow: int = 50
    adx_period: int = 14
    # 0 disables the ADX filter so a first walk-forward can measure the raw rule.
    min_adx: float = 20.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class EmaAdxTrendStrategy(Strategy):
    """Trend-following pullback: EMA regime + ADX + tag of the fast EMA."""

    name = "ema_adx_trend"

    def __init__(self, params: EmaAdxParams | None = None) -> None:
        super().__init__(params or EmaAdxParams())
        self.params: EmaAdxParams = self.params
        self.min_bars = max(self.params.ema_slow + 10, self.params.adx_period + 40)

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
        ema_fast = ind.ema(close, params.ema_fast)
        ema_slow = ind.ema(close, params.ema_slow)
        adx_value, plus_di, minus_di = ind.adx(high, low, close, params.adx_period)

        signals["ema_fast"] = ema_fast
        signals["ema_slow"] = ema_slow
        signals["adx"] = adx_value
        signals["plus_di"] = plus_di
        signals["minus_di"] = minus_di

        adx_ok = adx_value >= params.min_adx if params.min_adx > 0 else True
        # Prior close was on the trend side of the fast EMA, this bar tagged it
        # and closed back on the trend side — a pullback, not a raw breakout.
        was_above = close.shift(1) > ema_fast.shift(1)
        was_below = close.shift(1) < ema_fast.shift(1)
        tagged = low <= ema_fast
        spiked = high >= ema_fast

        if params.side is SignalSide.LONG:
            regime = ema_fast > ema_slow
            entry = regime & adx_ok & was_above & tagged & (close >= ema_fast)
            side_value = SignalSide.LONG.value
            signal_value = 1
        else:
            regime = ema_fast < ema_slow
            entry = regime & adx_ok & was_below & spiked & (close <= ema_fast)
            side_value = SignalSide.SHORT.value
            signal_value = -1

        entry = entry.fillna(False).astype(bool)
        entry.iloc[: self.min_bars] = False

        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        dist = (close - ema_fast).abs() / ema_fast.replace(0, pd.NA)
        adx_component = ((adx_value - 20.0) / 20.0).clip(0.0, 1.0)
        signals.loc[entry, "score"] = (adx_component.fillna(0.0) + (1.0 - dist.clip(0.0, 1.0).fillna(1.0)))[entry]
        signals["reason"] = self._reasons(entry, close, ema_fast, ema_slow, adx_value)
        return signals

    def _reasons(
        self,
        entry: pd.Series,
        close: pd.Series,
        ema_fast: pd.Series,
        ema_slow: pd.Series,
        adx_value: pd.Series,
    ) -> pd.Series:
        reasons = pd.Series("", index=entry.index, dtype="object")
        if not entry.any():
            return reasons
        side_label = "LONG" if self.params.side is SignalSide.LONG else "SHORT"
        fired = entry[entry].index
        reasons.loc[fired] = [
            (
                f"{side_label} EMA{self.params.ema_fast}/{self.params.ema_slow} pullback "
                f"close={close.loc[ts]:.4f} fast={ema_fast.loc[ts]:.4f} "
                f"slow={ema_slow.loc[ts]:.4f} adx={adx_value.loc[ts]:.1f}"
            )
            for ts in fired
        ]
        return reasons
