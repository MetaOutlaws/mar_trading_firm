"""Strategy layer: the SINGLE source of truth for trading signals.

Both the backtester (`research/`) and the live engine (`core/execution/`) import
signals from here. The predecessor project maintained two separate
implementations, which is why its backtests disagreed with each other by 30
percentage points of win rate. That failure mode is structurally impossible here.
"""

from core.strategy.base import Signal, SignalSide, Strategy, StrategyParams
from core.strategy.registry import get_strategy, list_strategies, register_strategy

__all__ = [
    "Signal",
    "SignalSide",
    "Strategy",
    "StrategyParams",
    "get_strategy",
    "list_strategies",
    "register_strategy",
]
