"""Follow money via unused turnover: a per-bar VWAP inflow surge.

Bybit already ships `turnover` (quote volume) beside base `volume`. Their
ratio is the bar's volume-weighted average price — not session VWAP, not a
cumulative ledger, and not a close-to-close force.

    bar_vwap = turnover / volume
    pulse    = volume * (close - bar_vwap) / ATR
    surge    = pulse / mean(|pulse| over the prior N bars)

The current bar is excluded from the baseline so a print cannot shrink its
own stretch. LONG when surge > k; SHORT when surge < -k. An optional
same-direction body keeps the close on the same side of the open as the
pulse. This is a continuation surge, not a fade, and it does not cumsum.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class BarVwapInflowSurgeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    atr_period: int = 14
    baseline_lookback: int = 20
    # Pulse / prior-|pulse| mean. 2 means "twice the recent typical print".
    surge_k: float = 2.0
    # When True, the candle body must point the same way as the pulse.
    require_body: bool = True
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class BarVwapInflowSurgeStrategy(Strategy):
    name = "bar_vwap_inflow_surge"

    def __init__(self, params: BarVwapInflowSurgeParams | None = None) -> None:
        super().__init__(params or BarVwapInflowSurgeParams())
        self.params: BarVwapInflowSurgeParams = self.params
        self.min_bars = (
            int(self.params.atr_period) + int(self.params.baseline_lookback) + 5
        )

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        if "turnover" not in candles.columns:
            raise ValueError(f"{self.name}: candles missing columns ['turnover']")
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        close = candles["close"]
        open_ = candles["open"]
        volume = candles["volume"].astype("float64")
        turnover = candles["turnover"].astype("float64")
        atr_value = ind.atr(
            candles["high"], candles["low"], close, int(params.atr_period)
        )

        # Per-bar VWAP from quote/base volume. Zero volume is undefined.
        bar_vwap = turnover / volume.replace(0.0, pd.NA)
        # Signed inflow on this bar only — do not cumsum.
        pulse = volume * (close - bar_vwap) / atr_value.replace(0.0, pd.NA)
        lookback = int(params.baseline_lookback)
        # Prior-N |pulse| mean; shift(1) drops the current print from the baseline.
        baseline = (
            pulse.abs()
            .shift(1)
            .rolling(lookback, min_periods=lookback)
            .mean()
        )
        surge = pulse / baseline.replace(0.0, pd.NA)

        signals["bar_vwap"] = bar_vwap
        signals["pulse"] = pulse
        signals["surge"] = surge
        signals["atr"] = atr_value

        threshold = float(params.surge_k)
        if params.side is SignalSide.LONG:
            raw = surge > threshold
            if params.require_body:
                raw = raw & (close > open_)
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = surge < -threshold
            if params.require_body:
                raw = raw & (close < open_)
            signal_value, side_value = -1, SignalSide.SHORT.value

        entry = raw.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = 1.0
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: bar-VWAP surge {surge.loc[i]:.2f} "
                    f"vwap {bar_vwap.loc[i]:.4f} close {close.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["BarVwapInflowSurgeParams", "BarVwapInflowSurgeStrategy"]
