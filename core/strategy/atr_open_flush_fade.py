"""Same-bar open flush then fade back through the open. BOTH sides.

SHORT: the bar opens, flushes up so high extends by ``>= k * ATR`` from
that open, then closes back *below* the open (fade).
LONG: the bar opens, flushes down so low extends by ``>= k * ATR`` from
that open, then closes back *above* the open (fade).

ATR is Wilder ``ATR(20)`` known *before* the signal bar so the flush
cannot lift its own threshold. Same-bar geometry only: flush extreme
and reclaim close live on bar ``t``. The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - ATR period = 20
    - same-bar flush extreme then close back through open
    - SHORT = up-flush fade; LONG = down-flush fade

Free search (1 only):

    - ``k`` (flush distance in ATR units from open) grid ``[1.0, 1.5]``

OHLCV only. Causal: bars ``<= t``. No volume gate.

Not ``ib_fail_reversion`` (124 — London IB mother + later fail).
Not ``prior_close_magnet_fade`` (128 — stretch of close vs prior close).
Not ``expansion_fail_fade`` (131 — next-bar fail of a prior expansion).
Not ``orb_fail_reversion`` (UTC-day ORB close-through then fail).
Not ``prior_week_extreme_reject`` (CEO superseded — do not implement).
Not NR7 / rectangle / three_black / bb_medium.
Do not recode spent families 118–137.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches k only.
ATR_N_LOCKED = 20


@dataclass(frozen=True)
class AtrOpenFlushFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Flush distance in ATR units from the bar open. Quant grid: [1.0, 1.5].
    k: float = 1.0
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class AtrOpenFlushFadeStrategy(Strategy):
    name = "atr_open_flush_fade"

    def __init__(self, params: AtrOpenFlushFadeParams | None = None) -> None:
        super().__init__(params or AtrOpenFlushFadeParams())
        self.params: AtrOpenFlushFadeParams = self.params
        # ATR seed plus one bar so the threshold is the *prior* ATR print.
        self.min_bars = ATR_N_LOCKED + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        open_ = candles["open"]
        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        # Locks stay locked even if a caller passes another atr_n.
        atr_n = ATR_N_LOCKED
        k = float(params.k)

        atr20 = ind.atr(high, low, close, atr_n)
        # Prevailing ATR before this bar. The flush cannot inflate the hurdle.
        atr_prev = atr20.shift(1)
        atr_ok = atr_prev.gt(0)

        # Same-bar flush distance from the open, in ATR units.
        up_flush_atr = (high - open_) / atr_prev.replace(0, pd.NA)
        down_flush_atr = (open_ - low) / atr_prev.replace(0, pd.NA)
        up_flush = atr_ok & up_flush_atr.ge(k)
        down_flush = atr_ok & down_flush_atr.ge(k)
        # Fade: close back through the same open the flush started from.
        faded_below_open = close.lt(open_)
        faded_above_open = close.gt(open_)

        short_raw = up_flush & faded_below_open
        long_raw = down_flush & faded_above_open

        signals["atr"] = atr20
        signals["atr_prev"] = atr_prev
        signals["bar_open"] = open_
        signals["up_flush_atr"] = up_flush_atr
        signals["down_flush_atr"] = down_flush_atr
        signals["up_flush"] = up_flush.fillna(False)
        signals["down_flush"] = down_flush.fillna(False)
        signals["faded_below_open"] = faded_below_open
        signals["faded_above_open"] = faded_above_open

        if params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            flush_atr = up_flush_atr
        elif params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            flush_atr = down_flush_atr
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value
            flush_atr = pd.Series(pd.NA, index=candles.index, dtype="float64")

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the flush extends further past k*ATR.
            excess = ((flush_atr - k) / k).clip(0.0, 1.0)
            signals.loc[entry, "score"] = excess.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: open-flush fade open {open_.loc[i]:.4f} "
                    f"close {close.loc[i]:.4f} high {high.loc[i]:.4f} "
                    f"low {low.loc[i]:.4f} flush {float(flush_atr.loc[i]):.3f} "
                    f"atr {atr_prev.loc[i]:.4f} k={k:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "AtrOpenFlushFadeParams",
    "AtrOpenFlushFadeStrategy",
]
