"""Per-scan Inbox summaries: diary rows, not decisions.

These tests do not place orders or change a signal, gate, risk check, or the
approval book. Live stays off.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from config.settings import get_settings
from core.db import session_scope
from core.strategy.base import SignalSide
from firm import memory
from firm.memory_models import Proposal, ProposalKind, ProposalStatus
from firm.scan_inbox import (
    HOURLY_CAP,
    expire_and_prune_scan_summaries,
    publish_book_notes,
    publish_f111_hourly,
    publish_scan_summary,
    summarise_f111_rows,
    summarise_sleeve_notes,
)
from tests.test_paper_bar_eval import Clock, RecordingStrategy, _engine, _entry

DASHBOARD = Path(__file__).resolve().parents[1] / "api" / "static" / "index.html"

# Floor the wall clock so every bar in one test shares one UTC hour, and the
# two-hour TTL is still in the future when the Inbox is listed.
HOUR = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _pending_summaries() -> list[dict]:
    return [row for row in memory.pending_proposals(limit=50) if row["kind"] == "informational"]


def _book(sleeve: str, bar: datetime, rejection: str, *, signal: bool = False, ordered: bool = False) -> dict:
    return {
        "sleeve_id": sleeve,
        "bar_time": bar.isoformat(),
        "signal": signal,
        "ordered": ordered,
        "rejection": rejection,
    }


def test_dedupe_is_scan_type_plus_bar_time(firm_db) -> None:
    """The same bar updates one row. A second scan type at that bar is another row."""
    bar = HOUR
    first = publish_book_notes(
        [_book("BTCUSDT|1h|LONG|sleeve", bar, "extension_gate")],
        now=HOUR,
    )
    again = publish_book_notes(
        [_book("BTCUSDT|1h|LONG|sleeve", bar, "extension_gate")],
        now=HOUR,
    )
    added = publish_book_notes(
        [_book("ETHUSDT|1h|SHORT|sleeve", bar, "compression_gate")],
        now=HOUR,
    )
    assert first[0]["action"] == "inserted"
    assert again[0]["action"] == "unchanged"
    assert added[0]["action"] == "updated"
    assert first[0]["id"] == again[0]["id"] == added[0]["id"]

    rows = _pending_summaries()
    assert len(rows) == 1
    payload = rows[0]["payload"]
    assert payload["dedupe_key"] == f"book|{bar.replace(microsecond=0).isoformat()}"
    assert payload["book_sleeves"] == 2
    assert payload["f111_sleeves"] == 0
    assert payload["rejection_counts"] == {"extension_gate": 1, "compression_gate": 1}
    assert "action" not in payload
    assert payload["informational"] is True

    f111 = publish_f111_hourly([], now=HOUR, pending_retests=0, bar_time=bar)
    assert f111["action"] == "inserted"
    assert f111["id"] != first[0]["id"]
    kinds = {row["payload"]["scan_type"] for row in _pending_summaries()}
    assert kinds == {"book", "f111"}


def test_summary_names_utc_and_gst_and_soko(firm_db) -> None:
    bar = HOUR
    soko = {"label": "chop", "as_of": HOUR.isoformat(), "age_seconds": 3 * 3600}
    publish_scan_summary(
        scan_type="book",
        bar_time=bar,
        summary=summarise_sleeve_notes([_book("BTCUSDT|1h|LONG|sleeve", bar, "no_signal")]),
        now=HOUR,
        soko=soko,
    )
    text = _pending_summaries()[0]["rationale"]
    gst = HOUR.astimezone(timezone(timedelta(hours=4)))
    assert HOUR.strftime("%Y-%m-%d %H:%M UTC") in text
    assert gst.strftime("%Y-%m-%d %H:%M GST") in text
    assert "Sleeves evaluated: F111 0, book 1." in text
    assert "Soko: chop, age 3h 0m." in text


def test_ttl_expiry_prunes_summaries_and_leaves_other_proposals(firm_db) -> None:
    """Past the two-hour TTL the row is expired and deleted. A risk proposal stays."""
    bar = HOUR
    publish_book_notes([_book("BTCUSDT|1h|LONG|sleeve", bar, "no_signal")], now=HOUR)
    risk_id = memory.record_proposal(
        agent="risk_officer",
        kind=ProposalKind.RISK,
        title="Veto BTCUSDT",
        payload={"action": "veto", "symbol": "BTCUSDT"},
        rationale="unrelated",
        confidence=0.5,
        symbol="BTCUSDT",
        ttl=timedelta(hours=4),
    )
    with session_scope() as session:
        risk = session.get(Proposal, risk_id)
        risk.expires_at = HOUR - timedelta(hours=1)

    # Still inside the summary TTL.
    assert expire_and_prune_scan_summaries(HOUR + timedelta(hours=1)) == {"expired": 0, "pruned": 0}
    assert len(_pending_summaries()) == 1

    result = expire_and_prune_scan_summaries(HOUR + timedelta(hours=2, seconds=1))
    assert result == {"expired": 1, "pruned": 1}
    assert _pending_summaries() == []
    with session_scope() as session:
        assert session.get(Proposal, risk_id) is not None
        assert session.get(Proposal, risk_id).status == ProposalStatus.PENDING.value
        leftover = session.query(Proposal).filter(Proposal.kind == "informational").count()
        assert leftover == 0

    # Listing the Inbox uses the same prune, so a stale diary cannot sit there.
    publish_book_notes([_book("ETHUSDT|1h|SHORT|sleeve", bar, "no_signal")], now=HOUR)
    with session_scope() as session:
        row = session.query(Proposal).filter(Proposal.kind == "informational").one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert _pending_summaries() == []


def test_hourly_cap_merges_the_extra_pass(firm_db) -> None:
    """Four new rows per UTC hour. The fifth pass is merged onto the newest."""
    created = []
    for offset in (0, 15, 30, 45, 50):
        bar = HOUR + timedelta(minutes=offset)
        created.append(
            publish_book_notes(
                [_book(f"BTCUSDT|15m|LONG|sleeve-{offset}", bar, "no_signal")],
                now=HOUR,
            )[0]
        )
    assert [item["action"] for item in created[:4]] == ["inserted"] * 4
    assert created[4]["action"] == "merged"
    rows = _pending_summaries()
    assert len(rows) == HOURLY_CAP
    keys = [key for row in rows for key in row["payload"]["dedupe_keys"]]
    fifth = f"book|{(HOUR + timedelta(minutes=50)).isoformat()}"
    assert fifth in keys
    host = next(row for row in rows if fifth in row["payload"]["dedupe_keys"])
    assert "Also this hour:" in host["rationale"]
    assert host["payload"]["informational"] is True

    # A later hour is a new row. The cap does not spill backward.
    later = HOUR + timedelta(hours=1)
    nxt = publish_book_notes(
        [_book("BTCUSDT|15m|LONG|next", later, "no_signal")],
        now=later,
    )[0]
    assert nxt["action"] == "inserted"
    assert len(_pending_summaries()) == HOURLY_CAP + 1


def test_informational_rows_have_no_action_buttons(firm_db) -> None:
    """The dashboard draws no approve/reject, and the API cannot turn the row into work."""
    html = DASHBOARD.read_text(encoding="utf-8")
    assert 'p.kind === "informational"' in html
    assert "Informational only. No approve or reject." in html
    # The buttons exist for real proposals. They are the other branch.
    guard = html.find("Informational only. No approve or reject.")
    buttons = html.find('onclick="decide(${p.id}, true)"', guard)
    assert guard != -1 and buttons > guard

    bar = HOUR
    result = publish_book_notes([_book("BTCUSDT|1h|LONG|sleeve", bar, "no_signal")], now=HOUR)
    pid = result[0]["id"]
    proposal = memory.get_proposal(pid)
    assert proposal["kind"] == "informational"
    assert "action" not in (proposal["payload"] or {})

    assert memory.decide_proposal(pid, approved=True, decided_by="operator") is False
    assert memory.decide_proposal(pid, approved=False, decided_by="operator") is False
    assert memory.get_proposal(pid)["status"] == "pending"

    from firm.research_jobs import on_operator_approved

    routed = on_operator_approved(memory.get_proposal(pid) or {})
    assert routed["queued"] is False
    assert routed.get("handed_to_cursor") is False
    assert "Nothing is queued" in routed["next_step"]

    from firm.continuity import _consume_matching_inbox

    _consume_matching_inbox("opening_range_breakout", "1h/1h", "test")
    assert memory.get_proposal(pid)["status"] == "pending"

    from firm.orchestrator import Orchestrator

    advice = Orchestrator().advice_for_engine()
    assert advice.sit_out is False
    assert advice.vetoes == {}
    assert advice.size_multipliers == {}

    from api.app import app

    client = TestClient(app)
    response = client.post(
        f"/api/inbox/{pid}/decide",
        headers={"X-API-Token": get_settings().api_token},
        json={"approved": True, "decided_by": "operator", "reason": "should not apply"},
    )
    assert response.status_code == 409
    assert memory.get_proposal(pid)["status"] == "pending"

    # A real proposal is still decidable. The guard is the informational kind.
    strategy_id = memory.record_proposal(
        agent="quant_researcher",
        kind=ProposalKind.STRATEGY,
        title="Test something_else",
        payload={"name": "something_else"},
        rationale="not a scan summary",
        confidence=0.2,
    )
    assert memory.decide_proposal(strategy_id, approved=False, decided_by="operator") is True


def test_reason_counts_and_near_misses_from_sample_telemetry() -> None:
    rows = [
        {
            "record_kind": "registry",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "rejection_reason": "no_signal",
        },
        {
            "symbol": "BTCUSDT",
            "side": "LONG",
            "rejection_reason": "base_signal_blocked",
            "gate_decision": False,
            "feature_values": {"extension_atr": 0.2, "compression": 0.8},
        },
        {
            "symbol": "ETHUSDT",
            "side": "SHORT",
            "rejection_reason": "high_vol_filter",
            "gate_decision": False,
            "feature_values": {"prior_atr": 0.009, "close": 1.0, "compression": 0.9, "extension_atr": 0.1},
        },
        {
            "symbol": "SOLUSDT",
            "side": "LONG",
            "rejection_reason": "extension_gate",
            "gate_decision": False,
            "feature_values": {"extension_atr": 1.02, "compression": 0.8},
        },
        {
            "symbol": "XRPUSDT",
            "side": "LONG",
            "rejection_reason": "extension_gate",
            "gate_decision": False,
            "feature_values": {"extension_atr": 3.5, "compression": 0.7},
        },
        {
            "symbol": "ADAUSDT",
            "side": "SHORT",
            "rejection_reason": "compression_gate",
            "gate_decision": False,
            "feature_values": {"compression": 0.49, "extension_atr": 0.4},
        },
        {
            "symbol": "DOGEUSDT",
            "side": "LONG",
            "rejection_reason": "regime sit-out: chop is blocked for sleeve",
            "gate_decision": False,
        },
        {
            "symbol": "BNBUSDT",
            "side": "LONG",
            "instrument_unavailable": True,
            "rejection_reason": "Contract not found",
            "gate_decision": False,
        },
        {
            "symbol": "LINKUSDT",
            "side": "SHORT",
            "rejection_reason": "stale_signal_not_backfilled",
            "gate_decision": False,
        },
        {
            "symbol": "AVAXUSDT",
            "side": "LONG",
            "rejection_reason": "already holding AVAXUSDT (no pyramiding)",
            "occupancy_or_risk_rejection": "already holding AVAXUSDT (no pyramiding)",
            "gate_decision": False,
        },
        {
            "symbol": "LTCUSDT",
            "side": "LONG",
            "source_signal_id": "LTCUSDT|LONG|pass",
            "gate_decision": True,
            "rejection_reason": None,
            "pending_retest_created_at": "2026-10-10T15:00:00+00:00",
        },
        {
            "symbol": "LTCUSDT",
            "side": "LONG",
            "source_signal_id": "LTCUSDT|LONG|fill",
            "gate_decision": True,
            "rejection_reason": None,
            "simulated_fill": 100.0,
            "action_time": "2026-10-10T15:05:00+00:00",
        },
        {
            "symbol": "DOTUSDT",
            "side": "SHORT",
            "rejection_reason": "4 open positions >= limit 3",
            "gate_decision": False,
        },
    ]
    summary = summarise_f111_rows(rows)
    assert summary["f111_sleeves"] == 12
    assert summary["book_sleeves"] == 0
    assert summary["signals"] == 1
    assert summary["entries_opened"] == 1
    assert summary["pending_retests_opened"] == 1
    assert summary["rejection_counts"] == {
        "base_signal_blocked": 1,
        "high_vol_filter": 1,
        "extension_gate": 2,
        "compression_gate": 1,
        "regime sit-out": 1,
        "unavailable instrument": 1,
        "latency/stale bar": 1,
        "existing position": 1,
        "risk cap": 1,
    }
    # Ranked by gap / threshold, not by the raw gap. BTC's 0.80 compression
    # misses the base cap of 0.70. XRP is the same extension gate as SOL, further away.
    misses = summary["near_misses"]
    assert [item["symbol"] for item in misses] == [
        "ADAUSDT",
        "SOLUSDT",
        "ETHUSDT",
        "BTCUSDT",
        "XRPUSDT",
    ]
    assert misses[0]["metric"] == "compression"
    assert misses[0]["gap"] == pytest.approx(0.01)
    assert misses[1]["metric"] == "extension_atr"
    assert misses[1]["value"] == pytest.approx(1.02)
    assert misses[2]["metric"] == "prior_atr/close"
    assert misses[2]["gap"] == pytest.approx(0.001)
    assert misses[3]["condition"] == "base_compression"
    assert misses[4]["symbol"] == "XRPUSDT"


def test_book_summary_failure_does_not_change_the_poll(tmp_path, monkeypatch, firm_db) -> None:
    """A raised diary write leaves the evaluated bar and the flat book alone."""
    calls: list[str] = []

    def boom(*_args, **_kwargs):
        calls.append("write")
        raise RuntimeError("inbox down")

    monkeypatch.setattr("firm.scan_inbox.publish_book_notes", boom)
    clock = Clock(datetime(2026, 10, 10, 12, 1, tzinfo=timezone.utc))
    strategy = RecordingStrategy("flat_book")
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("BTCUSDT", SignalSide.LONG, strategy, "1h")],
    )
    from core.execution.paper_bar_eval import poll_paper_book

    assert poll_paper_book(engine) == 1
    assert calls == ["write"]
    assert strategy.seen
    assert engine.broker.get_positions() == []


def test_f111_summary_failure_does_not_drop_the_hourly_pass(tmp_path, monkeypatch, caplog) -> None:
    """The hourly sleeve pass still records its telemetry when the diary write raises."""
    from core.strategy.mar_f111_r12_extension_latefloor_v1 import (
        MarF111R12ExtensionLatefloorV1Strategy,
    )
    from tests.test_f111_paper import _runtime

    calls: list[str] = []

    def boom(*_args, **_kwargs):
        calls.append("write")
        raise RuntimeError("inbox down")

    monkeypatch.setattr("firm.scan_inbox.publish_f111_hourly", boom)

    def fake_signals(self, candles):
        out = self.empty_signals(candles)
        out["compression"] = 0.8
        out["extension_atr"] = 2.5
        out["prior_atr"] = 2.0
        out["entry_boundary"] = 100.0
        out["signal"] = 0
        out["f111_rejection_reason"] = "extension_gate"
        return out

    monkeypatch.setattr(MarF111R12ExtensionLatefloorV1Strategy, "generate_signals", fake_signals)
    bars = MarF111R12ExtensionLatefloorV1Strategy.min_bars + 2
    index = pd.date_range("2024-01-01", periods=bars, freq="h", tz="UTC", name="timestamp")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 10.0,
            "turnover": 1000.0,
        },
        index=index,
    )

    class _Hourly:
        def fetch_latest(self, symbol: str, timeframe: str, bars: int = 860) -> pd.DataFrame:
            return frame

    now = index[-1].to_pydatetime() + timedelta(hours=1)
    runtime = _runtime(tmp_path)
    with caplog.at_level(logging.ERROR):
        runtime._consume_hourly(_Hourly(), now)
    assert calls == ["write"]
    logged = [row for row in runtime.events if row.get("side") in {"LONG", "SHORT"}]
    assert logged
    assert {row["rejection_reason"] for row in logged} == {"extension_gate"}
    assert "F111 scan summary was not written" in caplog.text


def _expires_at(proposal_id: int) -> datetime | None:
    with session_scope() as session:
        row = session.get(Proposal, proposal_id)
        assert row is not None
        return row.expires_at


def test_exit_and_pending_retest_are_not_entries() -> None:
    """An exit is a close. A pending retest is not a trade."""
    closed = summarise_f111_rows(
        [
            {
                "symbol": "XRPUSDT",
                "side": "SHORT",
                "source_signal_id": "XRPUSDT|SHORT|exit",
                "gate_decision": True,
                "rejection_reason": "initial_stop",
                "simulated_fill": 90.0,
                "exit_fee": 0.0,
                "realised_net_profit": -1.0,
            }
        ]
    )
    assert closed["entries_opened"] == 0
    assert closed["fills"] == 0
    assert closed["exits"] == 1
    assert closed["sleeve_rows"][0]["exited"] is True
    assert closed["sleeve_rows"][0]["ordered"] is False

    waiting = summarise_f111_rows(
        [
            {
                "symbol": "ADAUSDT",
                "side": "LONG",
                "source_signal_id": "ADAUSDT|LONG|retest",
                "gate_decision": True,
                "rejection_reason": None,
                "pending_retest_created_at": "2026-10-10T15:00:00+00:00",
            }
        ]
    )
    assert waiting["entries_opened"] == 0
    assert waiting["fills"] == 0
    assert waiting["exits"] == 0
    assert waiting["pending_retests_opened"] == 1
    assert waiting["signals"] == 1

    book_exit = summarise_sleeve_notes(
        [
            {
                "sleeve_id": "BTCUSDT|1h|LONG|sleeve",
                "bar_time": HOUR.isoformat(),
                "signal": False,
                "ordered": False,
                "exited": True,
                "rejection": "stop_loss",
            }
        ]
    )
    assert book_exit["entries_opened"] == 0
    assert book_exit["exits"] == 1


def test_trade_cards_persist_and_no_trade_cards_expire(firm_db) -> None:
    """Entry, fill, and exit cards have no TTL. A no-trade card still expires."""
    # Four cards share the first scan hour (the cap). Two more land an hour
    # later, still inside the no-trade TTL, so publishing them does not prune
    # the first hour.
    no_trade = publish_book_notes(
        [_book("BTCUSDT|1h|LONG|flat", HOUR, "no_signal")],
        now=HOUR,
    )[0]
    entry = publish_book_notes(
        [_book("ETHUSDT|1h|LONG|entry", HOUR + timedelta(minutes=15), "", signal=True, ordered=True)],
        now=HOUR,
    )[0]
    fill = publish_f111_hourly(
        [
            {
                "symbol": "SOLUSDT",
                "side": "LONG",
                "source_signal_id": "SOLUSDT|LONG|fill",
                "gate_decision": True,
                "rejection_reason": None,
                "simulated_fill": 100.0,
            }
        ],
        now=HOUR,
        bar_time=HOUR + timedelta(minutes=30),
        pending_retests=0,
    )
    closed = publish_f111_hourly(
        [
            {
                "symbol": "XRPUSDT",
                "side": "SHORT",
                "source_signal_id": "XRPUSDT|SHORT|exit",
                "gate_decision": True,
                "rejection_reason": "protected_stop",
                "simulated_fill": 90.0,
                "exit_fee": 0.1,
                "realised_net_profit": -1.5,
            }
        ],
        now=HOUR,
        bar_time=HOUR + timedelta(minutes=45),
        pending_retests=0,
    )
    retest_clock = HOUR + timedelta(hours=1)
    retest = publish_f111_hourly(
        [
            {
                "symbol": "ADAUSDT",
                "side": "LONG",
                "source_signal_id": "ADAUSDT|LONG|retest",
                "gate_decision": True,
                "rejection_reason": None,
                "pending_retest_created_at": retest_clock.isoformat(),
            }
        ],
        now=retest_clock,
        bar_time=retest_clock,
        pending_retests=1,
    )
    # A fill that was not counted as an entry still has to persist.
    fill_only_bar = retest_clock + timedelta(minutes=15)
    fill_only = publish_scan_summary(
        scan_type="book",
        bar_time=fill_only_bar,
        summary={
            "entries_opened": 0,
            "fills": 1,
            "exits": 0,
            "signals": 0,
            "pending_retests_opened": 0,
            "rejection_counts": {},
            "near_misses": [],
            "sleeve_rows": [
                {
                    "sleeve_id": "LTCUSDT|1h|LONG|fill",
                    "filled": True,
                    "ordered": False,
                    "exited": False,
                }
            ],
            "sleeve_ids": ["LTCUSDT|1h|LONG|fill"],
            "book_sleeves": 1,
            "f111_sleeves": 0,
        },
        now=retest_clock,
        soko={"label": None, "as_of": None, "age_seconds": None},
    )

    assert _expires_at(no_trade["id"]) == HOUR + timedelta(hours=2)
    assert _expires_at(retest["id"]) == retest_clock + timedelta(hours=2)
    for trade_id in (entry["id"], fill["id"], closed["id"], fill_only["id"]):
        assert _expires_at(trade_id) is None

    with session_scope() as session:
        exit_row = session.get(Proposal, closed["id"])
        assert exit_row.payload["entries_opened"] == 0
        assert exit_row.payload["exits"] == 1
        assert exit_row.payload["durable"] is True
        assert session.get(Proposal, fill["id"]).payload["fills"] == 1
        assert session.get(Proposal, fill_only["id"]).payload["entries_opened"] == 0
        assert session.get(Proposal, fill_only["id"]).payload["fills"] == 1

    # Inside the no-trade window nothing is pruned.
    assert expire_and_prune_scan_summaries(HOUR + timedelta(hours=1, minutes=59)) == {
        "expired": 0,
        "pruned": 0,
    }
    # Past both no-trade clocks. Trade cards are still pending, with no expiry.
    later = retest_clock + timedelta(hours=2, seconds=1)
    assert expire_and_prune_scan_summaries(later) == {"expired": 2, "pruned": 2}
    with session_scope() as session:
        assert session.get(Proposal, no_trade["id"]) is None
        assert session.get(Proposal, retest["id"]) is None
        for trade_id in (entry["id"], fill["id"], closed["id"], fill_only["id"]):
            row = session.get(Proposal, trade_id)
            assert row is not None
            assert row.status == ProposalStatus.PENDING.value
            assert row.expires_at is None

    listed = {row["id"] for row in _pending_summaries()}
    assert {entry["id"], fill["id"], closed["id"], fill_only["id"]} <= listed

    # A no-trade card that later records an entry loses the two-hour clock.
    grow_bar = HOUR + timedelta(hours=8)
    grown = publish_book_notes(
        [_book("BTCUSDT|1h|LONG|grow", grow_bar, "no_signal")],
        now=grow_bar,
    )[0]
    assert _expires_at(grown["id"]) == grow_bar + timedelta(hours=2)
    updated = publish_book_notes(
        [_book("BTCUSDT|1h|LONG|grow", grow_bar, "", signal=True, ordered=True)],
        now=grow_bar + timedelta(minutes=1),
    )[0]
    assert updated == {"action": "updated", "id": grown["id"]}
    assert _expires_at(grown["id"]) is None
    expire_and_prune_scan_summaries(grow_bar + timedelta(hours=5))
    with session_scope() as session:
        assert session.get(Proposal, grown["id"]) is not None
        assert session.get(Proposal, grown["id"]).expires_at is None

    # The hourly cap folds a trade into a no-trade host. The host must stay.
    cap_hour = HOUR + timedelta(hours=10)
    hosts = []
    for offset in (0, 15, 30, 45):
        bar = cap_hour + timedelta(minutes=offset)
        hosts.append(
            publish_book_notes(
                [_book(f"BTCUSDT|15m|LONG|cap-{offset}", bar, "no_signal")],
                now=cap_hour,
            )[0]
        )
    merged = publish_book_notes(
        [
            _book(
                "ETHUSDT|15m|LONG|cap-trade",
                cap_hour + timedelta(minutes=50),
                "",
                signal=True,
                ordered=True,
            )
        ],
        now=cap_hour,
    )[0]
    assert merged["action"] == "merged"
    assert merged["id"] == hosts[-1]["id"]
    assert _expires_at(merged["id"]) is None
    expire_and_prune_scan_summaries(cap_hour + timedelta(hours=2, seconds=1))
    with session_scope() as session:
        host = session.get(Proposal, merged["id"])
        assert host is not None
        assert host.expires_at is None
        assert host.payload["durable"] is True
        assert any(section.get("entries_opened") == 1 for section in host.payload["merged_scans"])
        for item in hosts[:-1]:
            assert session.get(Proposal, item["id"]) is None


def test_scan_summary_jsonl_appends_the_full_card(firm_db, tmp_path, monkeypatch) -> None:
    """Two publishes append two lines. The file only grows."""
    path = tmp_path / "scan_summaries.jsonl"
    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", path)
    bar = HOUR + timedelta(hours=12)
    publish_book_notes(
        [_book("BTCUSDT|1h|LONG|log", bar, "extension_gate")],
        now=bar,
    )
    first = path.read_bytes()
    lines = [json.loads(line) for line in first.decode().splitlines() if line.strip()]
    assert len(lines) == 1
    card = lines[0]
    assert card["action"] == "inserted"
    assert card["durable"] is False
    assert card["expires_at"] is not None
    assert card["payload"]["dedupe_key"] == f"book|{bar.replace(microsecond=0).isoformat()}"
    assert card["payload"]["rejection_counts"] == {"extension_gate": 1}
    assert "extension_gate 1" in card["payload"]["summary"]
    assert card["rationale"] == card["payload"]["summary"]
    assert "entries opened 0, fills 0, exits 0" in card["rationale"]

    trade_bar = bar + timedelta(minutes=15)
    publish_book_notes(
        [_book("ETHUSDT|1h|SHORT|log", trade_bar, "", signal=True, ordered=True)],
        now=bar,
    )
    grown = path.read_bytes()
    assert grown.startswith(first)
    assert len(grown) > len(first)
    lines = [json.loads(line) for line in grown.decode().splitlines() if line.strip()]
    assert len(lines) == 2
    assert lines[0]["payload"]["dedupe_key"] == card["payload"]["dedupe_key"]
    assert lines[1]["action"] == "inserted"
    assert lines[1]["durable"] is True
    assert lines[1]["expires_at"] is None
    assert lines[1]["payload"]["entries_opened"] == 1
    assert lines[1]["payload"]["dedupe_key"] in lines[1]["rationale"] or "entries opened 1" in lines[1]["rationale"]

    # The same bar again is an unchanged republish. It still appends a line.
    before = path.read_bytes()
    again = publish_book_notes(
        [_book("ETHUSDT|1h|SHORT|log", trade_bar, "", signal=True, ordered=True)],
        now=bar,
    )[0]
    assert again["action"] == "unchanged"
    after = path.read_bytes()
    assert after.startswith(before)
    assert after.count(b"\n") == before.count(b"\n") + 1


def test_summary_log_failure_still_writes_the_inbox(firm_db, monkeypatch, tmp_path) -> None:
    """A log writer that raises does not drop the Inbox row or the flush."""
    path = tmp_path / "scan_summaries.jsonl"
    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("log down")

    monkeypatch.setattr("firm.scan_summary_log.append_scan_summary", boom)
    bar = HOUR + timedelta(hours=14)
    result = publish_book_notes(
        [_book("BTCUSDT|1h|LONG|iso", bar, "no_signal")],
        now=bar,
    )
    assert result[0]["action"] == "inserted"
    assert any(row["id"] == result[0]["id"] for row in _pending_summaries())
    assert not path.exists()

    from firm.scan_inbox import flush_scan_notes

    flush_bar = bar + timedelta(minutes=15)
    flush_scan_notes(
        [_book("ETHUSDT|1h|SHORT|flush", flush_bar, "no_signal")],
        None,
        now=bar,
    )
    kinds = {row["payload"]["dedupe_key"] for row in _pending_summaries()}
    assert f"book|{flush_bar.replace(microsecond=0).isoformat()}" in kinds


def test_summary_log_oserror_is_swallowed(firm_db, monkeypatch, tmp_path) -> None:
    """A disk error inside the append is logged and does not block the card."""
    path = tmp_path / "state" / "scan_summaries.jsonl"
    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", path)

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("firm.scan_summary_log.os.open", boom)
    from firm.scan_summary_log import append_scan_summary

    append_scan_summary({"payload": {"summary": "must not raise"}})
    bar = HOUR + timedelta(hours=15)
    result = publish_book_notes(
        [_book("BTCUSDT|1h|LONG|disk", bar, "no_signal")],
        now=bar,
    )
    assert result[0]["action"] == "inserted"
    assert any(row["id"] == result[0]["id"] for row in _pending_summaries())
    assert not path.exists()
