"""Classic three white soldiers — LONG after the third soldier confirms.

Exactly three consecutive bullish candles with ascending closes
(``close[t] > close[t-1] > close[t-2]``). Each soldier opens inside the
prior candle's high-low. Bodies are substantial; lower wicks are
limited. LONG-only: do not implement three black crows / SHORT here.
``three_black_crows`` remains the SHORT-only sibling (job 134); this
file must not change that geometry.

Geometry (range = high-low; zero-range bars never qualify as a soldier):

    - ``body_frac = |close - open| / range``
    - ``lower_wick_frac = (min(open, close) - low) / range``

Quant-locked (not searched):

    - exactly ``n_bars = 3``
    - each soldier opens in the prior bar's high-low
    - LONG side only
    - ascending closes across the three soldiers
    - each of the three is bullish (close > open)

Free search (2 only):

    - ``min_body_frac`` grid ``[0.40, 0.50]``
    - ``max_lower_wick_frac`` grid ``[0.15, 0.25]``

OHLCV only. Causal: bars ``<= t``. The engine fills at ``t+1`` open.

Not ``three_black_crows`` (job 134 — SHORT-only descending bearish
crows, upper-wick cap). Not ``three_bar_play`` (trend mother + narrow
rest inside it + break of the rest). Not ``engulfing_fail_reversion``
(job 126 — two-bar body engulf, then a later close back through the
engulf open). Not ``atr_open_flush_fade`` (138 — same-bar bar-open
flush fade). Not ``utc_day_open_flush_fade`` (139 — UTC day-open flush
fade). Not ``ny_close_inventory_fade`` (banned/parked). Do not recode
spent families 118–139. Do not modify three_black_crows geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams

# Classic three-bar soldier window. Walk-forward must not search this.
N_BARS_LOCKED = 3
# Each soldier must open inside the immediately prior bar's high-low.
REQUIRE_OPEN_IN_PRIOR_RANGE_LOCKED = True


@dataclass(frozen=True)
class ThreeWhiteSoldiersParams(StrategyParams):
    # LONG-bias family. SHORT / three black crows is not implemented here.
    side: SignalSide = SignalSide.LONG
    # Minimum body share of each soldier. Quant grid: [0.40, 0.50].
    min_body_frac: float = 0.40
    # Maximum lower-wick share of each soldier. Quant grid: [0.15, 0.25].
    max_lower_wick_frac: float = 0.25
    # Quant-locked bar count (Garwe stamp n_bars=3). Not a free search param.
    n_bars: int = N_BARS_LOCKED
    # Quant-locked open-in-prior-range. Not a free search param.
    require_open_in_prior_range: bool = REQUIRE_OPEN_IN_PRIOR_RANGE_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ThreeWhiteSoldiersStrategy(Strategy):
    name = "three_white_soldiers"

    def __init__(self, params: ThreeWhiteSoldiersParams | None = None) -> None:
        super().__init__(params or ThreeWhiteSoldiersParams())
        self.params: ThreeWhiteSoldiersParams = self.params
        # Prior bar + three soldiers. A few quiet prints keep the first bars flat.
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
        max_lower = float(params.max_lower_wick_frac)
        n_bars = N_BARS_LOCKED
        require_open = REQUIRE_OPEN_IN_PRIOR_RANGE_LOCKED

        bar_range = (high - low).replace(0, pd.NA)
        body_low = pd.concat([open_, close], axis=1).min(axis=1)
        body_frac = (close - open_).abs() / bar_range
        # Stub-lower: (min(open, close) - low) / range. Mirror of crows' stub-upper.
        lower_wick_frac = (body_low - low) / bar_range
        bullish = close.gt(open_)

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

        # One soldier: bullish, substantial body, stub lower wick, valid range.
        soldier = (
            bar_range.notna()
            & bullish
            & body_frac.ge(min_body)
            & lower_wick_frac.le(max_lower)
        )
        if require_open:
            soldier = soldier & open_in_prior

        # Exactly three consecutive soldiers ending at t. n_bars is locked at 3.
        three = soldier
        for lag in range(1, n_bars):
            three = three & soldier.shift(lag)

        # Ascending closes across the three-soldier window only.
        ascending = close.gt(close.shift(1)) & close.shift(1).gt(close.shift(2))

        signals["body_frac"] = body_frac
        signals["lower_wick_frac"] = lower_wick_frac
        signals["open_in_prior_range"] = open_in_prior.fillna(False)
        signals["soldier"] = soldier.fillna(False)
        # Window diagnostics so a later shock cannot rewrite bar-t geometry.
        min_body_3 = body_frac.rolling(n_bars, min_periods=n_bars).min()
        max_lower_3 = lower_wick_frac.rolling(n_bars, min_periods=n_bars).max()
        signals["min_body_frac_3"] = min_body_3
        signals["max_lower_wick_frac_3"] = max_lower_3

        # LONG-only. SHORT / three black crows is intentionally absent.
        if params.side is SignalSide.LONG:
            entry = three & ascending
            signal_value, side_value = 1, SignalSide.LONG.value
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
                    f"{side_value}: three white soldiers close {close.loc[i]:.4f} "
                    f"> {close.shift(1).loc[i]:.4f} > {close.shift(2).loc[i]:.4f} "
                    f"min_body {min_body_3.loc[i]:.3f}>={min_body:.2f} "
                    f"max_lower {max_lower_3.loc[i]:.3f}<={max_lower:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "N_BARS_LOCKED",
    "REQUIRE_OPEN_IN_PRIOR_RANGE_LOCKED",
    "ThreeWhiteSoldiersParams",
    "ThreeWhiteSoldiersStrategy",
]
