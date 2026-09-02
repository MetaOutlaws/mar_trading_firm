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
    role = "Desk Head (GM)"
    cadence = Cadence.DAILY
    tier = ModelTier.STANDARD
    prompt_version = "v6"
    output_model = DailyBriefing
    max_tokens = 1_800
    mandate = (
        "Runs daily ops. Owns the research pipeline so work does not stop "
        "when a test finishes. Briefs the operator and files the next gate."
    )

    def system_prompt(self) -> str:
        return (
            "You are the Desk Head and general manager of a systematic crypto "
            "trading firm. Your job is continuity with a human only at written "
            "gates. Be blunt. Do not invent P&L. Use the briefing pack. "
            "If the last walk-forward finished, name the next catalog family "
            "(including backlog — coded-and-untested is still work) and whether "
            "Inbox already has that gate. Idle with empty Inbox after a rejected "
            "test is a miss; Strategy Advisor will flag you. If a family was approved "
            "for coding and is NOT in the registry, that is a blocking miss — "
            "do not say the floor is moving or that nothing waits on the "
            "operator. If it IS coded, the floor starts the test — do not "
            "ask for a second approve. Read duty_board.slips first: "
            "those are deterministic misses (idle pipeline, uncoded mandate, "
            "LLM timeout, paper mismatch). Name the owner. A Gemini timeout is Ops + Quant retry, "
            "not a sit-out. Flag contradictions between employees. You cannot "
            "raise risk limits or approve live trading. "
            "llm_seats is the source of truth for providers. If "
            "employee_seats_ok is true, Gemini is serving the floor. Do not "
            "call missing DeepSeek or OpenAI keys degradation. A missing xAI "
            "key only skips Sentiment. Ignore historical_noise, including "
            "KillSwitchState.is_tripped (patched). Do not file a sit-out for "
            "retired-provider skips, a single LLM timeout, or because research "
            "is waiting on a test."
        )

    def gather(self) -> dict[str, Any]:
        from firm.accountability import accountability_snapshot
        from firm.health_filters import llm_seat_briefing, mark_superseded_failures
        from firm.org import org_snapshot
        from firm.research_catalog import research_plan
        from firm.research_jobs import advance_pipeline, pipeline_snapshot

        memory.clear_resolved_health_noise()
        # GM function: keep the pipeline moving before writing the briefing.
        advance_pipeline()
        return {
            "llm_seats": llm_seat_briefing(),
            "org": org_snapshot(),
            "duty_board": accountability_snapshot(),
            "pipeline": pipeline_snapshot(),
            "research_plan": research_plan(),
            "regime": memory.latest_regime(),
            "sentiment": memory.latest_sentiment(limit=12),
            "pending_proposals": memory.pending_proposals(limit=20),
            "open_escalations": memory.open_escalations(limit=20),
            "recent_activity": mark_superseded_failures(memory.recent_runs(limit=20)),
            "research": memory.research_board(limit=10),
            "trust": [r.summary() for r in all_records()],
        }

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return (
            "Write today's desk briefing. Lead with the duty board: is the "
            "research pipeline moving, who is slipping, and what the next "
            "operator gate is (if any). The rest of the pack is context.\n"
            f"{inputs}"
        )

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
