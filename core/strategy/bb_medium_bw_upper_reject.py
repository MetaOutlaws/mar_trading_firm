"""Bollinger medium-bandwidth band reject / fade. BOTH sides.

SHORT: wick tags the upper band, then the bar closes back below that
upper band (and back inside the envelope). LONG: wick tags the lower
band, then the bar closes back above that lower band (and back inside).

Only fires when Bollinger bandwidth is in the **medium** window — not a
squeeze and not a blowoff expansion. Bandwidth is the repo helper
``(upper - lower) / mid``.

Quant-locked (not searched):

    - BB period = 20
    - medium bandwidth window ``[0.04, 0.10]``
    - SHORT = upper reject; LONG = lower reject
    - same-bar tag-then-close-back (not a next-bar fail)

Free search (1 only):

    - ``k`` (BB stdev multiplier) grid ``[1.8, 2.0]``

OHLCV only. Causal: bars ``<= t``. The engine fills at ``t+1`` open.

Not ``bollinger_mean_reversion`` (close-through stretch fade, no
medium-BW gate, no tag-then-close-back). Not
``squeeze_momentum_break`` / ``bb_squeeze_breakout`` leftover
(BB-inside-Keltner squeeze then release). Not ``nr7_fail_reversion``
(narrowest-of-7 close-through fail). Not ``expansion_fail_fade``
(single ATR expansion bar then next-bar fail / blowoff). Do not recode
spent families 118–135. Not a displacement / H&S / cup / diamond /
pennant / wedge recode.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Classic BB lookback. Walk-forward must not search this.
BB_PERIOD_LOCKED = 20
# Medium-bandwidth window. Not a squeeze and not blowoff expansion.
BW_MIN_LOCKED = 0.04
BW_MAX_LOCKED = 0.10


@dataclass(frozen=True)
class BbMediumBwUpperRejectParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # BB stdev multiplier. Quant grid: [1.8, 2.0].
    k: float = 1.8
    # Quant-locked BB period. Not a free search param.
    bb_period: int = BB_PERIOD_LOCKED
    # Quant-locked medium-bandwidth floor. Not a free search param.
    bw_min: float = BW_MIN_LOCKED
    # Quant-locked medium-bandwidth cap. Not a free search param.
    bw_max: float = BW_MAX_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class BbMediumBwUpperRejectStrategy(Strategy):
    name = "bb_medium_bw_upper_reject"

    def __init__(self, params: BbMediumBwUpperRejectParams | None = None) -> None:
        super().__init__(params or BbMediumBwUpperRejectParams())
        self.params: BbMediumBwUpperRejectParams = self.params
        # BB(20) plus a few quiet prints so the first bands are real.
        self.min_bars = BB_PERIOD_LOCKED + 5

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
        # Searched k stays caller-set. Period and medium-BW window stay locked
        # even if a caller tries to override them on the params object.
        k = float(params.k)
        period = BB_PERIOD_LOCKED
        bw_min = BW_MIN_LOCKED
        bw_max = BW_MAX_LOCKED

        mid, upper, lower = ind.bollinger_bands(close, period, k)
        # Repo helper: (upper - lower) / mid. Same definition as elsewhere.
        bandwidth = ind.bollinger_width(close, period, k)
        medium_bw = bandwidth.ge(bw_min) & bandwidth.le(bw_max)

        # Same-bar reject: tag the band, close back inside the envelope.
        tagged_upper = high.ge(upper)
        tagged_lower = low.le(lower)
        closed_inside = close.lt(upper) & close.gt(lower)
        upper_reject = medium_bw & tagged_upper & closed_inside
        lower_reject = medium_bw & tagged_lower & closed_inside

        signals["bb_mid"] = mid
        signals["bb_upper"] = upper
        signals["bb_lower"] = lower
        signals["bb_bandwidth"] = bandwidth
        signals["medium_bw"] = medium_bw.fillna(False)
        signals["tagged_upper"] = tagged_upper.fillna(False)
        signals["tagged_lower"] = tagged_lower.fillna(False)
        signals["closed_inside"] = closed_inside.fillna(False)

        if params.side is SignalSide.SHORT:
            entry = upper_reject
            signal_value, side_value = -1, SignalSide.SHORT.value
        elif params.side is SignalSide.LONG:
            entry = lower_reject
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the wick tags further through the band.
            width = (upper - lower).replace(0, pd.NA)
            if params.side is SignalSide.SHORT:
                depth = ((high - upper) / width).clip(0.0, 1.0)
            else:
                depth = ((lower - low) / width).clip(0.0, 1.0)
            signals.loc[entry, "score"] = depth.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            band = upper if params.side is SignalSide.SHORT else lower
            reasons.loc[entry] = [
                (
                    f"{side_value}: BB medium-BW reject close {close.loc[i]:.4f} "
                    f"band {band.loc[i]:.4f} bw {bandwidth.loc[i]:.4f} "
                    f"in [{bw_min:.2f}, {bw_max:.2f}] k={k:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "BB_PERIOD_LOCKED",
    "BW_MAX_LOCKED",
    "BW_MIN_LOCKED",
    "BbMediumBwUpperRejectParams",
    "BbMediumBwUpperRejectStrategy",
]
