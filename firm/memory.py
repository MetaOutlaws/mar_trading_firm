"""
Firm memory: the read/write API over the agent-audit tables.

Everything an employee does passes through here, which is what turns "the AI
said something" into an auditable record with a cost, a confidence, a prompt
version, and eventually a measured outcome. Two consequences matter:

* The trust ladder can be evaluated from data rather than impressions, because
  `Proposal.outcome_correct` and `outcome_pnl` are filled in after the fact.
* The dashboard needs no separate bookkeeping. "What are my employees doing" is
  a query against `agent_runs`, not a special code path.

Sessions are short-lived and scoped per call, and callers receive plain dicts
rather than ORM objects, so nothing can accidentally trigger a lazy load against
a closed session.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from core.db import session_scope
from firm.memory_models import (
    AgentRun,
    AgentTrust,
    EscalationRecord,
    Proposal,
    ProposalKind,
    ProposalStatus,
    RegimeSnapshot,
    ResearchReport,
    RunStatus,
    SentimentScore,
)

logger = logging.getLogger(__name__)

#: Trade proposals are only meaningful for a short window; a stale one must
#: never execute. Research proposals get a much longer life (set explicitly).
DEFAULT_PROPOSAL_TTL = timedelta(hours=4)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _summarise(payload: Any, limit: int = 2_000) -> str:
    """Compact a payload for the `input_summary` column.

    Full inputs would bloat the database quickly (candle frames, watchlists,
    sentiment batches). A truncated JSON rendering is enough to answer "what was
    this agent looking at?" during a post-mortem.
    """
    try:
        text = json.dumps(payload, default=str, sort_keys=True)
    except (TypeError, ValueError):
        text = str(payload)
    return text if len(text) <= limit else text[: limit - 3] + "..."


# ---------------------------------------------------------------------------
# Agent runs
# ---------------------------------------------------------------------------
def start_run(
    agent: str,
    role: str,
    task: str,
    inputs: Any = None,
    prompt_version: str = "v1",
) -> int:
    """Open an `agent_runs` row and return its id.

    Written *before* the LLM call so a crashed or hung run leaves evidence
    behind. A run stuck in `running` is itself a signal the Ops Engineer looks
    for.
    """
    with session_scope() as session:
        run = AgentRun(
            agent=agent,
            role=role,
            task=task,
            input_summary=_summarise(inputs) if inputs is not None else "",
            prompt_version=prompt_version,
            status=RunStatus.RUNNING.value,
        )
        session.add(run)
        session.flush()
        return int(run.id)


def finish_run(
    run_id: int,
    status: RunStatus,
    output: dict[str, Any] | None = None,
    reasoning: str = "",
    confidence: float = 0.0,
    model: str = "",
    cost_usd: float = 0.0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: int = 0,
    error: str = "",
) -> None:
    """Close out an agent run with its result and cost."""
    with session_scope() as session:
        run = session.get(AgentRun, run_id)
        if run is None:
            logger.warning("finish_run: no run %d", run_id)
            return

        run.status = status.value
        run.finished_at = utcnow()
        run.output = output or {}
        run.reasoning = reasoning
        run.confidence = confidence
        run.model = model
        run.cost_usd = cost_usd
        run.tokens_in = tokens_in
        run.tokens_out = tokens_out
        run.latency_ms = latency_ms
        run.error = error


def recent_runs(agent: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Latest runs, newest first. Powers the dashboard activity feed."""
    with session_scope() as session:
        query = select(AgentRun)
        if agent:
            query = query.where(AgentRun.agent == agent)
        query = query.order_by(AgentRun.started_at.desc()).limit(limit)

        return [
            {
                "id": run.id,
                "agent": run.agent,
                "role": run.role,
                "task": run.task,
                "status": run.status,
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "confidence": round(run.confidence, 3),
                "reasoning": run.reasoning,
                "output": run.output,
                "model": run.model,
                "cost_usd": round(run.cost_usd, 5),
                "latency_ms": run.latency_ms,
                "error": run.error,
            }
            for run in session.scalars(query)
        ]


