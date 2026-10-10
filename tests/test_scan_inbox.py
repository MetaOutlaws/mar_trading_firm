"""Per-scan Inbox summaries: diary rows, not decisions.

These tests do not place orders or change a signal, gate, risk check, or the
approval book. Live stays off.
"""

from __future__ import annotations

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
