"""Inbox approve must queue a walk-forward; auditor findings must not."""

from __future__ import annotations

from config.universe import parse_approval_key
from config.pipeline import APPROVED_RESEARCH_SYMBOLS
from firm.research_jobs import infer_family, on_strategy_approved


def _isolate_finished_grids(monkeypatch, tmp_path) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_catalog, "WALK_FORWARD_HISTORY_PATH", tmp_path / "wf_history.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_catalog, "paper_book_finished_keys", lambda: set())
    research_jobs._LAST_GOOD_JOBS = None


def test_research_majors_include_bnb_xrp_avax() -> None:
    assert APPROVED_RESEARCH_SYMBOLS == (
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "AVAXUSDT",
    )


def test_infer_family_from_title_and_payload() -> None:
    assert infer_family({"name": "donchian_breakout"}, "") == "donchian_breakout"
    assert infer_family({}, "Donchian on majors") == "donchian_breakout"
    assert infer_family({"name": "rsi_trend"}, "") == "rsi_trend"
    assert infer_family({}, "Funding rate fade") == "funding_fade"
    assert infer_family({}, "Bollinger fade in chop") == "bollinger_mean_reversion"
    assert infer_family({"name": "ema_adx_trend"}, "") == "ema_adx_trend"
    assert infer_family({}, "ATR channel breakout") == "atr_channel_breakout"
    assert infer_family({}, "4h trend 1h pullback") == "trend_pullback_htf"
    assert infer_family({}, "Next: code UTC opening-range breakout") == "opening_range_breakout"
    assert infer_family({"family": "utc_session_vwap_reversion"}, "Donchian on majors") == (
        "utc_session_vwap_reversion"
    )


def test_parse_approval_key_legacy_and_namespaced() -> None:
    assert parse_approval_key("BTCUSDT:LONG") == ("rsi_trend", "BTCUSDT", "LONG")
    assert parse_approval_key("donchian_breakout:ETHUSDT:SHORT") == (
        "donchian_breakout",
        "ETHUSDT",
        "SHORT",
    )
    assert parse_approval_key("donchian_breakout:BTCUSDT:LONG:15m") == (
        "donchian_breakout",
        "BTCUSDT",
        "LONG",
    )
    assert parse_approval_key("_generated_at") is None
    assert parse_approval_key("not-a-key") is None


def test_non_strategy_approve_does_not_queue() -> None:
    result = on_strategy_approved(
        {"id": 9, "kind": "risk", "title": "Veto BTC", "payload": {}, "status": "approved"}
    )
    assert result["queued"] is False
    assert "not a strategy" in result["next_step"].lower()


def test_coded_family_queues_without_spawning(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)

    result = on_strategy_approved(
        {
            "id": 3,
            "kind": "strategy",
            "title": "Donchian breakout on majors",
            "payload": {"name": "donchian_breakout", "symbols": ["BTCUSDT", "ETHUSDT"]},
            "status": "approved",
        }
    )
    assert result["queued"] is True
    assert result["family"] == "donchian_breakout"
    assert "Walk-forward" in result["next_step"]
    jobs = research_jobs.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["family"] == "donchian_breakout"
    assert jobs[0]["symbols"] == [
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "AVAXUSDT",
    ]
    assert jobs[0]["side"] == "BOTH"


def test_uncoded_family_is_blocked_not_spawned(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: spawned.append(job_id) or True)
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)

    result = on_strategy_approved(
        {
            "id": 4,
            "kind": "strategy",
            "title": "Funding fade on majors",
            "payload": {"name": "funding_fade"},
            "status": "approved",
        }
    )
    assert result["queued"] is False
    assert result["family"] == "funding_fade"
    assert spawned == []
    assert research_jobs.list_jobs() == []


def test_catch_up_only_starts_coded_untested_families(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)
    monkeypatch.setattr("firm.memory.approved_code_mandates", lambda limit=20: [])
    monkeypatch.setattr(
        "firm.memory.decided_strategy_proposals",
        lambda limit=20: [
            {
                "id": 1,
                "kind": "strategy",
                "status": "approved",
                "title": "RSI again",
                "payload": {"name": "rsi_trend"},
            },
            {
                "id": 2,
                "kind": "strategy",
                "status": "approved",
                "title": "vague idea",
                "payload": {"name": "mystery_sleeve"},
            },
            {
                "id": 3,
                "kind": "strategy",
                "status": "approved",
                "title": "Donchian breakout",
                "payload": {"name": "donchian_breakout"},
            },
        ],
    )
    result = research_jobs.catch_up_approved_proposals()
    assert result["started"] == [1]
    jobs = research_jobs.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["family"] == "donchian_breakout"


