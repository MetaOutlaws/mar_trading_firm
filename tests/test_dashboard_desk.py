"""Dashboard display: F111 census, header clocks, live book, stale escalations.

These tests do not place orders, write config/approved_strategies.json, or
change a signal, gate, risk check, or engine plan.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.desk_status import (
    desk_header,
    f111_status,
    live_approvals_path,
    read_live_approval_book,
)
from config.settings import get_settings

NOW = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc)


def _book(n_approved: int, n_override: int, *, generated: str, verdict: str) -> dict:
    payload: dict = {"_generated_at": generated, "_verdict": verdict}
    for i in range(n_approved):
        payload[f"sleeve:A{i:03d}USDT:LONG:1h"] = {
            "approved": True,
            "strategy": "sleeve",
            "timeframe": "1h",
        }
    for i in range(n_override):
        payload[f"veto:B{i:03d}USDT:SHORT:4h"] = {
            "approved": False,
            "paper_override": True,
            "strategy": "veto",
            "timeframe": "4h",
        }
    return payload


def test_strategies_panel_reads_live_book_not_oct1_snapshot(monkeypatch, tmp_path) -> None:
    """A cached universe loaded from an Oct 1 snapshot must not win.

    The panel follows the mounted ``approved_strategies.json`` symlink.
    """
    from config import universe as universe_mod
    from config.universe import get_universe
    from api.app import strategies

    live = tmp_path / "mount" / "approved_strategies.json"
    live.parent.mkdir()
    live.write_text(
        json.dumps(
            _book(12, 50, generated="2026-10-10T08:00:00+00:00", verdict="LIVE BOOK")
        ),
        encoding="utf-8",
    )
    snapshot = tmp_path / "approved_strategies.2026-10-01.json"
    snapshot.write_text(
        json.dumps(
            _book(3, 4, generated="2026-10-01T00:00:00+00:00", verdict="STALE SNAPSHOT")
        ),
        encoding="utf-8",
    )
    mounted = tmp_path / "approved_strategies.json"
    mounted.symlink_to(live)

    monkeypatch.setattr(universe_mod, "APPROVALS_PATH", snapshot)
    get_universe.cache_clear()
    stale = get_universe()
    assert len(stale.approved_records) == 3

    with pytest.raises(RuntimeError, match="dated snapshot"):
        live_approvals_path(snapshot)

    monkeypatch.setattr(universe_mod, "APPROVALS_PATH", mounted)
    payload = strategies()
    assert payload["approved_count"] == 12
    assert payload["paper_override_count"] == 50
    assert payload["verdict"] == "LIVE BOOK"
    assert payload["generated_at"].startswith("2026-10-10")
    assert payload["source_path"] == str(live.resolve())
    assert "STALE" not in payload["verdict"]
    direct = read_live_approval_book()
    strategy_rows = [
        key for key in direct["approvals"] if not str(key).startswith("_")
    ]
    assert len(strategy_rows) == 62


def test_quiet_reasons_use_the_live_scan_not_an_rsi_template(monkeypatch, tmp_path) -> None:
    from config import universe as universe_mod
    from api.app import _quiet_reasons

    book = tmp_path / "approved_strategies.json"
    book.write_text(
        json.dumps(_book(12, 50, generated="2026-10-10T00:00:00+00:00", verdict="LIVE")),
        encoding="utf-8",
    )
    monkeypatch.setattr(universe_mod, "APPROVALS_PATH", book)

    idle = " ".join(_quiet_reasons(None, employee_llm_ok=True, xai_ok=True))
    assert "RSI" not in idle
    assert "golden-cross" not in idle
    assert "40 pairs/50 vetoes" not in idle
    assert "12 research-approved" in idle
    assert "50 operator paper override" in idle

    scanned = _quiet_reasons(
        {
            "symbols_scanned": 40,
            "signals_found": 0,
            "orders_placed": 0,
            "rejections": 0,
            "plan": [
                {"strategy": "week_open_reclaim", "approved": True, "paper_override": False},
                {"strategy": "mama_fama_cross", "approved": False, "paper_override": True},
            ],
        },
        employee_llm_ok=True,
        xai_ok=True,
    )
    text = " ".join(scanned)
    assert "RSI + golden-cross" not in text
    assert "40 pairs/50 vetoes" not in text
    assert any("scanned 40 pairs" in row and "week_open_reclaim" in row for row in scanned)
    assert any("mama_fama_cross" in row for row in scanned)


def test_f111_panel_counts_sleeves_reasons_and_retests(tmp_path) -> None:
    telemetry = tmp_path / "f111_telemetry.jsonl"
    state = tmp_path / "f111_paper_state.json"
    old_registry = [
        {
            "record_kind": "registry",
            "symbol": "OLDUSDT",
            "side": side,
            "instrument_unavailable": True,
            "rejection_reason": "exchange status Closed",
            "gate_decision": False,
        }
        for side in ("LONG", "SHORT")
    ]
    latest_registry = []
    for index in range(3):
        for side in ("LONG", "SHORT"):
            latest_registry.append(
                {
                    "record_kind": "registry",
                    "symbol": f"A{index}USDT",
                    "side": side,
                    "instrument_unavailable": False,
                    "rejection_reason": "no_signal",
                    "gate_decision": False,
                }
            )
    latest_registry.append(
        {
            "record_kind": "registry",
            "symbol": "DEADUSDT",
            "side": "LONG",
            "instrument_unavailable": True,
            "rejection_reason": "exchange status Closed",
            "gate_decision": False,
        }
    )
    latest_registry.append(
        {
            "record_kind": "registry",
            "symbol": "DEADUSDT",
            "side": "SHORT",
            "instrument_unavailable": True,
            "rejection_reason": "not listed on Bybit linear",
            "gate_decision": False,
        }
    )
    gates = [
        {
            "symbol": "A0USDT",
            "side": "LONG",
            "gate_decision": False,
            "rejection_reason": "compression_gate",
            "source_signal_time": "2026-10-09T10:00:00+00:00",
        },
        {
            "symbol": "A0USDT",
            "side": "LONG",
            "gate_decision": False,
            "rejection_reason": "compression_gate",
            "source_signal_time": "2026-10-10T14:00:00+00:00",
        },
        {
            "symbol": "A0USDT",
            "side": "SHORT",
            "gate_decision": False,
            "rejection_reason": "extension_gate",
            "source_signal_time": "2026-10-10T15:00:00+00:00",
        },
        {
            "symbol": "A1USDT",
            "side": "LONG",
            "gate_decision": False,
            "rejection_reason": "extension_gate",
            "source_signal_time": "2026-10-10T15:10:00+00:00",
        },
        {
            "symbol": "A1USDT",
            "side": "SHORT",
            "gate_decision": True,
            "rejection_reason": None,
            "source_signal_time": "2026-10-10T15:00:00+00:00",
        },
        {
            "deploy_marker": "restart",
            "rejection_reason": "restart",
            "gate_decision": None,
        },
    ]
    lines = old_registry + gates[:1] + latest_registry + gates[1:]
    telemetry.write_text(
        "\n".join(json.dumps(row) for row in lines) + "\n",
        encoding="utf-8",
    )
    state.write_text(
        json.dumps(
            {
                "version": 1,
                "pending": [
                    {"symbol": "A0USDT", "status": "watching"},
                    {"symbol": "A1USDT", "status": "scheduled"},
                    {"symbol": "A2USDT", "status": "filled"},
                ],
                "protection": {"A0USDT": {"side": 1}, "A1USDT": {"side": -1}},
            }
        ),
        encoding="utf-8",
    )

    panel = f111_status(now=NOW, telemetry_path=telemetry, state_path=state)
    assert panel["expected_sleeves"] == 192
    assert panel["registry"]["evaluated"] == 8
    assert panel["registry"]["available"] == 6
    assert panel["registry"]["closed"] == 2
    assert panel["registry"]["closed_by_reason"] == {
        "exchange status Closed": 1,
        "not listed on Bybit linear": 1,
    }
    assert panel["rejections"]["latest_hour"]["hour_start"].startswith("2026-10-10T15:00:00")
    assert panel["rejections"]["latest_hour"]["by_reason"] == {"extension_gate": 2}
    assert panel["rejections"]["last_24h"]["by_reason"]["compression_gate"] == 1
    assert panel["rejections"]["last_24h"]["by_reason"]["extension_gate"] == 2
    assert "restart" not in panel["rejections"]["last_24h"]["by_reason"]
    assert panel["last_bar_close_evaluation"].startswith("2026-10-10T15:10:00")
    assert panel["pending_retests"] == 2
    assert panel["protection"] == 2
    assert panel["telemetry_path"] == str(telemetry)


def test_header_shows_sha_cycle_soko_and_bar_clocks(monkeypatch, tmp_path) -> None:
    soko = tmp_path / "last_soko_trend.json"
    soko.write_text(
        json.dumps({"trend": "chop", "as_of": "2026-10-10T12:30:00+00:00"}),
        encoding="utf-8",
    )
    bars = tmp_path / "paper_bar_eval_state.json"
    bars.write_text(
        json.dumps(
            {
                "version": 1,
                "sleeves": {
                    "BTCUSDT|15m|LONG|sleeve": {
                        "bar_open": "2026-10-10T15:00:00+00:00",
                        "evaluated_at": "2026-10-10T15:15:02+00:00",
                    },
                    "BTCUSDT|15min|SHORT|older": {
                        "evaluated_at": "2026-10-10T15:00:00+00:00",
                    },
                    "ETHUSDT|1h|LONG|hourly": {
                        "evaluated_at": "2026-10-10T15:00:10+00:00",
                    },
                    "ETHUSDT|4h|SHORT|four": {
                        "evaluated_at": "2026-10-10T12:00:05+00:00",
                    },
                    "XRPUSDT|30m|LONG|ignored": {
                        "evaluated_at": "2026-10-10T15:20:00+00:00",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEPLOYED_GIT_SHA", "abc123def4567890")
    header = desk_header(
        now=NOW,
        cycle={"started_at": "2026-10-10T15:00:00+00:00"},
        soko_path=soko,
        bar_state_path=bars,
    )
    assert header["git"]["sha"] == "abc123def4567890"
    assert header["git"]["short"] == "abc123def456"
    assert header["cycle"]["started_at"].startswith("2026-10-10T15:00:00")
    assert header["cycle"]["age_seconds"] == 30 * 60
    assert header["soko"]["label"] == "chop"
    assert header["soko"]["as_of"].startswith("2026-10-10T12:30:00")
    assert header["soko"]["age_seconds"] == 3 * 60 * 60
    assert header["bar_close"]["15m"]["evaluated_at"].startswith("2026-10-10T15:15:02")
    assert header["bar_close"]["1h"]["evaluated_at"].startswith("2026-10-10T15:00:10")
    assert header["bar_close"]["4h"]["evaluated_at"].startswith("2026-10-10T12:00:05")
    assert header["bar_close"]["15m"]["age_seconds"] == 15 * 60 - 2


def test_suspended_escalation_expires_without_a_manual_edit(firm_db) -> None:
    """The outdated halt ticket clears through expiry, not a one-row SQL edit."""
    from core.db import session_scope
    from firm import memory
    from firm.memory_models import EscalationRecord

    stale = memory.escalate(
        "ops_engineer",
        "Trading is suspended",
        "kill switch was tripped last week",
        severity="critical",
    )
    fresh = memory.escalate(
        "ops_engineer",
        "Bybit feed is slow",
        "still inside the timeout",
        severity="warning",
    )
    moment = datetime.now(timezone.utc)
    with session_scope() as session:
        row = session.get(EscalationRecord, stale)
        row.created_at = moment - timedelta(hours=48)
        row.timeout_hours = 24.0
        session.get(EscalationRecord, fresh).timeout_hours = 24.0

    opened = memory.open_escalations()
    titles = [row["title"] for row in opened]
    assert "Trading is suspended" not in titles
    assert "Bybit feed is slow" in titles

    # A new suspension after expiry is a new row. The expired one stays closed.
    again = memory.escalate_once(
        "ops_engineer",
        "Trading is suspended",
        "a later halt",
        severity="critical",
    )
    assert again is not None
    assert again != stale
    titles = [row["title"] for row in memory.open_escalations()]
    assert titles.count("Trading is suspended") == 1


def test_bulk_ack_endpoint_expires_stale_rows(firm_db) -> None:
    from core.db import session_scope
    from firm import memory
    from firm.memory_models import EscalationRecord

    first = memory.escalate("ops_engineer", "Trading is suspended", "old", severity="critical")
    second = memory.escalate("desk_head", "Catalog review waiting", "also old", severity="warning")
    kept = memory.escalate("ops_engineer", "Bybit feed is slow", "fresh", severity="warning")
    moment = datetime.now(timezone.utc)
    with session_scope() as session:
        for eid in (first, second):
            row = session.get(EscalationRecord, eid)
            row.created_at = moment - timedelta(hours=30)
            row.timeout_hours = 24.0

    client = TestClient(app_module_app())
    response = client.post(
        "/api/escalations/ack-stale",
        headers={"X-API-Token": get_settings().api_token},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert set(body["ids"]) == {first, second}
    titles = [row["title"] for row in memory.open_escalations()]
    assert titles == ["Bybit feed is slow"]
    assert kept in {row["id"] for row in memory.open_escalations()}


def app_module_app():
    from api.app import app

    return app
