"""
The trust ladder: how an employee earns authority, and what it can never earn.

Authority is granted on evidence, not on how convincing an agent sounds. A
promotion needs a minimum number of *scored* decisions (outcome known), a hit
rate above chance, positive attributed P&L, and an explicit human approval. Any
one of those missing means no promotion.

The invariant that makes the whole design safe:

    An agent may always REDUCE risk. No agent, at any trust level, can raise a
    limit, size above the deterministic cap, disable the kill switch, or trade
    outside the approved universe.

That is enforced structurally rather than by prompt. `core.risk` clamps agent
size multipliers to <= 1.0 and owns the final decision, so even a compromised or
hallucinating L4 agent cannot exceed the risk engine's bounds. This module only
decides *how much of that reducing authority* an employee currently has.

Prompt versions matter: a rewritten prompt is a different employee. Changing it
resets the track record, because a record earned under different instructions
does not predict behaviour under the new ones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from core.db import session_scope
from firm.memory_models import AgentTrust, TrustLevel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromotionCriteria:
    """What an employee must demonstrate to move up one rung.

    Deliberately strict on sample size. Twenty scored decisions is already a
    small sample for a hit-rate estimate; anything less would promote on noise,
    and the whole point of the ladder is to avoid that.
    """

    min_scored_decisions: int = 20
    min_hit_rate_pct: float = 55.0
    require_positive_pnl: bool = True
    #: Auditor sign-off and operator approval are separate gates on purpose:
    #: one is an analytical judgement, the other is accountability.
    require_auditor_recommendation: bool = True
    require_human_approval: bool = True


DEFAULT_CRITERIA = PromotionCriteria()

#: Every employee starts here. L1 opinions are visible and logged but change
#: nothing, which is the right default for an unproven track record.
STARTING_LEVEL = TrustLevel.ADVISOR

#: Roles that are deterministic code and therefore have no trust level at all.
#: Listing them explicitly prevents someone later "promoting" the risk engine.
DETERMINISTIC_ROLES = frozenset({"risk_manager", "execution_trader"})

#: The widest size reduction an L3 employee may request, as a multiplier on the
#: risk engine's own sizing. It can shrink a position but never remove or
#: enlarge it; a 0.0 multiplier is a veto and requires L2 separately.
SIZING_BAND = (0.5, 1.0)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TrustRecord:
    """An employee's current authority and the evidence behind it."""

    agent: str
    role: str
    level: TrustLevel
    decisions_logged: int
    decisions_scored: int
    decisions_correct: int
    pnl_attribution: float
    prompt_version: str
    updated_at: datetime | None = None
    promoted_at: datetime | None = None
    notes: str = ""

    @property
    def hit_rate(self) -> float:
        if not self.decisions_scored:
            return 0.0
        return self.decisions_correct / self.decisions_scored * 100.0

    @property
    def may_veto(self) -> bool:
        return self.level >= TrustLevel.VETO

    @property
    def may_resize(self) -> bool:
        return self.level >= TrustLevel.SIZING

    @property
    def may_trade(self) -> bool:
        return self.level >= TrustLevel.AUTONOMOUS

    def summary(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "role": self.role,
            "level": int(self.level),
            "level_label": self.level.label,
            "decisions_logged": self.decisions_logged,
            "decisions_scored": self.decisions_scored,
            "hit_rate_pct": round(self.hit_rate, 2),
            "pnl_attribution": round(self.pnl_attribution, 2),
            "prompt_version": self.prompt_version,
            "may_veto": self.may_veto,
            "may_resize": self.may_resize,
            "may_trade": self.may_trade,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
            "notes": self.notes,
        }


def _to_record(row: AgentTrust) -> TrustRecord:
    return TrustRecord(
        agent=row.agent,
        role=row.role,
        level=TrustLevel(row.level),
        decisions_logged=row.decisions_logged,
        decisions_scored=row.decisions_scored,
        decisions_correct=row.decisions_correct,
        pnl_attribution=row.pnl_attribution,
        prompt_version=row.prompt_version,
        updated_at=row.updated_at,
        promoted_at=row.promoted_at,
        notes=row.notes,
    )


def register(agent: str, role: str, prompt_version: str = "v1") -> TrustRecord:
    """Ensure an employee has a trust row, creating it at L1 if absent.

    Also detects a prompt-version change and resets the track record, since the
    evidence was gathered under different instructions. Resetting is the
    conservative choice: it costs the agent time, but keeps the hit rate honest.
    """
    if role in DETERMINISTIC_ROLES:
        raise ValueError(
            f"{role} is deterministic code and has no trust level. "
            "Only LLM employees sit on the ladder."
        )

    with session_scope() as session:
        row = session.get(AgentTrust, agent)

        if row is None:
            row = AgentTrust(
                agent=agent,
                role=role,
                level=int(STARTING_LEVEL),
                prompt_version=prompt_version,
            )
            session.add(row)
            session.flush()
            logger.info("Registered %s (%s) at %s.", agent, role, STARTING_LEVEL.label)
            return _to_record(row)

        if row.prompt_version != prompt_version:
            logger.warning(
                "%s prompt changed %s -> %s: resetting track record and demoting to %s.",
                agent, row.prompt_version, prompt_version, STARTING_LEVEL.label,
            )
            row.prompt_version = prompt_version
            row.level = int(STARTING_LEVEL)
            row.decisions_logged = 0
            row.decisions_scored = 0
            row.decisions_correct = 0
            row.pnl_attribution = 0.0
            row.notes = (
                f"Track record reset on {utcnow().date()} because the prompt "
                f"changed to {prompt_version}."
            )
            row.updated_at = utcnow()

        row.role = role
        return _to_record(row)


