"""BL8 observer card: read-only status, degraded when the book is not mounted.

These tests do not start the shadow worker, call Bybit, or write the hourly
ledger. The SQLite file is a fixture shaped like the isolated BL8 book.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.observer_status import bl8_observer

NOW = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)
RELEASE = "b1f1c3fedba7fbda03e4d478077763eb971e636d"


@pytest.fixture(autouse=True)
def _no_bl8_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("BL8_STATE_DIR", "BL8_STATUS_PATH", "BL8_DB_PATH", "BL8_CONFIG_PATH"):
        monkeypatch.delenv(key, raising=False)


def _ms(stamp: datetime) -> int:
    return int(stamp.timestamp() * 1000)


def _init_db(path) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
        CREATE TABLE observations(id INTEGER PRIMARY KEY, t INTEGER, kind TEXT, payload TEXT);
        CREATE TABLE signals(uid TEXT PRIMARY KEY, symbol TEXT, status TEXT, payload TEXT);
        CREATE TABLE positions(uid TEXT PRIMARY KEY, symbol TEXT, status TEXT, payload TEXT);
        CREATE TABLE events(id TEXT PRIMARY KEY, uid TEXT, t INTEGER, kind TEXT, amount REAL, payload TEXT);
        """
    )
    return db


def _sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_missing_bl8_files_are_a_degraded_empty_card(tmp_path) -> None:
    status = tmp_path / "status.json"
    database = tmp_path / "paper.db"
    card = bl8_observer(now=NOW, status_path=status, db_path=database, config_path=tmp_path / "missing.json")
    assert card["id"] == "bl8"
    assert card["health"] == "unavailable"
    assert card["degraded"] is True
    assert card["isolated"] is True
    assert card["live_book"] is False
    assert card["paper_only"] is True
    assert card["coverage"]["available"] is None
    assert card["coverage"]["expected"] is None
    assert card["open_positions_count"] is None
    assert card["open_positions"] is None
    assert card["paper_pnl"]["equity_usdt"] is None
    assert card["paper_pnl"]["cash_usdt"] is None
    assert card["scan"]["complete"] is None
    assert card["scan"]["rate_limit_errors"] is None
    assert card["scan"]["label"] == "unknown"
    assert card["blotter"] is None
    assert status.exists() is False
    assert database.exists() is False
    assert "status.json" in card["degraded_reason"]
    assert "paper.db" in card["degraded_reason"]


