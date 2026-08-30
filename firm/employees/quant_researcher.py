"""
Quant Researcher: the edge factory.

Weekly, strongest model. Proposes a small number of testable hypotheses, then
the orchestrator runs them through the same walk-forward pipeline that rejected
the legacy RSI+golden-cross setup. The researcher never grants trading rights --
`research.validate.write_approvals` is the only writer of
`approved_strategies.json`.

Institutional memory is the important part. Before proposing anything, the
agent is shown every previously tested hypothesis so it cannot keep
re-suggesting "RSI 30-40 with a golden cross" after the firm already measured
it as negative expectancy.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from pydantic import Field

from config.universe import get_universe
from firm import memory
from firm.llm import ModelTier
from firm.memory_models import ProposalKind
from firm.runtime import Agent, AgentOutput, Cadence


class Hypothesis(AgentOutput):
    """One research idea, specified tightly enough to test."""

    name: str = Field(description="Short stable name, e.g. rsi_adx_trend_long.")
    description: str = Field(description="What the idea is, in one paragraph.")
    symbols: list[str] = Field(description="Symbols to test first.")
    side: str = Field(description="LONG or SHORT.")
    timeframe: str = Field(description="Candle timeframe, e.g. 15m or 4h.")
    parameter_changes: dict[str, float] = Field(
        default_factory=dict,
        description="Fields on RsiTrendParams to override, if this is a variant.",
    )
    why_it_might_work: str = Field(default="")
    why_it_might_fail: str = Field(default="")


class ResearchAgenda(AgentOutput):
    """The week's research plan: a few hypotheses, not a brainstorm dump."""

    hypotheses: list[Hypothesis] = Field(max_length=3)
    skip_reason: str = Field(
        default="",
        description="If proposing nothing, explain why (usually: wait for more data).",
    )


class QuantResearcher(Agent):
    name = "quant_researcher"
    role = "Quant Researcher"
    cadence = Cadence.WEEKLY
    tier = ModelTier.STRONG
    prompt_version = "v1"
    output_model = ResearchAgenda
    max_tokens = 3_500

    def system_prompt(self) -> str:
        return (
            "You are the Quant Researcher of a systematic crypto trading firm. "
            "Your job is to propose at most three tightly specified hypotheses "
            "that can be walk-forward validated. Never propose an idea the firm "
            "has already rejected unless you can name a concrete reason the "
            "previous test was invalid. Prefer small, mechanistic changes "
            "(add an ADX floor, widen the stop, change the RSI band) over "
            "brand-new strategies. If the current book has no completed trades "
            "and the baseline strategy already failed validation, propose "
            "parameter variants of rsi_trend -- do not invent a new indicator "
            "stack. Do not claim an edge exists. The validation pipeline decides."
        )

    def gather(self) -> dict[str, Any]:
        universe = get_universe()
        prior = memory.research_board(limit=40)
        keywords = ["rsi", "golden", "adx", "volume", "macd", "funding"]
        already = memory.already_tested(keywords)
        return {
            "approved_pairs": [f"{s}:{side}" for s, side in universe.approved_pairs],
            "long_candidates": universe.research_candidates("LONG")[:20],
            "short_candidates": universe.research_candidates("SHORT")[:20],
            "prior_reports": prior,
            "already_tested": already,
            "audit_questions": [
                p["payload"]
                for p in memory.pending_proposals()
                if p["kind"] == "strategy" and p["agent"] == "performance_auditor"
            ],
            "regime": memory.latest_regime(),
        }

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return (
            "Propose this week's research agenda. Do not repeat rejected ideas "
            f"from already_tested unless you can justify a retest.\n{inputs}"
        )

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        del inputs
        agenda = ResearchAgenda.model_validate(output.model_dump())
        ids: list[int] = []
        for hypo in agenda.hypotheses:
            memory.record_research(
                hypothesis=f"{hypo.name}: {hypo.description}",
                symbols=hypo.symbols,
                agent=self.name,
                status="proposed",
            )
            ids.append(
                self.propose(
                    kind=ProposalKind.STRATEGY,
                    title=f"Test {hypo.name} on {hypo.side} {hypo.timeframe}",
                    payload=hypo.model_dump(),
                    rationale=hypo.why_it_might_work or agenda.reasoning,
                    confidence=hypo.confidence,
                    run_id=run_id,
                    symbol=hypo.symbols[0] if hypo.symbols else "",
                    ttl=timedelta(days=14),
                )
            )
        return ids
