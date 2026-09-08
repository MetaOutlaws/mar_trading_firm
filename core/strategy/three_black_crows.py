"""Classic three black crows — SHORT after the third crow confirms.

Exactly three consecutive bearish candles with descending closes
(``close[t] < close[t-1] < close[t-2]``). Each crow opens inside the
prior candle's high-low. Bodies are substantial; upper wicks are
limited. SHORT-only: do not implement three white soldiers / LONG.

Geometry (range = high-low; zero-range bars never qualify as a crow):

    - ``body_frac = |close - open| / range``
    - ``upper_wick_frac = (high - max(open, close)) / range``

Quant-locked (not searched):

    - exactly ``n_bars = 3``
    - each crow opens in the prior bar's high-low
    - SHORT side only
    - descending closes across the three crows
    - each of the three is bearish (close < open)

Free search (2 only):

    - ``min_body_frac`` grid ``[0.40, 0.50]``
    - ``max_upper_wick_frac`` grid ``[0.15, 0.25]``

OHLCV only. Causal: bars ``<= t``. The engine fills at ``t+1`` open.

Not ``three_bar_play`` (trend mother + narrow rest inside it + break of
the rest). Not ``engulfing_fail_reversion`` (job 126 — two-bar body
engulf, then a later close back through the engulf open). Not
``candle_reject_reversal`` / ``consecutive_bar_exhaustion`` /
``open_in_prior_range_fail``. Do not recode spent families 118–133.
Do not code three white soldiers / BOTH.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams

# Classic three-bar crow window. Walk-forward must not search this.
N_BARS_LOCKED = 3
# Each crow must open inside the immediately prior bar's high-low.
REQUIRE_OPEN_IN_PRIOR_RANGE_LOCKED = True


@dataclass(frozen=True)
class ThreeBlackCrowsParams(StrategyParams):
    # SHORT-bias family. LONG / three white soldiers is not implemented.
    side: SignalSide = SignalSide.SHORT
    # Minimum body share of each crow. Quant grid: [0.40, 0.50].
    min_body_frac: float = 0.40
    # Maximum upper-wick share of each crow. Quant grid: [0.15, 0.25].
    max_upper_wick_frac: float = 0.25
    # Quant-locked bar count (Garwe stamp n_bars=3). Not a free search param.
    n_bars: int = N_BARS_LOCKED
    # Quant-locked open-in-prior-range. Not a free search param.
    require_open_in_prior_range: bool = REQUIRE_OPEN_IN_PRIOR_RANGE_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ThreeBlackCrowsStrategy(Strategy):
    name = "three_black_crows"

    def __init__(self, params: ThreeBlackCrowsParams | None = None) -> None:
        super().__init__(params or ThreeBlackCrowsParams())
        self.params: ThreeBlackCrowsParams = self.params
        # Prior bar + three crows. A few quiet prints keep the first bars flat.
        self.min_bars = 6

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
        # Searched knobs stay caller-set. Locks stay locked even if overridden.
        min_body = float(params.min_body_frac)
        max_upper = float(params.max_upper_wick_frac)
        n_bars = N_BARS_LOCKED
        require_open = REQUIRE_OPEN_IN_PRIOR_RANGE_LOCKED

        bar_range = (high - low).replace(0, pd.NA)
        body_high = pd.concat([open_, close], axis=1).max(axis=1)
        body_frac = (close - open_).abs() / bar_range
        upper_wick_frac = (high - body_high) / bar_range
        bearish = close.lt(open_)

        prior_high = high.shift(1)
        prior_low = low.shift(1)
        # Open inside the prior candle's range (inclusive high-low).
        open_in_prior = (
            prior_high.notna()
            & prior_low.notna()
            & prior_high.gt(prior_low)
            & open_.ge(prior_low)
            & open_.le(prior_high)
        )

        # One crow: bearish, substantial body, stub upper wick, valid range.
        crow = (
            bar_range.notna()
            & bearish
            & body_frac.ge(min_body)
            & upper_wick_frac.le(max_upper)
        )
        if require_open:
            crow = crow & open_in_prior

        # Exactly three consecutive crows ending at t. n_bars is locked at 3.
        three = crow
        for lag in range(1, n_bars):
            three = three & crow.shift(lag)

        # Descending closes across the three-crow window only.
        descending = close.lt(close.shift(1)) & close.shift(1).lt(close.shift(2))

        signals["body_frac"] = body_frac
        signals["upper_wick_frac"] = upper_wick_frac
        signals["open_in_prior_range"] = open_in_prior.fillna(False)
        signals["crow"] = crow.fillna(False)
        # Window diagnostics so a later shock cannot rewrite bar-t geometry.
        min_body_3 = body_frac.rolling(n_bars, min_periods=n_bars).min()
        max_upper_3 = upper_wick_frac.rolling(n_bars, min_periods=n_bars).max()
        signals["min_body_frac_3"] = min_body_3
        signals["max_upper_wick_frac_3"] = max_upper_3

        # SHORT-only. LONG / three white soldiers is intentionally absent.
        if params.side is SignalSide.SHORT:
            entry = three & descending
            signal_value, side_value = -1, SignalSide.SHORT.value
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when all three bodies are large.
            signals.loc[entry, "score"] = min_body_3.clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: three black crows close {close.loc[i]:.4f} "
                    f"< {close.shift(1).loc[i]:.4f} < {close.shift(2).loc[i]:.4f} "
                    f"min_body {min_body_3.loc[i]:.3f}>={min_body:.2f} "
                    f"max_upper {max_upper_3.loc[i]:.3f}<={max_upper:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "N_BARS_LOCKED",
    "REQUIRE_OPEN_IN_PRIOR_RANGE_LOCKED",
    "ThreeBlackCrowsParams",
    "ThreeBlackCrowsStrategy",
]
