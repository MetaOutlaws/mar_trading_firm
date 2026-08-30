"""
Firm memory: the tables that record what every employee did and why.

This schema is what makes the "what are my employees doing" dashboard possible,
and more importantly what makes the trust ladder honest. An agent cannot be
promoted on vibes: promotion requires a minimum number of logged decisions with
a measured hit rate and attributed P&L, and those numbers come from here.

Every agent run stores its inputs, its prompt version, its structured output,
its confidence, its cost and its latency. Prompt version matters because a
prompt change invalidates the track record accumulated under the old one --
without it, a rewritten prompt would silently inherit its predecessor's trust.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base, UtcDateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # budget exhausted, or gated off
    BLOCKED = "blocked"  # waiting on a human decision


class ProposalKind(str, Enum):
    TRADE = "trade"
    STRATEGY = "strategy"  # a research hypothesis or parameter change
    ALLOCATION = "allocation"
    RISK = "risk"  # tighten a limit, halt trading
    OPERATIONAL = "operational"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"


class TrustLevel(int, Enum):
    """Authority ladder. Every employee starts at ADVISOR."""

    OBSERVER = 0  # opinions logged only
    ADVISOR = 1  # opinions surfaced in the dashboard
    VETO = 2  # may block a trade
    SIZING = 3  # may reduce size within a fixed band
    AUTONOMOUS = 4  # may open trades within hard limits

    @property
    def label(self) -> str:
        return {
            TrustLevel.OBSERVER: "L0 Observer",
            TrustLevel.ADVISOR: "L1 Advisor",
            TrustLevel.VETO: "L2 Veto",
            TrustLevel.SIZING: "L3 Sizing",
            TrustLevel.AUTONOMOUS: "L4 Autonomous",
        }[self]


class AgentRun(Base):
    """One execution of one employee.

    The audit unit of the whole firm. If an agent influenced a decision, there
    is a row here explaining what it saw, what it said, and what it cost.
    """

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    agent: Mapped[str] = mapped_column(String(48), index=True)
    role: Mapped[str] = mapped_column(String(64), default="")

    started_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=RunStatus.RUNNING.value, index=True)

    task: Mapped[str] = mapped_column(String(160), default="")
    #: Compact description of inputs. Full payloads would bloat the DB; this is
    #: enough to understand what the agent was looking at.
    input_summary: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    model: Mapped[str] = mapped_column(String(64), default="")
    #: Track record accumulated under one prompt version does not transfer to
    #: another, so this is recorded on every run.
    prompt_version: Mapped[str] = mapped_column(String(24), default="v1")

    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    error: Mapped[str] = mapped_column(Text, default="")

    proposals: Mapped[list["Proposal"]] = relationship(back_populates="run")

    __table_args__ = (Index("ix_agent_runs_agent_started", "agent", "started_at"),)


class Proposal(Base):
    """Something an employee wants to do, awaiting authority or approval.

    Proposals are the mechanism by which a low-trust agent's opinion becomes
    visible without becoming an action. At L1 a proposal is surfaced and logged;
    only higher trust levels, or explicit human approval, let it execute.
    """

    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id"), nullable=True, index=True
    )

    agent: Mapped[str] = mapped_column(String(48), index=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )

    kind: Mapped[str] = mapped_column(String(24), index=True)
    symbol: Mapped[str] = mapped_column(String(32), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    rationale: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[str] = mapped_column(
        String(16), default=ProposalStatus.PENDING.value, index=True
    )
    #: "human", "auto:<trust level>", or "expiry".
    decided_by: Mapped[str] = mapped_column(String(48), default="")
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    decision_reason: Mapped[str] = mapped_column(Text, default="")

    #: Trade proposals go stale fast; an expired proposal must never execute.
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    #: Set once the outcome is known, for scoring the agent's track record.
    outcome_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    run: Mapped["AgentRun | None"] = relationship(back_populates="proposals")


class AgentTrust(Base):
    """An employee's authority level and the track record justifying it."""

    __tablename__ = "agent_trust"

    agent: Mapped[str] = mapped_column(String(48), primary_key=True)
    role: Mapped[str] = mapped_column(String(64), default="")

    level: Mapped[int] = mapped_column(Integer, default=TrustLevel.ADVISOR.value)

    decisions_logged: Mapped[int] = mapped_column(Integer, default=0)
    decisions_scored: Mapped[int] = mapped_column(Integer, default=0)
    decisions_correct: Mapped[int] = mapped_column(Integer, default=0)
    pnl_attribution: Mapped[float] = mapped_column(Float, default=0.0)

    #: Reset whenever the prompt changes, since the record no longer applies.
    prompt_version: Mapped[str] = mapped_column(String(24), default="v1")

    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow)
    promoted_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    @property
    def hit_rate(self) -> float:
        """Share of scored decisions that turned out correct."""
        if not self.decisions_scored:
            return 0.0
        return self.decisions_correct / self.decisions_scored * 100.0


