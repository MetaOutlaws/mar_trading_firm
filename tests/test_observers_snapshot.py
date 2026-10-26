"""GET /api/observers serves a snapshot. The request path does not compute it."""

from __future__ import annotations

import inspect
import math
import time

import pytest
from fastapi.testclient import TestClient

from api.observer_snapshot import snapshot_store, stamp_payload

READY = {
    "ok": True,
    "status": "ready",
    "warming": False,
    "empty": False,
    "generated_at": "2026-10-19T21:00:00.000000Z",
    "observers": [{"id": "f111", "label": "F111"}, {"id": "bl8", "label": "BL8"}],
    "pulses": [{"id": "f111"}, {"id": "bl8"}],
}


def _percentile(samples: list[float], pct: float) -> float:
    """Nearest-rank percentile. p95 of 50 samples is the 48th sorted value."""
    ordered = sorted(samples)
    rank = math.ceil(pct / 100.0 * len(ordered))
    return ordered[max(0, rank - 1)]


def test_observers_endpoint_p95_never_calls_compute(firm_db, monkeypatch) -> None:
    """Fifty GETs stay under 500ms p95 and do not enter the compute function."""
    calls = {"n": 0}

    def explode() -> dict:
        calls["n"] += 1
        time.sleep(0.6)
        return {
            "ok": True,
            "observers": [{"id": "f111"}, {"id": "bl8"}],
            "pulses": [],
        }

    monkeypatch.setattr("api.observer_snapshot.compute_observers_payload", explode)
    monkeypatch.setattr("api.observer_status.list_observers", explode)

    from api.app import app, observers as observers_route

    source = inspect.getsource(observers_route)
    assert "list_observers" not in source
    assert "compute_observers_payload" not in source
    assert "refresh(" not in source

    def token_on_request() -> tuple:
        raise AssertionError("request path read the scan token")

    monkeypatch.setattr("api.observer_snapshot.read_scan_token", token_on_request)
    monkeypatch.setattr(snapshot_store, "_safe_scan_token", token_on_request)

    snapshot_store.stop()
    with TestClient(app) as client:
        snapshot_store.stop()
        calls["n"] = 0
        snapshot_store.seed(READY)
        samples: list[float] = []
        for _ in range(50):
            started = time.perf_counter()
            response = client.get("/api/observers")
            samples.append(time.perf_counter() - started)
            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "ready"
            assert body["generated_at"] == READY["generated_at"]
            assert [row["id"] for row in body["observers"]] == ["f111", "bl8"]
        p95 = _percentile(samples, 95)
        print(f"OBSERVERS_P95_SECONDS={p95:.6f}")
        assert p95 < 0.5, f"p95 {p95:.4f}s over 50 requests"
        assert calls["n"] == 0


def test_warming_is_not_an_empty_list(firm_db, monkeypatch) -> None:
    def explode() -> dict:
        raise AssertionError("request path computed a warming miss")

    monkeypatch.setattr("api.observer_snapshot.compute_observers_payload", explode)
    monkeypatch.setattr("api.observer_status.list_observers", explode)

    from api.app import app

    snapshot_store.stop()
    snapshot_store.clear()
    with TestClient(app) as client:
        snapshot_store.stop()
        snapshot_store.clear()
        response = client.get("/api/observers")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "warming"
    assert body["warming"] is True
    assert body["empty"] is False
    assert body["observers"] is None
    assert body["pulses"] is None
    assert body["generated_at"] is None
    assert "not an empty book" in body["detail"]


def test_refresh_failure_keeps_the_previous_snapshot(monkeypatch) -> None:
    good = {
        "ok": True,
        "observers": [{"id": "f111", "label": "kept"}, {"id": "bl8", "label": "BL8"}],
        "pulses": [{"id": "f111"}],
    }

    monkeypatch.setattr("api.observer_snapshot.compute_observers_payload", lambda: good)
    snapshot_store.stop()
    snapshot_store.clear()
    snapshot_store.refresh()
    first = snapshot_store.serve()
    assert first["status"] == "ready"
    assert first["generated_at"].endswith("Z")
    generated_at = first["generated_at"]

    def boom() -> dict:
        raise RuntimeError("scan read failed")

    monkeypatch.setattr("api.observer_snapshot.compute_observers_payload", boom)
    snapshot_store.refresh()
    second = snapshot_store.serve()
    assert second["status"] == "ready"
    assert second["generated_at"] == generated_at
    assert second["observers"][0]["label"] == "kept"
    assert second["refresh_error"] == "RuntimeError: scan read failed"
    assert first.get("refresh_error") in (None, "")