def test_paper_scan_family_follows_latest_coded_job(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":[{"family":"donchian_breakout","status":"running","symbols":["BTCUSDT"]}]}',
        encoding="utf-8",
    )
    assert research_jobs.paper_scan_family() == "donchian_breakout"


def test_paper_plan_scans_donchian_when_that_job_is_running(tmp_path, monkeypatch) -> None:
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
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":[{"family":"donchian_breakout","status":"running","symbols":["BTCUSDT"]}]}',
        encoding="utf-8",
    )
    plan = build_plan(require_approval=False, candidates=["BTCUSDT"])
    assert plan.entries
    donch = [e for e in plan.entries if e.strategy.name == "donchian_breakout"]
    assert donch
    clocks = {entry.side.value: entry.timeframe for entry in donch}
    assert clocks["LONG"] == "1h"
    assert clocks["SHORT"] == "4h"


def test_three_part_approval_keys_are_readable() -> None:
    from config.universe import Universe

    universe = Universe(
        approvals={
            "donchian_breakout:BTCUSDT:LONG": {"approved": True},
            "ETHUSDT:SHORT": {"approved": True},
            "rsi_trend:SOLUSDT:LONG": {"approved": False},
            "donchian_breakout:BTCUSDT:LONG:15m": {"approved": False},
        }
    )
    assert universe.is_approved("BTCUSDT", "LONG")
    assert universe.is_approved("ETHUSDT", "SHORT")
    assert not universe.is_approved("SOLUSDT", "LONG")
    assert ("BTCUSDT", "LONG") in universe.approved_pairs
    assert ("ETHUSDT", "SHORT") in universe.approved_pairs


def test_write_approvals_keeps_separate_timeframes(tmp_path) -> None:
    """A 1h Donchian run must not erase the 15m LONG rows."""
    import json

    from research.validate import SymbolVerdict, write_approvals

    path = tmp_path / "approved_strategies.json"
    write_approvals(
        [
            SymbolVerdict(
                symbol="BTCUSDT",
                side="LONG",
                timeframe="15m",
                strategy="donchian_breakout",
                failures=["OOS profit factor 0.68 < 1.15"],
            )
        ],
        path=path,
    )
    write_approvals(
        [
            SymbolVerdict(
                symbol="BTCUSDT",
                side="LONG",
                timeframe="1h",
                strategy="donchian_breakout",
                failures=["OOS profit factor 0.81 < 1.15"],
            )
        ],
        path=path,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "donchian_breakout:BTCUSDT:LONG:15m" in data
    assert "donchian_breakout:BTCUSDT:LONG:1h" in data
    assert data["donchian_breakout:BTCUSDT:LONG:15m"]["oos_profit_factor"] is None
    assert data["donchian_breakout:BTCUSDT:LONG:15m"]["failures"][0].startswith("OOS profit factor 0.68")


def test_migrate_approval_keys_adds_timeframe() -> None:
    from config.universe import migrate_approval_keys

    migrated = migrate_approval_keys(
        {
            "_generated_at": "x",
            "BTCUSDT:LONG": {"approved": False, "timeframe": "15m"},
            "donchian_breakout:ETHUSDT:LONG": {"approved": False, "timeframe": "1h"},
        }
    )
    assert "rsi_trend:BTCUSDT:LONG:15m" in migrated
    assert "donchian_breakout:ETHUSDT:LONG:1h" in migrated
    assert "BTCUSDT:LONG" not in migrated
    assert migrated["_generated_at"] == "x"


def test_research_plan_has_ranked_backlog() -> None:
    from core.strategy.registry import list_strategies
    from firm.research_catalog import research_plan

    plan = research_plan()
    ids = {row["id"] for row in plan["families"]}
    assert "atr_channel_breakout" in ids
    assert any(row["id"] == "trend_pullback_htf" for row in plan["families"])
    htf = next(row for row in plan["families"] if row["id"] == "trend_pullback_htf")
    assert htf["status"] == "rejected"
    atr = next(row for row in plan["families"] if row["id"] == "atr_channel_breakout")
    assert atr["coded"] is True
    coded = set(list_strategies())
    assert "session_liquidity_sweep" in coded
    assert "bar_vwap_inflow_surge" in coded
    assert "fib_retracement_bounce" in coded
    assert "fib_extension_break" in coded
    assert "measured_move_break" in coded
    assert "up_down_turnover_imbalance" in coded
    assert "signed_range_turnover_trend" in coded
    assert "swing_anchored_vwap_pullback" in coded
    novel_ready = {row["family"] for row in (plan.get("novel_ready") or [])}
    assert "session_liquidity_sweep" not in novel_ready
    assert "bar_vwap_inflow_surge" not in novel_ready
    assert "fib_retracement_bounce" not in novel_ready
    assert "fib_extension_break" not in novel_ready
    assert "measured_move_break" not in novel_ready
    assert "up_down_turnover_imbalance" not in novel_ready
    assert "signed_range_turnover_trend" not in novel_ready
    assert "swing_anchored_vwap_pullback" not in novel_ready
    assert "kama_trend" not in novel_ready
    next_to_code = plan.get("next_to_code")
    if next_to_code is not None:
        assert next_to_code["family"] not in coded
    assert plan["lessons"]
    assert "next_tests" in plan
    assert isinstance(plan["next_tests"], list)


def test_code_family_approve_starts_walk_forward_when_coded(tmp_path, monkeypatch) -> None:
    from firm import research_jobs
    from firm.research_jobs import on_operator_approved

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)

    result = on_operator_approved(
        {
            "id": 29,
            "kind": "operational",
            "title": "Next: code EMA trend + ADX pullback",
            "payload": {"action": "code_family", "family": "ema_adx_trend"},
            "status": "approved",
        }
    )
    assert result["queued"] is True
    assert result["family"] == "ema_adx_trend"
    assert "second time" in result["next_step"].lower()
    jobs = research_jobs.list_jobs()
    assert jobs[0]["family"] == "ema_adx_trend"


