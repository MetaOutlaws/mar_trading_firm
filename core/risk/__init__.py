"""Deterministic risk engine. Contains no LLM calls, by design and by test.

This is the final authority on whether an order may be placed. Agents can ask
this layer to be *more* conservative; nothing can make it less so.

``limits`` and ``sizing`` import on their own. The engine and kill switch load
on first use so a standard-library caller does not pull application settings.
"""

from __future__ import annotations

from typing import Any

__all__ = ["RiskLimits", "RiskEngine", "RiskDecision", "TradeIntent", "KillSwitch"]


def __getattr__(name: str) -> Any:
    if name == "RiskLimits":
        from core.risk.limits import RiskLimits

        return RiskLimits
    if name in {"RiskDecision", "RiskEngine", "TradeIntent"}:
        from core.risk.engine import RiskDecision, RiskEngine, TradeIntent

        return {
            "RiskDecision": RiskDecision,
            "RiskEngine": RiskEngine,
            "TradeIntent": TradeIntent,
        }[name]
    if name == "KillSwitch":
        from core.risk.killswitch import KillSwitch

        return KillSwitch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
