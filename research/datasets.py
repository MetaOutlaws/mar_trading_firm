"""
Multi-regime datasets and data-driven regime labelling.

The go-live gate requires validation across at least three distinct market
regimes including a bear leg. The legacy project tested five weeks of Q4 2024 --
a single bull impulse -- which is why a trend-following strategy looked
excellent there and could not be trusted anywhere else.

Regimes are classified **from the data** rather than from hardcoded dates. A
hand-written list of "the 2022 bear market" bakes in the author's assumptions and
silently goes stale as new data arrives; measuring BTC's realised return and
volatility per quarter does not.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import numpy as np
import pandas as pd

from core.data.ohlcv import BybitOHLCV

logger = logging.getLogger(__name__)

# BTC is the market's beta; every altcoin regime is downstream of it.
REGIME_REFERENCE_SYMBOL = "BTCUSDT"

# Quarterly return thresholds separating the three regimes.
BULL_THRESHOLD = 0.15
BEAR_THRESHOLD = -0.15

# Earliest date Bybit serves linear perpetual klines.
HISTORY_START = datetime(2021, 1, 1, tzinfo=timezone.utc)


class Regime(str, Enum):
    """Coarse market regime for a period."""

    BULL = "bull"
    BEAR = "bear"
    CHOP = "chop"


@dataclass(frozen=True)
class Period:
    """A labelled slice of history."""

    name: str
    start: datetime
    end: datetime
    regime: Regime
    btc_return_pct: float
    btc_volatility_pct: float

    @property
    def days(self) -> int:
        return (self.end - self.start).days

    def __str__(self) -> str:
        return (
            f"{self.name} [{self.regime.value}] "
            f"{self.start.date()}..{self.end.date()} "
            f"BTC {self.btc_return_pct:+.1f}% vol {self.btc_volatility_pct:.1f}%"
        )


def classify_periods(
    reference: pd.DataFrame | None = None,
    freq: str = "QE",
) -> list[Period]:
    """Split history into periods and label each by realised BTC behaviour.

    Args:
        reference: Daily BTC candles. Fetched if omitted.
        freq: Pandas period frequency. "QE" gives calendar quarters.

    Returns:
        Chronological labelled periods.
    """
    if reference is None:
        with BybitOHLCV() as source:
            reference = source.fetch(
                REGIME_REFERENCE_SYMBOL, "1d", HISTORY_START, datetime.now(timezone.utc)
            )

    if reference.empty:
        logger.warning("No reference data; cannot classify regimes.")
        return []

    periods: list[Period] = []

    for period, group in reference.groupby(pd.Grouper(freq=freq)):
        if len(group) < 20:  # too short to characterise
            continue

        opening = float(group["close"].iloc[0])
        closing = float(group["close"].iloc[-1])
        total_return = (closing / opening - 1.0) if opening > 0 else 0.0

        daily_returns = group["close"].pct_change().dropna()
        annualised_vol = float(daily_returns.std() * np.sqrt(365)) if len(daily_returns) > 1 else 0.0

        if total_return >= BULL_THRESHOLD:
            regime = Regime.BULL
        elif total_return <= BEAR_THRESHOLD:
            regime = Regime.BEAR
        else:
            regime = Regime.CHOP

        stamp = pd.Timestamp(period)
        periods.append(
            Period(
                name=f"{stamp.year}Q{stamp.quarter}",
                start=group.index[0].to_pydatetime(),
                end=group.index[-1].to_pydatetime(),
                regime=regime,
                btc_return_pct=total_return * 100.0,
                btc_volatility_pct=annualised_vol * 100.0,
            )
        )

    return periods


def regime_summary(periods: list[Period]) -> dict[str, object]:
    """Aggregate counts and coverage, for reports and go-live gate checks."""
    by_regime: dict[str, list[str]] = {r.value: [] for r in Regime}
    for period in periods:
        by_regime[period.regime.value].append(period.name)

    return {
        "total_periods": len(periods),
        "distinct_regimes": sum(1 for names in by_regime.values() if names),
        "by_regime": by_regime,
        "has_bear": bool(by_regime[Regime.BEAR.value]),
        "span_days": sum(p.days for p in periods),
        "first": periods[0].name if periods else None,
        "last": periods[-1].name if periods else None,
    }


@dataclass
class DatasetLoader:
    """Loads and caches candle histories for research runs."""

    timeframe: str = "15m"
    start: datetime = HISTORY_START
    end: datetime | None = None

    def __post_init__(self) -> None:
        self.end = self.end or datetime.now(timezone.utc)
        self._source = BybitOHLCV()
        self._loaded: dict[str, pd.DataFrame] = {}

    def close(self) -> None:
        self._source.close()

    def __enter__(self) -> "DatasetLoader":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def load(self, symbol: str) -> pd.DataFrame:
        """Full history for a symbol at the configured timeframe."""
        if symbol not in self._loaded:
            self._loaded[symbol] = self._source.fetch(
                symbol, self.timeframe, self.start, self.end
            )
        return self._loaded[symbol]

    def load_period(self, symbol: str, period: Period, warmup_bars: int = 300) -> pd.DataFrame:
        """Candles for a period, prefixed with warm-up bars.

        Indicators need history before the first tradable bar. Slicing exactly
        to the period boundary would leave the first ~250 bars unusable and
        quietly shrink every window.
        """
        full = self.load(symbol)
        if full.empty:
            return full

        start_index = full.index.searchsorted(pd.Timestamp(period.start))
        warmed_start = max(0, start_index - warmup_bars)
        end_index = full.index.searchsorted(pd.Timestamp(period.end), side="right")

        return full.iloc[warmed_start:end_index]

    def available_symbols(self, candidates: list[str], min_bars: int = 5_000) -> list[str]:
        """Filter candidates down to those with enough history to test.

        Newly listed perps cannot be validated across regimes, so including
        them would create false confidence from a short bull-only sample.
        """
        usable = []
        for symbol in candidates:
            try:
                frame = self.load(symbol)
            except Exception as exc:
                logger.warning("Skipping %s: %s", symbol, exc)
                continue
            if len(frame) >= min_bars:
                usable.append(symbol)
            else:
                logger.info("Skipping %s: only %d bars", symbol, len(frame))
        return usable
