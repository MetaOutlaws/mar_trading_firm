"""Next-step Inbox asks must not re-file a terminal family@clock@side.

opening_range_breakout 1h BOTH already has a paper-book verdict and a stack
of rejected Inbox asks. After a job finishes, the pipeline used to file that
same ask again because remaining hypotheses ignore the book and dedupe only
looked at pending rows.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

import pytest

from firm.memory_models import ProposalKind


def _isolate_finished_grids(monkeypatch, tmp_path) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_catalog, "WALK_FORWARD_HISTORY_PATH", tmp_path / "wf_history.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_catalog, "paper_book_finished_keys", lambda: set())
    monkeypatch.setattr(research_catalog, "paper_book_approved_keys", lambda: set())
    research_jobs._LAST_GOOD_JOBS = None


def _write_jobs(path, jobs: list[dict]) -> None:
    path.write_text(json.dumps({"jobs": jobs}), encoding="utf-8")


def _orb_row(*, side: str = "BOTH") -> dict:
    return {
        "id": "opening_range_breakout@1h/1h",
        "family": "opening_range_breakout",
        "name": "opening_range_breakout 1h BOTH",
        "clock": "1h/1h",
        "side": side,
        "justification": "CLOCK_BY_FAMILY leftover",
        "param_change": {"clock": "1h/1h"},
    }


def _fresh_row() -> dict:
    return {
        "id": "fresh_session_family@4h/4h",
        "family": "fresh_session_family",
        "name": "fresh_session_family 4h BOTH",
        "clock": "4h/4h",
        "side": "BOTH",
        "justification": "Inbox-approved new brief",
        "param_change": {"clock": "4h/4h"},
    }


def _arm(monkeypatch, tmp_path, jobs: list[dict], remaining: list[dict]):
    """Point the ledger and the catalog at this test, and keep auto-advance off."""
    from dataclasses import replace

    from config.pipeline import pipeline_config
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _write_jobs(tmp_path / "research_jobs.json", jobs)
    monkeypatch.setattr(research_catalog, "remaining_hypotheses", lambda jobs=None: list(remaining))
    manual = replace(pipeline_config(), auto_advance=False)
    monkeypatch.setattr("config.pipeline.pipeline_config", lambda: manual)
    return research_jobs


def _proposal_count() -> int:
    from sqlalchemy import func, select

    from core.db import session_scope
    from firm.memory_models import Proposal

    with session_scope() as session:
        return int(session.scalar(select(func.count()).select_from(Proposal)) or 0)


def _file_next(research_jobs) -> None:
    """Job completion is what used to file the repeated walk-forward ask."""
    research_jobs._notify_job_complete(
        {
            "id": 99,
            "family": "ema_adx_trend",
            "status": "done",
            "clock": "4h/4h",
            "side": "BOTH",
            "pairs_approved": 0,
            "inbox_posted": False,
            "detail": "finished",
        }
    )


def _suppressed(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        rec.message
        for rec in caplog.records
        if rec.message.startswith("Suppressing next-step")
    ]


@pytest.fixture
def info_log(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    caplog.set_level(logging.INFO, logger="firm.research_jobs")
    return caplog


def test_terminal_approved_suppresses_walk_forward_ask(
    tmp_path, monkeypatch, firm_db, info_log
) -> None:
    """An approved family@clock@side is not proposed again after the next job."""
    research_jobs = _arm(
        monkeypatch,
        tmp_path,
        [
            {
                "id": 7,
                "family": "opening_range_breakout",
                "status": "done",
                "clock": "1h/1h",
                "side": "BOTH",
                "pairs_approved": 2,
            }
        ],
        [_orb_row()],
    )
    _file_next(research_jobs)
    assert _proposal_count() == 0
    assert _suppressed(info_log) == [
        "Suppressing next-step Inbox ask walk-forward opening_range_breakout 1h/1h BOTH: approved"
    ]


def test_rejected_inbox_ask_is_not_refiled(tmp_path, monkeypatch, firm_db, info_log) -> None:
    """A previously rejected identical ask stays rejected. BOTH covers LONG."""
    from firm import memory

    research_jobs = _arm(monkeypatch, tmp_path, [], [_orb_row(side="BOTH")])
    pid = memory.record_proposal(
        agent="research_pipeline",
        kind=ProposalKind.STRATEGY,
        title="Next: walk-forward opening_range_breakout 1h BOTH",
        payload={
            "action": "walk_forward",
            "family": "opening_range_breakout",
            "name": "opening_range_breakout",
            "clock": "1h",
            "side": "LONG",
        },
        rationale="operator already rejected this grid",
        confidence=0.4,
        ttl=timedelta(days=14),
    )
    assert memory.decide_proposal(pid, approved=False, decided_by="operator", reason="no")
    _file_next(research_jobs)
    assert _proposal_count() == 1
    assert memory.pending_proposals(limit=20) == []
    assert _suppressed(info_log) == [
        "Suppressing next-step Inbox ask walk-forward opening_range_breakout 1h/1h BOTH: "
        "previously rejected identical Inbox ask"
    ]


def test_completed_grid_suppresses_walk_forward_ask(
    tmp_path, monkeypatch, firm_db, info_log
) -> None:
    """A finished grid (paper book / history) is terminal even after a ledger reset.

    The jobs file does not mention opening_range. LONG on the book still
    covers a BOTH ask.
    """
    from firm.research_catalog import coverage_keys

    research_jobs = _arm(
        monkeypatch,
        tmp_path,
        [
            {
                "id": 3,
                "family": "ema_adx_trend",
                "status": "done",
                "clock": "4h/4h",
                "side": "BOTH",
                "pairs_approved": 0,
            }
        ],
        [_orb_row()],
    )
    finished = coverage_keys("opening_range_breakout", "1h/1h", "LONG")
    monkeypatch.setattr(
        "firm.research_catalog.paper_book_finished_keys",
        lambda: set(finished),
    )
    _file_next(research_jobs)
    assert _proposal_count() == 0
    assert _suppressed(info_log) == [
        "Suppressing next-step Inbox ask walk-forward "
        "opening_range_breakout 1h/1h BOTH: completed grid"
    ]

    from firm import research_jobs as jobs_mod

    gate = jobs_mod.ensure_next_gate()
    assert gate["filed"] is False
    assert gate["reason"] == "terminal_family_idle"
    assert _proposal_count() == 0


def test_new_family_still_gets_walk_forward_ask(tmp_path, monkeypatch, firm_db, info_log) -> None:
    """A terminal leftover is skipped. The next family that is actually open is filed."""
    from firm import memory

    research_jobs = _arm(
        monkeypatch,
        tmp_path,
        [
            {
                "id": 4,
                "family": "opening_range_breakout",
                "status": "done",
                "clock": "1h/1h",
                "side": "BOTH",
                "pairs_approved": 0,
            }
        ],
        [_orb_row(), _fresh_row()],
    )
    _file_next(research_jobs)
    pending = memory.pending_proposals(limit=20)
    assert _proposal_count() == 1
    assert pending[0]["payload"]["family"] == "fresh_session_family"
    assert pending[0]["payload"]["action"] == "walk_forward"
    assert pending[0]["payload"]["clock"] == "4h/4h"
    assert pending[0]["payload"]["side"] == "BOTH"
    assert _suppressed(info_log) == [
        "Suppressing next-step Inbox ask walk-forward "
        "opening_range_breakout 1h/1h BOTH: completed grid"
    ]


def test_pending_identical_ask_is_not_duplicated(tmp_path, monkeypatch, firm_db, info_log) -> None:
    """An identical pending ask is a duplicate. Do not file a second copy."""
    from firm import memory

    research_jobs = _arm(monkeypatch, tmp_path, [], [_orb_row()])
    memory.record_proposal(
        agent="research_pipeline",
        kind=ProposalKind.STRATEGY,
        title="Next: walk-forward opening_range_breakout 1h BOTH",
        payload={
            "action": "walk_forward",
            "family": "opening_range_breakout",
            "name": "opening_range_breakout",
            "clock": "1h/1h",
            "side": "BOTH",
        },
        rationale="already waiting",
        confidence=0.4,
        ttl=timedelta(days=14),
    )
    _file_next(research_jobs)
    assert _proposal_count() == 1
    assert len(memory.pending_proposals(limit=20)) == 1
    assert _suppressed(info_log) == [
        "Suppressing next-step Inbox ask walk-forward opening_range_breakout 1h/1h BOTH: "
        "duplicate pending Inbox ask"
    ]