def agent_activity(agent: str) -> dict[str, Any]:
    """Current status and lifetime totals for one employee."""
    with session_scope() as session:
        latest = session.scalars(
            select(AgentRun)
            .where(AgentRun.agent == agent)
            .order_by(AgentRun.started_at.desc())
            .limit(1)
        ).first()

        totals = session.execute(
            select(
                func.count(AgentRun.id),
                func.coalesce(func.sum(AgentRun.cost_usd), 0.0),
                func.coalesce(func.avg(AgentRun.latency_ms), 0.0),
            ).where(AgentRun.agent == agent)
        ).one()

        return {
            "agent": agent,
            "status": latest.status if latest else "never_run",
            "current_task": latest.task if latest else "",
            "last_run_at": latest.started_at.isoformat() if latest else None,
            "last_reasoning": latest.reasoning if latest else "",
            "last_output": latest.output if latest else {},
            "runs_total": int(totals[0]),
            "cost_usd_total": round(float(totals[1]), 4),
            "avg_latency_ms": int(totals[2]),
        }


def spend_today(agent: str | None = None) -> float:
    """LLM spend since midnight UTC, for the dashboard's per-employee card."""
    midnight = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    with session_scope() as session:
        query = select(func.coalesce(func.sum(AgentRun.cost_usd), 0.0)).where(
            AgentRun.started_at >= midnight
        )
        if agent:
            query = query.where(AgentRun.agent == agent)
        return float(session.scalar(query) or 0.0)


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------
def record_proposal(
    agent: str,
    kind: ProposalKind,
    title: str,
    payload: dict[str, Any],
    rationale: str,
    confidence: float,
    run_id: int | None = None,
    symbol: str = "",
    ttl: timedelta | None = DEFAULT_PROPOSAL_TTL,
) -> int:
    """Log a proposal and return its id.

    A proposal is an opinion made durable. At L1 that is all it is: recording it
    does not authorise anything.
    """
    with session_scope() as session:
        proposal = Proposal(
            run_id=run_id,
            agent=agent,
            kind=kind.value,
            symbol=symbol,
            title=title[:200],
            payload=payload,
            rationale=rationale,
            confidence=confidence,
            expires_at=utcnow() + ttl if ttl else None,
        )
        session.add(proposal)
        session.flush()
        return int(proposal.id)


def decide_proposal(
    proposal_id: int,
    approved: bool,
    decided_by: str,
    reason: str = "",
) -> bool:
    """Approve or reject a pending proposal.

    Returns False when the proposal is already decided or has expired, so a
    stale click in the dashboard cannot resurrect an old trade idea.
    """
    with session_scope() as session:
        proposal = session.get(Proposal, proposal_id)
        if proposal is None:
            return False

        if proposal.status != ProposalStatus.PENDING.value:
            logger.info("Proposal %d already %s.", proposal_id, proposal.status)
            return False

        if proposal.expires_at and proposal.expires_at < utcnow():
            proposal.status = ProposalStatus.EXPIRED.value
            proposal.decided_by = "expiry"
            proposal.decided_at = utcnow()
            logger.info("Proposal %d expired before it was decided.", proposal_id)
            return False

        proposal.status = (
            ProposalStatus.APPROVED.value if approved else ProposalStatus.REJECTED.value
        )
        proposal.decided_by = decided_by
        proposal.decided_at = utcnow()
        proposal.decision_reason = reason
        return True


def expire_stale_proposals() -> int:
    """Mark past-due pending proposals expired. Returns how many."""
    with session_scope() as session:
        stale = session.scalars(
            select(Proposal).where(
                Proposal.status == ProposalStatus.PENDING.value,
                Proposal.expires_at.is_not(None),
                Proposal.expires_at < utcnow(),
            )
        ).all()
        for proposal in stale:
            proposal.status = ProposalStatus.EXPIRED.value
            proposal.decided_by = "expiry"
            proposal.decided_at = utcnow()
        return len(stale)


def pending_proposals(limit: int = 50) -> list[dict[str, Any]]:
    """Proposals awaiting a human decision. Powers the decision inbox."""
    with session_scope() as session:
        rows = session.scalars(
            select(Proposal)
            .where(Proposal.status == ProposalStatus.PENDING.value)
            .order_by(Proposal.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": p.id,
                "agent": p.agent,
                "kind": p.kind,
                "symbol": p.symbol,
                "title": p.title,
                "payload": p.payload,
                "rationale": p.rationale,
                "confidence": round(p.confidence, 3),
                "created_at": p.created_at.isoformat(),
                "expires_at": p.expires_at.isoformat() if p.expires_at else None,
            }
            for p in rows
        ]


