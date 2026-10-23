"""Desk panel cache. Display only. The trading path is not imported here."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.dashboard_cache import PanelCache, panel_cache
from api.desk_status import f111_status
from api.observer_status import list_observers

ROOT = Path(__file__).resolve().parents[1]
HOUR = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 16, 15, 30, tzinfo=timezone.utc)

# Blobs of the trading path and the book. A desk patch that edits one of
# these has changed more than the dashboard.
_UNTOUCHED = {
    # Manual closes drain after the book lock. Previous pin:
    # 96d213af8bd2fba886b6f72aa09342b23c8e28b3.
    "core/execution/engine.py": "dd5492d0ae8ca6f629f690348a224169b2712103",
    # The funding hook runs between plan and book while the lock is held.
    # Previous pin: 66479045eda3fd04ebe1c9cad50d6ebfe996bdee.
    "core/execution/paper.py": "821ec3eace98334565a11a7d5a8a22c447e97c68",
    # Open-position marks are fetched only when a fill is scheduled. Previous pin:
    # f820f0b81784c1cf4066481dd8e7a88505b31946.
    "core/execution/f111_paper.py": "20445ce624844b87c0d880963c0f7fb024517762",
    # GBN commit skips a bar that was already submitted. Previous pin:
    # 90df0f765fc32c27866f250697361896b8fe19e6.
    "core/execution/paper_bar_eval.py": "4462166658ad22b81c63bf07bddccb6a53575bcd",
    # STRATEGY_LOSS_BLOCK is refused above 10. Previous pin:
    # 31e6a009207c733e85adb378e5297636a37a6469.
    "config/settings.py": "556ea0784ce5c94c2bee16f19d9037593e36a569",
    # Feat book after #139. The repair-base pin 97d3f2ca is b00c4f73.
    "config/approved_strategies.json": "d33719d4c721c2ecfc5d90c5a079e9ce1c73c5aa",
}


def _book(path: Path, rows: int, *, marker: str) -> None:
    """A live-named book. ``marker`` is inside each row so a rewrite changes the sha."""
    payload: dict[str, object] = {"_generated_at": marker, "_verdict": "paper"}
    families = ("rsi_trend", "donchian_breakout", "ema_adx_trend")
    for index in range(rows):
        family = families[index % len(families)]
        side = "LONG" if index % 2 == 0 else "SHORT"
        payload[f"{family}:T{index}USDT:{side}:1h"] = {
            "approved": True,
            "paper_override": False,
            "failures": [],
            "timeframe": "1h",
            "strategy": family,
            "params": {"ema_period": 20, "marker": marker},
            "oos_trades": 40,
            "validated_at": "2026-09-01T00:00:00+00:00",
        }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _gate_row(index: int, *, run_id: str, registry: bool) -> dict[str, object]:
    stamp = HOUR.isoformat()
    reason = (
        "compression_gate",
        "extension_gate",
        "high_vol_filter",
        "base_signal_blocked",
    )[index % 4]
    row: dict[str, object] = {
        "strategy_version": "f111-paper-v1",
        "source_signal_time": stamp,
        "emitted_at": stamp,
        "symbol": f"T{index}USDT",
        "side": "LONG" if index % 2 == 0 else "SHORT",
        "run_id": run_id,
        "gate_decision": False,
        "rejection_reason": reason if not registry else "no_signal",
        "instrument_unavailable": False,
        "feature_values": {
            "extension_atr": 1.2,
            "compression": 0.3,
            "prior_atr": 80.0,
            "close": 100.0,
            "boundary": 99.0,
            "efficiency24": 0.2,
            "passes_loweff_cap": False,
            "exchange_status": "Trading",
            "f111_rejection_reason": reason,
        },
        "feature_asof_times": {"signal_close": stamp},
    }
    if registry:
        row["record_kind"] = "registry"
    return row


def _write_telemetry(path: Path, rows: int, *, run_id: str) -> None:
    # Census first, then the gate rows of that same scan. The cache key
    # reads the last line, so the scan id is ``run_id``.
    lines = [_gate_row(index, run_id=run_id, registry=True) for index in range(min(rows, 192))]
    lines.extend(_gate_row(index, run_id=run_id, registry=False) for index in range(rows))
    path.write_text("".join(json.dumps(row) + "\n" for row in lines), encoding="utf-8")


def _state(path: Path) -> None:
    path.write_text(
        json.dumps({"pending": [{"symbol": "T0USDT", "status": "watching"}], "protection": {}}),
        encoding="utf-8",
    )


def _bl8(path: Path, symbols: int, *, heartbeat_ms: int) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE observations(id INTEGER PRIMARY KEY, t INTEGER, kind TEXT, payload TEXT);
        CREATE TABLE signals(uid TEXT PRIMARY KEY, symbol TEXT, status TEXT, payload TEXT);
        CREATE TABLE positions(uid TEXT PRIMARY KEY, symbol TEXT, status TEXT, payload TEXT);
        CREATE TABLE events(
            id TEXT PRIMARY KEY, uid TEXT, t INTEGER, kind TEXT, amount REAL, payload TEXT
        );
        """
    )
    signal_ms = int(HOUR.timestamp() * 1000)
    for index in range(symbols):
        payload = {
            "symbol": f"T{index}USDT",
            "eligible_signal": False,
            "reason": "no_signal",
            "signal_ms": signal_ms,
            "instrument": {"symbol": f"T{index}USDT", "status": "Trading"},
        }
        db.execute(
            "INSERT INTO observations(t, kind, payload) VALUES (?, 'context', ?)",
            (signal_ms, json.dumps(payload)),
        )
    db.commit()
    db.close()
    status = path.parent / "status.json"
    status.write_text(
        json.dumps(
            {
                "heartbeat_ms": heartbeat_ms,
                "started_ms": heartbeat_ms - 60_000,
                "release": "cache-test",
                "paper_only": True,
                "universe_scan_complete": True,
            }
        ),
        encoding="utf-8",
    )


