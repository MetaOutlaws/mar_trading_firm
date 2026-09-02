"""Pipeline continuity: envelope, same-tick slot fill, hung median, post-mortem."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from config.pipeline import pipeline_config
from firm.envelope import classify_hypothesis
from firm.research_catalog import remaining_hypotheses


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
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: spawned.append(job_id) or True)
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


def test_fill_slots_does_not_drain_catalog_when_breaker_tripped(
    tmp_path, monkeypatch, firm_db
) -> None:
    from firm import continuity, pipeline_state, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(continuity, "auto_advance_allowed", lambda: (False, "circuit breaker"))
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
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
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
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
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
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
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
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
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
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
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr("firm.research_catalog.remaining_hypotheses", lambda jobs=None: [])
    monkeypatch.setattr(continuity, "remaining_hypotheses", lambda jobs=None: [])
    monkeypatch.setattr("firm.research_catalog.replenish_catalog", lambda **kwargs: [])
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: True)
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
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: spawned.append(job_id) or True)
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
    monkeypatch.setattr(pipeline_state, "STATE_PATH", tmp_path / "state.json")
    spawned: list[int] = []
    monkeypatch.setattr(research_jobs, "start_job", lambda job_id: spawned.append(job_id) or True)
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
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "jobs.json").write_text(
        '{"jobs":[{"family":"atr_channel_breakout","status":"done","clock":"1h/1h","side":"BOTH"}]}',
        encoding="utf-8",
    )
    left = remaining_hypotheses(research_jobs.list_jobs())
    ids = [r["id"] for r in left]
    assert "atr_channel_breakout@1h/1h" not in ids
    assert left[0]["family"] == "opening_range_breakout"


def test_replenish_catalog_fills_depth(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
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
    row = cursor_coding.enqueue_next_novel_if_catalog_empty()
    assert row is not None
    assert row["family"] == "kama_trend"
    assert "kama_trend" in (tmp_path / "NOW.md").read_text(encoding="utf-8")


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
