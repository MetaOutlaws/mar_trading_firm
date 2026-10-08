"""Closed vocabulary and freshness for the paper Soko trend hook.

A label is usable only when it is bull/bear/chop (after aliases) and its
clock is fresh. The file clock is ``as_of``. The memory clock is
``recorded_at``. Missing, unparseable, too old, and far-future clocks are
stale. A lead of at most ``SOKO_TREND_FUTURE_SKEW`` (5 minutes) is clock
skew and still fresh. Age equal to ``SOKO_TREND_MAX_AGE_HOURS`` is still
fresh; older than that is stale.

When the hook returns None, paper ``build_plan`` sits out every
regime-gated sleeve. That is ``paper_record_sitout_reason`` seeing a
missing trend, which runs before the blocked-list and allow-list checks.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from config.settings import get_settings
from config.universe import ShortParams, Universe
from core.data.soko_trend import (
    SOKO_TREND_FUTURE_SKEW,
    normalize_trend_label,
    read_live_soko_trend,
)
from core.execution.engine import build_plan

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)


def _freeze(monkeypatch) -> None:
    monkeypatch.setattr("core.data.soko_trend._utcnow", lambda: NOW)


def _memory(monkeypatch, snap) -> None:
    monkeypatch.setattr("firm.memory.latest_regime", lambda: snap)


def _write(path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fresh_as_of(**kwargs) -> str:
    """ISO timestamp ``kwargs`` before NOW, default zero. Trailing Z."""
    stamp = NOW - timedelta(**kwargs) if kwargs else NOW
    return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _warnings(caplog) -> list[str]:
    return [
        rec.getMessage()
        for rec in caplog.records
        if rec.levelno >= logging.WARNING and rec.name == "core.data.soko_trend"
    ]


def test_future_skew_default_is_five_minutes() -> None:
    assert SOKO_TREND_FUTURE_SKEW == timedelta(minutes=5)


def test_normalize_maps_aliases_and_rejects_other_labels(caplog) -> None:
    assert normalize_trend_label("Bull") == "bull"
    assert normalize_trend_label(" up ") == "bull"
    assert normalize_trend_label("bearish") == "bear"
    assert normalize_trend_label("sideways") == "chop"
    assert normalize_trend_label("range") == "chop"
    assert normalize_trend_label(None) is None
    assert normalize_trend_label("  ") is None
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert normalize_trend_label("Neutral") is None
    assert any("neutral" in msg for msg in _warnings(caplog))


def test_valid_fresh_file_wins_over_memory(tmp_path, monkeypatch) -> None:
    """File label is used, including an explicit non-UTC offset, and memory is ignored."""
    _freeze(monkeypatch)
    # A different fresh memory label would leak if the file did not win.
    _memory(monkeypatch, {"regime": "bear", "recorded_at": _fresh_as_of()})
    dest = tmp_path / "last_soko_trend.json"
    # 14:00+02:00 is 12:00Z, the same instant as NOW.
    _write(dest, {"trend": "bull", "as_of": "2026-10-08T14:00:00+02:00"})
    assert read_live_soko_trend(dest) == "bull"


def test_alias_mapped_on_file_pairs_and_memory(tmp_path, monkeypatch) -> None:
    _freeze(monkeypatch)
    _memory(monkeypatch, None)
    dest = tmp_path / "last_soko_trend.json"
    _write(dest, {"trend": "sideways", "as_of": _fresh_as_of(minutes=5)})
    assert read_live_soko_trend(dest) == "chop"

    _write(dest, {"btc_trend": "down", "as_of": "2026-10-08T11:00:00+00:00"})
    assert read_live_soko_trend(dest) == "bear"

    _write(
        dest,
        {
            "pairs": [{"symbol": "BTCUSDT", "trend": "up"}],
            "as_of": _fresh_as_of(minutes=1),
        },
    )
    assert read_live_soko_trend(dest) == "bull"

    dest.unlink()
    _memory(
        monkeypatch,
        {"regime": "range", "btc_trend": "down", "recorded_at": _fresh_as_of()},
    )
    assert read_live_soko_trend(dest) == "chop"


def test_invalid_neutral_from_file_is_no_label(tmp_path, monkeypatch, caplog) -> None:
    """'neutral' is not a regime. A later key or a BTC pair must not rescue it."""
    _freeze(monkeypatch)
    dest = tmp_path / "last_soko_trend.json"
    _write(
        dest,
        {
            "trend": "neutral",
            "btc_trend": "bull",
            "pairs": [{"symbol": "BTCUSDT", "trend": "bear"}],
            "as_of": _fresh_as_of(),
        },
    )
    # Fresh valid memory is the fallback once the file label is rejected.
    # chop, not bear/bull: those are the trap values on btc_trend and pairs[].
    _memory(monkeypatch, {"regime": "chop", "recorded_at": _fresh_as_of()})
    with caplog.at_level(logging.INFO, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) == "chop"
    assert not any("fail-closed" in msg for msg in _warnings(caplog))

    caplog.clear()
    _memory(monkeypatch, None)
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "file label invalid 'neutral'" in warnings[0]
    assert "Regime-gated paper sleeves will sit out" in warnings[0]


def test_invalid_btc_pair_does_not_fall_through(tmp_path, monkeypatch, caplog) -> None:
    _freeze(monkeypatch)
    _memory(monkeypatch, None)
    dest = tmp_path / "last_soko_trend.json"
    _write(
        dest,
        {
            "pairs": [
                {"symbol": "BTCUSDT", "trend": "neutral"},
                {"symbol": "ETHUSDT", "trend": "bull"},
            ],
            "as_of": _fresh_as_of(),
        },
    )
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    assert any("file label invalid 'neutral'" in msg for msg in _warnings(caplog))


def test_stale_file_falls_back_to_fresh_memory(tmp_path, monkeypatch, caplog) -> None:
    _freeze(monkeypatch)
    dest = tmp_path / "last_soko_trend.json"
    _write(dest, {"trend": "bull", "as_of": _fresh_as_of(hours=30)})
    _memory(
        monkeypatch,
        {"regime": "range", "recorded_at": _fresh_as_of(hours=1)},
    )
    with caplog.at_level(logging.INFO, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) == "chop"
    assert not any("fail-closed" in msg for msg in _warnings(caplog))
    assert any("stale by 30.0 hours" in rec.getMessage() for rec in caplog.records)


def test_stale_file_with_invalid_memory_fails_closed(tmp_path, monkeypatch, caplog) -> None:
    """Invalid memory does not fall through to btc_trend."""
    _freeze(monkeypatch)
    dest = tmp_path / "last_soko_trend.json"
    _write(dest, {"trend": "bear", "as_of": _fresh_as_of(hours=30)})
    _memory(
        monkeypatch,
        {
            "regime": "neutral",
            "btc_trend": "bull",
            "recorded_at": _fresh_as_of(),
        },
    )
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "file stale by 30.0 hours, memory label invalid 'neutral'" in warnings[0]


def test_both_stale_fails_closed(tmp_path, monkeypatch, caplog) -> None:
    _freeze(monkeypatch)
    dest = tmp_path / "last_soko_trend.json"
    _write(dest, {"trend": "bull", "as_of": _fresh_as_of(hours=30)})
    _memory(
        monkeypatch,
        {"regime": "bear", "recorded_at": _fresh_as_of(hours=48)},
    )
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "file stale by 30.0 hours" in warnings[0]
    assert "memory snapshot stale by 48.0 hours" in warnings[0]
    assert "Regime-gated paper sleeves will sit out" in warnings[0]


def test_missing_or_bad_as_of_is_stale(tmp_path, monkeypatch, caplog) -> None:
    _freeze(monkeypatch)
    _memory(monkeypatch, None)
    dest = tmp_path / "last_soko_trend.json"
    _write(dest, {"trend": "bull"})
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    assert any("file as_of missing (stale)" in msg for msg in _warnings(caplog))

    caplog.clear()
    _write(dest, {"trend": "bull", "as_of": "yesterday"})
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    assert any("file as_of unparseable (stale)" in msg for msg in _warnings(caplog))

    caplog.clear()
    # Memory with a real label but no recorded_at is stale as well.
    _write(dest, {"trend": "sideways"})  # no as_of, so the file cannot win
    _memory(monkeypatch, {"regime": "bull"})
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    assert any("recorded_at missing (stale)" in msg for msg in _warnings(caplog))


def test_future_dated_as_of(tmp_path, monkeypatch, caplog) -> None:
    """Skew within 5 minutes is fresh. Further ahead is stale, not live forever."""
    _freeze(monkeypatch)
    dest = tmp_path / "last_soko_trend.json"
    # Different fresh memory label: if the future file were rejected we would
    # see bear. Exactly 5 minutes ahead is still the file.
    _memory(monkeypatch, {"regime": "bear", "recorded_at": _fresh_as_of()})
    on_skew = (NOW + SOKO_TREND_FUTURE_SKEW).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write(dest, {"trend": "bull", "as_of": on_skew})
    assert read_live_soko_trend(dest) == "bull"

    past_skew = (NOW + SOKO_TREND_FUTURE_SKEW + timedelta(seconds=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    _write(dest, {"trend": "bull", "as_of": past_skew})
    assert read_live_soko_trend(dest) == "bear"

    _memory(monkeypatch, None)
    far = (NOW + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _write(dest, {"trend": "bull", "as_of": far})
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    assert any(
        "file as_of future-dated by 2.0 hours" in msg for msg in _warnings(caplog)
    )

    # The snapshot clock uses the same future rule.
    dest.unlink()
    _memory(
        monkeypatch,
        {
            "regime": "bull",
            "recorded_at": (NOW + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        assert read_live_soko_trend(dest) is None
    assert any(
        "recorded_at future-dated by 3.0 hours" in msg for msg in _warnings(caplog)
    )


def test_configured_max_age_is_respected(tmp_path, monkeypatch) -> None:
    _freeze(monkeypatch)
    _memory(monkeypatch, None)
    dest = tmp_path / "last_soko_trend.json"
    monkeypatch.delenv("SOKO_TREND_MAX_AGE_HOURS", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().soko_trend_max_age_hours == 6.0
        _write(dest, {"trend": "bull", "as_of": _fresh_as_of(hours=6)})
        assert read_live_soko_trend(dest) == "bull"
        _write(dest, {"trend": "bull", "as_of": _fresh_as_of(hours=5)})
        assert read_live_soko_trend(dest) == "bull"
        just_over = (NOW - timedelta(hours=6, seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write(dest, {"trend": "bull", "as_of": just_over})
        assert read_live_soko_trend(dest) is None
        _write(dest, {"trend": "bull", "as_of": _fresh_as_of(hours=7)})
        assert read_live_soko_trend(dest) is None

        monkeypatch.setenv("SOKO_TREND_MAX_AGE_HOURS", "1")
        get_settings.cache_clear()
        assert get_settings().soko_trend_max_age_hours == 1.0
        _write(dest, {"trend": "chop", "as_of": _fresh_as_of(minutes=30)})
        assert read_live_soko_trend(dest) == "chop"
        _write(dest, {"trend": "chop", "as_of": _fresh_as_of(minutes=90)})
        assert read_live_soko_trend(dest) is None
    finally:
        get_settings.cache_clear()


def _sitout_universe() -> Universe:
    """Gated shapes that a leaked 'neutral' or stale 'chop' would let trade.

    The canary (``orb_fail_reversion``) is regime-gated with no blocked list
    and no activation filter, so any non-empty label scans it. The bull-blocked
    sleeve trades on 'neutral' because neutral is not in its blocked list.
    The paper override is the same function on the override path.
    """
    return Universe(
        long_params={},
        short_params={
            "BTCUSDT": ShortParams(symbol="BTCUSDT", timeframe="4h"),
            "ETHUSDT": ShortParams(symbol="ETHUSDT", timeframe="4h"),
        },
        approvals={
            "atr_channel_breakout:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
                "params": {"atr_k": 2.0},
                "blocked_regimes": ["bull"],
                "regime_disable": ["bull"],
                "activation_mode": "regime_gated",
            },
            "mama_fama_cross:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "mama_fama_cross",
                "params": {"fastlimit": 0.5, "slowlimit": 0.05},
                "activation_mode": "regime_gated",
                "regime_activation_filter": ["bear"],
            },
            "orb_fail_reversion:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "orb_fail_reversion",
                "params": {},
                "activation_mode": "regime_gated",
            },
            "week_open_reclaim:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "week_open_reclaim",
                "params": {},
                "activation_mode": "unrestricted",
            },
            "atr_channel_breakout:ETHUSDT:SHORT:4h": {
                "approved": False,
                "paper_override": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
                "params": {"atr_k": 2.0},
                "blocked_regimes": ["bear"],
                "activation_mode": "regime_gated",
            },
        },
    )


def _patch_plan(monkeypatch, dest) -> None:
    _freeze(monkeypatch)
    monkeypatch.setattr("core.data.soko_trend.LAST_SOKO_TREND_PATH", dest)
    monkeypatch.setattr("core.execution.engine.get_universe", _sitout_universe)
    monkeypatch.setattr(
        "firm.research_jobs.paper_scan_family", lambda: "bb_squeeze_breakout"
    )
    monkeypatch.setattr("firm.research_jobs._active_job_for", lambda family: None)


@pytest.fixture
def plan_file(tmp_path, monkeypatch):
    dest = tmp_path / "last_soko_trend.json"
    _patch_plan(monkeypatch, dest)
    return dest


def test_build_plan_sits_out_every_gated_sleeve_when_fail_closed(
    plan_file, monkeypatch, caplog
) -> None:
    """None from the real reader sits out every gated sleeve, including overrides.

    File says neutral (fresh). Memory says chop but the snapshot is two days
    old. Either leaked label would scan the canary and the bull-blocked
    sleeve. Both must sit out, and the warning must name why.
    """
    _write(plan_file, {"trend": "neutral", "as_of": _fresh_as_of()})
    _memory(
        monkeypatch,
        {"regime": "chop", "recorded_at": _fresh_as_of(hours=48)},
    )
    gated = {
        "atr_channel_breakout",
        "mama_fama_cross",
        "orb_fail_reversion",
    }
    with caplog.at_level(logging.WARNING, logger="core.data.soko_trend"):
        paper = build_plan(require_approval=False, candidates=["BTCUSDT"])

    sat = {row["strategy"] for row in paper.regime_sitouts}
    names = {entry.strategy.name for entry in paper.entries}
    assert paper.soko_trend is None
    assert gated <= sat
    assert "atr_channel_breakout" in sat  # approved and the ETH override share the name
    assert gated.isdisjoint(names)
    assert "week_open_reclaim" in names
    override_rows = [
        row for row in paper.regime_sitouts if row["symbol"] == "ETHUSDT"
    ]
    assert len(override_rows) == 1
    assert "fail-closed" in override_rows[0]["reason"]
    for row in paper.regime_sitouts:
        assert "fail-closed" in row["reason"]
    # Canary has no blocked list and no allow-list: only a missing label sits it out.
    canary = next(row for row in paper.regime_sitouts if row["strategy"] == "orb_fail_reversion")
    assert canary["blocked_regimes"] == []
    assert canary["regime_activation_filter"] == []
    warnings = _warnings(caplog)
    assert len(warnings) == 1
    assert "file label invalid 'neutral'" in warnings[0]
    assert "memory snapshot stale by 48.0 hours" in warnings[0]


def test_build_plan_scans_canary_when_fresh_file_says_bull(plan_file, monkeypatch) -> None:
    """A fresh bull file is the label the plan gates on. Memory must not override it."""
    _write(plan_file, {"trend": "bull", "as_of": _fresh_as_of()})
    _memory(
        monkeypatch,
        {"regime": "chop", "recorded_at": _fresh_as_of(hours=48)},
    )
    paper = build_plan(require_approval=False, candidates=["BTCUSDT"])
    names = {entry.strategy.name for entry in paper.entries}
    assert paper.soko_trend == "bull"
    # No filter and not bull-blocked: the canary and the bear-blocked override scan.
    assert "orb_fail_reversion" in names
    assert "week_open_reclaim" in names
    assert any(
        entry.strategy.name == "atr_channel_breakout" and entry.symbol == "ETHUSDT"
        for entry in paper.entries
    )
    sat = {(row["strategy"], row["symbol"]): row for row in paper.regime_sitouts}
    assert ("atr_channel_breakout", "BTCUSDT") in sat
    assert "bull" in sat[("atr_channel_breakout", "BTCUSDT")]["reason"]
    assert "fail-closed" not in sat[("atr_channel_breakout", "BTCUSDT")]["reason"]
    assert ("mama_fama_cross", "BTCUSDT") in sat
    assert "not in regime_activation_filter" in sat[("mama_fama_cross", "BTCUSDT")]["reason"]
    assert ("orb_fail_reversion", "BTCUSDT") not in sat
