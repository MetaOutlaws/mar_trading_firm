"""Trust ladder: promotions need evidence, demotions do not, agents cannot raise risk."""

from __future__ import annotations

import pytest

from firm import trust
from firm.memory_models import TrustLevel


def test_new_employee_starts_at_advisor(firm_db) -> None:
    record = trust.register("regime_analyst", "Regime Analyst")
    assert record.level is TrustLevel.ADVISOR
    assert not record.may_veto
    assert not record.may_resize
    assert not record.may_trade


def test_deterministic_roles_cannot_join_the_ladder(firm_db) -> None:
    with pytest.raises(ValueError, match="deterministic"):
        trust.register("risk_manager", "risk_manager")


def test_prompt_change_resets_track_record(firm_db) -> None:
    trust.register("desk_head", "Desk Head", prompt_version="v1")
    trust.note_decision("desk_head", 5)
    trust.register("desk_head", "Desk Head", prompt_version="v2")
    record = trust.get("desk_head")
    assert record is not None
    assert record.level is TrustLevel.ADVISOR
    assert record.decisions_logged == 0
    assert record.prompt_version == "v2"


def test_promotion_requires_evidence_and_approver(firm_db) -> None:
    trust.register("risk_officer", "Risk Officer")
    ok, reason = trust.promote(
        "risk_officer", TrustLevel.VETO, approved_by="operator", auditor_recommends=True
    )
    assert not ok
    assert "scored decisions" in reason


def test_cannot_skip_rungs(firm_db) -> None:
    trust.register("risk_officer", "Risk Officer")
    ok, reason = trust.promote(
        "risk_officer", TrustLevel.AUTONOMOUS, approved_by="operator", auditor_recommends=True
    )
    assert not ok
    assert "one rung" in reason


def test_demote_needs_no_approval(firm_db) -> None:
    trust.register("risk_officer", "Risk Officer")
    with trust.session_scope() if False else _force_level("risk_officer", TrustLevel.SIZING):
        pass
    trust.demote("risk_officer", "bad week")
    record = trust.get("risk_officer")
    assert record is not None
    assert record.level is TrustLevel.ADVISOR


def _force_level(agent: str, level: TrustLevel):
    """Test helper: write a level directly, simulating a prior promotion."""
    from core.db import session_scope
    from firm.memory_models import AgentTrust

    with session_scope() as session:
        row = session.get(AgentTrust, agent)
        assert row is not None
        row.level = int(level)
    return _Null()


class _Null:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_size_multiplier_never_exceeds_one(firm_db) -> None:
    trust.register("portfolio_manager", "Portfolio Manager")
    assert trust.clamp_size_multiplier("portfolio_manager", 1.5) == 1.0
    # L1 cannot resize, so a requested shrink is ignored rather than applied.
    assert trust.clamp_size_multiplier("portfolio_manager", 0.6) == 1.0


def test_l3_can_shrink_within_band(firm_db) -> None:
    trust.register("portfolio_manager", "Portfolio Manager")
    _force_level("portfolio_manager", TrustLevel.SIZING)
    assert trust.clamp_size_multiplier("portfolio_manager", 0.7) == 0.7
    # Below the band is a backdoor veto; clamp up unless the agent also has L2.
    assert trust.clamp_size_multiplier("portfolio_manager", 0.1) == trust.SIZING_BAND[0]


def test_only_veto_authority_can_zero_size(firm_db) -> None:
    trust.register("risk_officer", "Risk Officer")
    _force_level("risk_officer", TrustLevel.VETO)
    assert trust.clamp_size_multiplier("risk_officer", 0.0) == 0.0
