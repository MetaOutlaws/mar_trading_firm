"""Why-no-trade panel. Latest scan only. No orders and no threshold edits."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from api.observer_status import bl8_observer
from api.why_no_trade import MEAN_DISTANCE_MIN, build_f111_why, score_bl8_hours
from core.strategy.f111_semantics import EXTENSION_MAX_INCLUSIVE

NOW = datetime(2026, 10, 16, 15, 30, tzinfo=timezone.utc)
HOUR = datetime(2026, 10, 16, 15, 0, tzinfo=timezone.utc)
HOUR_MS = 3_600_000


def _ms(stamp: datetime) -> int:
    return int(stamp.timestamp() * 1000)


def _hours(close: float, opened: float, *, prev_close: float = 97.5) -> tuple[dict, int]:
    """25 hourly bars. The last bar is the one the scan judged."""
    rows = []
    for index in range(25):
        stamp = HOUR - timedelta(hours=24 - index)
        price = 100.0
        if 3 <= index <= 22:
            price = 99.0 if (index - 3) % 2 == 0 else 101.0
        bar_open = bar_high = bar_low = bar_close = price
        if index == 23:
            bar_open, bar_high, bar_low, bar_close = 98.0, 98.2, 97.0, prev_close
        if index == 24:
            bar_open = opened
            bar_close = close
            bar_high = max(opened, close, 100.0)
            bar_low = min(opened, close, 98.5)
        start = _ms(stamp) - HOUR_MS
        rows.append([str(start), str(bar_open), str(bar_high), str(bar_low), str(bar_close), "10", "10"])
    return {"result": {"list": rows}}, _ms(HOUR)


def _context(symbol: str, close: float, opened: float, *, reason: str, eligible: bool) -> dict:
    raw, signal_ms = _hours(close, opened)
    return {
        "symbol": symbol,
        "eligible_signal": eligible,
        "reason": reason,
        "signal_ms": signal_ms,
        "instrument": {"symbol": symbol, "status": "Trading"},
        "raw_context": [raw, {"result": {"list": []}}],
    }


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


def _insert(db: sqlite3.Connection, stamp: datetime, kind: str, payload: dict) -> None:
    db.execute(
        "INSERT INTO observations(t, kind, payload) VALUES (?, ?, ?)",
        (_ms(stamp), kind, json.dumps(payload)),
    )


def test_bl8_band_math_matches_the_frozen_distance() -> None:
    """Close, threshold, and gap come from the stored bars, not a new rule."""
    raw, _signal = _hours(99.30, 99.0)
    bars = []
    for row in raw["result"]["list"]:
        bars.append(
            {
                "t": int(row[0]) + HOUR_MS,
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
            }
        )
    bars.sort(key=lambda bar: bar["t"])
    readings = score_bl8_hours(bars)
    assert readings is not None
    distance = next(row for row in readings if row["gate"] == "mean_distance")
    value = 100.0 / 99.30 - 1.0
    assert distance["passed"] is False
    assert distance["value"] == pytest.approx(value, abs=1e-6)
    assert distance["threshold"] == MEAN_DISTANCE_MIN
    assert distance["gap"] == pytest.approx(MEAN_DISTANCE_MIN - value, abs=1e-6)
    assert distance["gap_text"].startswith("0.3%")
    earlier = [row for row in readings if row["gate"] != "mean_distance"]
    assert all(row["passed"] for row in earlier)


def test_prior_scan_does_not_inflate_the_current_why_panel(tmp_path) -> None:
    """A previous hour's no_signal pile stays out. Unavailable names are listed."""
    status = tmp_path / "status.json"
    database = tmp_path / "paper.db"
    status.write_text(
        json.dumps(
            {
                "heartbeat_ms": _ms(NOW),
                "started_ms": _ms(NOW - timedelta(minutes=20)),
                "release": "190ad181760744688db66306c8f19f3f113e6ed9",
                "paper_only": True,
                "universe_scan_complete": True,
            }
        ),
        encoding="utf-8",
    )
    db = _init_db(database)
    previous = HOUR - timedelta(hours=1)
    for index in range(30):
        _insert(
            db,
            previous,
            "context",
            {
                "symbol": f"OLD{index}USDT",
                "reason": "no_signal",
                "eligible_signal": False,
                "signal_ms": _ms(previous),
                "instrument": {"status": "Trading"},
            },
        )
    tight = _context("SOLUSDT", 99.05, 98.8, reason="no_signal", eligible=False)
    wide = _context("ETHUSDT", 99.30, 99.0, reason="no_signal", eligible=False)
    green = _context("XRPUSDT", 100.0, 110.0, reason="no_signal", eligible=False)
    for payload in (tight, wide, green):
        _insert(db, NOW, "context", payload)
    for index in range(17):
        status_name = "Closed" if index % 2 == 0 else "PreLaunch"
        _insert(
            db,
            NOW - timedelta(seconds=index),
            "context",
            {
                "symbol": f"DOWN{index}USDT",
                "reason": "instrument_unavailable",
                "eligible_signal": False,
                "instrument": [{"symbol": f"DOWN{index}USDT", "status": status_name}],
            },
        )
    _insert(
        db,
        NOW,
        "error",
        {
            "operation": "context",
            "identity": "ERRUSDT",
            "error": "RateLimited: HTTP 200 retCode 10006 after 5 attempts",
        },
    )
    _insert(
        db,
        previous,
        "error",
        {
            "operation": "context",
            "identity": "STALEUSDT",
            "error": "RateLimited: HTTP 200 retCode 10006 after 5 attempts",
        },
    )
    db.commit()
    db.close()

    card = bl8_observer(now=NOW, status_path=status, db_path=database)
    why = card["why_no_trade"]
    assert why["ok"] is True
    scanned = next(step for step in why["funnel"] if step["id"] == "scanned")
    data = next(step for step in why["funnel"] if step["id"] == "data_ok")
    distance = next(step for step in why["funnel"] if step["id"] == "mean_distance")
    # 3 measured symbols + 17 unavailable + the context error. The old hour is absent.
    assert scanned["count"] == 21
    assert data["drop_off"] == 18
    assert data["count"] == 3
    assert distance["count"] == 0
    assert distance["drop_off"] == 2
    assert {row["token"] for row in distance["failed"]} == {"SOL", "ETH"}
    assert "OLD0" not in json.dumps(why["funnel"])
    assert why["unavailable_count"] == 17
    assert {row["status"] for row in why["unavailable"]} == {"Closed", "PreLaunch"}
    assert [row["symbol"] for row in why["unavailable"]].count("DOWN0USDT") == 1
    assert why["closest_misses"][0]["token"] == "SOL"
    assert why["closest_misses"][0]["side"] == "LONG"
    assert why["closest_misses"][0]["gate"] == "mean_distance"
    assert why["closest_misses"][0]["threshold"] == MEAN_DISTANCE_MIN
    assert "0 of 2 passed the distance to the mean gate" in why["summary"]
    assert "Closest was SOL long" in why["summary"]
    assert "no_signal, count" not in why["summary"]
    assert any(row["symbol"] == "ERRUSDT" and row["reason"] == "error" for row in why["attempts"])
    assert all(row["symbol"] != "STALEUSDT" for row in why["attempts"])
    assert card["scan"]["complete"] is True
    assert card["live_book"] is False


