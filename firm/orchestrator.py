"""
Desk schedule: who runs when, and how their opinions reach the trading engine.

The orchestrator is a calendar, not a brain. It does not decide trades. It
wakes employees on their cadence, collects their proposals, and translates
those that the trust ladder currently permits into *advisory context* on the
next trading cycle -- vetoes and size reductions only.

Human escalation is a first-class output: anything an employee marks as needing
a person becomes a row the dashboard inbox can act on. The orchestrator never
auto-approves a promotion or a live-mode change.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from firm import memory, trust
from firm.employees.desk_head import DeskHead
from firm.employees.ops_engineer import OpsEngineer
from firm.employees.performance_auditor import PerformanceAuditor
from firm.employees.portfolio_manager import PortfolioManager
from firm.employees.quant_researcher import QuantResearcher
from firm.employees.regime_analyst import RegimeAnalyst
from firm.employees.risk_officer import RiskOfficer
from firm.employees.sentiment_analyst import SentimentAnalyst
from firm.llm import LlmRouter
from firm.memory_models import ProposalKind
from firm.runtime import Agent, AgentResult, Cadence
from firm.trust import TrustLevel

logger = logging.getLogger(__name__)


#: How often each cadence is allowed to fire. PER_CYCLE is the trading engine's
#: own interval; the orchestrator treats it as "every time we are asked".
CADENCE_INTERVALS: dict[Cadence, timedelta] = {
    Cadence.PER_CYCLE: timedelta(0),
    Cadence.HOURLY: timedelta(hours=1),
    Cadence.FOUR_HOURLY: timedelta(hours=4),
    Cadence.DAILY: timedelta(hours=24),
    Cadence.WEEKLY: timedelta(days=7),
    Cadence.ON_DEMAND: timedelta(days=365 * 100),  # never auto-scheduled
}


@dataclass
class CycleAdvice:
    """What employees currently want the trading engine to do.

    The engine treats this as *requests*. The risk layer still has the last
    word, and every multiplier here is already clamped to <= 1.0.
    """

    vetoes: dict[str, str] = field(default_factory=dict)
    size_multipliers: dict[str, float] = field(default_factory=dict)
    contributing_agents: list[str] = field(default_factory=list)
    sit_out: bool = False
    notes: list[str] = field(default_factory=list)

    def apply_to(self, engine: Any) -> None:
        """Write this advice onto a TradingEngine for the next cycle."""
        engine.agent_vetoes = dict(self.vetoes)
        engine.agent_size_multipliers = dict(self.size_multipliers)
        engine.active_agent_context = list(self.contributing_agents)


class Orchestrator:
    """Owns the employee roster and the daily schedule."""

    def __init__(self, router: LlmRouter | None = None) -> None:
        self.router = router or LlmRouter()
        self._owns_router = router is None
        self.employees: list[Agent] = [
            RegimeAnalyst(self.router),
            RiskOfficer(self.router),
            OpsEngineer(self.router),
            SentimentAnalyst(self.router),
            DeskHead(self.router),
            PerformanceAuditor(self.router),
            PortfolioManager(self.router),
            QuantResearcher(self.router),
        ]
        self._last_run: dict[str, datetime] = {}

    def close(self) -> None:
        for employee in self.employees:
            employee.close()
        if self._owns_router:
            self.router.close()

    def employee(self, name: str) -> Agent:
        for employee in self.employees:
            if employee.name == name:
                return employee
        raise KeyError(name)

    def due(self, now: datetime | None = None) -> list[Agent]:
        """Employees whose cadence interval has elapsed."""
        now = now or datetime.now(timezone.utc)
        due: list[Agent] = []
        for employee in self.employees:
            interval = CADENCE_INTERVALS[employee.cadence]
            last = self._last_run.get(employee.name)
            if last is None or now - last >= interval:
                due.append(employee)
        return due

    def run_due(self, now: datetime | None = None) -> list[AgentResult]:
        """Run every employee that is due. Failures stay isolated."""
        now = now or datetime.now(timezone.utc)
        memory.expire_stale_proposals()
        results: list[AgentResult] = []
        for employee in self.due(now):
            logger.info("Running %s (%s)", employee.name, employee.cadence.value)
            result = employee.run()
            results.append(result)
            self._last_run[employee.name] = now
        return results

    def run_named(self, names: Iterable[str]) -> list[AgentResult]:
        """Force-run specific employees, ignoring cadence. Used by the API."""
        results = []
        for name in names:
            employee = self.employee(name)
            results.append(employee.run())
            self._last_run[name] = datetime.now(timezone.utc)
        return results

    def advice_for_engine(self) -> CycleAdvice:
        """Translate currently-valid proposals into engine context.

        Only veto / resize / sit-out proposals whose author's trust level
        actually permits the action are applied. Everything else stays in the
        inbox for the human.
        """
        advice = CycleAdvice()
        pending = memory.pending_proposals(limit=100)

        for proposal in pending:
            record = trust.get(proposal["agent"])
            if record is None:
                continue
            kind = proposal["kind"]
            payload = proposal.get("payload") or {}
            symbol = proposal.get("symbol") or payload.get("symbol") or ""
            action = payload.get("action")

            if kind == ProposalKind.RISK.value and action == "veto" and record.may_veto and symbol:
                advice.vetoes[symbol] = proposal["agent"]
                advice.contributing_agents.append(proposal["agent"])
                advice.notes.append(f"{proposal['agent']} vetoes {symbol}")

            elif action == "resize" and record.may_resize and symbol:
                requested = float(payload.get("clamped", payload.get("requested", 1.0)))
                multiplier = trust.clamp_size_multiplier(proposal["agent"], requested)
                if multiplier < 1.0:
                    current = advice.size_multipliers.get(symbol, 1.0)
                    advice.size_multipliers[symbol] = min(current, multiplier)
                    advice.contributing_agents.append(proposal["agent"])

            elif action == "sit_out" and record.level >= TrustLevel.VETO:
                if not symbol:
                    advice.sit_out = True
                    advice.notes.append(f"{proposal['agent']}: sit out")
                elif record.may_veto:
                    advice.vetoes[symbol] = proposal["agent"]

        advice.contributing_agents = sorted(set(advice.contributing_agents))
        return advice

    def floor_snapshot(self) -> dict[str, Any]:
        """Everything the Employee Floor dashboard needs in one payload."""
        advice = self.advice_for_engine()
        return {
            "employees": [e.status_card() for e in self.employees],
            "activity": memory.recent_runs(limit=40),
            "inbox": memory.pending_proposals(limit=40),
            "escalations": memory.open_escalations(limit=20),
            "regime": memory.latest_regime(),
            "sentiment": memory.latest_sentiment(limit=20),
            "research": memory.research_board(limit=20),
            "budget": self.router.budget.snapshot(),
            "advice": {
                "vetoes": advice.vetoes,
                "size_multipliers": advice.size_multipliers,
                "sit_out": advice.sit_out,
                "notes": advice.notes,
            },
        }