def get(agent: str) -> TrustRecord | None:
    """Read one employee's trust record."""
    with session_scope() as session:
        row = session.get(AgentTrust, agent)
        return _to_record(row) if row else None


def all_records() -> list[TrustRecord]:
    """Every employee's trust record, for the dashboard."""
    with session_scope() as session:
        rows = session.scalars(select(AgentTrust).order_by(AgentTrust.agent))
        return [_to_record(row) for row in rows]


def note_decision(agent: str, count: int = 1) -> None:
    """Increment the logged-decision counter.

    Logged decisions alone never justify promotion -- only *scored* ones do --
    but the count shows whether an agent is doing enough work to ever accumulate
    evidence.
    """
    with session_scope() as session:
        row = session.get(AgentTrust, agent)
        if row is None:
            return
        row.decisions_logged += count
        row.updated_at = utcnow()


def evaluate_promotion(
    agent: str,
    auditor_recommends: bool = False,
    criteria: PromotionCriteria = DEFAULT_CRITERIA,
) -> tuple[bool, TrustLevel, list[str]]:
    """Assess whether an employee is eligible for the next rung.

    Args:
        agent: Employee name.
        auditor_recommends: Whether the Performance Auditor has signed off.
        criteria: Thresholds to apply.

    Returns:
        (eligible, proposed_level, blockers). `eligible` being True still does
        not promote anyone: `promote()` requires explicit human approval.
    """
    record = get(agent)
    if record is None:
        return False, STARTING_LEVEL, [f"{agent} has no trust record"]

    blockers: list[str] = []

    if record.level is TrustLevel.AUTONOMOUS:
        return False, record.level, ["already at the top of the ladder"]

    if record.decisions_scored < criteria.min_scored_decisions:
        blockers.append(
            f"{record.decisions_scored} scored decisions "
            f"(need >= {criteria.min_scored_decisions})"
        )

    if record.hit_rate < criteria.min_hit_rate_pct:
        blockers.append(
            f"hit rate {record.hit_rate:.1f}% < {criteria.min_hit_rate_pct}%"
        )

    if criteria.require_positive_pnl and record.pnl_attribution <= 0:
        blockers.append(f"attributed P&L {record.pnl_attribution:+.2f} is not positive")

    if criteria.require_auditor_recommendation and not auditor_recommends:
        blockers.append("no Performance Auditor recommendation")

    proposed = TrustLevel(min(int(record.level) + 1, int(TrustLevel.AUTONOMOUS)))
    return (not blockers), proposed, blockers


def promote(
    agent: str,
    to_level: TrustLevel,
    approved_by: str,
    auditor_recommends: bool = False,
    criteria: PromotionCriteria = DEFAULT_CRITERIA,
) -> tuple[bool, str]:
    """Raise an employee's authority. Requires human approval.

    Only one rung at a time, and only when the evidence gates pass. Skipping
    rungs would put an agent straight into position-opening authority on the
    strength of advisory-level evidence.
    """
    record = get(agent)
    if record is None:
        return False, f"{agent} has no trust record"

    if criteria.require_human_approval and not approved_by:
        return False, "promotion requires an explicit approver"

    if int(to_level) != int(record.level) + 1:
        return False, (
            f"promotions move one rung at a time: {record.level.label} -> "
            f"{TrustLevel(int(record.level) + 1).label}, not {to_level.label}"
        )

    eligible, _, blockers = evaluate_promotion(agent, auditor_recommends, criteria)
    if not eligible:
        return False, "; ".join(blockers)

    with session_scope() as session:
        row = session.get(AgentTrust, agent)
        if row is None:
            return False, f"{agent} disappeared"
        row.level = int(to_level)
        row.promoted_at = utcnow()
        row.updated_at = utcnow()
        row.notes = f"Promoted to {to_level.label} by {approved_by} on {utcnow().date()}."

    logger.warning("%s promoted to %s by %s.", agent, to_level.label, approved_by)
    return True, f"{agent} is now {to_level.label}"


def demote(agent: str, reason: str, to_level: TrustLevel = STARTING_LEVEL) -> None:
    """Reduce authority immediately.

    Intentionally asymmetric with promotion: no gates, no approval, no one-rung
    limit. Removing authority is always safe, so nothing should stand in its way.
    """
    with session_scope() as session:
        row = session.get(AgentTrust, agent)
        if row is None:
            return
        previous = TrustLevel(row.level)
        row.level = int(to_level)
        row.updated_at = utcnow()
        row.notes = f"Demoted from {previous.label} on {utcnow().date()}: {reason}"

    logger.warning("%s demoted %s -> %s: %s", agent, previous.label, to_level.label, reason)


def clamp_size_multiplier(agent: str, requested: float) -> float:
    """Constrain a size request to what this employee is allowed to ask for.

    Returns a multiplier in [0, 1]. Above 1.0 is clamped to 1.0 regardless of
    trust level: increasing risk is not on the ladder at all. Below the L3 band
    is clamped upward, so a sizing agent cannot use a 0.01 multiplier as a
    backdoor veto without holding veto authority.
    """
    record = get(agent)
    if record is None:
        return 1.0

    # Nothing may ever increase risk.
    requested = min(max(requested, 0.0), 1.0)

    if requested == 0.0:
        return 0.0 if record.may_veto else 1.0

    if not record.may_resize:
        return 1.0

    floor, ceiling = SIZING_BAND
    return min(max(requested, floor), ceiling)


__all__ = [
    "DEFAULT_CRITERIA",
    "DETERMINISTIC_ROLES",
    "PromotionCriteria",
    "SIZING_BAND",
    "STARTING_LEVEL",
    "TrustLevel",
    "TrustRecord",
    "all_records",
    "clamp_size_multiplier",
    "demote",
    "evaluate_promotion",
    "get",
    "note_decision",
    "promote",
    "register",
]