def score_proposal(proposal_id: int, pnl: float, correct: bool) -> None:
    """Attach a measured outcome to a proposal.

    This is the only input to trust promotion that an eloquent agent cannot
    influence: it is what actually happened afterwards.
    """
    with session_scope() as session:
        proposal = session.get(Proposal, proposal_id)
        if proposal is None:
            return
        proposal.outcome_pnl = pnl
        proposal.outcome_correct = correct

        trust = session.get(AgentTrust, proposal.agent)
        if trust is None:
            trust = AgentTrust(agent=proposal.agent)
            session.add(trust)
        trust.decisions_scored += 1
        trust.decisions_correct += 1 if correct else 0
        trust.pnl_attribution += pnl
        trust.updated_at = utcnow()


def scored_proposals(agent: str, limit: int = 200) -> list[dict[str, Any]]:
    """Proposals with known outcomes, for the Performance Auditor."""
    with session_scope() as session:
        rows = session.scalars(
            select(Proposal)
            .where(Proposal.agent == agent, Proposal.outcome_correct.is_not(None))
            .order_by(Proposal.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": p.id,
                "kind": p.kind,
                "symbol": p.symbol,
                "title": p.title,
                "confidence": p.confidence,
                "outcome_pnl": p.outcome_pnl,
                "outcome_correct": p.outcome_correct,
                "created_at": p.created_at.isoformat(),
            }
            for p in rows
        ]


# ---------------------------------------------------------------------------
# Escalations
# ---------------------------------------------------------------------------
def escalate(agent: str, title: str, detail: str, severity: str = "warning") -> int:
    """Raise something for the human operator. Returns the record id."""
    with session_scope() as session:
        record = EscalationRecord(
            agent=agent, title=title[:200], detail=detail, severity=severity
        )
        session.add(record)
        session.flush()
        logger.warning("ESCALATION [%s] %s: %s", severity, agent, title)
        return int(record.id)


