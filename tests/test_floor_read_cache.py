"""Read-side caches for the dashboard thread pool.

These checks do not place orders, edit the live book, or start a walk-forward.
A cache hit must return the same values the uncached read would.
"""

from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path

from api.dashboard_cache import panel_cache
from api.desk_status import clear_jsonl_cache, read_telemetry, telemetry_cache_stats
from core.strategy import spec_sleeve
from firm import integrity, memory
from firm.orchestrator import Orchestrator
from firm.read_cache import ResponseCache, floor_cache
from firm.research_catalog import _ranking_overlay, clear_ranking_overlay_cache

ROOT = Path(__file__).resolve().parents[1]

# Trading-path blobs. A read-side cache must not edit them.
# engine.py gives testnet the dataclass gross default, not PAPER_LIMITS.
# Previous pin: dd5492d0ae8ca6f629f690348a224169b2712103.
_ENGINE = "52f4e678922dbb81e03dba79514b4df7943f1ad1"
# paper.py runs the funding hook between plan and book under the lock.
# Previous pin: 66479045eda3fd04ebe1c9cad50d6ebfe996bdee.
_PAPER = "821ec3eace98334565a11a7d5a8a22c447e97c68"


def test_integrity_snapshot_is_once_per_book_sha(monkeypatch) -> None:
    """The second hypothesis reuses the pack. A new sha builds again."""
    integrity.clear_integrity_snapshot_cache()
    state = {"key": ("sha-a",), "n": 0}

    def key() -> tuple[str]:
        return state["key"]

    def build() -> dict[str, int]:
        state["n"] += 1
        return {"ok": True, "n": state["n"]}

    monkeypatch.setattr(integrity, "_integrity_key", key)
    monkeypatch.setattr(integrity, "_integrity_snapshot_uncached", build)
    first = integrity.integrity_snapshot()
    second = integrity.integrity_snapshot()
    assert first == second
    assert state["n"] == 1
    state["key"] = ("sha-b",)
    third = integrity.integrity_snapshot()
    assert third["n"] == 2
    assert state["n"] == 2
    integrity.clear_integrity_snapshot_cache()


def test_book_sha_follows_the_file_bytes(tmp_path) -> None:
    path = tmp_path / "approved_strategies.json"
    path.write_text('{"a": 1}', encoding="utf-8")
    integrity.clear_integrity_snapshot_cache()
    first = integrity._book_sha(path)
    path.write_text('{"a": 22}', encoding="utf-8")
    second = integrity._book_sha(path)
    assert first != second
    assert integrity._book_sha(path) == second
    integrity.clear_integrity_snapshot_cache()


def test_approval_clock_index_matches_the_first_approved_row(monkeypatch) -> None:
    """The indexed clock is the first approved row, not a later duplicate."""

    class _Universe:
        approvals = {
            "clock_probe:BTCUSDT:LONG:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "clock_probe",
            },
            "clock_probe:BTCUSDT:LONG:1h": {
                "approved": True,
                "timeframe": "1h",
                "strategy": "clock_probe",
            },
            "_generated_at": "skip",
        }

    universe = _Universe()
    monkeypatch.setattr("config.universe.get_universe", lambda: universe)
    monkeypatch.setattr("firm.integrity.get_universe", lambda: universe, raising=False)
    index = integrity._approval_clock_index(universe)
    row = {
        "strategy": "clock_probe",
        "symbol": "BTCUSDT",
        "side": "long",
        "timeframe": "15m",
    }
    with_index = integrity._row_expected_clock(row, "other_family", "1h/4h", index)
    without = integrity._row_expected_clock(row, "other_family", "1h/4h", None)
    assert with_index == without
    assert index[("clock_probe", "BTCUSDT", "LONG")] == with_index


