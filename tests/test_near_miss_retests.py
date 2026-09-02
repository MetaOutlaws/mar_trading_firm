"""Near-miss retests: frozen grids must actually run, not clone a reject."""

from __future__ import annotations

from datetime import datetime, timezone

from core.strategy.base import SignalSide
from firm.envelope import classify_family_clock
from firm.research_catalog import (
    FIB_EXTENSION_NEAR_MISS,
    NEAR_MISS_RETESTS,
    TODAY_CLOSE_RETESTS,
    is_explicit_retest,
    is_param_variant,
    remaining_hypotheses,
)
from research.validate import merge_search_space, strategy_kit


def _isolate_finished_grids(monkeypatch, tmp_path) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_catalog, "WALK_FORWARD_HISTORY_PATH", tmp_path / "wf_history.json")
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    monkeypatch.setattr(research_catalog, "paper_book_finished_keys", lambda: set())
    research_jobs._LAST_GOOD_JOBS = None


def test_fifteen_near_misses_are_tagged_variants() -> None:
    ids = [str(row["id"]) for row in NEAR_MISS_RETESTS]
    assert len(ids) == 15
    assert len(set(ids)) == 15
    for row in NEAR_MISS_RETESTS:
        assert is_param_variant(row)
        assert row.get("coded") is True
        assert row.get("disposition") == "re-parameterise"
        assert row.get("justification")
        change = row.get("param_change") or {}
        assert any(k not in {"clock", "side"} for k in change)


def test_merge_search_space_freezes_adx() -> None:
    _factory, _base, space = strategy_kit("donchian_breakout", SignalSide.SHORT)
    merged = merge_search_space(space, {"lookback": [55], "min_adx": [20.0]})
    assert merged["lookback"] == [55]
    assert merged["min_adx"] == [20.0]
    assert "take_profit_pct" in merged


def test_remaining_keeps_variant_after_base_clock(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "jobs.json").write_text(
        '{"jobs":[{"family":"bb_squeeze_breakout","status":"done","clock":"4h/4h",'
        '"side":"BOTH","pairs_approved":0,"hypothesis_id":"bb_squeeze_breakout@4h/4h"}]}',
        encoding="utf-8",
    )
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    research_catalog.append_hypothesis(dict(NEAR_MISS_RETESTS[0]), added_by="test")
    left_ids = [r["id"] for r in remaining_hypotheses(research_jobs.list_jobs())]
    assert "bb_squeeze_breakout@4h/4h@LONG@no_adx" in left_ids


def test_rsi_variant_is_not_blocked_by_never_replenish(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    rsi = next(r for r in NEAR_MISS_RETESTS if r["family"] == "rsi_trend")
    research_catalog.append_hypothesis(dict(rsi), added_by="test")
    left_ids = [r["id"] for r in remaining_hypotheses(research_jobs.list_jobs())]
    assert rsi["id"] in left_ids


def test_classify_prefers_hypothesis_id(monkeypatch) -> None:
    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: False)
    row = dict(NEAR_MISS_RETESTS[2])
    row["rank"] = 1
    monkeypatch.setattr("firm.envelope.ranked_hypotheses", lambda: [row])
    jobs = [
        {
            "family": row["family"],
            "status": "done",
            "clock": row["clock"],
            "pairs_approved": 0,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
    ]
    result = classify_family_clock(
        row["family"],
        row["clock"],
        side=row["side"],
        jobs=jobs,
        hypothesis_id=str(row["id"]),
    )
    assert result["checks"]["reject_cooldown"] is True
    assert result["hypothesis_id"] == row["id"]
    assert result["tier"] in {"A", "B"}


def test_near_miss_skips_auditor_inbox_gate(monkeypatch) -> None:
    from firm.envelope import classify_hypothesis

    monkeypatch.setattr("firm.envelope._auditor_flag", lambda family, **kwargs: True)
    row = dict(NEAR_MISS_RETESTS[0])
    row["rank"] = 1
    result = classify_hypothesis(row, jobs=[])
    assert result["checks"]["no_auditor_flag"] is True
    assert result["tier"] == "A"


def test_remaining_skips_seed_tags_that_are_not_near_misses(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "jobs.json").write_text('{"jobs":[]}', encoding="utf-8")
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    left_ids = [r["id"] for r in remaining_hypotheses(research_jobs.list_jobs())]
    assert "ema_adx_trend@4h/4h@frozen_adx" not in left_ids
    assert "bollinger_mean_reversion@4h/4h@tight" not in left_ids


def test_overlay_added_param_variant_stays_in_remaining(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "jobs.json").write_text(
        '{"jobs":[{"family":"bb_squeeze_breakout","status":"done","clock":"4h/4h",'
        '"side":"BOTH","pairs_approved":0,"hypothesis_id":"bb_squeeze_breakout@4h/4h"}]}',
        encoding="utf-8",
    )
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(research_catalog, "_family_peak_pf", lambda: {"bb_squeeze_breakout": 1.67})
    research_catalog.append_hypothesis(
        {
            "id": "bb_squeeze_breakout@4h/4h@LONG@atr_k_2_5",
            "family": "bb_squeeze_breakout",
            "name": "BB squeeze 4h longs, atr_k 2.5",
            "clock": "4h/4h",
            "side": "LONG",
            "coded": True,
            "rank": 1,
            "disposition": "re-parameterise",
            "justification": "SOL 4h long PF 1.67; freeze atr_k at 2.5.",
            "param_change": {"atr_k": [2.5]},
        },
        added_by="quant_researcher",
    )
    left_ids = [r["id"] for r in remaining_hypotheses(research_jobs.list_jobs())]
    assert "bb_squeeze_breakout@4h/4h@LONG@atr_k_2_5" in left_ids


def test_today_close_retests_are_frozen_variants() -> None:
    ids = [str(row["id"]) for row in TODAY_CLOSE_RETESTS]
    assert len(ids) == 2
    assert len(set(ids)) == 2
    for row in TODAY_CLOSE_RETESTS:
        assert is_param_variant(row)
        assert row.get("disposition") == "re-parameterise"
        change = row.get("param_change") or {}
        assert change.get("trend_sma") == [50]


def test_today_close_retests_stay_in_remaining(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "jobs.json").write_text(
        '{"jobs":['
        '{"family":"mass_index_reversal","status":"done","clock":"4h/4h",'
        '"side":"BOTH","pairs_approved":0,"hypothesis_id":"mass_index_reversal@4h/4h"},'
        '{"family":"mama_fama_cross","status":"done","clock":"4h/4h",'
        '"side":"BOTH","pairs_approved":0,"hypothesis_id":"mama_fama_cross@4h/4h"}'
        "]}",
        encoding="utf-8",
    )
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        research_catalog,
        "_family_peak_pf",
        lambda: {"mass_index_reversal": 2.30, "mama_fama_cross": 1.56},
    )
    landed = research_catalog.queue_today_close_retests(added_by="test")
    assert {row["id"] for row in landed} == {row["id"] for row in TODAY_CLOSE_RETESTS}
    left_ids = [r["id"] for r in remaining_hypotheses(research_jobs.list_jobs())]
    assert "mass_index_reversal@4h/4h@LONG@trend_sma50" in left_ids
    assert "mama_fama_cross@4h/4h@SHORT@trend_sma50" in left_ids


