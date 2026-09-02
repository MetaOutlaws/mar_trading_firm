"""Duty board, LLM timeout routing, and Quant retry after a failed Gemini call."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from firm.health_filters import is_transient_llm_error
from firm.memory_models import RunStatus
from firm import memory


def test_gemini_timeout_is_transient_not_noise() -> None:
    assert is_transient_llm_error("gemini call failed: The read operation timed out")
    assert not is_transient_llm_error("Skipped: set DEEPSEEK_API_KEY. This seat uses deepseek-chat.")


def test_escalate_once_does_not_duplicate(firm_db) -> None:
    first = memory.escalate_once("ops_engineer", "LLM timeout: quant_researcher", "detail")
    second = memory.escalate_once("ops_engineer", "LLM timeout: quant_researcher", "again")
    assert first is not None
    assert second is None
    open_rows = memory.open_escalations()
    assert sum(1 for row in open_rows if row["title"] == "LLM timeout: quant_researcher") == 1


def test_timeout_routes_to_ops_escalation(firm_db, monkeypatch, tmp_path) -> None:
    from firm.accountability import notify_employee_failure
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(research_catalog, "WALK_FORWARD_HISTORY_PATH", tmp_path / "wf_history.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_catalog, "paper_book_finished_keys", lambda: set())
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    monkeypatch.setattr("firm.research_jobs.start_job", lambda job_id: True)

    result = notify_employee_failure(
        "quant_researcher", "gemini call failed: The read operation timed out"
    )
    assert result["alerted"] is True
    titles = [row["title"] for row in memory.open_escalations()]
    assert "LLM timeout: quant_researcher" in titles


def test_idle_pipeline_with_untested_catalog_is_gm_slip(firm_db, monkeypatch) -> None:
    from firm.accountability import accountability_snapshot

    monkeypatch.setattr("firm.research_jobs.open_code_mandates", lambda: [])
    monkeypatch.setattr("firm.continuity.auto_advance_allowed", lambda: (True, "ok"))
    monkeypatch.setattr(
        "firm.research_jobs.list_jobs",
        lambda: [
            {"family": "rsi_trend", "status": "done", "pairs_approved": 0},
            {"family": "donchian_breakout", "status": "done", "pairs_approved": 0},
            {"family": "ema_adx_trend", "status": "done", "pairs_approved": 0},
            {"family": "bollinger_mean_reversion", "status": "done", "pairs_approved": 0},
            {"family": "trend_pullback_htf", "status": "done", "pairs_approved": 0},
        ],
    )
    monkeypatch.setattr(
        "firm.research_catalog.remaining_hypotheses",
        lambda jobs=None: [
            {
                "id": "atr_channel_breakout@1h/1h",
                "family": "atr_channel_breakout",
                "clock": "1h/1h",
                "side": "BOTH",
            }
        ],
    )
    monkeypatch.setattr("firm.memory.pending_proposals", lambda limit=40: [])
    monkeypatch.setattr(
        "firm.integrity.certify_paper",
        lambda: {"ok": True, "checks": []},
    )
    snap = accountability_snapshot()
    gm = next(d for d in snap["duties"] if d["id"] == "desk_head")
    assert gm["on_track"] is False
    assert snap["pipeline_moving"] is False
    issues = [s["issue"] for s in snap["slips"] if s["owner"] == "desk_head"]
    assert any("atr_channel_breakout" in i for i in issues)
    advisor = next(d for d in snap["duties"] if d["id"] == "strategy_advisor")
    assert advisor["on_track"] is False


def test_uncoded_mandate_is_a_gm_slip(firm_db, monkeypatch) -> None:
    from firm.accountability import accountability_snapshot

    monkeypatch.setattr(
        "firm.research_jobs.open_code_mandates",
        lambda: [{"family": "trend_pullback_htf", "phase": "implement"}],
    )
    monkeypatch.setattr("firm.research_jobs.list_jobs", lambda: [])
    monkeypatch.setattr(
        "firm.integrity.certify_paper",
        lambda: {"ok": True, "checks": []},
    )
    snap = accountability_snapshot()
    issues = [s["issue"] for s in snap["slips"]]
    assert any("not in the registry" in i for i in issues)
    assert snap["pipeline_moving"] is False


def test_drained_catalog_with_approvals_is_not_a_gm_slip(firm_db, monkeypatch) -> None:
    from firm.accountability import accountability_snapshot

    monkeypatch.setattr("firm.research_jobs.open_code_mandates", lambda: [])
    monkeypatch.setattr("firm.research_catalog.remaining_hypotheses", lambda jobs=None: [])
    monkeypatch.setattr("firm.research_catalog.next_catalog_step", lambda **kwargs: None)
    monkeypatch.setattr(
        "firm.research_jobs.list_jobs",
        lambda: [
            {
                "family": "atr_channel_breakout",
                "status": "done",
                "pairs_approved": 2,
            }
        ],
    )
    monkeypatch.setattr("firm.memory.pending_proposals", lambda limit=40: [])
    monkeypatch.setattr(
        "firm.integrity.certify_paper",
        lambda: {"ok": True, "checks": []},
    )
    snap = accountability_snapshot()
    gm = next(d for d in snap["duties"] if d["id"] == "desk_head")
    assert gm["on_track"] is True
    assert not any(s["owner"] == "desk_head" for s in snap["slips"])


def test_quant_retries_after_timeout_not_twelve_hours(firm_db, monkeypatch) -> None:
    from firm.accountability import quant_should_run_now
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", firm_db.parent / "jobs.json")
    (firm_db.parent / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    monkeypatch.setattr("firm.memory.pending_proposals", lambda limit=40: [])
    monkeypatch.setattr("firm.research_jobs.open_code_mandates", lambda: [])

    run_id = memory.start_run("quant_researcher", "Quant Researcher", "agenda")
    memory.finish_run(
        run_id,
        RunStatus.FAILED,
        error="gemini call failed: The read operation timed out",
    )
    # Stamp the run as 20 minutes ago so the 10-minute retry window has elapsed.
    from core.db import session_scope
    from firm.memory_models import AgentRun

    old = datetime.now(timezone.utc) - timedelta(minutes=20)
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        row.started_at = old
        row.finished_at = old

    assert quant_should_run_now() is True


def test_quant_does_not_retry_within_ten_minutes(firm_db, monkeypatch) -> None:
    from firm.accountability import quant_should_run_now
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", firm_db.parent / "jobs.json")
    (firm_db.parent / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    monkeypatch.setattr("firm.memory.pending_proposals", lambda limit=40: [])
    monkeypatch.setattr("firm.research_jobs.open_code_mandates", lambda: [])

    run_id = memory.start_run("quant_researcher", "Quant Researcher", "agenda")
    memory.finish_run(
        run_id,
        RunStatus.FAILED,
        error="gemini call failed: The read operation timed out",
    )
    assert quant_should_run_now() is False


def test_recovered_timeout_is_not_a_live_failure(firm_db, monkeypatch, tmp_path) -> None:
    from firm.accountability import (
        clear_recovered_timeout_alerts,
        live_llm_failures,
        notify_employee_failure,
    )
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(research_catalog, "WALK_FORWARD_HISTORY_PATH", tmp_path / "wf_history.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_catalog, "paper_book_finished_keys", lambda: set())
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    monkeypatch.setattr("firm.research_jobs.start_job", lambda job_id: True)

    fail_id = memory.start_run("quant_researcher", "Quant Researcher", "agenda")
    memory.finish_run(
        fail_id,
        RunStatus.FAILED,
        error="gemini call failed: The read operation timed out",
    )
    notify_employee_failure(
        "quant_researcher", "gemini call failed: The read operation timed out"
    )
    memory.escalate_once(
        "ops_engineer",
        "Live LLM Timeout / Gemini Read Timeout",
        "historical failed rows",
    )
    assert any(row["agent"] == "quant_researcher" for row in live_llm_failures())

    ok_id = memory.start_run("quant_researcher", "Quant Researcher", "agenda")
    memory.finish_run(ok_id, RunStatus.SUCCESS, output={"ok": True}, confidence=0.9)
    assert live_llm_failures() == []
    assert clear_recovered_timeout_alerts() >= 1
    titles = [row["title"] for row in memory.open_escalations()]
    assert "LLM timeout: quant_researcher" not in titles
    assert "Live LLM Timeout / Gemini Read Timeout" not in titles


def test_refresh_scan_plan_switches_sleeve(tmp_path, monkeypatch) -> None:
    from config.universe import Universe, get_universe
    from core.execution.engine import build_plan
    from firm import research_jobs

    live = get_universe()
    monkeypatch.setattr(
        "core.execution.engine.get_universe",
        lambda: Universe(
            long_params=live.long_params,
            short_params=live.short_params,
            approvals={},
        ),
    )
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":[{"family":"donchian_breakout","status":"done","symbols":["BTCUSDT"]}]}',
        encoding="utf-8",
    )
    first = build_plan(require_approval=False, candidates=["BTCUSDT"])
    first_names = {e.strategy.name for e in first.entries}
    assert "donchian_breakout" in first_names
    assert first_names <= {"donchian_breakout", "atr_channel_breakout"}

    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":['
        '{"family":"donchian_breakout","status":"done","symbols":["BTCUSDT"]},'
        '{"family":"bollinger_mean_reversion","status":"running","symbols":["BTCUSDT"]}'
        "]}",
        encoding="utf-8",
    )
    second = build_plan(require_approval=False, candidates=["BTCUSDT"])
    second_names = {e.strategy.name for e in second.entries}
    assert "bollinger_mean_reversion" in second_names
    assert second_names <= {"bollinger_mean_reversion", "atr_channel_breakout"}


def test_named_strategy_does_not_fall_back_to_rsi() -> None:
    from core.execution.engine import _named_strategy
    from core.strategy.base import SignalSide

    sleeve = _named_strategy("bollinger_mean_reversion", "BTCUSDT", SignalSide.LONG)
    assert sleeve.name == "bollinger_mean_reversion"
    assert sleeve.params.side is SignalSide.LONG