def test_spec_sleeves_are_read_once_per_directory_mtime(monkeypatch) -> None:
    spec_sleeve.clear_spec_sleeve_cache()
    calls = {"n": 0}
    real = spec_sleeve.load_spec

    def wrapped(path: Path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(spec_sleeve, "load_spec", wrapped)
    first = spec_sleeve.load_spec_sleeves()
    read_once = calls["n"]
    second = spec_sleeve.load_spec_sleeves()
    assert second == first
    assert calls["n"] == read_once
    assert read_once > 0
    spec_sleeve.clear_spec_sleeve_cache()


def test_ranking_overlay_is_read_once_per_mtime(tmp_path, monkeypatch) -> None:
    path = tmp_path / "catalog_ranking.json"
    path.write_text(json.dumps({"retired_families": ["old_family"]}), encoding="utf-8")
    monkeypatch.setattr("firm.research_catalog.CATALOG_RANKING_PATH", path)
    clear_ranking_overlay_cache()
    reads = {"n": 0}
    real_read = Path.read_text

    def wrapped(self: Path, *args, **kwargs):
        if self == path:
            reads["n"] += 1
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", wrapped)
    first = _ranking_overlay()
    first["retired_families"] = ["mutated"]
    second = _ranking_overlay()
    assert reads["n"] == 1
    assert second["retired_families"] == ["old_family"]
    path.write_text(json.dumps({"retired_families": ["fresh"]}), encoding="utf-8")
    third = _ranking_overlay()
    assert third["retired_families"] == ["fresh"]
    assert reads["n"] == 2
    clear_ranking_overlay_cache()


def test_jsonl_parse_is_cached_on_mtime_and_size(tmp_path) -> None:
    """A quiet file is not parsed again. An append parses only the new line."""
    import api.why_no_trade  # noqa: F401 — bind row parsers before counting loads
    import core.execution.f111_paper  # noqa: F401

    path = tmp_path / "f111_telemetry.jsonl"
    path.write_text(json.dumps({"run_id": "scan-a", "symbol": "BTCUSDT"}) + "\n", encoding="utf-8")
    clear_jsonl_cache()
    loads = {"n": 0}
    real_loads = json.loads

    def wrapped(*args, **kwargs):
        loads["n"] += 1
        return real_loads(*args, **kwargs)

    original = json.loads
    json.loads = wrapped
    try:
        read_telemetry(path)
        assert telemetry_cache_stats()["parsed_rows"] == 1
        parsed = loads["n"]
        read_telemetry(path)
        assert loads["n"] == parsed
        # Telemetry is append-only. A new line changes the size. The fold
        # seeks to the previous offset instead of parsing the prefix again.
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"run_id": "scan-b", "symbol": "ETHUSDT"}) + "\n")
        read_telemetry(path)
        assert telemetry_cache_stats()["parsed_rows"] == 2
        assert loads["n"] == parsed + 1
    finally:
        json.loads = original
        clear_jsonl_cache()


def test_floor_response_is_single_flight_and_reused() -> None:
    floor_cache.clear()
    calls = {"n": 0}

    def build() -> dict[str, int]:
        calls["n"] += 1
        return {"employees": [], "n": calls["n"]}

    orch = object.__new__(Orchestrator)
    orch._floor_snapshot_uncached = build
    first = orch.floor_snapshot()
    second = orch.floor_snapshot()
    assert calls["n"] == 1
    assert second["computed_at"] == first["computed_at"]
    assert second["n"] == 1
    assert isinstance(second["age"], int)
    floor_cache.clear()


def test_response_cache_single_flight() -> None:
    cache = ResponseCache(ttl_seconds=30)
    builds = {"n": 0}
    gate = threading.Barrier(6)

    def build() -> dict[str, int]:
        builds["n"] += 1
        time.sleep(0.05)
        return {"n": 1}

    def worker() -> None:
        gate.wait()
        payload = cache.fetch("panel", ("same",), build)
        assert payload["n"] == 1

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert builds["n"] == 1


def test_scan_prune_on_read_is_once_a_minute(firm_db, monkeypatch) -> None:
    from firm.scan_inbox import expire_and_prune_scan_summaries

    calls = {"n": 0}
    real = expire_and_prune_scan_summaries

    def wrapped(now=None):
        calls["n"] += 1
        return real(now)

    monkeypatch.setattr("firm.scan_inbox.expire_and_prune_scan_summaries", wrapped)
    memory.clear_read_maintenance()
    memory.pending_proposals()
    memory.pending_proposals()
    assert calls["n"] == 1
    wrapped()
    assert calls["n"] == 2


def test_escalation_expiry_on_read_is_once_a_minute_and_ack_is_not(firm_db, monkeypatch) -> None:
    calls = {"n": 0}
    real = memory.expire_stale_escalations

    def wrapped(now=None):
        calls["n"] += 1
        return real(now)

    monkeypatch.setattr(memory, "expire_stale_escalations", wrapped)
    memory.clear_read_maintenance()
    memory.open_escalations()
    memory.open_escalations()
    assert calls["n"] == 1
    memory.acknowledge_stale_escalations()
    assert calls["n"] == 2


def test_inbox_rows_are_not_cached_for_the_paper_cycle(firm_db) -> None:
    """A veto written after the minute's prune is still visible to the engine."""
    from firm.memory_models import ProposalKind

    memory.clear_read_maintenance()
    assert memory.pending_proposals() == []
    pid = memory.record_proposal(
        agent="risk_officer",
        kind=ProposalKind.RISK,
        title="Veto BTCUSDT",
        payload={"action": "veto", "symbol": "BTCUSDT"},
        rationale="drawdown",
        confidence=0.8,
        symbol="BTCUSDT",
    )
    listed = memory.pending_proposals()
    assert any(row["id"] == pid for row in listed)


def test_desk_ttl_is_thirty_seconds_and_trading_blobs_are_unchanged() -> None:
    assert panel_cache.ttl_seconds == 30.0
    assert floor_cache.ttl_seconds == 30.0
    for rel, blob in (
        ("core/execution/engine.py", _ENGINE),
        ("core/execution/paper.py", _PAPER),
    ):
        hashed = subprocess.check_output(
            ["git", "hash-object", str(ROOT / rel)],
            text=True,
        ).strip()
        assert hashed == blob
    engine = (ROOT / "core" / "execution" / "engine.py").read_text(encoding="utf-8")
    assert "firm.read_cache" not in engine
    assert "floor_cache" not in engine