def _use_book(monkeypatch, book: Path) -> None:
    monkeypatch.setattr("config.universe.APPROVALS_PATH", book)
    panel_cache.clear()


def test_cached_request_is_under_one_second_on_a_2270_row_book(tmp_path, monkeypatch) -> None:
    """The warm F111 and observers reads must not rebuild the 2270-row scan."""
    book = tmp_path / "approved_strategies.json"
    _book(book, 2270, marker="scan-a")
    _use_book(monkeypatch, book)
    telemetry = tmp_path / "f111_telemetry.jsonl"
    state = tmp_path / "state.json"
    _write_telemetry(telemetry, 2270, run_id="scan-2270")
    _state(state)
    database = tmp_path / "paper.db"
    _bl8(database, 2270, heartbeat_ms=int(NOW.timestamp() * 1000))

    cold_f = f111_status(now=NOW, telemetry_path=telemetry, state_path=state)
    started = time.perf_counter()
    warm_f = f111_status(now=NOW, telemetry_path=telemetry, state_path=state)
    warm_f_s = time.perf_counter() - started
    assert warm_f_s < 1.0
    assert warm_f["computed_at"] == cold_f["computed_at"]
    assert isinstance(warm_f["age"], int) and warm_f["age"] >= 0
    why = warm_f["why_no_trade"]
    assert why["computed_at"] == warm_f["computed_at"]
    assert why["age"] == warm_f["age"]
    assert why["ok"] is True

    cold_o = list_observers(
        now=NOW,
        telemetry_path=telemetry,
        state_path=state,
        status_path=tmp_path / "status.json",
        db_path=database,
    )
    started = time.perf_counter()
    warm_o = list_observers(
        now=NOW,
        telemetry_path=telemetry,
        state_path=state,
        status_path=tmp_path / "status.json",
        db_path=database,
    )
    warm_o_s = time.perf_counter() - started
    assert warm_o_s < 1.0
    assert warm_o["computed_at"] == cold_o["computed_at"]
    assert isinstance(warm_o["age"], int)
    f111_card = next(card for card in warm_o["observers"] if card["id"] == "f111")
    assert f111_card["computed_at"] == warm_o["computed_at"]
    assert f111_card["age"] == warm_o["age"]
    assert f111_card["why_no_trade"]["computed_at"] == warm_o["computed_at"]
    assert f111_card["why_no_trade"]["ok"] is True


def test_cache_invalidates_when_the_book_or_the_scan_changes(tmp_path, monkeypatch) -> None:
    """A new book sha or a new scan id builds again. The same key does not."""
    book = tmp_path / "approved_strategies.json"
    _book(book, 30, marker="first")
    _use_book(monkeypatch, book)
    telemetry = tmp_path / "f111_telemetry.jsonl"
    state = tmp_path / "state.json"
    _write_telemetry(telemetry, 30, run_id="scan-1")
    _state(state)
    database = tmp_path / "paper.db"
    _bl8(database, 8, heartbeat_ms=int(NOW.timestamp() * 1000))
    kwargs = {
        "now": NOW,
        "telemetry_path": telemetry,
        "state_path": state,
        "status_path": tmp_path / "status.json",
        "db_path": database,
    }

    first = f111_status(now=NOW, telemetry_path=telemetry, state_path=state)
    again = f111_status(now=NOW, telemetry_path=telemetry, state_path=state)
    assert again["computed_at"] == first["computed_at"]

    time.sleep(0.01)
    _book(book, 30, marker="second")
    retimed = f111_status(now=NOW, telemetry_path=telemetry, state_path=state)
    assert retimed["computed_at"] != first["computed_at"]

    time.sleep(0.01)
    with telemetry.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_gate_row(0, run_id="scan-2", registry=True)) + "\n")
    rescanned = f111_status(now=NOW, telemetry_path=telemetry, state_path=state)
    assert rescanned["computed_at"] != retimed["computed_at"]
    assert rescanned["registry"]["evaluated"] == 1

    observers = list_observers(**kwargs)
    time.sleep(0.01)
    db = sqlite3.connect(database)
    signal_ms = int(HOUR.timestamp() * 1000)
    db.execute(
        "INSERT INTO observations(t, kind, payload) VALUES (?, 'context', ?)",
        (
            signal_ms,
            json.dumps({"symbol": "NEWUSDT", "reason": "no_signal", "signal_ms": signal_ms}),
        ),
    )
    db.commit()
    db.close()
    # Touch the heartbeat too. MAX(id) is the scan id; either change misses.
    status = tmp_path / "status.json"
    blob = json.loads(status.read_text(encoding="utf-8"))
    blob["heartbeat_ms"] = int((NOW + timedelta(seconds=5)).timestamp() * 1000)
    status.write_text(json.dumps(blob), encoding="utf-8")
    refreshed = list_observers(**kwargs)
    assert refreshed["computed_at"] != observers["computed_at"]


