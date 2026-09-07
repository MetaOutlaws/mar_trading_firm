"""Fade a stretch away from the prior bar's close (the magnet).

Distance is ``(close_t - close_{t-1}) / ATR(atr_n)``. When that stretch
exceeds ``k`` ATR, fade back toward the prior close:

- LONG if close is stretched *below* the magnet
- SHORT if close is stretched *above* the magnet

OHLCV only. No volume gate. Causal: bars ``<= t``. The engine fills at
``t+1`` open.

Quant lock: ``atr_n = 20`` is fixed (not searched). Free param (max 2,
here only one): ``k`` grid ``[1.2, 1.4]``.

Not VWAP / session-VWAP band fade. Not session mid. Not week-open reclaim.
Not CLV persistence. Not Wyckoff spring. Not the 118–127 spent fail/reject
families. Not H&S / ``asia_close_inventory_fade``.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches k only.
ATR_N_LOCKED = 20


@dataclass(frozen=True)
class PriorCloseMagnetFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Stretch threshold in ATR units. Quant grid: [1.2, 1.4].
    k: float = 1.2
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class PriorCloseMagnetFadeStrategy(Strategy):
    name = "prior_close_magnet_fade"

    def __init__(self, params: PriorCloseMagnetFadeParams | None = None) -> None:
        super().__init__(params or PriorCloseMagnetFadeParams())
        self.params: PriorCloseMagnetFadeParams = self.params
        # ATR seed plus one bar for the prior-close magnet.
        self.min_bars = max(ATR_N_LOCKED, int(self.params.atr_n)) + 2

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
        # atr_n stays locked even if a caller passes another value.
        atr_n = ATR_N_LOCKED
        k = float(params.k)
        # Magnet is the prior bar close, not VWAP / session mid / week open.
        magnet = close.shift(1)
        atr = ind.atr(high, low, close, atr_n)
        # Signed distance in ATR units. Positive = stretched above the magnet.
        stretch = (close - magnet) / atr.replace(0, pd.NA)

        long_raw = atr.gt(0) & magnet.notna() & stretch.le(-k)
        short_raw = atr.gt(0) & magnet.notna() & stretch.ge(k)

        signals["prior_close"] = magnet
        signals["atr"] = atr
        signals["stretch"] = stretch

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        # How far past the threshold, in units of k. 0 at the edge, 1 at 2k.
        excess = ((stretch.abs() - k) / k).clip(0.0, 1.0)
        signals.loc[entry, "score"] = excess.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: prior-close magnet fade close {close.loc[i]:.4f} "
                    f"magnet {magnet.loc[i]:.4f} stretch {stretch.loc[i]:.3f} "
                    f"atr {atr.loc[i]:.4f} k {k:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "PriorCloseMagnetFadeParams",
    "PriorCloseMagnetFadeStrategy",
]
