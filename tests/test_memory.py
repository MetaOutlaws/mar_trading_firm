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


def test_research_board_exposes_rationale(firm_db) -> None:
    """The Research tab needs one or two sentences, not just a hypothesis title."""
    memory.record_research(
        hypothesis="donchian_20: break prior 20-bar high",
        symbols=["BTCUSDT"],
        metrics={
            "rationale": "Trend continuation after a compressed range.",
            "why_it_might_fail": "Whipsaws in chop.",
        },
    )
    board = memory.research_board()
    assert board[0]["rationale"] == "Trend continuation after a compressed range."
    assert board[0]["why_it_might_fail"] == "Whipsaws in chop."


def test_research_board_backfills_rationale_from_inbox(firm_db) -> None:
    """Older rows stored the why only on the strategy proposal."""
    memory.record_research(
        hypothesis="donchian_55: slower channel on ETH",
        symbols=["ETHUSDT"],
    )
    memory.record_proposal(
        agent="quant_researcher",
        kind=ProposalKind.STRATEGY,
        title="Test donchian_55",
        payload={"name": "donchian_55", "why_it_might_fail": "late entries"},
        rationale="A slower channel should fire less in chop.",
        confidence=0.6,
    )
    board = memory.research_board()
    match = next(row for row in board if row["hypothesis"].startswith("donchian_55"))
    assert "slower channel" in match["rationale"]
    assert match["why_it_might_fail"] == "late entries"


def test_quant_weekly_task_is_rewritten(firm_db) -> None:
    run_id = memory.start_run(
        "quant_researcher", "Quant Researcher", "Quant Researcher weekly run", {}
    )
    memory.finish_run(run_id, RunStatus.SUCCESS, output={"ok": True}, confidence=0.7)
    activity = memory.agent_activity("quant_researcher")
    assert "weekly" not in activity["current_task"].lower()
    assert "catalog family" in activity["current_task"].lower()
    rows = memory.recent_runs(agent="quant_researcher")
    assert "weekly" not in rows[0]["task"].lower()
