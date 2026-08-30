"""Firm memory: runs, proposals, and expiry behave as the dashboard expects."""

from __future__ import annotations

from datetime import timedelta

from firm import memory
from firm.memory_models import ProposalKind, ProposalStatus, RunStatus
from core.db import session_scope
from firm.memory_models import Proposal


def test_run_lifecycle(firm_db) -> None:
    run_id = memory.start_run("ops_engineer", "Ops Engineer", "health check", {"ok": True})
    memory.finish_run(run_id, RunStatus.SUCCESS, output={"overall": "healthy"}, confidence=0.9)
    rows = memory.recent_runs(agent="ops_engineer")
    assert len(rows) == 1
    assert rows[0]["status"] == RunStatus.SUCCESS.value
    assert rows[0]["confidence"] == 0.9


def test_expired_proposal_cannot_be_approved(firm_db) -> None:
    pid = memory.record_proposal(
        agent="risk_officer",
        kind=ProposalKind.RISK,
        title="Veto BTCUSDT",
        payload={"action": "veto", "symbol": "BTCUSDT"},
        rationale="test",
        confidence=0.8,
        symbol="BTCUSDT",
        ttl=timedelta(seconds=-1),
    )
    assert memory.decide_proposal(pid, approved=True, decided_by="operator") is False
    with session_scope() as session:
        row = session.get(Proposal, pid)
        assert row is not None
        assert row.status == ProposalStatus.EXPIRED.value


def test_score_proposal_updates_trust(firm_db) -> None:
    from firm import trust

    trust.register("regime_analyst", "Regime Analyst")
    pid = memory.record_proposal(
        agent="regime_analyst",
        kind=ProposalKind.TRADE,
        title="bull",
        payload={},
        rationale="test",
        confidence=0.7,
    )
    memory.score_proposal(pid, pnl=12.5, correct=True)
    record = trust.get("regime_analyst")
    assert record is not None
    assert record.decisions_scored == 1
    assert record.decisions_correct == 1
    assert record.pnl_attribution == 12.5