def test_code_family_approve_starts_opening_range_when_coded(tmp_path, monkeypatch) -> None:
    from firm import research_jobs
    from firm.research_jobs import on_operator_approved

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)

    result = on_operator_approved(
        {
            "id": 88,
            "kind": "operational",
            "title": "Next: code UTC opening-range breakout",
            "payload": {"action": "code_family", "family": "opening_range_breakout"},
            "status": "approved",
        }
    )
    assert result["queued"] is True
    assert result["family"] == "opening_range_breakout"
    assert result["coding"]["action"] == "already_coded"
    jobs = research_jobs.list_jobs()
    assert jobs[0]["family"] == "opening_range_breakout"
    assert jobs[0]["clock"] == "1h/1h"


def test_catch_up_starts_approved_code_mandate(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)
    monkeypatch.setattr("firm.memory.decided_strategy_proposals", lambda limit=20: [])
    monkeypatch.setattr(
        "firm.memory.approved_code_mandates",
        lambda limit=20: [
            {
                "id": 29,
                "kind": "operational",
                "status": "approved",
                "title": "Next: code EMA trend + ADX pullback",
                "payload": {"action": "code_family", "family": "ema_adx_trend"},
            }
        ],
    )
    result = research_jobs.catch_up_approved_proposals()
    assert result["started"] == [1]
    assert research_jobs.list_jobs()[0]["family"] == "ema_adx_trend"


def test_headline_job_ignores_unknown_blocked(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":['
        '{"family":"donchian_breakout","status":"done","pairs_approved":0,"clock":"1h/4h"},'
        '{"family":"unknown","status":"blocked","detail":"not coded"}'
        "]}",
        encoding="utf-8",
    )
    headline = research_jobs._headline_job(research_jobs.list_jobs())
    assert headline is not None
    assert headline["family"] == "donchian_breakout"


def test_headline_job_prefers_approval_over_old_crash(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":['
        '{"id":58,"family":"engulfing_reversal","status":"failed",'
        '"finished_at":"2026-08-31T17:31:11+00:00","detail":"name _novel_kit"},'
        '{"id":109,"family":"doji_star_reversal","status":"done","pairs_approved":1,'
        '"finished_at":"2026-08-31T19:15:01+00:00"}'
        "]}",
        encoding="utf-8",
    )
    headline = research_jobs._headline_job(research_jobs.list_jobs())
    assert headline["family"] == "doji_star_reversal"


def test_headline_job_skips_code_crash_for_later_reject(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":['
        '{"id":58,"family":"engulfing_reversal","status":"failed",'
        '"finished_at":"2026-08-31T17:31:11+00:00",'
        '"detail":"engulfing_reversal failed: name \'_novel_kit\' is not defined"},'
        '{"id":128,"family":"stochastic_fade","status":"done","pairs_approved":0,'
        '"finished_at":"2026-09-01T03:44:11+00:00","detail":"0 of 6"}'
        "]}",
        encoding="utf-8",
    )
    headline = research_jobs._headline_job(research_jobs.list_jobs())
    assert headline["family"] == "stochastic_fade"


