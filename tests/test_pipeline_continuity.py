"""Pipeline continuity: envelope, same-tick slot fill, hung median, post-mortem."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from config.pipeline import pipeline_config
from firm.envelope import classify_hypothesis
from firm.research_catalog import remaining_hypotheses


def _isolate_finished_grids(monkeypatch, tmp_path) -> None:
    """Keep catalog tests from reading the live paper book or history file."""
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_catalog, "WALK_FORWARD_HISTORY_PATH", tmp_path / "wf_history.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_catalog, "paper_book_finished_keys", lambda: set())
    research_jobs._LAST_GOOD_JOBS = None


def _enable_auto_advance(monkeypatch) -> None:
    """Opt in to auto-start. Default is fail-closed (PIPELINE_AUTO_ADVANCE unset/false)."""
    from config.settings import get_settings

    monkeypatch.setenv("PIPELINE_AUTO_ADVANCE", "true")
    get_settings.cache_clear()


def test_atr_1h_is_tier_a(monkeypatch) -> None:
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    hypo = {
        "id": "atr_channel_breakout@1h/1h",
        "family": "atr_channel_breakout",
        "clock": "1h/1h",
        "rank": 1,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": "frozen min_adx after 4h near-miss",
        "param_change": {"min_adx": [20.0]},
        "needs_feed": False,
        "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    }
    jobs = [
        {
            "family": "atr_channel_breakout",
            "status": "done",
            "clock": "4h/4h",
            "pairs_approved": 0,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    result = classify_hypothesis(hypo, jobs=jobs)
    assert result["tier"] == "A"
    assert result["auto"] is True


def test_funding_fade_is_tier_c() -> None:
    result = classify_hypothesis(
        {
            "id": "funding_fade@4h/4h",
            "family": "funding_fade",
            "clock": "4h/4h",
            "rank": 1,
            "free_params": 2,
            "needs_feed": True,
            "justification": "needs feed",
            "param_change": {},
        }
    )
    assert result["tier"] == "C"


def test_hung_threshold_is_three_times_median() -> None:
    from firm.continuity import hung_threshold_seconds

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    jobs = []
    for i, minutes in enumerate([10, 10, 10, 20, 10]):
        jobs.append(
            {
                "status": "done",
                "started_at": base.isoformat(),
                "finished_at": (base + timedelta(minutes=minutes)).isoformat(),
            }
        )
    jobs.append(
        {
            "status": "done",
            "manual_interrupt": True,
            "started_at": base.isoformat(),
            "finished_at": (base + timedelta(hours=5)).isoformat(),
        }
    )
    # median of 10,10,10,20,10 minutes = 10 min; 3x = 1800s
    assert abs(hung_threshold_seconds(jobs) - 1800) < 1


def test_fill_slots_starts_standby_same_tick(tmp_path, monkeypatch, firm_db) -> None:
    from firm import continuity, pipeline_state, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _enable_auto_advance(monkeypatch)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: spawned.append(job_id) or True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    result = continuity.fill_walk_forward_slots(source="event")
    assert result["started"]
    assert spawned == result["started"]
    jobs = research_jobs.list_jobs()
    live = [j for j in jobs if j.get("status") in {"running", "queued"}]
    assert live
    assert all(j.get("last_updated_by") for j in live)
    assert all(j.get("stage") == "walk_forward" for j in live)


def test_empty_catalog_does_not_spawn_finished_family(tmp_path, monkeypatch, firm_db) -> None:
    """After a ledger reset, CLOCK_BY_FAMILY leftovers must not refill slots."""
    from firm import continuity, pipeline_state, research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: spawned.append(job_id) or True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    leftovers = [
        {
            "id": "atr_channel_breakout@4h/4h@SHORT",
            "family": "atr_channel_breakout",
            "clock": "4h/4h",
            "side": "SHORT",
            "rank": 1,
            "coded": True,
            "name": "ATR 4h shorts leftover",
            "justification": "CLOCK_BY_FAMILY leftover after ledger reset",
            "param_change": {"clock": "4h/4h", "side": "SHORT"},
        },
        {
            "id": "ema_adx_trend@4h/4h@SHORT",
            "family": "ema_adx_trend",
            "clock": "4h/4h",
            "side": "SHORT",
            "rank": 2,
            "coded": True,
            "name": "EMA 4h shorts leftover",
            "justification": "legacy family already had a 4h SHORT grid",
            "param_change": {"clock": "4h/4h", "side": "SHORT"},
        },
    ]
    monkeypatch.setattr(research_catalog, "remaining_hypotheses", lambda jobs=None: leftovers)
    monkeypatch.setattr(continuity, "remaining_hypotheses", lambda jobs=None: leftovers)
    monkeypatch.setattr(research_catalog, "replenish_catalog", lambda **kwargs: [])
    research_catalog.record_finished_walk_forward(
        {
            "id": 50,
            "family": "atr_channel_breakout",
            "clock": "4h/4h",
            "side": "SHORT",
            "status": "done",
            "hypothesis_id": "atr_channel_breakout@4h/4h@SHORT",
        }
    )
    research_catalog.record_finished_walk_forward(
        {
            "id": 12,
            "family": "ema_adx_trend",
            "clock": "4h/4h",
            "side": "SHORT",
            "status": "done",
            "hypothesis_id": "ema_adx_trend@4h/4h@SHORT",
        }
    )
    result = continuity.fill_walk_forward_slots(source="event")
    assert result["started"] == []
    assert spawned == []
    live = [
        j
        for j in research_jobs.list_jobs()
        if j.get("status") in {"running", "queued"}
    ]
    assert live == []
    assert all(
        j.get("family") not in {"atr_channel_breakout", "ema_adx_trend"}
        or j.get("status") not in {"running", "queued", "standby"}
        for j in research_jobs.list_jobs()
    )


def test_explicit_near_miss_queue_still_advances(tmp_path, monkeypatch, firm_db) -> None:
    """Operator-queued frozen near-miss retests still start when catalog is otherwise empty."""
    from firm import continuity, pipeline_state, research_catalog, research_jobs
    from firm.research_catalog import NEAR_MISS_RETESTS

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _enable_auto_advance(monkeypatch)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: spawned.append(job_id) or True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    monkeypatch.setattr(
        continuity,
        "classify_hypothesis",
        lambda *args, **kwargs: {"tier": "A", "checks": {}, "reasons": []},
    )
    monkeypatch.setattr(
        continuity,
        "classify_family_clock",
        lambda *args, **kwargs: {"tier": "A", "checks": {}, "reasons": []},
    )
    row = dict(NEAR_MISS_RETESTS[0])
    row["operator_queued"] = True
    row["added_by"] = "operator"
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    research_catalog.record_finished_walk_forward(
        {
            "id": 80,
            "family": row["family"],
            "clock": row["clock"],
            "side": "BOTH",
            "status": "done",
            "hypothesis_id": f"{row['family']}@{row['clock']}",
        }
    )
    monkeypatch.setattr(research_catalog, "remaining_hypotheses", lambda jobs=None: [row])
    monkeypatch.setattr(continuity, "remaining_hypotheses", lambda jobs=None: [row])
    monkeypatch.setattr(research_catalog, "replenish_catalog", lambda **kwargs: [])
    result = continuity.fill_walk_forward_slots(source="event")
    assert result["started"]
    assert spawned == result["started"]
    jobs = research_jobs.list_jobs()
    live = [j for j in jobs if j.get("status") in {"running", "queued"}]
    assert live
    assert live[0]["hypothesis_id"] == row["id"]
    assert live[0]["family"] == row["family"]


def test_fill_slots_does_not_drain_catalog_when_breaker_tripped(
    tmp_path, monkeypatch, firm_db
) -> None:
    from firm import continuity, pipeline_state, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(continuity, "auto_advance_allowed", lambda: (False, "circuit breaker"))
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: True)
    (tmp_path / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": 1,
                        "family": "ema_adx_trend",
                        "clock": "1h/4h",
                        "side": "BOTH",
                        "status": "standby",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = continuity.fill_walk_forward_slots(source="event")
    assert result.get("blocked") == "circuit breaker"
    jobs = research_jobs.list_jobs()
    assert jobs[0]["status"] == "standby"


def test_breaker_releases_for_a_new_clock(tmp_path, monkeypatch, firm_db) -> None:
    from firm import continuity, pipeline_state, research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _enable_auto_advance(monkeypatch)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    pipeline_state.save_state(
        {
            "circuit_breaker_tripped": True,
            "consecutive_auto_rejects": 3,
            "auto_advances": [
                {"family": "ema_adx_trend", "clock": "1h/1h", "side": "BOTH"},
                {"family": "bollinger_mean_reversion", "clock": "1h/1h", "side": "BOTH"},
                {"family": "donchian_breakout", "clock": "4h/4h", "side": "BOTH"},
            ],
        }
    )
    result = continuity.fill_walk_forward_slots(source="event")
    assert result.get("blocked") in (None, "")
    assert result.get("started")
    state = pipeline_state.load_state()
    assert state.get("circuit_breaker_tripped") is False


def test_budget_exhausted_still_starts_new_followup(tmp_path, monkeypatch, firm_db) -> None:
    """A 10/24h cap must not freeze a different family@clock@side."""
    from firm import continuity, pipeline_state, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _enable_auto_advance(monkeypatch)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    monkeypatch.setattr(
        continuity,
        "auto_advance_allowed",
        lambda: (False, "auto-advance budget 10/24h exhausted"),
    )
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()
    pipeline_state.save_state(
        {
            "auto_advances": [
                {
                    "at": now,
                    "family": "rsi_trend",
                    "clock": "1h/1h",
                    "side": "BOTH",
                }
            ]
            * 10
        }
    )
    result = continuity.fill_walk_forward_slots(source="event")
    assert result.get("started")
    assert not result.get("blocked")


def test_budget_still_blocks_same_grid(tmp_path, monkeypatch, firm_db) -> None:
    """Re-running a grid already auto-started this window stays paused."""
    from firm import continuity, memory, pipeline_state, research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    monkeypatch.setattr(
        continuity,
        "auto_advance_allowed",
        lambda: (False, "auto-advance budget 10/24h exhausted"),
    )
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    leftover = research_catalog.remaining_hypotheses([])
    assert leftover
    nxt = leftover[0]
    now = datetime.now(timezone.utc).isoformat()
    pipeline_state.save_state(
        {
            "auto_advances": [
                {
                    "at": now,
                    "family": nxt["family"],
                    "clock": nxt["clock"],
                    "side": nxt.get("side") or "BOTH",
                }
            ]
            * 10
        }
    )
    result = continuity.fill_walk_forward_slots(source="event")
    assert result.get("started") == []
    assert "budget" in str(result.get("blocked") or "")
    titles = [row["title"] for row in memory.open_escalations()]
    assert any("GM continuity" in t for t in titles)


def test_backstop_fill_is_dropped_event(tmp_path, monkeypatch, firm_db) -> None:
    from firm import continuity, pipeline_state, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _enable_auto_advance(monkeypatch)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    continuity.fill_walk_forward_slots(source="backstop")
    state = pipeline_state.load_state()
    assert state.get("dropped_events")
    assert any(
        row.get("event") == "on_walk_forward_slot_free"
        for row in state["dropped_events"]
    )


def test_empty_standby_opens_ticket(tmp_path, monkeypatch, firm_db) -> None:
    from firm import continuity, pipeline_state, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr("firm.research_catalog.remaining_hypotheses", lambda jobs=None: [])
    monkeypatch.setattr(continuity, "remaining_hypotheses", lambda jobs=None: [])
    monkeypatch.setattr("firm.research_catalog.replenish_catalog", lambda **kwargs: [])
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: True)
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    continuity.evaluate_invariants()
    tickets = pipeline_state.open_tickets()
    assert any(t.get("id") == "standby_floor" for t in tickets)
    assert any(t.get("owner") in {"sleeve_engineer", "quant_researcher"} for t in tickets)


def test_evaluate_invariants_starts_walk_forward_when_idle(
    tmp_path, monkeypatch, firm_db
) -> None:
    """A free slot plus a coded leftover must launch, not only open a ticket."""
    from firm import continuity, pipeline_state, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _enable_auto_advance(monkeypatch)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: spawned.append(job_id) or True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    continuity.evaluate_invariants()
    assert spawned
    live = [j for j in research_jobs.list_jobs() if j.get("status") in {"running", "queued"}]
    assert live


def test_llm_timeout_still_starts_waiting_walk_forward(
    tmp_path, monkeypatch, firm_db
) -> None:
    """Quant Gemini dying must launch the next coded family, not freeze research."""
    from firm import accountability, pipeline_state, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _enable_auto_advance(monkeypatch)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id, explicit=False: spawned.append(job_id) or True)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    accountability.notify_employee_failure(
        "quant_researcher", "gemini call failed: The read operation timed out"
    )
    assert spawned


def test_postmortem_mutates_ranking(tmp_path, monkeypatch) -> None:
    from firm import postmortem

    monkeypatch.setattr(postmortem, "POSTMORTEM_DIR", tmp_path)
    monkeypatch.setattr(postmortem, "RANKING_PATH", tmp_path / "ranking.json")
    report = postmortem.write_postmortem(
        {
            "id": 99,
            "family": "atr_channel_breakout",
            "clock": "4h/4h",
            "side": "BOTH",
            "pairs_approved": 0,
            "detail": "unstable min_adx (cv=0.9); expectancy CI includes zero",
            "hypothesis_id": "atr_channel_breakout@4h/4h",
        }
    )
    assert report["disposition"] == "retire"
    assert (tmp_path / "postmortem_job_99.json").exists()
    ranking = postmortem._load_ranking()
    assert ranking["dispositions"]["atr_channel_breakout@4h/4h"] == "retire"
    assert "atr_channel_breakout@4h/4h" in ranking["retired"]
    assert "atr_channel_breakout@4h/4h@SHORT" in ranking["retired"]


def test_remaining_hypotheses_skips_tested_clock(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "jobs.json").write_text(
        '{"jobs":[{"family":"atr_channel_breakout","status":"done","clock":"1h/1h","side":"BOTH"}]}',
        encoding="utf-8",
    )
    left = remaining_hypotheses(research_jobs.list_jobs())
    ids = [r["id"] for r in left]
    assert "atr_channel_breakout@1h/1h" not in ids
    # Advisor walk order: Inbox families first, leftovers after.
    assert left[0]["family"] == "london_close_inventory_fade"


def test_replenish_catalog_fills_depth(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "jobs.json").write_text(
        '{"jobs":[{"family":"atr_channel_breakout","status":"done","clock":"1h/1h","side":"BOTH"}]}',
        encoding="utf-8",
    )
    added = research_catalog.replenish_catalog(
        jobs=research_jobs.list_jobs(), target=16
    )
    assert added
    assert all(a.get("added_by") == "quant_researcher" for a in added)
    assert all(not str(a.get("clock") or "").startswith("15m") for a in added)
    assert all(a.get("family") != "rsi_trend" for a in added)
    assert all(a.get("id") != "atr_channel_breakout@1h/1h@SHORT" for a in added)
    left = research_catalog.remaining_hypotheses(research_jobs.list_jobs())
    assert len(left) >= 16
    cfg = pipeline_config()
    assert cfg.wf_parallelism >= 1
    assert cfg.catalog_min_unqueued >= 0
    assert cfg.max_free_params == 6


def test_replenish_lands_coded_novel_families(tmp_path, monkeypatch) -> None:
    """Novel Python in the registry must enter the catalog, not only JSON templates."""
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    added = research_catalog.replenish_catalog(
        jobs=research_jobs.list_jobs(), target=1
    )
    families = {str(row.get("family") or "") for row in added}
    assert "stochastic_fade" in families
    assert "cci_reversion" in families
    assert "supertrend_flip" in families
    leftover = research_catalog.remaining_hypotheses(research_jobs.list_jobs())
    leftover_families = {str(row.get("family") or "") for row in leftover}
    assert "stochastic_fade" in leftover_families
    stoch_clocks = [row["clock"] for row in leftover if row["family"] == "stochastic_fade"]
    assert stoch_clocks == ["4h/4h"]


def test_replenish_does_not_clone_clocks_after_primary_zero(tmp_path, monkeypatch) -> None:
    """A 4h 0-for-6 is the verdict. Do not auto-queue 1h of the same sleeve."""
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "jobs.json").write_text(
        '{"jobs":[{"family":"mfi_fade","status":"done","clock":"4h/4h","side":"BOTH","pairs_approved":0}]}',
        encoding="utf-8",
    )
    jobs = research_jobs.list_jobs()
    assert research_catalog.primary_clocks_failed(jobs, "mfi_fade") is True
    added = research_catalog.replenish_catalog(jobs=jobs, target=4)
    assert all(a.get("family") != "mfi_fade" for a in added)
    leftover = research_catalog.remaining_hypotheses(research_jobs.list_jobs())
    assert all(row.get("family") != "mfi_fade" for row in leftover)


def test_enqueue_next_novel_when_catalog_empty(tmp_path, monkeypatch) -> None:
    from firm import cursor_coding, sleeve_factory

    monkeypatch.setattr(cursor_coding, "QUEUE_PATH", tmp_path / "queue.json")
    monkeypatch.setattr(cursor_coding, "INBOX_DIR", tmp_path)
    monkeypatch.setattr(cursor_coding, "NOW_PATH", tmp_path / "NOW.md")
    monkeypatch.setattr(sleeve_factory, "CODING_REQUESTS_DIR", tmp_path)
    from core.strategy.registry import list_strategies

    row = cursor_coding.enqueue_next_novel_if_catalog_empty()
    coded = set(list_strategies())
    if row is None:
        from firm.sleeve_factory import ready_novel_specs

        assert ready_novel_specs() == []
        return
    assert row["family"] not in coded
    assert row["family"] in (tmp_path / "NOW.md").read_text(encoding="utf-8")


def test_both_job_covers_short_on_same_clock() -> None:
    from firm.research_catalog import coverage_keys, hypothesis_tested_keys

    jobs = [
        {
            "family": "rsi_trend",
            "status": "done",
            "clock": "1h/1h",
            "side": "BOTH",
            "pairs_approved": 0,
        }
    ]
    tested = hypothesis_tested_keys(jobs)
    assert "rsi_trend@1h/1h" in tested
    assert "rsi_trend@1h/1h@SHORT" in tested
    assert "rsi_trend@4h/4h@SHORT" not in coverage_keys("rsi_trend", "1h/1h", "BOTH")


def test_postmortem_keeps_short_when_shorts_near_miss(tmp_path, monkeypatch) -> None:
    from firm import postmortem

    monkeypatch.setattr(postmortem, "POSTMORTEM_DIR", tmp_path)
    monkeypatch.setattr(postmortem, "RANKING_PATH", tmp_path / "ranking.json")
    report = postmortem.write_postmortem(
        {
            "id": 100,
            "family": "atr_channel_breakout",
            "clock": "4h/4h",
            "side": "BOTH",
            "pairs_approved": 0,
            "detail": "atr_channel_breakout: 0 of 6 pairs approved.",
            "hypothesis_id": "atr_channel_breakout@4h/4h",
        },
        pair_blurbs=(
            "BTCUSDT SHORT: REJECTED | PF 1.24 | Exp +0.310%/trade; "
            "ETHUSDT LONG: REJECTED | PF 0.80 | Exp -0.20%/trade"
        ),
    )
    assert report["disposition"] == "retest_under_different_regime"
    assert report["keep_short_followup"] is True
    ranking = postmortem._load_ranking()
    assert "atr_channel_breakout@4h/4h@SHORT" not in ranking.get("retired", [])


def test_promote_remaining_into_top5_after_postmortem(tmp_path, monkeypatch) -> None:
    """Finished tests occupying ranks 1–5 must not freeze the next untested ones at 6+."""
    from firm import research_catalog, research_jobs
    from firm.envelope import classify_hypothesis

    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    (tmp_path / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {"family": "atr_channel_breakout", "status": "done", "clock": "1h/1h", "side": "BOTH", "pairs_approved": 0},
                    {"family": "ema_adx_trend", "status": "done", "clock": "1h/1h", "side": "BOTH", "pairs_approved": 0},
                    {"family": "bollinger_mean_reversion", "status": "done", "clock": "1h/1h", "side": "BOTH", "pairs_approved": 0},
                    {"family": "donchian_breakout", "status": "done", "clock": "4h/4h", "side": "BOTH", "pairs_approved": 0},
                    {"family": "atr_channel_breakout", "status": "done", "clock": "1h/4h", "side": "BOTH", "pairs_approved": 0},
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "ranking.json").write_text(
        json.dumps(
            {
                "ranks": {
                    "london_close_inventory_fade@4h/4h": 16,
                    "utc_open_fail_reversion@4h/4h": 16,
                    "range_compression_volume_thrust@4h/4h": 16,
                    "turnover_climax_rejection_fade@4h/4h": 16,
                    "volume_dryup_range_break@4h/4h": 16,
                    "body_efficiency_follow@4h/4h": 16,
                    "week_open_reclaim@4h/4h": 16,
                    "prior_session_mid_reclaim@4h/4h": 16,
                    "close_location_persistence@4h/4h": 16,
                    "open_in_prior_range_fail@4h/4h": 16,
                    "equal_high_low_restest_fade@4h/4h": 16,
                    "double_bottom_neckline_break@4h/4h": 16,
                    "double_top_neckline_break@4h/4h": 16,
                    "ascending_triangle_break@4h/4h": 16,
                    "prior_day_extreme_reject@4h/4h": 16,
                    "failed_range_break_reversion@4h/4h": 16,
                    "asia_range_london_reject@4h/4h": 16,
                    "orb_fail_reversion@4h/4h": 16,
                    "nr7_fail_reversion@4h/4h": 16,
                    "ib_fail_reversion@4h/4h": 16,
                    "converging_wedge_break@4h/4h": 16,
                    "engulfing_fail_reversion@4h/4h": 16,
                    "wyckoff_spring_reclaim@4h/4h": 16,
                    "prior_close_magnet_fade@4h/4h": 16,
                    "classic_floor_pivot_reject@4h/4h": 16,
                    "failed_break_reclaim@4h/4h": 16,
                    "expansion_fail_fade@4h/4h": 16,
                    "candle_reject_reversal@4h/4h": 16,
                    "bullish_rectangle_fail_reclaim@4h/4h": 16,
                    "three_black_crows@4h/4h": 16,
                    "bb_medium_bw_upper_reject@4h/4h": 16,
                    "session_boundary_volume_fade@4h/4h": 16,
                    "vwap_spread_exhaustion@4h/4h": 16,
                    "vwap_volatility_band_fade@1h/1h": 16,
                    "opening_range_breakout@1h/1h": 16,
                    "atr_channel_breakout@1h/1h": 16,
                    "ema_adx_trend@1h/1h": 16,
                    "bollinger_mean_reversion@1h/1h": 16,
                    "donchian_breakout@4h/4h": 16,
                    "atr_channel_breakout@1h/4h": 16,
                },
                "retired": [],
                "added": [],
            }
        ),
        encoding="utf-8",
    )
    jobs = research_jobs.list_jobs()
    leftover = research_catalog.remaining_hypotheses(jobs)
    assert leftover
    assert leftover[0]["rank"] > 5
    promoted = research_catalog.promote_remaining_into_top5(jobs)
    assert promoted
    refreshed = research_catalog.remaining_hypotheses(research_jobs.list_jobs())
    assert refreshed[0]["rank"] == 1
    assert classify_hypothesis(refreshed[0], jobs=jobs)["checks"]["top5"] is True


def test_escalate_once_increments_counter(firm_db) -> None:
    from firm import memory

    first = memory.escalate_once(
        "ops_engineer",
        "LLM timeout: quant_researcher",
        "one",
        root_cause="llm_timeout:quant_researcher",
    )
    second = memory.escalate_once(
        "ops_engineer",
        "LLM timeout: quant_researcher",
        "two",
        root_cause="llm_timeout:quant_researcher",
    )
    assert first is not None
    assert second is None
    rows = memory.open_escalations()
    match = [r for r in rows if r["root_cause"] == "llm_timeout:quant_researcher"]
    assert len(match) == 1
    assert match[0]["occurrence_count"] >= 2
    assert match[0]["lifecycle"] == "open"


def test_resolve_escalation_hides_row(firm_db) -> None:
    from firm import memory

    eid = memory.escalate("ops_engineer", "stale", "detail", root_cause="stale_x")
    assert memory.resolve_escalation(eid) is True
    assert all(r["id"] != eid for r in memory.open_escalations())


def test_auto_advance_unset_is_fail_closed(monkeypatch) -> None:
    """PIPELINE_AUTO_ADVANCE unset/false never auto-starts a walk-forward."""
    from config.settings import get_settings
    from firm.continuity import auto_advance_gate, auto_advance_switch_on

    monkeypatch.delenv("PIPELINE_AUTO_ADVANCE", raising=False)
    get_settings.cache_clear()
    allowed, why = auto_advance_switch_on()
    assert allowed is False
    assert "PIPELINE_AUTO_ADVANCE" in why
    gated, gate_why = auto_advance_gate()
    assert gated is False
    assert "PIPELINE_AUTO_ADVANCE" in gate_why


def test_harvest_4h_win_does_not_start_1h_expand_when_auto_advance_off(
    tmp_path, monkeypatch, firm_db, caplog
) -> None:
    """A successful 4h harvest must not enqueue or start a 1h clock expand.

    Jobs 135 (three_black_crows 1h SHORT) and 137 (bb_medium_bw 1h BOTH)
    launched after 4h wins while PIPELINE_AUTO_ADVANCE=false. Harvest/win
    may not call start_job unless Inbox/operator authorizes that expand.
    """
    import logging

    from config.settings import get_settings
    from firm import continuity, pipeline_state, research_catalog, research_jobs

    monkeypatch.setenv("PIPELINE_AUTO_ADVANCE", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    spawned: list[int] = []

    def _capture_start(job_id: int, *, explicit: bool = False) -> bool:
        spawned.append(job_id)
        return True

    monkeypatch.setattr(research_jobs, "start_job", _capture_start)
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    leftover_1h = {
        "id": "three_black_crows@1h/1h@SHORT",
        "family": "three_black_crows",
        "name": "three_black_crows 1h/1h SHORT expand",
        "clock": "1h/1h",
        "side": "SHORT",
        "rank": 1,
        "coded": True,
        "justification": "unauthorized harvest expand",
        "param_change": {"clock": "1h/1h"},
    }
    (tmp_path / "ranking.json").write_text(
        json.dumps(
            {
                "added": [leftover_1h],
                "ranks": {leftover_1h["id"]: 1},
                "retired": [],
                "justifications": {},
                "dispositions": {},
            }
        ),
        encoding="utf-8",
    )
    harvest_job = {
        "id": 134,
        "family": "three_black_crows",
        "clock": "4h/4h",
        "side": "SHORT",
        "status": "done",
        "pairs_approved": 2,
        "auto_advanced": False,
        "hypothesis_id": "three_black_crows@4h/4h@SHORT",
        "detail": "three_black_crows: 2 of 6 pairs approved.",
    }
    (tmp_path / "jobs.json").write_text(
        json.dumps({"jobs": [harvest_job]}),
        encoding="utf-8",
    )
    research_catalog.record_finished_walk_forward(harvest_job)
    caplog.set_level(logging.WARNING)
    result = continuity.on_job_finished(harvest_job)
    fill = result.get("fill") or {}
    assert fill.get("started") == []
    assert spawned == []
    assert "PIPELINE_AUTO_ADVANCE" in str(fill.get("blocked") or "")
    live = [
        j
        for j in research_jobs.list_jobs()
        if j.get("status") in {"running", "queued"}
    ]
    assert live == []
    assert all(j.get("clock") != "1h/1h" or j.get("status") not in {"running", "queued", "standby"} for j in research_jobs.list_jobs())
    assert any("Refusing auto-expand" in rec.message for rec in caplog.records)


def test_harvest_does_not_expand_even_if_fill_is_invoked(
    tmp_path, monkeypatch, firm_db
) -> None:
    """Direct fill after a 4h win still cannot start the 1h leftover."""
    from config.settings import get_settings
    from firm import continuity, pipeline_state, research_catalog, research_jobs

    monkeypatch.setenv("PIPELINE_AUTO_ADVANCE", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    spawned: list[int] = []
    monkeypatch.setattr(
        research_jobs,
        "start_job",
        lambda job_id, explicit=False: spawned.append(job_id) or True,
    )
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    leftover = [
        {
            "id": "bb_medium_bw_upper_reject@1h/1h",
            "family": "bb_medium_bw_upper_reject",
            "clock": "1h/1h",
            "side": "BOTH",
            "rank": 1,
            "name": "bb_medium_bw_upper_reject 1h BOTH expand",
            "justification": "unauthorized harvest expand",
            "param_change": {"clock": "1h/1h"},
        }
    ]
    monkeypatch.setattr(research_catalog, "remaining_hypotheses", lambda jobs=None: leftover)
    monkeypatch.setattr(continuity, "remaining_hypotheses", lambda jobs=None: leftover)
    monkeypatch.setattr(research_catalog, "replenish_catalog", lambda **kwargs: [])
    (tmp_path / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": 136,
                        "family": "bb_medium_bw_upper_reject",
                        "clock": "4h/4h",
                        "side": "BOTH",
                        "status": "done",
                        "pairs_approved": 3,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = continuity.fill_walk_forward_slots(source="event")
    assert result.get("started") == []
    assert spawned == []
    assert "PIPELINE_AUTO_ADVANCE" in str(result.get("blocked") or "")


def test_operator_explicit_start_still_works_when_auto_advance_off(
    tmp_path, monkeypatch, firm_db
) -> None:
    """Marcus/operator Inbox approve must still record+start a job."""
    from config.settings import get_settings
    from firm import research_jobs

    monkeypatch.setenv("PIPELINE_AUTO_ADVANCE", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "research_jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    started: list[tuple[int, bool]] = []

    def _start(job_id: int, *, explicit: bool = False) -> bool:
        started.append((job_id, explicit))
        return True

    monkeypatch.setattr(research_jobs, "start_job", _start)
    monkeypatch.setattr("firm.memory.mark_research_status", lambda *args, **kwargs: 0)
    result = research_jobs.on_strategy_approved(
        {
            "id": 9,
            "kind": "strategy",
            "title": "Walk-forward three_black_crows 4h SHORT",
            "payload": {
                "family": "three_black_crows",
                "name": "three_black_crows",
                "clock": "4h/4h",
                "side": "SHORT",
                "action": "walk_forward",
            },
            "status": "approved",
        }
    )
    assert result["queued"] is True
    assert result["family"] == "three_black_crows"
    assert started and started[0][1] is True
    jobs = research_jobs.list_jobs()
    assert jobs[0]["clock"] == "4h/4h"
    assert jobs[0]["side"] == "SHORT"


def test_harvest_same_family_1h_expand_needs_inbox_even_when_auto_advance_on(
    tmp_path, monkeypatch, firm_db
) -> None:
    """A 4h win must not silently start the same family's leftover 1h clock."""
    from firm import continuity, pipeline_state, research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    _enable_auto_advance(monkeypatch)
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    spawned: list[int] = []
    monkeypatch.setattr(
        research_jobs,
        "start_job",
        lambda job_id, explicit=False: spawned.append(job_id) or True,
    )
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    leftover = [
        {
            "id": "three_black_crows@1h/1h@SHORT",
            "family": "three_black_crows",
            "clock": "1h/1h",
            "side": "SHORT",
            "rank": 1,
            "coded": True,
            "free_params": 2,
            "name": "three_black_crows 1h SHORT expand",
            "justification": "harvest leftover",
            "param_change": {"clock": "1h/1h"},
        }
    ]
    monkeypatch.setattr(research_catalog, "remaining_hypotheses", lambda jobs=None: leftover)
    monkeypatch.setattr(continuity, "remaining_hypotheses", lambda jobs=None: leftover)
    monkeypatch.setattr(
        continuity,
        "classify_hypothesis",
        lambda *args, **kwargs: {"tier": "A", "checks": {}, "reasons": []},
    )
    monkeypatch.setattr(
        continuity,
        "classify_family_clock",
        lambda *args, **kwargs: {"tier": "A", "checks": {}, "reasons": []},
    )
    monkeypatch.setattr(research_catalog, "replenish_catalog", lambda **kwargs: [])
    (tmp_path / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "id": 134,
                        "family": "three_black_crows",
                        "clock": "4h/4h",
                        "side": "SHORT",
                        "status": "done",
                        "pairs_approved": 2,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = continuity.fill_walk_forward_slots(source="event")
    assert spawned == []
    assert result.get("started") == []
    assert any("clock expand" in s for s in (result.get("skipped") or []))
    gated = [j for j in research_jobs.list_jobs() if j.get("status") == "gated"]
    assert gated
    assert gated[0]["clock"] == "1h/1h"
    assert gated[0]["blocked_by"] == "clock_expand_inbox"
