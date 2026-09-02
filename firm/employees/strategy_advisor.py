"""
Strategy Advisor: the operator's second pair of eyes, including on the GM.

Daily, standard model, plus a short recheck whenever the pipeline is idle
with catalog work still left. Does not trade, does not grant rights, and
does not write strategy files. Its job is to notice dropped balls — empty
Inbox after a rejected test, a GM marked 'on track' while nothing is
running, an uncoded mandate painted as progress — and escalate them.

The GM still owns filing the next gate. This seat exists because that
ownership was not enough: the duty board called the GM on track while ATR
sat in the backlog untested.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from firm import memory
from firm.llm import ModelTier
from firm.runtime import Agent, AgentOutput, Cadence


class StrategyReview(AgentOutput):
    """Independent read of whether research is actually moving."""

    gm_held_accountable: bool = Field(
        description="True if the GM currently has a deterministic miss on the duty board."
    )
    dropped_balls: list[str] = Field(
        default_factory=list,
        description="Concrete stalls: idle pipeline, uncoded mandate, missing Inbox gate.",
    )
    next_research_move: str = Field(
        description="The next catalog action (family + walk_forward or code_family)."
    )
    operator_should: str = Field(
        description="What the operator must do, or 'nothing' if a gate is already in Inbox."
    )


class StrategyAdvisor(Agent):
    name = "strategy_advisor"
    role = "Strategy Advisor"
    cadence = Cadence.DAILY
    tier = ModelTier.STANDARD
    prompt_version = "v1"
    output_model = StrategyReview
    max_tokens = 1_800
    mandate = (
        "Advises the operator. Audits the GM and the research pipeline so "
        "work does not stop when a test finishes. Cannot trade or raise risk."
    )

    def system_prompt(self) -> str:
        return (
            "You are the Strategy Advisor to the operator of a systematic "
            "crypto trading firm. You do not run daily ops — Desk Head (GM) "
            "does — and you do not invent edges — Quant does. You look at "
            "everything and name dropped balls, including the GM's. "
            "duty_board.slips are deterministic truth: if Desk Head is idle "
            "with catalog work, that is a miss, not 'on track'. "
            "Your gather already called fill_walk_forward_slots. If jobs "
            "started, say so. Do not tell the operator to approve Inbox for "
            "a Tier A walk-forward. Do not propose live trading. Do not "
            "ask for a second approve after a coded family is already gated. "
            "Do not claim a walk-forward is running unless pipeline.now says so. "
            "You cannot raise risk limits."
        )

    def gather(self) -> dict[str, Any]:
        from firm.accountability import accountability_snapshot
        from firm.org import org_snapshot
        from firm.research_catalog import next_catalog_step, research_plan
        from firm.research_jobs import advance_pipeline, list_jobs, pipeline_snapshot
        from core.strategy.registry import list_strategies

        # Belt and suspenders: GM should have launched; we launch if they did not.
        progressed = advance_pipeline()
        fill: dict[str, Any] = {}
        started: list[int] = []
        try:
            from firm.continuity import fill_walk_forward_slots

            fill = fill_walk_forward_slots(source="event")
            started = list(fill.get("started") or [])
        except Exception:
            fill = {}
        duty = accountability_snapshot()
        gm_slips = [s for s in (duty.get("slips") or []) if s.get("owner") == "desk_head"]
        if gm_slips:
            issues = "; ".join(str(s.get("issue") or "") for s in gm_slips)
            if started:
                memory.escalate_once(
                    agent="strategy_advisor",
                    title="GM miss — Advisor started the next test",
                    detail=(
                        f"Desk Head was idle. Strategy Advisor started jobs "
                        f"{started}. That is the enforcement; Inbox is not.\n\n"
                        f"GM miss was: {issues}"
                    ),
                    severity="warning",
                    root_cause="advisor_enforced_gm_miss",
                )
            else:
                blocked = ""
                try:
                    blocked = str(fill.get("blocked") or "")
                except Exception:
                    blocked = ""
                memory.escalate_once(
                    agent="strategy_advisor",
                    title="GM continuity miss",
                    detail=(
                        "Desk Head is accountable for a running walk-forward. "
                        f"Current miss: {issues}\n\n"
                        + (
                            f"Launch blocked: {blocked}. That is the operator gate."
                            if blocked
                            else "Strategy Advisor called fill_walk_forward_slots; "
                            "nothing started. Name the block, do not file a dummy Inbox."
                        )
                    ),
                    severity="warning",
                    root_cause="gm_continuity_miss",
                )
        tested = {
            str(j.get("family"))
            for j in list_jobs()
            if j.get("status") in {"done", "failed"} and j.get("family")
        }
        nxt = next_catalog_step(tested=tested, coded=set(list_strategies()))
        return {
            "org": org_snapshot(),
            "duty_board": duty,
            "pipeline": pipeline_snapshot(),
            "research_plan": research_plan(),
            "gm_slips": gm_slips,
            "next_gate": progressed.get("next_gate"),
            "started_jobs": started,
            "fill_blocked": fill.get("blocked") or "",
            "next_catalog_step": nxt,
            "pending_proposals": memory.pending_proposals(limit=20),
            "open_escalations": memory.open_escalations(limit=20),
        }

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return (
            "Review the firm. Is research actually moving? Is the GM on "
            "track or slipping? Name every dropped ball. Tell the operator "
            "the single next action.\n"
            f"{inputs}"
        )

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        del output, inputs, run_id
        # Deterministic GM miss is already escalate_once in gather. Do not
        # flood Inbox with a new row every daily run.
        return []
