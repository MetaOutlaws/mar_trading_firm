"""
Portfolio Manager: allocates across validated strategies, correlation-aware.

Daily, standard model. Reads research approvals, the current regime, and open
exposure, then proposes per-symbol size multipliers. Those multipliers can only
shrink the risk engine's own size -- `clamp_size_multiplier` and the risk
engine both refuse anything above 1.0 -- so a bullish PM cannot lever up.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from config.universe import get_universe
from firm import memory
from firm.llm import ModelTier
from firm.memory_models import ProposalKind
from firm.runtime import Agent, AgentOutput, Cadence
from firm.trust import clamp_size_multiplier


class AllocationPlan(AgentOutput):
    """How the PM would tilt the book, expressed as size multipliers."""

    size_multipliers: dict[str, float] = Field(
        description="Per-symbol multipliers in (0, 1]. Omit names that should stay at 1.0."
    )
    sit_out: list[str] = Field(
        default_factory=list, description="Symbols to skip entirely this cycle."
    )
    notes: str = Field(default="")


class PortfolioManager(Agent):
    name = "portfolio_manager"
    role = "Portfolio Manager"
    cadence = Cadence.DAILY
    tier = ModelTier.STANDARD
    prompt_version = "v1"
    output_model = AllocationPlan
    max_tokens = 1_600

    def system_prompt(self) -> str:
        return (
            "You are the Portfolio Manager of a systematic crypto trading firm. "
            "You allocate across already-validated strategies. You may reduce "
            "size or sit out; you may never increase size above 1.0, never add "
            "an unapproved symbol, and never override the risk engine. Prefer "
            "concentration in a few uncorrelated names over sprinkling size "
            "across everything. If the regime is chop or high-vol, default to "
            "smaller size rather than more names."
        )

    def gather(self) -> dict[str, Any]:
        universe = get_universe()
        approvals = {
            f"{symbol}:{side}": True
            for symbol, side in universe.approved_pairs
        }
        return {
            "approved_pairs": [f"{s}:{side}" for s, side in universe.approved_pairs],
            "approvals_empty": not approvals,
            "regime": memory.latest_regime(),
            "sentiment": memory.latest_sentiment(limit=15),
            "pending_risk_proposals": [
                p for p in memory.pending_proposals() if p["kind"] == "risk"
            ],
        }

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        if inputs.get("approvals_empty"):
            return (
                "No research-approved pairs exist. Produce an empty allocation "
                "(no multipliers, sit_out empty) and explain that the firm "
                "must wait for validation. Do not invent names to trade.\n"
                f"{inputs}"
            )
        return f"Propose today's allocation tilts.\n{inputs}"

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        del inputs
        plan = AllocationPlan.model_validate(output.model_dump())
        ids: list[int] = []

        for symbol in plan.sit_out:
            ids.append(
                self.propose(
                    kind=ProposalKind.ALLOCATION,
                    title=f"Sit out {symbol}",
                    payload={"action": "sit_out", "symbol": symbol},
                    rationale=plan.reasoning,
                    confidence=plan.confidence,
                    run_id=run_id,
                    symbol=symbol,
                )
            )

        for symbol, requested in plan.size_multipliers.items():
            clamped = clamp_size_multiplier(self.name, float(requested))
            if clamped >= 1.0:
                continue
            ids.append(
                self.propose(
                    kind=ProposalKind.ALLOCATION,
                    title=f"Tilt {symbol} to {clamped:.2f}x",
                    payload={
                        "action": "resize",
                        "symbol": symbol,
                        "requested": requested,
                        "clamped": clamped,
                    },
                    rationale=plan.reasoning,
                    confidence=plan.confidence,
                    run_id=run_id,
                    symbol=symbol,
                )
            )
        return ids