def test_mark_current_prefers_running_test_over_quant_fail() -> None:
    from firm.research_jobs import _mark_current_stage

    stages = [
        {"id": "propose", "state": "bad"},
        {"id": "approve", "state": "done"},
        {"id": "test", "state": "active"},
        {"id": "verdict", "state": "done"},
        {"id": "trade", "state": "wait"},
    ]
    out = _mark_current_stage(stages)
    assert next(s for s in out if s["current"])["id"] == "test"


def test_already_tested_clock_does_not_spawn(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":[{"family":"donchian_breakout","status":"done","clock":"1h/4h","pairs_approved":0}]}',
        encoding="utf-8",
    )
    result = on_strategy_approved(
        {
            "id": 8,
            "kind": "strategy",
            "title": "Donchian again",
            "payload": {"name": "donchian_breakout"},
            "status": "approved",
        }
    )
    assert result["queued"] is False
    assert "already finished" in result["next_step"].lower()


def test_next_step_after_htf_is_opening_range_walk_forward(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":['
        '{"family":"rsi_trend","status":"done","pairs_approved":0},'
        '{"family":"donchian_breakout","status":"done","clock":"1h/4h","pairs_approved":0},'
        '{"family":"ema_adx_trend","status":"done","pairs_approved":0},'
        '{"family":"bollinger_mean_reversion","status":"done","pairs_approved":0},'
        '{"family":"trend_pullback_htf","status":"done","pairs_approved":0}'
        "]}",
        encoding="utf-8",
    )
    spec = research_jobs._next_step_spec(
        {"family": "trend_pullback_htf", "status": "done", "pairs_approved": 0}
    )
    assert spec is not None
    assert spec["family"] == "opening_range_breakout"
    assert spec["action"] == "walk_forward"
    assert spec["clock"] == "1h/1h"
    assert spec["family"] != "funding_fade"


def test_next_step_prefers_uncoded_opening_range_before_atr_followup(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":['
        '{"family":"atr_channel_breakout","status":"done","clock":"4h/4h","pairs_approved":0}'
        "]}",
        encoding="utf-8",
    )
    spec = research_jobs._next_step_spec(
        {"family": "atr_channel_breakout", "status": "done", "clock": "4h/4h", "pairs_approved": 0}
    )
    assert spec is not None
    assert spec["family"] == "opening_range_breakout"
    assert spec["clock"] == "1h/1h"
    assert spec["action"] == "walk_forward"


def test_ensure_next_gate_files_next_novel_when_grid_exhausted(tmp_path, monkeypatch, firm_db) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":['
        '{"family":"rsi_trend","status":"done","pairs_approved":0},'
        '{"family":"donchian_breakout","status":"done","clock":"1h/4h","pairs_approved":0},'
        '{"family":"ema_adx_trend","status":"done","pairs_approved":0},'
        '{"family":"bollinger_mean_reversion","status":"done","pairs_approved":0},'
        '{"family":"trend_pullback_htf","status":"done","pairs_approved":0},'
        '{"family":"atr_channel_breakout","status":"done","clock":"4h/4h","pairs_approved":0},'
        '{"family":"atr_channel_breakout","status":"done","clock":"1h/1h","pairs_approved":0}'
        "]}",
        encoding="utf-8",
    )
    monkeypatch.setattr("firm.memory.pending_proposals", lambda limit=40: [])
    monkeypatch.setattr("firm.research_jobs.open_code_mandates", lambda: [])
    monkeypatch.setattr(research_jobs, "_already_decided_catalog_review", lambda: False)
    monkeypatch.setattr("firm.research_catalog.remaining_hypotheses", lambda jobs=None: [])
    recorded: list[dict] = []

    def _record(**kwargs):
        recorded.append(kwargs)
        return 1

    monkeypatch.setattr("firm.memory.record_proposal", _record)
    result = research_jobs.ensure_next_gate()
    assert result["filed"] is True
    assert result["action"] in {"code_family", "catalog_review", "walk_forward"}
    if result["action"] == "code_family":
        from core.strategy.registry import list_strategies

        assert recorded[0]["payload"]["family"] not in set(list_strategies())


