"""
Risk Officer: an LLM reviewer sitting *on top of* the deterministic risk engine.

Hourly, cheap model. Can flag and veto, never loosen. That is the entire job:
look at the current book, the recent rejections, the kill-switch state, and
say whether anything looks wrong that the rules have not already caught.

It cannot raise a limit, disable the kill switch, or enlarge a position --
`core.risk.apply_agent_adjustment` clamps any size request to <= 1.0, and this
employee never even offers an increase. A veto request is recorded as a
proposal; whether it is honoured depends on this agent's trust level (L2+).
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from core.db import session_scope
from core.ledger.models import Position, RejectedSignal, RiskEvent
from core.risk.killswitch import KillSwitch
from firm import memory
from firm.llm import ModelTier
from firm.memory_models import ProposalKind
from firm.runtime import Agent, AgentOutput, Cadence
from firm.trust import clamp_size_multiplier


class RiskReview(AgentOutput):
    """The Risk Officer's reading of current conditions."""

    stance: str = Field(description="One of: comfortable, cautious, tighten, halt.")
    veto_symbols: list[str] = Field(
        default_factory=list,
        description="Symbols that should not be entered this cycle.",
    )
    size_multipliers: dict[str, float] = Field(
        default_factory=dict,
        description="Per-symbol size multipliers in (0, 1]. Never above 1.",
    )
    concerns: list[str] = Field(default_factory=list)


class RiskOfficer(Agent):
    name = "risk_officer"
    role = "Risk Officer"
    cadence = Cadence.HOURLY
    tier = ModelTier.CHEAP
    prompt_version = "v1"
    output_model = RiskReview
    max_tokens = 1_400

    def system_prompt(self) -> str:
        return (
            "You are the Risk Officer of a systematic crypto trading firm. You "
            "review the current book, recent rejections and risk events. You may "
            "recommend vetoes or size reductions. You may NEVER recommend raising "
            "a limit, increasing size above 1.0, disabling the kill switch, or "
            "trading an unapproved symbol. If nothing is wrong, say so with high "
            "confidence and empty veto/size lists. Prefer fewer, sharper concerns "
            "over a laundry list."
        )

    def gather(self) -> dict[str, Any]:
        kill = KillSwitch().read()
        with session_scope() as session:
            open_positions = [
                {
                    "symbol": p.symbol,
                    "side": p.side,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "notional": p.notional,
                    "strategy": p.strategy,
                }
                for p in session.query(Position).filter(Position.status == "open").all()
            ]
            recent_rejects = [
                {
                    "symbol": r.symbol,
                    "side": r.side,
                    "verdict": r.verdict,
                    "reasons": r.reasons,
                }
                for r in session.query(RejectedSignal)
                .order_by(RejectedSignal.occurred_at.desc())
                .limit(15)
                .all()
            ]
            recent_events = [
                {
                    "kind": e.event_type,
                    "severity": e.severity,
                    "detail": e.detail,
                    "symbol": e.symbol,
                }
                for e in session.query(RiskEvent)
                .order_by(RiskEvent.occurred_at.desc())
                .limit(10)
                .all()
            ]

        return {
            "kill_switch": {
                "tripped": kill.tripped,
                "reason": kill.reason.value,
                "detail": kill.detail,
            },
            "open_positions": open_positions,
            "recent_rejections": recent_rejects,
            "recent_risk_events": recent_events,
            "regime": memory.latest_regime(),
        }

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return (
            "Review the firm's current risk picture and decide whether to veto "
            f"or shrink any names.\n{inputs}"
        )

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        del inputs
        review = RiskReview.model_validate(output.model_dump())
        ids: list[int] = []

        for symbol in review.veto_symbols:
            ids.append(
                self.propose(
                    kind=ProposalKind.RISK,
                    title=f"Veto {symbol}",
                    payload={"action": "veto", "symbol": symbol},
                    rationale=review.reasoning,
                    confidence=review.confidence,
                    run_id=run_id,
                    symbol=symbol,
                )
            )

        for symbol, requested in review.size_multipliers.items():
            clamped = clamp_size_multiplier(self.name, float(requested))
            if clamped >= 1.0:
                continue
            ids.append(
                self.propose(
                    kind=ProposalKind.RISK,
                    title=f"Reduce {symbol} to {clamped:.2f}x",
                    payload={
                        "action": "resize",
                        "symbol": symbol,
                        "requested": requested,
                        "clamped": clamped,
                    },
                    rationale=review.reasoning,
                    confidence=review.confidence,
                    run_id=run_id,
                    symbol=symbol,
                )
            )

        if review.stance == "halt":
            self.escalate(
                "Risk Officer recommends a halt",
                review.reasoning,
                severity="critical",
            )

        return ids
