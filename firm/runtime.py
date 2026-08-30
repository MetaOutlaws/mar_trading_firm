"""
The agent runtime: what it means to be an employee of this firm.

An `Agent` is a small, boring template. It gathers inputs, produces a validated
structured output, and records everything it did. The boring part is deliberate:
the interesting behaviour belongs in the prompts and in the deterministic core,
not in the framework.

Four rules are enforced here rather than left to each employee:

* **Structured output or nothing.** Every agent declares a Pydantic output model.
  Unparseable output is a failed run, not a partially-trusted one.
* **Every run is recorded.** The `agent_runs` row is written before the call and
  closed after it, including on exceptions, so a crash leaves evidence.
* **Cost is metered.** The router charges spend against the monthly ceiling; a
  budget-exhausted run is `SKIPPED`, not an error, because it is expected
  behaviour late in an expensive month.
* **Output influences, it does not act.** An agent's result becomes proposals and
  advisory context. Only `core.risk` and `core.execution` move money, and they
  clamp anything an agent asks for.

`DeterministicAgent` exists for the two roles that must never involve an LLM
(Risk Manager, Execution Trader). They still get run records and appear on the
dashboard alongside everyone else -- the operator should see the whole floor, not
just the talkative half.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from firm import memory, trust
from firm.llm import BudgetExhausted, LlmError, LlmResult, LlmRouter, ModelTier
from firm.memory_models import ProposalKind, RunStatus

logger = logging.getLogger(__name__)


class Cadence(str, Enum):
    """How often an employee is scheduled.

    Cadence drives cost more than anything else, which is why model tier is
    assigned alongside it rather than independently.
    """

    ON_DEMAND = "on_demand"
    PER_CYCLE = "per_cycle"  # every trading cycle (15 min)
    HOURLY = "hourly"
    FOUR_HOURLY = "four_hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class AgentOutput(BaseModel):
    """Base structured output. Every employee's output model extends this.

    `confidence` is mandatory and bounded because an opinion without a stated
    confidence cannot be weighted, and an unbounded one cannot be compared
    between employees.
    """

    reasoning: str = Field(description="Concise explanation of the conclusion.")
    confidence: float = Field(ge=0.0, le=1.0, description="0 = guess, 1 = certain.")


@dataclass
class AgentResult:
    """What one agent run produced."""

    agent: str
    status: RunStatus
    run_id: int | None = None
    output: AgentOutput | None = None
    proposal_ids: list[int] = field(default_factory=list)
    model: str = ""
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status is RunStatus.SUCCESS and self.output is not None

    def summary(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "status": self.status.value,
            "run_id": self.run_id,
            "confidence": round(self.output.confidence, 3) if self.output else None,
            "reasoning": self.output.reasoning if self.output else "",
            "proposals": self.proposal_ids,
            "model": self.model,
            "cost_usd": round(self.cost_usd, 5),
            "latency_ms": self.latency_ms,
            "error": self.error,
        }

    def __str__(self) -> str:
        if self.status is RunStatus.SUCCESS and self.output:
            return (
                f"{self.agent}: {self.status.value} "
                f"(confidence {self.output.confidence:.2f}, ${self.cost_usd:.4f})"
            )
        return f"{self.agent}: {self.status.value} {self.error}".strip()


class Agent(ABC):
    """Base employee.

    Subclasses provide identity (`name`, `role`), an output model, a system
    prompt, and a task prompt built from gathered inputs. Everything else --
    auditing, cost metering, trust registration, error containment -- happens
    here so it cannot be forgotten in one employee and not another.
    """

    #: Stable identifier used for attribution, trust, and budget policy.
    name: str = "agent"
    role: str = "employee"
    cadence: Cadence = Cadence.ON_DEMAND
    tier: ModelTier = ModelTier.CHEAP
    #: Bump this whenever the prompt changes materially. It resets the agent's
    #: track record, which is the point: the old evidence no longer applies.
    prompt_version: str = "v1"
    output_model: type[AgentOutput] = AgentOutput
    #: Whether this employee needs live X/web search (only Grok tiers can).
    uses_search: bool = False
    max_tokens: int = 3_000
    temperature: float = 0.2

    def __init__(self, router: LlmRouter | None = None) -> None:
        self._router = router
        self._owns_router = router is None
        # Registering on construction means the dashboard shows an employee from
        # the moment it exists, with no track record rather than no row.
        try:
            trust.register(self.name, self.role, self.prompt_version)
        except Exception as exc:  # a trust-table hiccup must not block a run
            logger.warning("Could not register %s: %s", self.name, exc)

    # -----------------------------------------------------------------
    # Wiring
    # -----------------------------------------------------------------
    @property
    def router(self) -> LlmRouter:
        if self._router is None:
            self._router = LlmRouter()
        return self._router

    def close(self) -> None:
        if self._owns_router and self._router is not None:
            self._router.close()
            self._router = None

    @property
    def trust_level(self) -> trust.TrustLevel:
        record = trust.get(self.name)
        return record.level if record else trust.STARTING_LEVEL

    # -----------------------------------------------------------------
    # Subclass contract
    # -----------------------------------------------------------------
    @abstractmethod
    def system_prompt(self) -> str:
        """The employee's standing instructions."""

    @abstractmethod
    def task_prompt(self, inputs: dict[str, Any]) -> str:
        """The specific question, built from this run's inputs."""

    def gather(self) -> dict[str, Any]:
        """Collect the inputs this run needs. Override where data is required."""
        return {}

    def describe_task(self, inputs: dict[str, Any]) -> str:
        """Short label for the dashboard. Override for something more specific."""
        del inputs
        return f"{self.role} {self.cadence.value} run"

    def on_output(
        self, output: AgentOutput, inputs: dict[str, Any], run_id: int
    ) -> list[int]:
        """React to a validated output. Returns proposal ids created.

        Default behaviour is to record nothing beyond the run itself. Employees
        that want their opinion to reach the decision inbox override this and
        call `self.propose(...)`.
        """
        del output, inputs, run_id
        return []

    # -----------------------------------------------------------------
    # Helpers for subclasses
    # -----------------------------------------------------------------
    def propose(
        self,
        kind: ProposalKind,
        title: str,
        payload: dict[str, Any],
        rationale: str,
        confidence: float,
        run_id: int | None = None,
        symbol: str = "",
        ttl: Any = memory.DEFAULT_PROPOSAL_TTL,
    ) -> int:
        """Record a proposal attributed to this employee."""
        proposal_id = memory.record_proposal(
            agent=self.name,
            kind=kind,
            title=title,
            payload=payload,
            rationale=rationale,
            confidence=confidence,
            run_id=run_id,
            symbol=symbol,
            ttl=ttl,
        )
        trust.note_decision(self.name)
        return proposal_id

    def escalate(self, title: str, detail: str, severity: str = "warning") -> int:
        """Raise something for the human operator."""
        return memory.escalate(self.name, title, detail, severity)

    # -----------------------------------------------------------------
    # Execution
    # -----------------------------------------------------------------
    def execute(self, inputs: dict[str, Any]) -> tuple[AgentOutput, LlmResult | None]:
        """Produce this run's output. Default implementation calls the LLM."""
        result = self.router.complete(
            agent=self.name,
            system=self.system_prompt(),
            user=self.task_prompt(inputs),
            response_model=self.output_model,
            tier=self.tier,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            enable_search=self.uses_search,
        )
        output = result.parsed
        if output is None:  # _parse guarantees this, but be explicit
            raise LlmError(f"{self.name}: router returned no parsed output")
        return output, result  # type: ignore[return-value]

    def run(self) -> AgentResult:
        """Execute one full run, recording it whatever the outcome.

        Exceptions are caught and turned into a `FAILED` run rather than
        propagating: one broken employee must not stop the firm's schedule. The
        orchestrator decides what to do about repeated failures.
        """
        try:
            inputs = self.gather()
        except Exception as exc:
            logger.exception("%s: gathering inputs failed", self.name)
            run_id = memory.start_run(
                self.name, self.role, "gather inputs", prompt_version=self.prompt_version
            )
            memory.finish_run(run_id, RunStatus.FAILED, error=f"gather failed: {exc}")
            return AgentResult(
                agent=self.name, status=RunStatus.FAILED, run_id=run_id,
                error=f"gather failed: {exc}",
            )

        run_id = memory.start_run(
            agent=self.name,
            role=self.role,
            task=self.describe_task(inputs),
            inputs=inputs,
            prompt_version=self.prompt_version,
        )

        try:
            output, llm = self.execute(inputs)
        except BudgetExhausted as exc:
            # Expected, not exceptional: the ceiling did its job.
            logger.warning("%s skipped: %s", self.name, exc)
            memory.finish_run(run_id, RunStatus.SKIPPED, error=str(exc))
            return AgentResult(
                agent=self.name, status=RunStatus.SKIPPED, run_id=run_id, error=str(exc)
            )
        except Exception as exc:
            logger.exception("%s failed", self.name)
            memory.finish_run(run_id, RunStatus.FAILED, error=str(exc)[:1_000])
            return AgentResult(
                agent=self.name, status=RunStatus.FAILED, run_id=run_id, error=str(exc)
            )

        # Proposal creation is separated from output validation so that a bug in
        # one employee's reaction logic still leaves its analysis on record.
        proposal_ids: list[int] = []
        try:
            proposal_ids = self.on_output(output, inputs, run_id)
        except Exception as exc:
            logger.exception("%s: on_output failed", self.name)
            memory.escalate(
                self.name,
                f"{self.name} produced output but failed to act on it",
                str(exc),
                severity="warning",
            )

        memory.finish_run(
            run_id=run_id,
            status=RunStatus.SUCCESS,
            output=output.model_dump(),
            reasoning=output.reasoning,
            confidence=output.confidence,
            model=llm.model if llm else "deterministic",
            cost_usd=llm.cost_usd if llm else 0.0,
            tokens_in=llm.tokens_in if llm else 0,
            tokens_out=llm.tokens_out if llm else 0,
            latency_ms=llm.latency_ms if llm else 0,
        )

        result = AgentResult(
            agent=self.name,
            status=RunStatus.SUCCESS,
            run_id=run_id,
            output=output,
            proposal_ids=proposal_ids,
            model=llm.model if llm else "deterministic",
            cost_usd=llm.cost_usd if llm else 0.0,
            latency_ms=llm.latency_ms if llm else 0,
        )
        logger.info("%s", result)
        return result

    # -----------------------------------------------------------------
    # Dashboard
    # -----------------------------------------------------------------
    def status_card(self) -> dict[str, Any]:
        """Everything the Employee Floor needs about this employee."""
        record = trust.get(self.name)
        activity = memory.agent_activity(self.name)
        return {
            **activity,
            "role": self.role,
            "cadence": self.cadence.value,
            "tier": self.tier.value if self.tier else "deterministic",
            "prompt_version": self.prompt_version,
            "trust": record.summary() if record else None,
            "spend_today_usd": round(memory.spend_today(self.name), 5),
        }


class DeterministicAgent(Agent):
    """An employee implemented in pure code, with no LLM call.

    Used for the two roles where reproducibility outranks flexibility. They
    appear on the dashboard like any other employee, but their output is a
    function of their inputs and can be unit tested.
    """

    tier = None  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__(router=None)

    def system_prompt(self) -> str:  # never used
        return ""

    def task_prompt(self, inputs: dict[str, Any]) -> str:  # never used
        del inputs
        return ""

    @abstractmethod
    def decide(self, inputs: dict[str, Any]) -> AgentOutput:
        """Compute the output deterministically."""

    def execute(self, inputs: dict[str, Any]) -> tuple[AgentOutput, LlmResult | None]:
        return self.decide(inputs), None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


__all__ = [
    "Agent",
    "AgentOutput",
    "AgentResult",
    "Cadence",
    "DeterministicAgent",
]