def test_ensure_next_gate_does_not_file_review_after_approvals(
    tmp_path, monkeypatch, firm_db
) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":[{"family":"atr_channel_breakout","status":"done","pairs_approved":2}]}',
        encoding="utf-8",
    )
    monkeypatch.setattr("firm.memory.pending_proposals", lambda limit=40: [])
    monkeypatch.setattr("firm.research_jobs.open_code_mandates", lambda: [])
    monkeypatch.setattr("firm.research_catalog.remaining_hypotheses", lambda jobs=None: [])
    monkeypatch.setattr(research_jobs, "next_catalog_step", lambda **kwargs: None)
    recorded: list[dict] = []
    monkeypatch.setattr("firm.memory.record_proposal", lambda **kwargs: recorded.append(kwargs) or 1)
    result = research_jobs.ensure_next_gate()
    assert result["filed"] is False
    assert result["reason"] == "approvals_exist_catalog_drained"
    assert recorded == []


def test_now_banner_shows_approved_mandate_not_idle_ema() -> None:
    from firm.research_jobs import _now_banner

    banner = _now_banner(
        {"family": "ema_adx_trend", "status": "done", "pairs_approved": 0},
        "done",
        "ema done",
        [],
        "done",
        [{"family": "bollinger_mean_reversion", "phase": "start_test"}],
        [],
    )
    assert "bollinger" in banner["label"].lower()
    assert banner["state"] == "active"


def test_now_banner_uncoded_mandate_is_blocked_not_progress() -> None:
    from firm.research_jobs import _now_banner

    banner = _now_banner(
        {"family": "bollinger_mean_reversion", "status": "done"},
        "blocked",
        "not coded",
        [],
        "done",
        [{"family": "trend_pullback_htf", "phase": "implement"}],
        [],
    )
    assert banner["state"] == "bad"
    assert "not coded" in banner["label"].lower() or "blocked" in banner["label"].lower()


def test_mark_current_prefers_live_test_over_done_quant() -> None:
    from firm.research_jobs import _mark_current_stage

    stages = _mark_current_stage(
        [
            {"id": "propose", "state": "done"},
            {"id": "approve", "state": "done"},
            {"id": "test", "state": "active"},
            {"id": "verdict", "state": "wait"},
            {"id": "trade", "state": "wait"},
        ]
    )
    current = [s["id"] for s in stages if s.get("current")]
    assert current == ["test"]


def test_quant_progress_running_is_not_complete() -> None:
    from datetime import datetime, timedelta, timezone
    from firm.research_jobs import _quant_progress

    started = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    bar = _quant_progress({"status": "running", "started_at": started})
    assert bar["progress"] is not None
    assert bar["progress"] < 100
    assert "typical" in bar["progress_label"]


def test_open_code_mandates_phases(tmp_path, monkeypatch) -> None:
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    monkeypatch.setattr(
        "firm.memory.approved_code_mandates",
        lambda limit=20: [
            {
                "id": 30,
                "status": "approved",
                "title": "Next: code Bollinger fade in chop",
                "payload": {"action": "code_family", "family": "bollinger_mean_reversion"},
            }
        ],
    )
    rows = research_jobs.open_code_mandates()
    assert rows[0]["family"] == "bollinger_mean_reversion"
    assert rows[0]["phase"] == "start_test"


def test_mark_current_prefers_running_quant_over_queued_test() -> None:
    from firm.research_jobs import _mark_current_stage

    stages = _mark_current_stage(
        [
            {"id": "propose", "state": "active"},
            {"id": "approve", "state": "done"},
            {"id": "test", "state": "active"},
        ]
    )
    current = [s["id"] for s in stages if s.get("current")]
    assert current == ["test"]


def test_now_banner_running_quant_beats_implement_mandate() -> None:
    from firm.research_jobs import _now_banner

    banner = _now_banner(
        {"family": "bollinger_mean_reversion", "status": "done"},
        "queued",
        "implementing",
        [],
        "active",
        [{"family": "trend_pullback_htf", "phase": "implement"}],
        [],
        {"progress": 40, "progress_label": "30s / ~90s typical"},
    )
    assert "quant" in banner["label"].lower()
    assert "30s" in banner["detail"]