def open_escalations(limit: int = 50) -> list[dict[str, Any]]:
    """Unacknowledged escalations, newest first."""
    with session_scope() as session:
        rows = session.scalars(
            select(EscalationRecord)
            .where(EscalationRecord.acknowledged.is_(False))
            .order_by(EscalationRecord.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": r.id,
                "agent": r.agent,
                "severity": r.severity,
                "title": r.title,
                "detail": r.detail,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


def acknowledge_escalation(escalation_id: int) -> bool:
    with session_scope() as session:
        record = session.get(EscalationRecord, escalation_id)
        if record is None or record.acknowledged:
            return False
        record.acknowledged = True
        record.acknowledged_at = utcnow()
        return True


# ---------------------------------------------------------------------------
# Domain records written by specific employees
# ---------------------------------------------------------------------------
def record_regime(
    regime: str,
    volatility_bucket: str,
    btc_trend: str,
    permitted_strategies: list[str],
    reasoning: str,
    confidence: float,
    metrics: dict[str, Any] | None = None,
    btc_dominance: float | None = None,
) -> int:
    with session_scope() as session:
        snapshot = RegimeSnapshot(
            regime=regime,
            volatility_bucket=volatility_bucket,
            btc_trend=btc_trend,
            btc_dominance=btc_dominance,
            permitted_strategies=permitted_strategies,
            reasoning=reasoning,
            confidence=confidence,
            metrics=metrics or {},
        )
        session.add(snapshot)
        session.flush()
        return int(snapshot.id)


def latest_regime() -> dict[str, Any] | None:
    with session_scope() as session:
        snapshot = session.scalars(
            select(RegimeSnapshot).order_by(RegimeSnapshot.recorded_at.desc()).limit(1)
        ).first()
        if snapshot is None:
            return None
        return {
            "recorded_at": snapshot.recorded_at.isoformat(),
            "regime": snapshot.regime,
            "volatility_bucket": snapshot.volatility_bucket,
            "btc_trend": snapshot.btc_trend,
            "permitted_strategies": snapshot.permitted_strategies,
            "reasoning": snapshot.reasoning,
            "confidence": snapshot.confidence,
            "metrics": snapshot.metrics,
        }


def record_sentiment(
    symbol: str,
    score: float,
    narrative: str,
    hype_stage: str,
    confidence: float,
    sources: list[str],
    model: str,
    price_at_reading: float,
) -> int:
    """Store one sentiment reading together with the price at the time.

    The price matters: without it forward returns cannot be computed later, and
    an unvalidatable sentiment signal can never earn authority.
    """
    with session_scope() as session:
        record = SentimentScore(
            symbol=symbol,
            score=score,
            narrative=narrative,
            hype_stage=hype_stage,
            confidence=confidence,
            sources=sources,
            model=model,
            price_at_reading=price_at_reading,
        )
        session.add(record)
        session.flush()
        return int(record.id)


def latest_sentiment(limit: int = 100) -> list[dict[str, Any]]:
    """Most recent reading per symbol, newest first. Powers the heatmap."""
    with session_scope() as session:
        rows = session.scalars(
            select(SentimentScore)
            .order_by(SentimentScore.recorded_at.desc())
            .limit(limit * 3)
        )
        seen: dict[str, dict[str, Any]] = {}
        for row in rows:
            if row.symbol in seen:
                continue
            seen[row.symbol] = {
                "symbol": row.symbol,
                "score": round(row.score, 3),
                "narrative": row.narrative,
                "hype_stage": row.hype_stage,
                "confidence": round(row.confidence, 3),
                "sources": row.sources,
                "recorded_at": row.recorded_at.isoformat(),
                "price_at_reading": row.price_at_reading,
                "forward_return_4h": row.forward_return_4h,
                "forward_return_24h": row.forward_return_24h,
            }
            if len(seen) >= limit:
                break
        return list(seen.values())


def unscored_sentiment(older_than: timedelta) -> list[dict[str, Any]]:
    """Readings old enough to have a measurable forward return."""
    cutoff = utcnow() - older_than
    with session_scope() as session:
        rows = session.scalars(
            select(SentimentScore).where(
                SentimentScore.recorded_at <= cutoff,
                SentimentScore.forward_return_24h.is_(None),
                SentimentScore.price_at_reading > 0,
            )
        )
        return [
            {
                "id": r.id,
                "symbol": r.symbol,
                "recorded_at": r.recorded_at,
                "price_at_reading": r.price_at_reading,
                "score": r.score,
                "forward_return_4h": r.forward_return_4h,
            }
            for r in rows
        ]


def set_sentiment_forward_returns(
    sentiment_id: int, return_4h: float | None, return_24h: float | None
) -> None:
    with session_scope() as session:
        record = session.get(SentimentScore, sentiment_id)
        if record is None:
            return
        if return_4h is not None:
            record.forward_return_4h = return_4h
        if return_24h is not None:
            record.forward_return_24h = return_24h


def record_research(
    hypothesis: str,
    symbols: list[str],
    agent: str = "quant_researcher",
    status: str = "proposed",
) -> int:
    with session_scope() as session:
        report = ResearchReport(
            agent=agent, hypothesis=hypothesis, symbols=symbols, status=status
        )
        session.add(report)
        session.flush()
        return int(report.id)


def complete_research(
    report_id: int, status: str, verdict: str, metrics: dict[str, Any]
) -> None:
    with session_scope() as session:
        report = session.get(ResearchReport, report_id)
        if report is None:
            return
        report.status = status
        report.verdict = verdict
        report.metrics = metrics
        report.tested_at = utcnow()


def research_board(limit: int = 50) -> list[dict[str, Any]]:
    """Every hypothesis and its fate. The firm's institutional memory."""
    with session_scope() as session:
        rows = session.scalars(
            select(ResearchReport).order_by(ResearchReport.created_at.desc()).limit(limit)
        )
        return [
            {
                "id": r.id,
                "agent": r.agent,
                "hypothesis": r.hypothesis,
                "status": r.status,
                "verdict": r.verdict,
                "metrics": r.metrics,
                "symbols": r.symbols,
                "created_at": r.created_at.isoformat(),
                "tested_at": r.tested_at.isoformat() if r.tested_at else None,
            }
            for r in rows
        ]


def already_tested(keywords: list[str]) -> list[dict[str, Any]]:
    """Prior reports matching any keyword.

    Fed back to the Quant Researcher so it stops re-proposing ideas the firm has
    already rejected -- the most common failure mode of an LLM research loop
    with no memory.
    """
    with session_scope() as session:
        rows = session.scalars(
            select(ResearchReport).order_by(ResearchReport.created_at.desc())
        )
        matches = []
        for row in rows:
            text = f"{row.hypothesis} {row.verdict}".lower()
            if any(keyword.lower() in text for keyword in keywords):
                matches.append(
                    {
                        "hypothesis": row.hypothesis,
                        "status": row.status,
                        "verdict": row.verdict,
                    }
                )
        return matches
