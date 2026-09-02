"""
Sleeve Engineer: turns an approved catalog family into a coded, testable sleeve.

Hourly backstop plus event-driven (coding request, standby low). Does not
propose families, judge results, size positions, or touch live. Does not
LLM-write `core/strategy/*.py` — novel families escalate to Cursor.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from firm.llm import ModelTier
from firm.runtime import Agent, AgentOutput, Cadence


class SleeveReport(AgentOutput):
    """What coding/standby work happened this cycle."""

    staged_jobs: list[int] = Field(default_factory=list)
    novel_families: list[str] = Field(
        default_factory=list,
        description="Approved families that are not a known registry template.",
    )
    standby_depth: int = Field(default=0)
    blocker: str = Field(
        default="",
        description="Empty if coding/standby is on track; otherwise the stall.",
    )


class SleeveEngineer(Agent):
    name = "sleeve_engineer"
    role = "Sleeve Engineer"
    cadence = Cadence.HOURLY
    tier = ModelTier.CHEAP
    prompt_version = "v1"
    output_model = SleeveReport
    max_tokens = 900
    mandate = (
        "Converts an approved catalog family into a coded, registered sleeve "
        "and keeps launch-ready standby full. Template specs become JSON "
        "under config/sleeves. Novel math is a Cursor coding request. Does "
        "not write freeform strategy files, propose families, judge tests, "
        "size positions, or touch live."
    )

    def system_prompt(self) -> str:
        return (
            "You are the Sleeve Engineer of a systematic crypto trading firm. "
            "Your gather pack already staged known sleeves as standby jobs "
            "and materialized allowed JSON templates. Report what was staged. "
            "If novel_families is non-empty, that is a Cursor coding request "
            "under research/coding_requests/. You do not propose the next "
            "family, start live trading, or change risk limits. Standby depth "
            "below target is your miss. A walk-forward slot freeing is Desk Head's "
            "to launch; you only keep standby non-empty."
        )

    def gather(self) -> dict[str, Any]:
        from firm.continuity import code_pending_sleeves, evaluate_invariants, throughput_metrics

        work = code_pending_sleeves()
        tickets = evaluate_invariants()
        metrics = throughput_metrics()
        return {
            "coding_work": work,
            "standby_depth": metrics.get("standby_depth"),
            "standby_target": (metrics.get("config") or {}).get("standby_target"),
            "tickets": [
                t
                for t in tickets
                if t.get("owner") == "sleeve_engineer"
            ],
            "novel": work.get("novel") or [],
        }

    def describe_task(self, inputs: dict[str, Any]) -> str:
        del inputs
        return "Register coded sleeves into standby; escalate novel families"

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return (
            "Report coding/standby status from the pack. Name any novel family "
            "that needs a human. Do not invent a strategy file.\n"
            f"{inputs}"
        )