def test_single_flight_builds_once() -> None:
    """Concurrent readers wait for the build that is already running."""
    cache = PanelCache(ttl_seconds=30)
    builds = 0
    gate = threading.Barrier(6)

    def build() -> dict[str, int]:
        nonlocal builds
        builds += 1
        time.sleep(0.15)
        return {"n": builds}

    def worker() -> None:
        gate.wait()
        payload = cache.fetch("panel", ("same",), build)
        assert payload["n"] == 1
        assert payload["age"] == 0 or payload["age"] >= 0

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert builds == 1


def test_cache_expires_on_the_ttl() -> None:
    cache = PanelCache(ttl_seconds=0.05)
    calls = 0

    def build() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"n": calls}

    first = cache.fetch("ttl", ("k",), build)
    second = cache.fetch("ttl", ("k",), build)
    assert first["computed_at"] == second["computed_at"]
    assert calls == 1
    time.sleep(0.06)
    third = cache.fetch("ttl", ("k",), build)
    assert calls == 2
    assert third["computed_at"] != first["computed_at"]


def test_trading_path_does_not_import_the_desk_cache() -> None:
    """Engine, paper, config, and the book stay on their repair-base blobs."""
    banned = (
        "api.dashboard_cache",
        "api.why_no_trade",
        "api.observer_status",
        "dashboard_cache",
    )
    for base in (ROOT / "core", ROOT / "config", ROOT / "firm"):
        for path in base.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for name in banned:
                assert name not in text, f"{path.relative_to(ROOT)} mentions {name}"
    for rel, blob in _UNTOUCHED.items():
        hashed = subprocess.check_output(
            ["git", "hash-object", str(ROOT / rel)],
            text=True,
        ).strip()
        assert hashed == blob


def test_observers_poll_is_slow_and_pauses_while_hidden() -> None:
    """#152 poller: 60s on success, 4s abort, one loop, pause while hidden.

    The 15s desk load() does not fetch /api/observers, and the page does
    not arm a second observers interval beside ObserverPoll.
    """
    html = (ROOT / "api" / "static" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "api" / "static" / "observers_poll.js").read_text(encoding="utf-8")

    assert "var SUCCESS_MS = 60000;" in script
    assert "var DEFAULT_TIMEOUT_MS = 4000;" in script
    assert "var timeoutMs = opts.timeoutMs || DEFAULT_TIMEOUT_MS;" in script
    # A poll already running is the in-flight guard. It does not start another.
    assert "if (stopped || paused || inFlight) return Promise.resolve(view);" in script
    assert "inFlight = true;" in script
    assert "function pause()" in script
    assert "paused = true;" in script
    assert "if (retryTimer) clearTimeout(retryTimer);" in script
    assert "function resume()" in script
    assert "return poll();" in script
    # Failure backoff stays 2s doubling up to 60s. Only the success wait moved.
    assert "var FAILURE_BASE_MS = 2000;" in script
    assert "var MAX_BACKOFF_MS = 60000;" in script

    assert "const OBSERVERS_TIMEOUT_MS = 4000;" in html
    assert html.count("ObserverPoll.create(") == 1
    visibility = html.split('document.addEventListener("visibilitychange"', 1)[1].split("});", 1)[0]
    assert 'document.visibilityState === "hidden"' in visibility
    assert "observerPoll.pause()" in visibility
    assert "observerPoll.resume()" in visibility

    assert html.count("setInterval(load, 15000);") == 1
    load = html.split("async function load(", 1)[1].split("function tickClock(", 1)[0]
    assert "/api/observers" not in load
    # Clock (1s) and the desk load (15s) are the only intervals on the page.
    assert html.count("setInterval(") == 2
    assert "OBSERVERS_POLL_MS" not in html
    assert "function loadObservers(" not in html
    assert "function armObservers(" not in html
    assert html.count('get("/api/observers"') == 1
