"""Fade a London tag of the completed Asia session high/low that closes back inside.

Asia is the desk's 00:00–08:00 UTC box (same helper as ``asian_range_breakout``
/ ``session_liquidity_sweep``), published only after 08:00. A *London* bar
(08:00–16:00 UTC open, not NY 16:00–21:00) tags that extreme within
``touch_tol_atr * ATR`` and closes back inside the Asia range:

- LONG when ``low_t`` tags/pierces Asia low and ``close_t`` is back above it.
- SHORT when ``high_t`` tags/pierces Asia high and ``close_t`` is back below it.

Session bounds are fixed. The only searched free param is ``touch_tol_atr``
(default 0; grid ``[0.0, 0.10]``). No volume gate. OHLCV only. Causal: bars
``<= t``. The engine fills at ``t+1`` open.

Not ``asian_range_breakout`` (close *through* the Asia box — CEO-stopped).
Not ``session_liquidity_sweep`` (1h London+NY, ``max_sweep_pct`` cap).
Not ``prior_day_extreme_reject`` (prior UTC calendar day H/L).
Not ``failed_range_break_reversion`` (rolling N-bar channel).
Not ``monday_range_sweep_reversal`` (weekend Sat–Sun box).
Not ``range_compression_volume_thrust`` / ORB / NR7 fail / H&S / Wyckoff.
Do not recode ``asia_close_inventory_fade`` (fade *at* Asia close inventory).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# ATR period and close-inside are locked. Walk-forward searches touch_tol_atr only.
ATR_PERIOD = 14
# Desk standard Asia box. Not 00:00–07:00; 4h 00:00+04:00 bars are the same set.
ASIA_START_HOUR = 0.0
ASIA_END_HOUR = 8.0
# London cash hours UTC. Open-labeled 4h at 08:00 and 12:00. Not NY 16:00–21:00.
LONDON_START_HOUR = 8.0
LONDON_END_HOUR = 16.0


@dataclass(frozen=True)
class AsiaRangeLondonRejectParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Tag slack as a multiple of prior-bar ATR. Quant grid: [0.0, 0.10].
    touch_tol_atr: float = 0.0
    # Quant-locked True: close must sit back inside the Asia box.
    require_close_inside: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class AsiaRangeLondonRejectStrategy(Strategy):
    name = "asia_range_london_reject"

    def __init__(self, params: AsiaRangeLondonRejectParams | None = None) -> None:
        super().__init__(params or AsiaRangeLondonRejectParams())
        self.params: AsiaRangeLondonRejectParams = self.params
        # First prior-bar ATR prints at index ATR_PERIOD. Asia box is same-day.
        self.min_bars = ATR_PERIOD

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
        # Causal Asia 00:00–08:00 box. Blank until 08:00; current bar cannot
        # lift a still-forming session extreme.
        range_high, range_low, asia_ready = ind.utc_session_range(
            high,
            low,
            start_hour=ASIA_START_HOUR,
            end_hour=ASIA_END_HOUR,
        )
        utc_index = ind._as_utc_index(candles.index)
        hours_into = (utc_index - utc_index.normalize()) / pd.Timedelta(hours=1)
        in_london = pd.Series(
            (hours_into >= LONDON_START_HOUR) & (hours_into < LONDON_END_HOUR),
            index=candles.index,
        )
        # Prior-bar ATR so this London poke cannot widen its own tag band.
        atr = ind.atr(high, low, close, ATR_PERIOD).shift(1)
        touch = float(params.touch_tol_atr) * atr.fillna(0.0)
        close_inside = bool(params.require_close_inside)

        # Tag = trade to (or through) the Asia extreme, within ATR slack.
        tagged_high = (
            asia_ready & in_london & range_high.notna() & (high >= range_high - touch)
        )
        tagged_low = (
            asia_ready & in_london & range_low.notna() & (low <= range_low + touch)
        )
        # Reject = close back through the tagged extreme. Held breakouts do not fade.
        short_raw = tagged_high & (close < range_high)
        long_raw = tagged_low & (close > range_low)
        if close_inside:
            short_raw = short_raw & (close >= range_low)
            long_raw = long_raw & (close <= range_high)

        signals["range_high"] = range_high
        signals["range_low"] = range_low
        signals["touch"] = touch
        signals["atr"] = atr

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One fade per UTC day. Asia session box, not a rolling Donchian.
        day_key = ind.utc_day_key(candles.index)
        entry = raw.fillna(False) & raw.groupby(day_key).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (range_high - range_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((range_low - low) / width).clip(0.0, 1.0)
        else:
            score = ((high - range_high) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: Asia range London reject close {close.loc[i]:.4f} vs "
                    f"{range_high.loc[i]:.4f}/{range_low.loc[i]:.4f} "
                    f"touch {touch.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_PERIOD",
    "ASIA_START_HOUR",
    "ASIA_END_HOUR",
    "LONDON_START_HOUR",
    "LONDON_END_HOUR",
    "AsiaRangeLondonRejectParams",
    "AsiaRangeLondonRejectStrategy",
]