def test_bl8_card_reads_scan_pnl_and_rate_limits_without_writing(tmp_path) -> None:
    status = tmp_path / "status.json"
    database = tmp_path / "paper.db"
    config = tmp_path / "mar_bl8_shadow_v1.json"
    config.write_text(
        json.dumps(
            {
                "sizing_policy": "hourly_paper_limits",
                "live_authorized": False,
                "universe": ["AAAUSDT", "BBBUSDT", "CCCUSDT"],
            }
        ),
        encoding="utf-8",
    )
    started = NOW - timedelta(minutes=5)
    status.write_text(
        json.dumps(
            {
                "heartbeat_ms": _ms(NOW),
                "started_ms": _ms(started),
                "config_sha": "abc",
                "release": RELEASE,
                "paper_only": True,
                "jobs": 0,
                "universe_scan_complete": False,
                "equity": {
                    "cash_pnl_usdt": 1.5,
                    "unrealized_pnl_usdt": 2.0,
                    "account_equity_usdt": 10003.5,
                },
                "audit": {"open_positions": 1, "closed_positions": 1},
            }
        ),
        encoding="utf-8",
    )
    db = _init_db(database)
    observations = [
        (
            _ms(NOW - timedelta(hours=2)),
            "context",
            {"symbol": "AAAUSDT", "reason": "no_signal", "instrument": {"status": "Trading"}},
        ),
        (
            _ms(NOW - timedelta(hours=1, minutes=30)),
            "context",
            {"symbol": "AAAUSDT", "reason": "no_signal", "instrument": {"status": "Trading"}},
        ),
        (
            _ms(NOW - timedelta(hours=1, minutes=20)),
            "context",
            {"symbol": "BBBUSDT", "reason": "instrument_unavailable", "instrument": [{"status": "Closed"}]},
        ),
        (
            _ms(NOW - timedelta(minutes=5)),
            "error",
            {
                "operation": "context",
                "identity": "CCCUSDT",
                "error": "RateLimited: HTTP 200 retCode 10006 after 5 attempts",
            },
        ),
        (
            _ms(NOW - timedelta(minutes=20)),
            "entry_rejected",
            {"uid": "AAAUSDT|B|1|1", "reason": "below_min_notional"},
        ),
        (
            _ms(NOW - timedelta(minutes=10)),
            "entry_rejected",
            {"uid": "AAAUSDT|B|1|2", "reason": "fill_gate"},
        ),
        (
            _ms(NOW - timedelta(hours=30)),
            "entry_rejected",
            {"uid": "OLD|1", "reason": "missed_action"},
        ),
    ]
    for stamp, kind, payload in observations:
        db.execute(
            "INSERT INTO observations(t, kind, payload) VALUES (?, ?, ?)",
            (stamp, kind, json.dumps(payload)),
        )
    db.execute(
        "INSERT INTO positions VALUES (?, ?, ?, ?)",
        (
            "open-1",
            "AAAUSDT",
            "open",
            json.dumps(
                {
                    "uid": "open-1",
                    "symbol": "AAAUSDT",
                    "entry_price": 100.0,
                    "quantity": 2.0,
                    "mark_price": 101.0,
                    "stop": 90.0,
                    "target": 110.0,
                    "entry_ms": _ms(NOW - timedelta(minutes=30)),
                }
            ),
        ),
    )
    db.execute(
        "INSERT INTO positions VALUES (?, ?, ?, ?)",
        (
            "closed-1",
            "ETHUSDT",
            "closed",
            json.dumps(
                {
                    "uid": "closed-1",
                    "symbol": "ETHUSDT",
                    "entry_price": 2000.0,
                    "exit_price": 2010.0,
                    "quantity": 0.1,
                    "gross_pnl": 1.0,
                    "entry_fee": 0.2,
                    "exit_fee": 0.3,
                    "exit_reason": "target",
                    "exit_ms": _ms(NOW - timedelta(minutes=15)),
                }
            ),
        ),
    )
    db.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
        ("closed-1|entryfee", "closed-1", _ms(NOW - timedelta(hours=1)), "entry_fee", -0.2, "{}"),
    )
    db.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
        ("closed-1|close", "closed-1", _ms(NOW - timedelta(minutes=15)), "close", 1.7, "{}"),
    )
    db.commit()
    db.close()
    before = _sha(database)
    status_before = status.read_text(encoding="utf-8")

    card = bl8_observer(now=NOW, status_path=status, db_path=database, config_path=config)

    assert _sha(database) == before
    assert status.read_text(encoding="utf-8") == status_before
    assert database.with_name(database.name + "-wal").exists() is False
    assert card["health"] == "ok"
    assert card["degraded"] is False
    assert card["sizing_policy"] == "hourly_paper_limits"
    assert card["release_sha"] == RELEASE
    assert card["release_short"] == RELEASE[:12]
    assert card["coverage"] == {"available": 1, "closed": 1, "expected": 3, "scanned": 2}
    assert card["census"]["closed_by_reason"] == {"instrument_unavailable": 1}
    assert card["scan"]["complete"] is False
    assert card["scan"]["label"] == "incomplete"
    assert card["scan"]["rate_limit_errors"] == 1
    assert card["scan"]["error_count"] == 1
    assert card["scan"]["retcodes"] == {"10006": 1}
    assert card["banner"]["tone"] == "warn"
    assert card["rejections"]["latest_hour"]["by_reason"] == {
        "below_min_notional": 1,
        "fill_gate": 1,
    }
    assert card["rejections"]["last_24h"]["by_reason"]["no_signal"] == 2
    assert card["rejections"]["last_24h"]["by_reason"]["instrument_unavailable"] == 1
    assert "missed_action" not in card["rejections"]["last_24h"]["by_reason"]
    assert card["open_positions_count"] == 1
    assert card["open_positions"][0]["symbol"] == "AAAUSDT"
    assert card["open_positions"][0]["side"] == "LONG"
    assert card["open_positions"][0]["unrealised_pnl"] == pytest.approx(2.0)
    assert card["blotter"][0]["symbol"] == "ETHUSDT"
    assert card["blotter"][0]["net_pnl"] == pytest.approx(1.5)
    assert card["paper_pnl"]["equity_usdt"] == pytest.approx(10003.5)
    assert card["paper_pnl"]["cash_usdt"] == pytest.approx(1.5)
    assert card["live_book"] is False
    assert "mar-bl8-shadow.service" in card["health_hint"]