def test_empty_compute_is_an_explicit_empty_state(monkeypatch) -> None:
    monkeypatch.setattr(
        "api.observer_snapshot.compute_observers_payload",
        lambda: {"ok": True, "observers": [], "pulses": []},
    )
    snapshot_store.stop()
    snapshot_store.clear()
    snapshot_store.refresh()
    body = snapshot_store.serve()
    assert body["status"] == "empty"
    assert body["empty"] is True
    assert body["warming"] is False
    assert body["observers"] == []
    assert body["generated_at"].endswith("Z")


def test_scan_token_changes_when_telemetry_grows(monkeypatch, tmp_path) -> None:
    telemetry = tmp_path / "f111_telemetry.jsonl"
    state = tmp_path / "f111_paper_state.json"
    telemetry.write_text('{"run_id": "a"}\n', encoding="utf-8")
    state.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("core.strategy.f111_config.TELEMETRY_PATH", telemetry)
    monkeypatch.setattr("core.strategy.f111_config.STATE_PATH", state)
    monkeypatch.setenv("BL8_STATE_DIR", str(tmp_path / "bl8-paper"))
    monkeypatch.delenv("BL8_STATUS_PATH", raising=False)
    monkeypatch.delenv("BL8_DB_PATH", raising=False)
    monkeypatch.delenv("BL8_CONFIG_PATH", raising=False)

    from api.observer_snapshot import read_scan_token

    first = read_scan_token()
    telemetry.write_text('{"run_id": "a"}\n{"run_id": "b"}\n', encoding="utf-8")
    second = read_scan_token()
    assert first != second


def test_notify_scan_complete_refreshes_without_waiting(monkeypatch) -> None:
    calls = {"n": 0}

    def compute() -> dict:
        calls["n"] += 1
        return {
            "ok": True,
            "observers": [{"id": "f111"}, {"id": "bl8"}],
            "pulses": [],
        }

    monkeypatch.setattr("api.observer_snapshot.compute_observers_payload", compute)
    monkeypatch.setattr(snapshot_store, "_safe_scan_token", lambda: ("steady",))
    snapshot_store.stop()
    snapshot_store.clear()
    snapshot_store.interval_s = 3600.0
    snapshot_store.scan_poll_s = 0.05
    snapshot_store.start()
    try:
        deadline = time.monotonic() + 2.0
        while calls["n"] < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert calls["n"] == 1
        snapshot_store.notify_scan_complete()
        deadline = time.monotonic() + 2.0
        while calls["n"] < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert calls["n"] >= 2
    finally:
        snapshot_store.interval_s = 60.0
        snapshot_store.scan_poll_s = 2.0
        snapshot_store.stop()


def test_autostart_can_be_switched_off(monkeypatch) -> None:
    monkeypatch.setenv("OBSERVER_SNAPSHOTS_AUTOSTART", "0")
    snapshot_store.stop()
    assert snapshot_store.start_if_enabled() is False
    assert snapshot_store.running is False


def test_refreshes_keep_one_worker_thread(monkeypatch) -> None:
    """N snapshot builds do not start N threads, and the previous result is dropped."""
    import threading

    calls = {"n": 0}

    def compute() -> dict:
        calls["n"] += 1
        return {
            "ok": True,
            "observers": [{"id": "f111", "n": calls["n"]}],
            "pulses": [],
        }

    monkeypatch.setattr("api.observer_snapshot.compute_observers_payload", compute)
    snapshot_store.stop()
    snapshot_store.clear()
    snapshot_store.interval_s = 3600.0
    try:
        for _ in range(12):
            snapshot_store.refresh()
        assert calls["n"] == 12
        assert not any(
            thread.name == "observer-snapshot" and thread.is_alive()
            for thread in threading.enumerate()
        )
        served = snapshot_store.serve()
        assert served["observers"][0]["n"] == 12
        snapshot_store.start()
        for _ in range(10):
            snapshot_store.start()
        alive = [
            thread
            for thread in threading.enumerate()
            if thread.name == "observer-snapshot" and thread.is_alive()
        ]
        assert len(alive) == 1
    finally:
        snapshot_store.interval_s = 60.0
        snapshot_store.stop()
        snapshot_store.clear()


def test_stamp_marks_cards_ready() -> None:
    stamped = stamp_payload(
        {"ok": True, "observers": [{"id": "f111"}], "pulses": []},
        generated_at="2026-10-19T21:04:00.000000Z",
    )
    assert stamped["status"] == "ready"
    assert stamped["empty"] is False
    assert stamped["generated_at"] == "2026-10-19T21:04:00.000000Z"


@pytest.fixture(autouse=True)
def _stop_snapshot_thread():
    """Leave the suite without a refresher thread from these tests."""
    snapshot_store.stop()
    yield
    snapshot_store.stop()
    snapshot_store.interval_s = 60.0
    snapshot_store.scan_poll_s = 2.0