def test_pending_code_family_does_not_block_a_sibling(firm_db, monkeypatch) -> None:
    from firm import memory
    from firm.memory_models import ProposalKind
    from firm.research_jobs import _already_pending_next

    memory.record_proposal(
        agent="sleeve_engineer",
        kind=ProposalKind.OPERATIONAL,
        title="Code utc_session_vwap_reversion: fade VWAP",
        payload={"action": "code_family", "family": "utc_session_vwap_reversion"},
        rationale="brief",
        confidence=0.9,
    )
    assert _already_pending_next("code_family", "utc_session_vwap_reversion") is True
    assert _already_pending_next("code_family", "asian_range_breakout") is False


def test_file_novel_inbox_puts_full_brief_on_each_family(firm_db, tmp_path, monkeypatch) -> None:
    from firm import sleeve_factory
    from firm.research_jobs import file_novel_coding_inbox
    from firm import memory

    monkeypatch.setattr(sleeve_factory, "CODING_REQUESTS_DIR", tmp_path)
    result = file_novel_coding_inbox()
    families = {row["family"] for row in result["filed"]}
    assert "kama_trend" not in families
    assert "session_liquidity_sweep" not in families
    assert "volume_force_divergence" not in families
    assert "bar_vwap_inflow_surge" not in families
    assert "fib_retracement_bounce" not in families
    assert "fib_extension_break" not in families
    assert "measured_move_break" not in families
    assert "up_down_turnover_imbalance" not in families
    assert "signed_range_turnover_trend" not in families
    assert "swing_anchored_vwap_pullback" not in families
    pending = memory.pending_proposals(limit=40)
    for row in result["filed"]:
        payload = next(
            (p.get("payload") or {})
            for p in pending
            if (p.get("payload") or {}).get("family") == row["family"]
        )
        assert payload.get("novel") is True
        assert payload.get("brief")
        assert f"core/strategy/{row['family']}.py" in (payload.get("brief") or "")


def test_approve_novel_hands_brief_to_cursor(tmp_path, monkeypatch, firm_db) -> None:
    from firm import cursor_coding, research_jobs
    from firm.research_jobs import on_operator_approved

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(cursor_coding, "QUEUE_PATH", tmp_path / "queue.json")
    monkeypatch.setattr(cursor_coding, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(cursor_coding, "NOW_PATH", tmp_path / "NOW.md")
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)

    family = "momentum_velocity_acceleration"
    result = on_operator_approved(
        {
            "id": 91,
            "kind": "operational",
            "title": f"Code {family}: momentum acceleration",
            "payload": {
                "action": "code_family",
                "family": family,
                "brief": f"# Coding request: {family}\nWrite the acceleration sleeve.",
                "brief_path": f"research/coding_requests/{family}.md",
            },
            "status": "approved",
        }
    )
    assert result.get("handed_to_cursor") is True
    assert "NOW.md" in result["next_step"]
    job = cursor_coding.next_pending()
    assert job is not None
    assert job["family"] == family
    assert family in (tmp_path / "NOW.md").read_text(encoding="utf-8")


def test_jobs_ledger_refuses_to_wipe_on_save(tmp_path, monkeypatch) -> None:
    """A process that loaded empty must not replace a 220-row ledger with ids 1-32."""
    from firm import research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    existing = {
        "jobs": [
            {"id": i, "family": "session_liquidity_sweep", "status": "done", "clock": "1h/1h"}
            for i in range(1, 33)
        ]
        + [
            {
                "id": 220,
                "family": "session_liquidity_sweep",
                "status": "done",
                "clock": "1h/1h",
                "pairs_approved": 0,
            }
        ]
    }
    (tmp_path / "research_jobs.json").write_text(
        __import__("json").dumps(existing), encoding="utf-8"
    )
    research_jobs._LAST_GOOD_JOBS = None
    research_jobs._save(
        [
            {
                "id": 1,
                "family": "atr_channel_breakout",
                "status": "standby",
                "clock": "4h/4h",
                "side": "SHORT",
            }
        ]
    )
    jobs = research_jobs.list_jobs()
    ids = {int(j["id"]) for j in jobs}
    assert 220 in ids
    assert len(jobs) >= 33


def test_new_job_ids_continue_past_history_max(tmp_path, monkeypatch) -> None:
    """Ledger id reset to 1-32 must not reuse those ids for the next walk-forward."""
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "research_jobs.json").write_text(
        '{"jobs":[{"id":1,"family":"atr_channel_breakout","status":"standby","clock":"4h/4h"}]}',
        encoding="utf-8",
    )
    research_catalog.note_job_id(220)
    job = research_jobs._record_job(
        family="fresh_novel_sleeve",
        clock="4h/4h",
        side="BOTH",
        status="standby",
    )
    assert int(job["id"]) == 221
