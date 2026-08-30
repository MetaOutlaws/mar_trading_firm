"""
Desk Head: the orchestrator's voice. Summarises the day and escalates judgement calls.

Daily, standard model. Does not trade and does not override the risk engine.
Its job is to look at everything the other employees produced, decide what
needs a human, and write a briefing the dashboard can show without requiring
the operator to reconstruct the day from logs.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from firm import memory
from firm.llm import ModelTier
from firm.memory_models import ProposalKind
from firm.runtime import Agent, AgentOutput, Cadence
from firm.trust import all_records


class DailyBriefing(AgentOutput):
    """End-of-day (or on-demand) briefing."""

    headline: str = Field(description="One-sentence state of the firm.")
    priorities: list[str] = Field(description="What needs attention, most urgent first.")
    escalate_items: list[str] = Field(default_factory=list)
    ok_to_trade: bool = Field(description="False if the Desk Head would sit out.")


class DeskHead(Agent):
    name = "desk_head"
    role = "Desk Head"
    cadence = Cadence.DAILY
    tier = ModelTier.STANDARD
    prompt_version = "v1"
    output_model = DailyBriefing
    max_tokens = 1_800

    def system_prompt(self) -> str:
        return (
            "You are the Desk Head of a systematic crypto trading firm. You "
            "summarise the current state for the human operator. Be blunt. Do "
            "not invent P&L or invent employee activity -- use only the briefing "
            "pack. Flag contradictions between employees (e.g. Risk Officer "
            "wants a halt while Regime Analyst is bullish). You cannot raise "
            "risk limits or approve live trading."
        )

    def gather(self) -> dict[str, Any]:
        return {
            "regime": memory.latest_regime(),
            "sentiment": memory.latest_sentiment(limit=12),
            "pending_proposals": memory.pending_proposals(limit=20),
            "open_escalations": memory.open_escalations(limit=20),
            "recent_activity": memory.recent_runs(limit=20),
            "research": memory.research_board(limit=10),
            "trust": [r.summary() for r in all_records()],
        }

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return f"Write today's desk briefing from this pack.\n{inputs}"

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        del inputs
        briefing = DailyBriefing.model_validate(output.model_dump())
        ids: list[int] = []
        if not briefing.ok_to_trade:
            ids.append(
                self.propose(
                    kind=ProposalKind.OPERATIONAL,
                    title="Desk Head: sit out",
                    payload={"ok_to_trade": False, "priorities": briefing.priorities},
                    rationale=briefing.reasoning,
                    confidence=briefing.confidence,
                    run_id=run_id,
                )
            )
        for item in briefing.escalate_items:
            self.escalate("Desk Head: " + item[:160], briefing.reasoning, severity="warning")
        return ids