def test_complete_scan_with_no_errors_reports_a_real_zero(tmp_path) -> None:
    status = tmp_path / "status.json"
    database = tmp_path / "paper.db"
    status.write_text(
        json.dumps(
            {
                "heartbeat_ms": _ms(NOW),
                "started_ms": _ms(NOW - timedelta(minutes=2)),
                "release": RELEASE,
                "paper_only": True,
                "universe_scan_complete": True,
            }
        ),
        encoding="utf-8",
    )
    db = _init_db(database)
    db.execute(
        "INSERT INTO observations(t, kind, payload) VALUES (?, ?, ?)",
        (
            _ms(NOW),
            "context",
            json.dumps({"symbol": "AAAUSDT", "reason": "no_signal", "instrument": {"status": "Trading"}}),
        ),
    )
    db.commit()
    db.close()
    card = bl8_observer(now=NOW, status_path=status, db_path=database)
    assert card["scan"]["complete"] is True
    assert card["scan"]["label"] == "complete"
    assert card["scan"]["rate_limit_errors"] == 0
    assert card["scan"]["error_count"] == 0
    assert card["banner"]["tone"] == "ok"


def test_stale_heartbeat_is_not_a_fresh_service(tmp_path) -> None:
    status = tmp_path / "status.json"
    database = tmp_path / "paper.db"
    _init_db(database).close()
    status.write_text(
        json.dumps(
            {
                "heartbeat_ms": _ms(NOW - timedelta(minutes=5)),
                "release": RELEASE,
                "paper_only": True,
                "universe_scan_complete": True,
            }
        ),
        encoding="utf-8",
    )
    card = bl8_observer(now=NOW, status_path=status, db_path=database)
    assert card["health"] == "stale"
    assert card["degraded"] is True
    assert "heartbeat" in card["degraded_reason"]


def test_observer_routes_are_get_only(firm_db, monkeypatch, tmp_path) -> None:
    """The desk can poll BL8. It cannot post a scan, an order, or a write."""
    monkeypatch.setenv("BL8_STATE_DIR", str(tmp_path / "bl8-paper"))
    from api.app import app

    client = TestClient(app)
    listed = client.get("/api/observers")
    assert listed.status_code == 200
    body = listed.json()
    assert [row["id"] for row in body["observers"]] == ["f111", "bl8"]
    assert [row["id"] for row in body["pulses"]] == ["f111", "bl8"]
    assert all(row["live_book"] is False for row in body["observers"])
    bl8 = client.get("/api/bl8")
    assert bl8.status_code == 200
    card = bl8.json()
    assert card["health"] == "unavailable"
    assert card["coverage"]["available"] is None
    assert card["scan"]["rate_limit_errors"] is None
    one = client.get("/api/observers/f111")
    assert one.status_code == 200
    assert one.json()["id"] == "f111"
    assert client.get("/api/observers/NOPE").status_code == 404
    assert client.post("/api/observers/bl8").status_code == 405
    assert client.post("/api/bl8").status_code == 405
    assert client.post("/api/observers").status_code == 405
    f111 = client.get("/api/f111")
    assert f111.status_code == 200
    assert "registry" in f111.json()
    assert "closed_by_reason" in f111.json()["registry"]