def test_signalled_then_blocked_is_an_attempt_not_a_gate_miss(tmp_path) -> None:
    status = tmp_path / "status.json"
    database = tmp_path / "paper.db"
    status.write_text(
        json.dumps(
            {
                "heartbeat_ms": _ms(NOW),
                "started_ms": _ms(NOW - timedelta(minutes=5)),
                "release": "190ad181760744688db66306c8f19f3f113e6ed9",
                "paper_only": True,
                "universe_scan_complete": True,
            }
        ),
        encoding="utf-8",
    )
    db = _init_db(database)
    payload = _context("SOLUSDT", 98.6, 98.3, reason="candidate_requires_fill_gate", eligible=True)
    _insert(db, NOW, "context", payload)
    _insert(
        db,
        NOW,
        "entry_rejected",
        {"uid": "SOLUSDT|B|1|1", "reason": "below_min_notional"},
    )
    db.execute(
        "INSERT INTO signals VALUES (?, ?, ?, ?)",
        (
            "SOLUSDT|B|1|1",
            "SOLUSDT",
            "below_min_notional",
            json.dumps({"symbol": "SOLUSDT", "signal_ms": _ms(HOUR), "eligible_signal": True}),
        ),
    )
    db.commit()
    db.close()

    why = bl8_observer(now=NOW, status_path=status, db_path=database)["why_no_trade"]
    signal = next(step for step in why["funnel"] if step["id"] == "signal")
    risk = next(step for step in why["funnel"] if step["id"] == "risk_sizing")
    filled = next(step for step in why["funnel"] if step["id"] == "filled")
    assert signal["count"] == 1
    assert signal["drop_off"] == 0
    assert risk["drop_off"] == 1
    assert risk["failed"][0]["token"] == "SOL"
    assert filled["count"] == 0
    assert why["attempts"] == [
        {
            "symbol": "SOLUSDT",
            "token": "SOL",
            "side": "LONG",
            "reason": "min notional",
            "detail": "below_min_notional",
        }
    ]
    assert why["closest_misses"] == []
    assert "No fill: 1 signalled and none filled." in why["summary"]


