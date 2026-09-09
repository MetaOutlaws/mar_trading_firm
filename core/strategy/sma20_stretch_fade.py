"""SMA20 stretch fade — wick stretch vs SMA, then reclaim toward SMA. BOTH.

LONG: the bar stretches *below* SMA20 by ``>= k * ATR20``, then the close
reclaims toward SMA (``close > SMA - 0.5 * k * ATR``).
SHORT: the bar stretches *above* SMA20 by ``>= k * ATR20``, then the close
fades back toward SMA (``close < SMA + 0.5 * k * ATR``).

Magnet is SMA of close (period 20). Stretch unit is Wilder ATR(20) on
bars ``<= t``. Same-bar geometry: the wick extreme and the reclaim close
live on bar ``t``. The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - SMA period = 20
    - ATR period = 20
    - LONG = stretch below SMA then reclaim toward SMA
    - SHORT = stretch above SMA then fade toward SMA

Free search (1 only):

    - ``k`` (stretch distance in ATR units from SMA) grid ``[1.5, 2.0]``

OHLCV only. Causal: bars ``<= t``. No volume gate. No bandwidth /
session-close / bar-open / day-open / candle-pattern overlay.

Not ``bb_medium_bw_upper_reject`` (BB tag + medium-BW close-inside).
Not ``kairi_relative_fade`` (percent from SMA, turn-up, no ATR wick).
Not ``bollinger_mean_reversion`` (close-through BB, optional ADX chop).
Not ``prior_close_magnet_fade`` (magnet is prior close, not SMA).
Not ``atr_open_flush_fade`` (138 — same-bar flush of *bar open*).
Not ``utc_day_open_flush_fade`` (139 — flush of UTC day-open).
Not ``london_close_inventory_fade`` (100 — London-close bar + VWAP).
Not ``three_white_soldiers`` (140 — three-soldier LONG leftover).
Not ``ny_close_inventory_fade`` (banned/parked).
Not ``atr_fade_chop`` / Keltner break (channel extreme / breakout).
Do not recode spent families 118–140. Do not modify atr / three_* geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked SMA / ATR windows. Walk-forward searches k only.
SMA_N_LOCKED = 20
ATR_N_LOCKED = 20
# Reclaim line sits halfway from the k*ATR stretch back toward SMA.
RECLAIM_FRAC_LOCKED = 0.5


@dataclass(frozen=True)
class Sma20StretchFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # SMA of close. Quant-locked at 20 — not a free search param.
    sma_n: int = SMA_N_LOCKED
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Stretch distance in ATR units from SMA. Quant grid: [1.5, 2.0].
    k: float = 1.5
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class Sma20StretchFadeStrategy(Strategy):
    name = "sma20_stretch_fade"

    def __init__(self, params: Sma20StretchFadeParams | None = None) -> None:
        super().__init__(params or Sma20StretchFadeParams())
        self.params: Sma20StretchFadeParams = self.params
        # SMA(20) and ATR(20) seed plus a couple of quiet prints.
        self.min_bars = max(SMA_N_LOCKED, ATR_N_LOCKED) + 2

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
        # Searched k stays caller-set. Periods stay locked even if overridden.
        k = float(params.k)
        sma_n = SMA_N_LOCKED
        atr_n = ATR_N_LOCKED
        reclaim_frac = RECLAIM_FRAC_LOCKED

        sma = ind.sma(close, sma_n)
        atr = ind.atr(high, low, close, atr_n)
        atr_ok = atr.gt(0) & sma.notna()
        atr_safe = atr.replace(0, pd.NA)

        # Wick stretch from SMA, in ATR units. Not vs bar-open or day-open.
        stretch_below_atr = (sma - low) / atr_safe
        stretch_above_atr = (high - sma) / atr_safe
        stretched_below = atr_ok & stretch_below_atr.ge(k)
        stretched_above = atr_ok & stretch_above_atr.ge(k)

        # Halfway back toward SMA: 0.5 * k * ATR from the magnet.
        half = reclaim_frac * k * atr
        reclaimed_long = close.gt(sma - half)
        reclaimed_short = close.lt(sma + half)

        long_raw = stretched_below & reclaimed_long
        short_raw = stretched_above & reclaimed_short

        signals["sma"] = sma
        signals["atr"] = atr
        signals["stretch_below_atr"] = stretch_below_atr
        signals["stretch_above_atr"] = stretch_above_atr
        signals["stretched_below"] = stretched_below.fillna(False)
        signals["stretched_above"] = stretched_above.fillna(False)
        signals["reclaimed_toward_sma_long"] = reclaimed_long.fillna(False)
        signals["reclaimed_toward_sma_short"] = reclaimed_short.fillna(False)

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            stretch_atr = stretch_below_atr
        elif params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            stretch_atr = stretch_above_atr
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value
            stretch_atr = pd.Series(pd.NA, index=candles.index, dtype="float64")

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the wick extends further past k*ATR.
            excess = ((stretch_atr - k) / k).clip(0.0, 1.0)
            signals.loc[entry, "score"] = excess.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: SMA20 stretch-fade sma {sma.loc[i]:.4f} "
                    f"close {close.loc[i]:.4f} high {high.loc[i]:.4f} "
                    f"low {low.loc[i]:.4f} stretch {float(stretch_atr.loc[i]):.3f} "
                    f"atr {atr.loc[i]:.4f} k={k:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "RECLAIM_FRAC_LOCKED",
    "SMA_N_LOCKED",
    "Sma20StretchFadeParams",
    "Sma20StretchFadeStrategy",
]
