"""
Performance Auditor: post-trade review that feeds the research loop.

Daily, standard model. Looks at completed trades, scores outstanding proposals
against what actually happened, and writes findings the Quant Researcher reads
when the pipeline is next idle. This is the loop-closer: without it, the firm
never learns from its own book.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field
from sqlalchemy import select

from core.db import session_scope
from core.ledger.models import TradeRecord
from firm import memory
from firm.llm import ModelTier
from firm.memory_models import ProposalKind
from firm.runtime import Agent, AgentOutput, Cadence
from firm.trust import all_records, evaluate_promotion


class AuditFinding(AgentOutput):
    """A day's worth of post-trade review."""

    findings: list[str] = Field(description="Concrete observations, not platitudes.")
    research_questions: list[str] = Field(
        description="Hypotheses the Quant Researcher should test next."
    )
    promotion_recommendations: list[str] = Field(
        default_factory=list,
        description="Employee names whose evidence supports a promotion review.",
    )
    demotion_warnings: list[str] = Field(
        default_factory=list,
        description="Employees whose recent scored decisions look weak.",
    )


class PerformanceAuditor(Agent):
    name = "performance_auditor"
    role = "Performance Auditor"
    cadence = Cadence.DAILY
    tier = ModelTier.STANDARD
    prompt_version = "v3"
    output_model = AuditFinding
    max_tokens = 2_200
    mandate = (
        "Certifies walk-forward setup, paper sleeve, and that an approved "
        "coding mandate actually has a file in the registry. Reviews closed trades."
    )

    def system_prompt(self) -> str:
        return (
            "You are the Performance Auditor of a systematic crypto trading "
            "firm. You own test and trade integrity. The integrity pack is "
            "deterministic source of truth: quote failed checks by name. Do "
            "not declare a walk-forward valid if integrity.ok is false. "
            "OOS trade counts on Strategies are the test output, not proof "
            "the right test ran. Quote approved_sleeve_coded if an approved "
            "family is missing from the registry — that is a fail even when "
            "finished jobs look clean. Review closed trades for sleeve, slippage, "
            "and missing stops. Be specific. Do not recommend promoting "
            "anyone with fewer than 20 scored decisions. Never invent trades "
            "or test results that are not in the pack."
        )

    def gather(self) -> dict[str, Any]:
        from firm.integrity import integrity_snapshot
        from firm.postmortem import POSTMORTEM_DIR

        pack = integrity_snapshot()
        postmortems = []
        if POSTMORTEM_DIR.exists():
            for path in sorted(POSTMORTEM_DIR.glob("postmortem_job_*.json"))[-8:]:
                postmortems.append({"file": path.name})
        with session_scope() as session:
            trades = session.scalars(
                select(TradeRecord).order_by(TradeRecord.exit_time.desc()).limit(40)
            ).all()
            trade_rows = [
                {
                    "symbol": t.symbol,
                    "side": t.side,
                    "net_pnl": t.net_pnl,
                    "return_pct": t.return_pct,
                    "exit_reason": t.exit_reason,
                    "strategy": t.strategy,
                    "agents": t.contributing_agents,
                    "entry_slippage_bps": t.entry_slippage_bps,
                    "exit_slippage_bps": t.exit_slippage_bps,
                    "fees": t.fees,
                    "funding": t.funding,
                    "exit_time": t.exit_time.isoformat(),
                }
                for t in trades
            ]

        return {
            "integrity": pack,
            "postmortems": postmortems,
            "recent_trades": trade_rows,
            "trust": [r.summary() for r in all_records()],
            "promotion_eligibility": {
                record.agent: {
                    "eligible": eligible,
                    "proposed": proposed.label,
                    "blockers": blockers,
                }
                for record in all_records()
                for eligible, proposed, blockers in [
                    evaluate_promotion(record.agent, auditor_recommends=False)
                ]
            },
            "research_board": memory.research_board(limit=15),
        }

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return (
            "Certify the latest walk-forwards and paper clock from the integrity "
            "pack, then review recent trades. Lead with pass/fail of the "
            "certificate.\n"
            f"{inputs}"
        )

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        finding = AuditFinding.model_validate(output.model_dump())
        pack = inputs.get("integrity") if isinstance(inputs.get("integrity"), dict) else {}
        if pack and pack.get("ok") is False:
            fails = pack.get("failed_jobs") or []
            self.escalate(
                "Integrity pack failed",
                finding.reasoning + f" Failed jobs: {fails}",
                severity="warning",
            )
        ids: list[int] = []
        if finding.research_questions:
            ids.append(
                self.propose(
                    kind=ProposalKind.STRATEGY,
                    title="Audit findings for research",
                    payload={"questions": finding.research_questions, "findings": finding.findings},
                    rationale=finding.reasoning,
                    confidence=finding.confidence,
                    run_id=run_id,
                )
            )
        for name in finding.promotion_recommendations:
            ids.append(
                self.propose(
                    kind=ProposalKind.OPERATIONAL,
                    title=f"Review promotion for {name}",
                    payload={"agent": name, "auditor_recommends": True},
                    rationale=finding.reasoning,
                    confidence=finding.confidence,
                    run_id=run_id,
                )
            )
        return ids
