"""Classic hammer / hanging-man reject candle as one family.

LONG is a hammer: long lower wick, stub upper wick, non-doji body,
close in the upper half of the bar. SHORT is a hanging-man: the
*same* geometry, interpreted as a bearish reject. Both sides are
one family on clock ``4h/4h``.

Geometry (range = high-low; zero-range bars never fire):

- ``lower_wick_frac = (min(open, close) - low) / range``
- ``upper_wick_frac = (high - max(open, close)) / range``
- ``body_frac = |close - open| / range``

Quant-locked (not searched):

- ``max_upper_wick_frac = 0.15``
- ``min_body_frac = 0.15`` (not a doji; ``doji_star_reversal`` uses
  ``max_body ~0.10``)
- close in the upper half of the bar
- no ``run_bars``, no next-bar doji-star confirm

Free search (2 only):

- ``min_lower_wick_frac`` grid ``[0.55, 0.65]``
- ``max_body_frac`` grid ``[0.20, 0.35]``

OHLCV only. Causal: bars ``<= t``. The engine fills at ``t+1`` open.

Not ``wick_rejection_reversal`` (generic long wick; no stub-upper /
non-doji / close-upper-half kit). Not ``doji_star_reversal`` (doji
body + run + confirm bar). Do not recode spent families 118–131.
Displacement is parked. Rectangle / three_black_crows are buffer only.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy.base import SignalSide, Strategy, StrategyParams

# Stub upper wick. Walk-forward must not search this.
MAX_UPPER_WICK_FRAC_LOCKED = 0.15
# Floor that keeps the body out of doji territory (~0.10).
MIN_BODY_FRAC_LOCKED = 0.15
# Hammer / hanging-man body sits in the top half of the bar.
REQUIRE_CLOSE_UPPER_HALF_LOCKED = True


@dataclass(frozen=True)
class CandleRejectReversalParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Minimum lower-wick share of the bar. Quant grid: [0.55, 0.65].
    min_lower_wick_frac: float = 0.55
    # Maximum body share. Quant grid: [0.20, 0.35].
    max_body_frac: float = 0.35
    # Quant-locked stub-upper cap. Not a free search param.
    max_upper_wick_frac: float = MAX_UPPER_WICK_FRAC_LOCKED
    # Quant-locked non-doji floor. Not a free search param.
    min_body_frac: float = MIN_BODY_FRAC_LOCKED
    # Quant-locked: close must sit in the upper half of the bar.
    require_close_upper_half: bool = REQUIRE_CLOSE_UPPER_HALF_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class CandleRejectReversalStrategy(Strategy):
    name = "candle_reject_reversal"

    def __init__(self, params: CandleRejectReversalParams | None = None) -> None:
        super().__init__(params or CandleRejectReversalParams())
        self.params: CandleRejectReversalParams = self.params
        # Single-bar geometry; a few quiet prints keep the first bars flat.
        self.min_bars = 4

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
        # Locks stay locked even if a caller passes another value.
        min_lower = float(params.min_lower_wick_frac)
        max_body = float(params.max_body_frac)
        max_upper = MAX_UPPER_WICK_FRAC_LOCKED
        min_body = MIN_BODY_FRAC_LOCKED
        close_upper = REQUIRE_CLOSE_UPPER_HALF_LOCKED

        bar_range = (high - low).replace(0, pd.NA)
        body_low = pd.concat([open_, close], axis=1).min(axis=1)
        body_high = pd.concat([open_, close], axis=1).max(axis=1)
        lower_wick_frac = (body_low - low) / bar_range
        upper_wick_frac = (high - body_high) / bar_range
        body_frac = (close - open_).abs() / bar_range
        bar_mid = (high + low) / 2.0

        # Same hammer / hanging-man shape for both sides.
        geometry = (
            bar_range.notna()
            & lower_wick_frac.ge(min_lower)
            & upper_wick_frac.le(max_upper)
            & body_frac.ge(min_body)
            & body_frac.le(max_body)
        )
        if close_upper:
            geometry = geometry & close.ge(bar_mid)

        signals["lower_wick_frac"] = lower_wick_frac
        signals["upper_wick_frac"] = upper_wick_frac
        signals["body_frac"] = body_frac
        signals["bar_mid"] = bar_mid

        if params.side is SignalSide.LONG:
            entry = geometry
            signal_value, side_value = 1, SignalSide.LONG.value
            label = "hammer"
        else:
            entry = geometry
            signal_value, side_value = -1, SignalSide.SHORT.value
            label = "hanging-man"

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = lower_wick_frac.clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: {label} reject close {close.loc[i]:.4f} "
                    f"mid {bar_mid.loc[i]:.4f} "
                    f"lower {lower_wick_frac.loc[i]:.3f}>={min_lower:.2f} "
                    f"upper {upper_wick_frac.loc[i]:.3f}<={max_upper:.2f} "
                    f"body {body_frac.loc[i]:.3f} in [{min_body:.2f}, {max_body:.2f}]"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "MAX_UPPER_WICK_FRAC_LOCKED",
    "MIN_BODY_FRAC_LOCKED",
    "REQUIRE_CLOSE_UPPER_HALF_LOCKED",
    "CandleRejectReversalParams",
    "CandleRejectReversalStrategy",
]
