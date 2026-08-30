"""
The strategy contract.

Every strategy implements one method, `generate_signals`, which takes a canonical
OHLCV frame and returns a signal frame covering the *whole* history. The live
engine calls the identical method on a trailing window and reads the last row.

That single-entry-point design is deliberate. The predecessor project had one
signal implementation for live trading and a different one for backtesting; the
two disagreed by roughly 30 percentage points of win rate, and there was no way
to tell which (if either) was right. Here, live and backtest cannot diverge
because they execute the same code path.

## Timing convention (no lookahead)

- A signal at bar `t` may use data from bars `<= t` only.
- A signal at bar `t` is *actionable* at bar `t+1`'s open, because bar `t`'s
  close is not known until the bar has closed.
- The backtester therefore fills entries at `t+1` open. Filling at bar `t`'s
  close -- as the legacy engine did -- assumes knowledge of a price at the
  instant it becomes available, which flatters results.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

import pandas as pd

# Columns every strategy must return from `generate_signals`.
SIGNAL_COLUMNS = ["signal", "side", "score", "reason"]


class SignalSide(str, Enum):
    """Direction of a trade signal."""

    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"

    @property
    def bybit_side(self) -> str:
        """Bybit's order-side wording for this direction."""
        return "Buy" if self is SignalSide.LONG else "Sell"

    @property
    def sign(self) -> int:
        """+1 for long, -1 for short, 0 for flat. Handy for P&L arithmetic."""
        if self is SignalSide.LONG:
            return 1
        if self is SignalSide.SHORT:
            return -1
        return 0


@dataclass(frozen=True)
class Signal:
    """A single actionable signal, as consumed by the live engine."""

    symbol: str
    side: SignalSide
    timestamp: pd.Timestamp
    price: float  # Close of the bar that produced the signal
    score: float  # Strategy confidence, higher is stronger
    reason: str  # Human-readable explanation, surfaced in the dashboard
    strategy: str
    take_profit_pct: float
    stop_loss_pct: float
    indicators: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["side"] = self.side.value
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass(frozen=True)
class StrategyParams:
    """Base class for strategy parameter sets.

    Subclasses stay frozen dataclasses so a parameter set is hashable and can be
    used as a cache key during optimisation sweeps.
    """

    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.05
    max_holding_bars: int = 96  # 96 * 15min = 24h, the legacy timeout

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Strategy(ABC):
    """Base class for all strategies.

    A strategy is a pure function of price history plus parameters. It must not
    read the database, call an exchange, or consult an LLM -- those belong to
    other layers. This keeps strategies reproducible, which is the whole basis
    for trusting a backtest.
    """

    name: str = "unnamed"
    #: Minimum bars required before any signal can be emitted. The backtester
    #: and live engine both use this to avoid acting on warm-up noise.
    min_bars: int = 250

    def __init__(self, params: StrategyParams | None = None) -> None:
        self.params = params or StrategyParams()

    @abstractmethod
    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        """Compute signals across an entire OHLCV history.

        Args:
            candles: Canonical OHLCV frame (see `core.data.ohlcv`).

        Returns:
            A frame indexed identically to `candles`, with columns:
              - `signal`: int, 1 for long entry, -1 for short entry, 0 for none
              - `side`:   str, one of SignalSide values
              - `score`:  float, confidence
              - `reason`: str, why the signal fired (or why it did not)
            Plus any indicator columns the strategy wants to expose for
            diagnostics and dashboard display.
        """

    # -----------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------
    def empty_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        """A correctly-shaped all-flat signal frame."""
        frame = pd.DataFrame(index=candles.index)
        frame["signal"] = 0
        frame["side"] = SignalSide.FLAT.value
        frame["score"] = 0.0
        frame["reason"] = ""
        return frame

    def latest_signal(self, symbol: str, candles: pd.DataFrame) -> Signal | None:
        """Evaluate the most recent bar and return a Signal if one fired.

        This is the live engine's entry point. It calls `generate_signals` --
        the same method the backtester uses -- and reads the final row, so live
        behaviour is identical to simulated behaviour by construction.
        """
        if len(candles) < self.min_bars:
            return None

        signals = self.generate_signals(candles)
        if signals.empty:
            return None

        last = signals.iloc[-1]
        if int(last["signal"]) == 0:
            return None

        # Everything that is not a required column is an indicator reading worth
        # surfacing for diagnostics.
        indicators = {
            column: float(last[column])
            for column in signals.columns
            if column not in SIGNAL_COLUMNS and pd.notna(last[column])
        }

        return Signal(
            symbol=symbol,
            side=SignalSide(last["side"]),
            timestamp=signals.index[-1],
            price=float(candles["close"].iloc[-1]),
            score=float(last["score"]),
            reason=str(last["reason"]),
            strategy=self.name,
            take_profit_pct=self.params.take_profit_pct,
            stop_loss_pct=self.params.stop_loss_pct,
            indicators=indicators,
        )

    def validate_candles(self, candles: pd.DataFrame) -> None:
        """Reject malformed input loudly rather than producing quiet nonsense."""
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(candles.columns)
        if missing:
            raise ValueError(f"{self.name}: candles missing columns {sorted(missing)}")
        if not isinstance(candles.index, pd.DatetimeIndex):
            raise ValueError(f"{self.name}: candles must have a DatetimeIndex")
        if not candles.index.is_monotonic_increasing:
            raise ValueError(f"{self.name}: candles must be sorted ascending by time")
