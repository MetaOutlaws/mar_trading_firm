"""
Quant Researcher: the edge factory.

Fires when the pipeline is idle (weekly is only the budget floor). Proposes a
small number of testable hypotheses from the catalog. The researcher never
grants trading rights -- `research.validate.write_approvals` is the only writer
of `approved_strategies.json`.

Institutional memory is the important part. Before proposing anything, the
agent is shown every previously tested hypothesis so it cannot keep
re-suggesting "RSI 30-40 with a golden cross" after the firm already measured
it as negative expectancy.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from config.universe import get_universe
from firm import memory
from firm.llm import ModelTier
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
        description="Concrete numeric overrides for the named family (lookback, min_adx, rsi band, stops).",
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
    prompt_version = "v6"
    output_model = ResearchAgenda
    max_tokens = 3_500

    def system_prompt(self) -> str:
        return (
            "You are the Quant Researcher of a systematic crypto trading firm. "
            "You own catalog depth and new-edge intake, not walk-forward. "
            "Primary job when leftovers are thin: propose 1–3 NEW snake_case "
            "families with distinct math (new indicator or structure, not a "
            "rename of a loser). Those land as Cursor coding briefs. Secondary: "
            "near-miss param grids of families that were close. Do not re-queue "
            "rsi_trend. Do not clone a clear-loss family onto another clock. "
            "Do not queue SHORT after BOTH on the same clock. No 15m. Do not "
            "start walk-forward. Do not grant trading rights."
        )

    def gather(self) -> dict[str, Any]:
        from firm.research_catalog import remaining_hypotheses, research_plan
        from firm.sleeve_factory import ready_novel_specs
        from core.strategy.registry import list_strategies

        universe = get_universe()
        prior = memory.research_board(limit=40)
        keywords = ["rsi", "golden", "adx", "volume", "macd", "funding", "donchian", "ema", "bollinger", "pullback", "atr"]
        already = memory.already_tested(keywords)
        remaining = remaining_hypotheses()
        return {
            "research_catalog": research_plan(),
            "catalog_depth": len(remaining),
            "remaining_hypotheses": [
                {
                    "id": r.get("id"),
                    "family": r.get("family"),
                    "clock": r.get("clock"),
                    "rank": r.get("rank"),
                }
                for r in remaining[:12]
            ],
            "approved_pairs": [f"{s}:{side}" for s, side in universe.approved_pairs],
            "prior_reports": prior,
            "already_tested": already,
            "ready_novel_families": [spec.name for spec in ready_novel_specs()[:12]],
            "coded_family_count": len(list_strategies()),
        }

    def describe_task(self, inputs: dict[str, Any]) -> str:
        depth = int(inputs.get("catalog_depth") or 0)
        if depth <= 0:
            return "Catalog drained — propose NEW snake_case families with distinct math"
        return "Keep novel briefs flowing; add near-miss param grids if justified"

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return (
            "If catalog_depth is low, name NEW families (stochastic, volume, "
            "session structure, etc.) with why it might work/fail. Uncoded "
            "names become Cursor tickets. Do not only list clock clones of "
            "sleeves that already failed. Keep leftover novel briefs ready.\n"
            f"{inputs}"
        )

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        del inputs
        from core.strategy.registry import list_strategies
        from firm.research_catalog import append_hypothesis
        from firm.research_jobs import file_novel_coding_inbox, infer_family

        novel_ids = [
            int(row["proposal_id"])
            for row in (file_novel_coding_inbox().get("filed") or [])
            if row.get("proposal_id")
        ]
        agenda = ResearchAgenda.model_validate(output.model_dump())
        ids: list[int] = list(novel_ids)
        coded = set(list_strategies())
        from core.strategy.sleeve_spec import SleeveSpec
        from firm.cursor_coding import enqueue_approved, pending_jobs
        from firm.sleeve_factory import write_coding_request

        for hypo in agenda.hypotheses:
            slug = "".join(
                ch if ch.isalnum() or ch == "_" else "_"
                for ch in str(hypo.name or "").strip().lower().replace(" ", "_")
            )
            while "__" in slug:
                slug = slug.replace("__", "_")
            slug = slug.strip("_")
            family = slug if len(slug) >= 3 else infer_family({"name": hypo.name}, hypo.name)
            clock = str(hypo.timeframe or "4h/4h")
            if "/" not in clock:
                clock = f"{clock}/{clock}"
            if "15m" in clock:
                clock = "4h/4h"
            memory.record_research(
                hypothesis=f"{hypo.name}: {hypo.description}",
                symbols=hypo.symbols,
                agent=self.name,
                status="proposed",
                metrics={
                    "family": family,
                    "rationale": hypo.why_it_might_work or agenda.reasoning,
                    "why_it_might_fail": hypo.why_it_might_fail,
                    "side": hypo.side,
                    "timeframe": hypo.timeframe,
                    "parameter_changes": hypo.parameter_changes,
                },
            )
            if family in coded:
                hid = (
                    f"{family}@{clock}"
                    if str(hypo.side or "BOTH").upper() == "BOTH"
                    else f"{family}@{clock}@{str(hypo.side).upper()}"
                )
                change = dict(hypo.parameter_changes or {})
                append_hypothesis(
                    {
                        "id": hid if not change else f"{hid}@quant",
                        "family": family,
                        "name": hypo.name,
                        "clock": clock,
                        "side": str(hypo.side or "BOTH").upper(),
                        "coded": True,
                        "free_params": min(6, max(1, len(change) or 4)),
                        "disposition": "re-parameterise" if change else "retest_under_different_regime",
                        "justification": hypo.why_it_might_work or agenda.reasoning,
                        "param_change": change or {"clock": clock},
                        "needs_feed": False,
                    },
                    added_by="quant_researcher",
                )
                continue
            if family in {"unknown", "rsi_trend", "rsi"}:
                continue
            try:
                spec = SleeveSpec(
                    name=family,
                    template="novel",
                    clock=clock if clock in {"4h/4h", "1h/1h", "1h/4h", "4h/1h"} else "4h/4h",
                    side=str(hypo.side or "BOTH").upper() if str(hypo.side or "BOTH").upper() in {"BOTH", "LONG", "SHORT"} else "BOTH",
                    needs_new_indicator=True,
                    novel_reason=(hypo.description or "")[:400],
                    summary=(hypo.description or hypo.name)[:240],
                    justification=hypo.why_it_might_work or agenda.reasoning,
                )
            except Exception:
                continue
            path = write_coding_request(spec)
            md_path = path.with_suffix(".md")
            brief = md_path.read_text(encoding="utf-8") if md_path.exists() else spec.summary
            # One Cursor ticket at a time so NOW.md is a real implement-now brief.
            if not pending_jobs():
                enqueue_approved(
                    family=spec.name,
                    brief=brief,
                    brief_path=str(md_path),
                )
        return ids
