"""
RSI mean-reversion with a trend filter -- the strategy the legacy bot ran.

Ported faithfully from `legacy/new_multi_indicator.py::check_entry_conditions`
(~L2588) so that validation measures what was actually deployed, not an
idealised variant. The legacy project's fatal mistake was testing a *different*
strategy than it ran; correcting that requires porting the real rules first and
only then improving them.

LONG rules (all must hold):
  1. RSI within [rsi_min, rsi_max]           - pullback, not free-fall
  2. RSI rising versus the prior bar          - the bounce has begun
  3. EMA50 > EMA200 ("golden cross")          - buy dips in uptrends only
  4. Volume ratio > threshold                 - participation confirms the move

SHORT rules (all must hold):
  1. RSI >= rsi_threshold                     - overbought
  2. RSI falling versus the prior bar         - momentum turning over
  3. Price > EMA200                           - fade rallies inside uptrends
  4. Volume ratio > threshold

The SHORT construction is worth flagging: it shorts strength *within an uptrend*,
which is structurally fighting the prevailing trend. It was the legacy config's
choice and is preserved for a like-for-like test, but it is a prior reason to
expect shorts to validate worse than longs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import Signal, SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class RsiTrendParams(StrategyParams):
    """Parameters for the RSI + trend-filter strategy."""

    # Direction this instance trades. One strategy object handles one side, so
    # long and short performance are always measured separately.
    side: SignalSide = SignalSide.LONG

    # LONG: RSI must sit inside this band.
    rsi_min: float = 30.0
    rsi_max: float = 40.0
    # SHORT: RSI must be at or above this level.
    rsi_threshold: float = 65.0

    rsi_period: int = 14
    ema_fast: int = 50
    ema_slow: int = 200
    volume_period: int = 20
    volume_threshold: float = 1.2
    adx_period: int = 14

    # Optional trend-strength filter. 0 disables it (legacy behaviour).
    min_adx: float = 0.0


class RsiTrendStrategy(Strategy):
    """RSI pullback entries filtered by an EMA trend regime."""

    name = "rsi_trend"

    def __init__(self, params: RsiTrendParams | None = None) -> None:
        super().__init__(params or RsiTrendParams())
        self.params: RsiTrendParams = self.params  # narrow the type for readers
        # Need the slow EMA fully warmed plus headroom for Wilder seeding.
        self.min_bars = max(self.params.ema_slow + 50, 250)

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Vectorised signal computation across the full history."""
        self.validate_candles(candles)

        params = self.params
        signals = self.empty_signals(candles)

        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        close = candles["close"]

        # ---- indicators (all trailing, no lookahead) ----------------------
        rsi = ind.rsi(close, params.rsi_period)
        rsi_change = ind.slope(rsi, 1)
        ema_fast = ind.ema(close, params.ema_fast)
        ema_slow = ind.ema(close, params.ema_slow)
        vol_ratio = ind.volume_ratio(candles["volume"], params.volume_period)
        adx_value, plus_di, minus_di = ind.adx(
            candles["high"], candles["low"], close, params.adx_period
        )

        # Expose indicators for diagnostics, dashboard display, and post-trade
        # attribution ("what did the market look like when this fired?").
        signals["rsi"] = rsi
        signals["rsi_change"] = rsi_change
        signals["ema_fast"] = ema_fast
        signals["ema_slow"] = ema_slow
        signals["volume_ratio"] = vol_ratio
        signals["adx"] = adx_value
        signals["plus_di"] = plus_di
        signals["minus_di"] = minus_di

        # ---- shared conditions -------------------------------------------
        volume_ok = vol_ratio > params.volume_threshold
        adx_ok = adx_value >= params.min_adx if params.min_adx > 0 else True

        if params.side is SignalSide.LONG:
            rsi_ok = (rsi >= params.rsi_min) & (rsi <= params.rsi_max)
            momentum_ok = rsi_change > 0
            trend_ok = ema_fast > ema_slow  # golden cross
            entry = rsi_ok & momentum_ok & trend_ok & volume_ok & adx_ok
            side_value = SignalSide.LONG.value
            signal_value = 1
        else:
            rsi_ok = rsi >= params.rsi_threshold
            momentum_ok = rsi_change < 0
            trend_ok = close > ema_slow  # fade strength inside an uptrend
            entry = rsi_ok & momentum_ok & trend_ok & volume_ok & adx_ok
            side_value = SignalSide.SHORT.value
            signal_value = -1

        # A NaN anywhere in the warm-up region must not count as a signal.
        entry = entry.fillna(False).astype(bool)

        # Suppress the warm-up window outright rather than trusting partially
        # seeded indicators.
        entry.iloc[: self.min_bars] = False

        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        signals.loc[entry, "score"] = self._score(rsi, vol_ratio, adx_value)[entry]
        signals["reason"] = self._reasons(entry, rsi, vol_ratio, adx_value)

        return signals

    def _score(self, rsi: pd.Series, vol_ratio: pd.Series, adx_value: pd.Series) -> pd.Series:
        """Confidence score in roughly [0, 3].

        Used to rank competing signals when capital is scarce, not to decide
        entry (entry is the boolean confluence above). Three components, each
        contributing up to 1.0: RSI extremity, volume conviction, trend strength.
        """
        params = self.params

        if params.side is SignalSide.LONG:
            # Deeper into the oversold band scores higher.
            span = max(params.rsi_max - params.rsi_min, 1e-9)
            rsi_component = ((params.rsi_max - rsi) / span).clip(0.0, 1.0)
        else:
            # Further above the overbought threshold scores higher.
            rsi_component = ((rsi - params.rsi_threshold) / 20.0).clip(0.0, 1.0)

        # 1x threshold scores 0, 2x threshold or better scores 1.
        volume_component = (
            (vol_ratio - params.volume_threshold) / max(params.volume_threshold, 1e-9)
        ).clip(0.0, 1.0)

        # ADX 20 is the conventional "trending" line; 40 is strongly trending.
        adx_component = ((adx_value - 20.0) / 20.0).clip(0.0, 1.0)

        return (rsi_component + volume_component + adx_component).fillna(0.0)

    def _reasons(
        self,
        entry: pd.Series,
        rsi: pd.Series,
        vol_ratio: pd.Series,
        adx_value: pd.Series,
    ) -> pd.Series:
        """Build human-readable explanations for the bars that fired."""
        reasons = pd.Series("", index=entry.index, dtype="object")
        if not entry.any():
            return reasons

        side_label = "LONG" if self.params.side is SignalSide.LONG else "SHORT"
        fired = entry[entry].index
        reasons.loc[fired] = [
            (
                f"{side_label}: RSI {rsi.loc[stamp]:.1f}, "
                f"vol {vol_ratio.loc[stamp]:.2f}x, "
                f"ADX {adx_value.loc[stamp]:.1f}"
            )
            for stamp in fired
        ]
        return reasons