def test_stored_checks_report_is_used_when_the_klines_are_absent() -> None:
    """A report-only checks block is enough. Missing numbers are not invented."""
    from api.why_no_trade import build_bl8_why

    stamp = HOUR
    with_report = {
        "symbol": "SOLUSDT",
        "eligible_signal": False,
        "reason": "no_signal",
        "signal_ms": _ms(HOUR),
        "instrument": {"status": "Trading"},
        "checks": [
            {
                "gate": "mean_distance",
                "value": 0.007,
                "threshold": MEAN_DISTANCE_MIN,
                "gap": MEAN_DISTANCE_MIN - 0.007,
                "passed": False,
                "units": "fraction",
                "short": True,
            }
        ],
    }
    bare = {
        "symbol": "ETHUSDT",
        "eligible_signal": False,
        "reason": "no_signal",
        "signal_ms": _ms(HOUR),
        "instrument": {"status": "Trading"},
    }
    why = build_bl8_why([(stamp, with_report), (stamp, bare)])
    assert why["closest_misses"][0]["symbol"] == "SOLUSDT"
    assert why["closest_misses"][0]["value"] == pytest.approx(0.007)
    assert len(why["closest_misses"]) == 1
    signal = next(step for step in why["funnel"] if step["id"] == "signal")
    assert any(row["symbol"] == "ETHUSDT" for row in signal["failed"])


def _f111_features(**overrides) -> dict:
    features = {
        "compression": 0.6,
        "extension_atr": 0.4,
        "prior_atr": 2.0,
        "close": 100.0,
        "open": 99.0,
        "volume_ratio": 2.0,
        "r24": 0.01,
        "close_location": 0.9,
        "boundary": 98.0,
        "true_range": 4.0,
        "filter_crsi": 40.0,
        "passes_crsi": True,
        "is_btc": False,
        "efficiency24": 0.5,
        "passes_loweff_cap": True,
    }
    features.update(overrides)
    return features


def test_f111_why_names_the_gate_the_extension_and_the_block() -> None:
    when = "2026-10-16T15:00:00+00:00"
    rows = [
        {
            "symbol": "SOLUSDT",
            "side": "LONG",
            "gate_decision": False,
            "rejection_reason": "extension_gate",
            "source_signal_time": when,
            "feature_values": _f111_features(extension_atr=1.04),
        },
        {
            "symbol": "ETHUSDT",
            "side": "LONG",
            "gate_decision": True,
            "rejection_reason": "exposure cap",
            "occupancy_or_risk_rejection": "exposure cap",
            "source_signal_time": when,
            "pending_retest_created_at": when,
            "feature_values": _f111_features(),
        },
        {
            "symbol": "SOLUSDT",
            "side": "LONG",
            "gate_decision": False,
            "rejection_reason": "compression_gate",
            "source_signal_time": "2026-10-16T12:00:00+00:00",
            "feature_values": _f111_features(compression=0.1),
        },
    ]
    census = [
        {
            "record_kind": "registry",
            "symbol": "DEADUSDT",
            "side": "LONG",
            "instrument_unavailable": True,
            "rejection_reason": "exchange status Closed",
            "feature_values": {"exchange_status": "Closed"},
        }
    ]
    why = build_f111_why(rows, census)
    assert why["ok"] is True
    extension = next(step for step in why["funnel"] if step["id"] == "extension_gate")
    assert extension["drop_off"] == 1
    assert extension["failed"][0]["token"] == "SOL"
    assert "12:00" not in json.dumps(why)
    miss = why["closest_misses"][0]
    assert miss["token"] == "SOL"
    assert miss["side"] == "LONG"
    assert miss["threshold"] == EXTENSION_MAX_INCLUSIVE
    assert miss["value"] == pytest.approx(1.04)
    assert miss["gap"] == pytest.approx(1.04 - EXTENSION_MAX_INCLUSIVE)
    assert "ATR over" in miss["gap_text"]
    assert why["unavailable"] == [
        {"symbol": "DEADUSDT", "token": "DEAD", "status": "Closed", "side": "LONG"}
    ]
    assert why["attempts"][0]["symbol"] == "ETHUSDT"
    assert why["attempts"][0]["reason"] == "risk limit"
    assert "Closest was SOL long" in why["summary"]
    assert "No fill: 1 signalled" in why["summary"]