def test_fib_extension_kit_locks_1618() -> None:
    """Default walk-forward grid searches only 1.618; 1.272 is not a free param."""
    _factory, base, space = strategy_kit("fib_extension_break", SignalSide.SHORT)
    assert base.fib_ratio == 1.618
    assert base.skip_bull is False
    assert base.skip_bear is False
    assert space["fib_ratio"] == [1.618]
    assert 1.272 not in space["fib_ratio"]
    assert "skip_bull" not in space
    assert "skip_bear" not in space


def test_fib_extension_near_miss_overlay_sets_skip_bull() -> None:
    """SHORT-only 4h near-miss can freeze skip_bull and lock 1.618."""
    from dataclasses import replace

    _factory, base, space = strategy_kit("fib_extension_break", SignalSide.SHORT)
    row = FIB_EXTENSION_NEAR_MISS[0]
    change = row["param_change"]
    merged = merge_search_space(space, change)
    assert merged["fib_ratio"] == [1.618]
    assert merged["skip_bull"] == [True]
    assert 1.272 not in merged["fib_ratio"]
    frozen = replace(base, fib_ratio=merged["fib_ratio"][0], skip_bull=merged["skip_bull"][0])
    assert frozen.skip_bull is True
    assert frozen.fib_ratio == 1.618
    assert row["side"] == "SHORT"
    assert row["clock"] == "4h/4h"
    assert is_param_variant(row)
    assert is_explicit_retest(row)


def test_fib_extension_near_miss_stays_in_remaining(tmp_path, monkeypatch) -> None:
    from firm import research_catalog, research_jobs

    monkeypatch.setattr(research_jobs, "JOBS_PATH", tmp_path / "jobs.json")
    _isolate_finished_grids(monkeypatch, tmp_path)
    monkeypatch.setattr(research_catalog, "CATALOG_RANKING_PATH", tmp_path / "ranking.json")
    (tmp_path / "jobs.json").write_text(
        '{"jobs":[{"family":"fib_extension_break","status":"done","clock":"4h/4h",'
        '"side":"BOTH","pairs_approved":1,'
        '"hypothesis_id":"fib_extension_break@4h/4h"}]}',
        encoding="utf-8",
    )
    (tmp_path / "ranking.json").write_text(
        '{"added":[],"ranks":{},"retired":[],"justifications":{},"dispositions":{}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(research_catalog, "_family_peak_pf", lambda: {"fib_extension_break": 1.64})
    landed = research_catalog.queue_fib_extension_near_miss(added_by="test")
    assert {row["id"] for row in landed} == {row["id"] for row in FIB_EXTENSION_NEAR_MISS}
    left_ids = [r["id"] for r in remaining_hypotheses(research_jobs.list_jobs())]
    assert "fib_extension_break@4h/4h@SHORT@skip_bull_1618" in left_ids