class LlmSpend(Base):
    """Per-call LLM cost, for budget enforcement and the dashboard."""

    __tablename__ = "llm_spend"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
    agent: Mapped[str] = mapped_column(String(48), index=True)
    model: Mapped[str] = mapped_column(String(64))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    #: "YYYY-MM", denormalised so the monthly budget query stays trivial.
    billing_month: Mapped[str] = mapped_column(String(8), index=True, default="")


class SentimentScore(Base):
    """A Grok/X sentiment reading for one symbol.

    Stored with a forward-return column so the Sentiment Analyst's signal can be
    validated against what actually happened before it is granted any authority.
    """

    __tablename__ = "sentiment_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)

    #: -1 (maximally bearish) to +1 (maximally bullish).
    score: Mapped[float] = mapped_column(Float, default=0.0)
    narrative: Mapped[str] = mapped_column(Text, default="")
    #: "building", "peaking", "exhausted", "fading", "absent".
    hype_stage: Mapped[str] = mapped_column(String(24), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    #: Post URLs and handles backing the reading, so claims are checkable.
    sources: Mapped[list] = mapped_column(JSON, default=list)

    model: Mapped[str] = mapped_column(String(64), default="")
    price_at_reading: Mapped[float] = mapped_column(Float, default=0.0)

    #: Filled in later by the validation job.
    forward_return_4h: Mapped[float | None] = mapped_column(Float, nullable=True)
    forward_return_24h: Mapped[float | None] = mapped_column(Float, nullable=True)


class RegimeSnapshot(Base):
    """The Regime Analyst's classification of current market conditions."""

    __tablename__ = "regime_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )

    regime: Mapped[str] = mapped_column(String(24), default="")  # bull/bear/chop
    volatility_bucket: Mapped[str] = mapped_column(String(16), default="")  # low/normal/high
    btc_trend: Mapped[str] = mapped_column(String(24), default="")
    btc_dominance: Mapped[float | None] = mapped_column(Float, nullable=True)

    #: Strategies the analyst considers appropriate for this regime.
    permitted_strategies: Mapped[list] = mapped_column(JSON, default=list)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class ResearchReport(Base):
    """A Quant Researcher hypothesis and its validation outcome.

    This table is the firm's institutional memory for research. Without it, the
    same failed idea gets re-proposed every few weeks.
    """

    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
    agent: Mapped[str] = mapped_column(String(48), default="quant_researcher")

    hypothesis: Mapped[str] = mapped_column(Text)
    #: "proposed", "testing", "validated", "rejected".
    status: Mapped[str] = mapped_column(String(16), default="proposed", index=True)
    verdict: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    symbols: Mapped[list] = mapped_column(JSON, default=list)
    tested_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)


class EscalationRecord(Base):
    """Something requiring the human operator's attention."""

    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
    agent: Mapped[str] = mapped_column(String(48), default="")
    severity: Mapped[str] = mapped_column(String(16), default="info", index=True)
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str] = mapped_column(Text, default="")
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime, nullable=True
    )