def long_strategy_for(symbol: str, **overrides: float) -> RsiTrendStrategy:
    """Build the LONG strategy for a symbol using its configured parameters."""
    from config.universe import get_universe

    config = get_universe().long_params.get(symbol)
    params = RsiTrendParams(
        side=SignalSide.LONG,
        rsi_min=config.rsi_min if config else 30.0,
        rsi_max=config.rsi_max if config else 40.0,
        volume_threshold=config.volume_threshold if config else 1.2,
        take_profit_pct=config.take_profit_pct if config else 0.05,
        stop_loss_pct=config.stop_loss_pct if config else 0.05,
        **overrides,  # type: ignore[arg-type]
    )
    return RsiTrendStrategy(params)


def short_strategy_for(symbol: str, **overrides: float) -> RsiTrendStrategy:
    """Build the SHORT strategy for a symbol using its configured parameters."""
    from config.universe import get_universe

    config = get_universe().short_params.get(symbol)
    params = RsiTrendParams(
        side=SignalSide.SHORT,
        rsi_threshold=config.rsi_threshold if config else 65.0,
        volume_threshold=config.volume_threshold if config else 1.2,
        take_profit_pct=config.take_profit_pct if config else 0.05,
        stop_loss_pct=config.stop_loss_pct if config else 0.05,
        **overrides,  # type: ignore[arg-type]
    )
    return RsiTrendStrategy(params)


__all__ = [
    "RsiTrendParams",
    "RsiTrendStrategy",
    "Signal",
    "long_strategy_for",
    "short_strategy_for",
]
