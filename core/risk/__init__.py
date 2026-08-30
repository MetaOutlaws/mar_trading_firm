"""Deterministic risk engine. Contains no LLM calls, by design and by test.

This is the final authority on whether an order may be placed. Agents can ask
this layer to be *more* conservative; nothing can make it less so.
"""

from core.risk.limits import RiskLimits
from core.risk.engine import RiskDecision, RiskEngine, TradeIntent
from core.risk.killswitch import KillSwitch

__all__ = ["RiskLimits", "RiskEngine", "RiskDecision", "TradeIntent", "KillSwitch"]
