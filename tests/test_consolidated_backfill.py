"""Consolidation backfill against the attached DESKTOP ledger.

Variant B inserts DESKTOP trades 1–8 and seven journal closes (trade 8 is
the October XRP short: a trade row only). That lands on 18 trades,
sum of net -207.326039, cash 9792.673961. Variant A inserts all 14 and
lands on 24 trades, -218.766858, 9781.233142.

The printed SGP1 ETH net 48.41658 is one millionth high. The book sum
used by the dry-run reference is -71.753262, so the fixture stores
48.416579 for that one row. Prices and fees are the CSV values.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from core.db import session_scope
from core.execution.paper_cash import replay_events
from core.execution.paper_settle import load_durable_close_payloads
from core.ledger.models import PaperCashEvent, TradeRecord
from core.ledger.statement import live_book_statement
from scripts.backfill_consolidated_trades import (
    KnownTrade,
    load_input_rows,
    main,
    trade_exists,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
BACKFILL_CSV = FIXTURES / "backfill_input.csv"
MERGED_CSV = FIXTURES / "merged_ledger.csv"
GST = timezone(timedelta(hours=4))
# Prints as 9907.176466 and makes each running cash_after match the reference.
BOOK_CASH = float.fromhex("0x1.35996966d551ep+13")
ORPHAN_NET = -21.070272
ORPHAN_QTY = 670.1


def _gst(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=GST).astimezone(timezone.utc)


def _merged_rows() -> list[dict[str, str]]:
    import csv

    with MERGED_CSV.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row.get("source") == "SGP1"]


def _stored_net(raw: dict[str, str]) -> float:
    net = float(raw["net"])
    # The recon cell rounds this winner up by 0.000001.
    if raw["symbol"] == "ETHUSDT" and abs(net - 48.41658) < 1e-9:
        return 48.416579
    return net


def _seed(tmp_path: Path) -> Path:
    """Ten SGP1 trades, their closes, and the journal-only XRP close."""
    events: list[dict] = [{"kind": "capital", "amount": 10_000.0}]
    events.append(
        {
            "kind": "close",
            "symbol": "XRPUSDT",
            "side": "SHORT",
            "quantity": ORPHAN_QTY,
            "fill_price": 1.5199,
            "entry_price": 1.4898087,
            "gross_pnl": ORPHAN_NET,
            "fee": 0.0,
            "entry_fee": 0.0,
            "funding": 0.0,
            "ts": "2026-10-02T04:21:44.605Z",
        }
    )
    with session_scope() as session:
        for raw in _merged_rows():
            net = _stored_net(raw)
            entry = _gst(raw["entry_time_gst"])
            exit_time = _gst(raw["exit_time_gst"])
            quantity = float(raw["quantity"])
            entry_price = float(raw["entry_price"])
            session.add(
                TradeRecord(
                    position_id=None,
                    cash_event_id=raw["sgp1_journal_ref"],
                    symbol=raw["symbol"],
                    side=raw["side"],
                    mode="paper",
                    strategy=raw["strategy"],
                    quantity=quantity,
                    notional=quantity * entry_price,
                    entry_price=entry_price,
                    exit_price=float(raw["exit_price"]),
                    entry_time=entry,
                    exit_time=exit_time,
                    gross_pnl=float(raw["gross"]),
                    fees=float(raw["fees"]),
                    funding=float(raw["funding"]),
                    net_pnl=net,
                    exit_reason=raw["exit_reason"],
                )
            )
            events.append(
                {
                    "kind": "close",
                    "event_id": raw["sgp1_journal_ref"],
                    "symbol": raw["symbol"],
                    "side": raw["side"],
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "fill_price": float(raw["exit_price"]),
                    "gross_pnl": net,
                    "fee": 0.0,
                    "entry_fee": 0.0,
                    "funding": 0.0,
                    "ts": exit_time.isoformat(),
                }
            )
    journal = tmp_path / "paper_cash.json"
    doc = {
        "version": 1,
        "contributed_capital": 10_000.0,
        "cash": BOOK_CASH,
        "realised_pnl": BOOK_CASH - 10_000.0,
        "total_fees": 0.0,
        "total_funding": 0.0,
        "events": events,
    }
    journal.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return journal


def _argv(journal: Path, audit: Path, *extra: str) -> list[str]:
    return [
        "--input", str(BACKFILL_CSV),
        "--journal", str(journal),
        "--operator", "pytest",
        "--audit", str(audit),
        *extra,
    ]


def _line(output: str, prefix: str) -> str:
    matches = [line for line in output.splitlines() if line.startswith(prefix)]
    assert matches, output
    return matches[-1]


def test_variant_b_dry_run_hits_the_reference_totals(tmp_path, firm_db, capsys) -> None:
    journal = _seed(tmp_path)
    before = journal.read_bytes()
    code = main(_argv(journal, tmp_path / "audit.jsonl", "--variant", "B"))
    output = capsys.readouterr().out
    assert code == 0
    assert "mode=DRY-RUN variant=B" in output
    assert _line(output, "before: ") == (
        "before: trades=10 sum_net=-71.753262 cash=9907.176466 open_positions=0"
    )
    assert _line(output, "after : ") == (
        "after : trades=18 sum_net=-207.326039 cash=9792.673961 open_positions=0"
    )
    assert "diff -21.070272 MISMATCH" in _line(output, "identity before:")
    assert "diff +0.000000 OK" in _line(output, "identity after:")
    assert "backfill-close:desktop:8" in output
    assert "n/a(existing pap" in output
    assert "insert+close" not in output
    assert journal.read_bytes() == before
    assert not (tmp_path / "audit.jsonl").exists()
    with session_scope() as session:
        assert session.scalar(select(func.count(TradeRecord.id))) == 10


def test_variant_b_apply_is_idempotent_and_skips_trade_eight_cash(
    tmp_path, firm_db, capsys
) -> None:
    journal = _seed(tmp_path)
    audit = tmp_path / "audit.jsonl"
    code = main(_argv(journal, audit, "--variant", "B", "--apply"))
    output = capsys.readouterr().out
    assert code == 0
    assert "mode=APPLY variant=B" in output
    assert _line(output, "after : ") == (
        "after : trades=18 sum_net=-207.326039 cash=9792.673961 open_positions=0"
    )
    assert "diff +0.000000 OK" in _line(output, "identity after:")
    written = journal.read_bytes()
    doc = json.loads(written)
    assert f"{doc['cash']:.6f}" == "9792.673961"
    assert f"{replay_events(doc['events']).cash:.6f}" == "9792.673961"
    posted = [event for event in doc["events"] if event.get("backfill")]
    assert len(posted) == 7
    assert all(event["event_id"].startswith("backfill-close:desktop:") for event in posted)
    assert "backfill-close:desktop:8" not in {event.get("event_id") for event in doc["events"]}
    trade_one = next(event for event in posted if event["source_trade_id"] == 1)
    assert trade_one["backfill"] is True
    assert trade_one["entry_fee"] == 0.0
    assert trade_one["funding"] == 0.0
    assert trade_one["fee"] == pytest.approx(0.5311269414)
    assert trade_one["trade_exit_ts"] == "2026-09-01 17:59:30.333477"
    assert trade_one["source_db_sha256"].startswith("3a60e5b7")
    assert "position_id" not in trade_one
    with session_scope() as session:
        assert session.scalar(select(func.count(TradeRecord.id))) == 18
        trade = session.scalar(
            select(TradeRecord).where(
                TradeRecord.cash_event_id == "backfill-close:desktop:8"
            )
        )
        assert trade is not None
        assert trade.position_id is None
        assert trade.symbol == "XRPUSDT"
        assert trade.side == "SHORT"
        assert trade.net_pnl == pytest.approx(-21.070272377922063)
        pre = session.scalar(
            select(TradeRecord).where(
                TradeRecord.cash_event_id == "backfill-close:desktop:1"
            )
        )
        assert pre is not None
        assert pre.position_id is None
        assert pre.entry_fees == 0.0
        assert pre.exit_fees == 0.0
        assert pre.funding == 0.0
        assert pre.fees == pytest.approx(trade_one["fee"])
        pce = session.scalars(select(PaperCashEvent)).all()
        assert len(pce) == 7
        assert all(row.position_id is None for row in pce)
        assert all("event_id" not in row.payload for row in pce)
        assert load_durable_close_payloads() == []

    second = main(_argv(journal, audit, "--variant", "B", "--apply"))
    second_out = capsys.readouterr().out
    assert second == 0
    assert "skip(exists)" in second_out
    assert _line(second_out, "before: ") == (
        "before: trades=18 sum_net=-207.326039 cash=9792.673961 open_positions=0"
    )
    assert _line(second_out, "after : ") == _line(second_out, "before: ").replace(
        "before: ", "after : "
    )
    assert journal.read_bytes() == written
    with session_scope() as session:
        assert session.scalar(select(func.count(TradeRecord.id))) == 18
        assert session.scalar(select(func.count(PaperCashEvent.id))) == 7


def test_variant_a_hits_twenty_four_trades(tmp_path, firm_db, capsys) -> None:
    journal = _seed(tmp_path)
    code = main(_argv(journal, tmp_path / "audit.jsonl", "--variant", "A", "--apply"))
    output = capsys.readouterr().out
    assert code == 0
    assert _line(output, "after : ") == (
        "after : trades=24 sum_net=-218.766858 cash=9781.233142 open_positions=0"
    )
    assert "diff +0.000000 OK" in _line(output, "identity after:")
    doc = json.loads(journal.read_text(encoding="utf-8"))
    assert f"{doc['cash']:.6f}" == "9781.233142"
    assert f"{replay_events(doc['events']).cash:.6f}" == "9781.233142"
    funded = next(event for event in doc["events"] if event.get("source_trade_id") == 9)
    assert funded["entry_fee"] == 0.0
    assert funded["funding"] == pytest.approx(-0.49580204404917233)
    with session_scope() as session:
        assert session.scalar(select(func.count(TradeRecord.id))) == 24
        twin = session.scalar(
            select(TradeRecord).where(
                TradeRecord.cash_event_id == "backfill-close:desktop:14"
            )
        )
        assert twin is not None
        assert twin.position_id is None
        assert twin.entry_fees == pytest.approx(0.5530799088375001)
        assert session.scalar(select(func.count(PaperCashEvent.id))) == 13
    second = main(_argv(journal, tmp_path / "audit.jsonl", "--variant", "A", "--apply"))
    second_out = capsys.readouterr().out
    assert second == 0
    again = "trades=24 sum_net=-218.766858 cash=9781.233142 open_positions=0"
    assert _line(second_out, "before: ").endswith(again)
    assert _line(second_out, "after : ").endswith(again)
    with session_scope() as session:
        assert session.scalar(select(func.count(TradeRecord.id))) == 24
        assert session.scalar(select(func.count(PaperCashEvent.id))) == 13


def test_journal_keeps_its_original_format(tmp_path, firm_db, capsys) -> None:
    journal = _seed(tmp_path)
    original = json.loads(journal.read_text(encoding="utf-8"))
    original_events = json.loads(json.dumps(original["events"]))
    original_keys = list(original.keys())
    assert journal.read_text(encoding="utf-8").startswith("{\n")
    main(_argv(journal, tmp_path / "audit.jsonl", "--variant", "B", "--apply"))
    capsys.readouterr()
    text = journal.read_text(encoding="utf-8")
    assert text.startswith("{\n")
    assert "\n  " in text
    rewritten = json.loads(text)
    assert list(rewritten.keys()) == original_keys
    assert rewritten["events"][: len(original_events)] == original_events
    assert rewritten["events"][-1]["event_id"] == "backfill-close:desktop:7"

    compact_doc = {
        "cash": 10_000.0,
        "realised_pnl": 0.0,
        "total_fees": 0.0,
        "total_funding": 0.0,
        "events": [{"kind": "capital", "amount": 10_000.0}],
    }
    compact = tmp_path / "compact.json"
    compact.write_text(json.dumps(compact_doc, separators=(",", ":")), encoding="utf-8")
    tiny = tmp_path / "one.csv"
    tiny.write_text(BACKFILL_CSV.read_text(encoding="utf-8"), encoding="utf-8")
    code = main(
        [
            "--input", str(tiny),
            "--journal", str(compact),
            "--variant", "B",
            "--apply",
            "--audit", str(tmp_path / "compact-audit.jsonl"),
        ]
    )
    assert code == 0
    compact_text = compact.read_text(encoding="utf-8")
    assert "\n" not in compact_text
    assert ": " not in compact_text
    loaded = json.loads(compact_text)
    assert list(loaded.keys()) == list(compact_doc.keys())
    assert loaded["events"][0] == compact_doc["events"][0]


def test_dashboard_accepts_a_null_position_id(tmp_path, firm_db, monkeypatch, capsys) -> None:
    from core.execution import paper_cash as cash_mod

    journal = _seed(tmp_path)
    assert main(_argv(journal, tmp_path / "audit.jsonl", "--variant", "B", "--apply")) == 0
    capsys.readouterr()
    monkeypatch.setattr(cash_mod, "PAPER_CASH_PATH", journal)
    book = live_book_statement("paper", [], {})
    assert f"{book['cash']:.6f}" == "9792.673961"
    assert book["reconcile"]["journal_closes_without_trade"] == []
    assert book["reconcile"]["trades_without_journal_close"] == []

    from api import app as app_module

    client = TestClient(app_module.app)
    trades = client.get("/api/trades?limit=100")
    assert trades.status_code == 200
    body = trades.json()
    desktop_eth = [
        row for row in body
        if row["symbol"] == "ETHUSDT" and row["strategy"] == "wick_rejection_reversal"
    ]
    assert desktop_eth
    risk = client.get("/api/risk")
    assert risk.status_code == 200
    assert f"{risk.json()['book']['cash']:.6f}" == "9792.673961"
    with session_scope() as session:
        orphan = session.scalar(
            select(TradeRecord).where(
                TradeRecord.cash_event_id == "backfill-close:desktop:8"
            )
        )
        assert orphan is not None
        assert orphan.position is None
    html = (ROOT / "api" / "static" / "index.html").read_text(encoding="utf-8")
    blotter = html.split("function tradeRow", 1)[1].split("function prettyReason", 1)[0]
    assert "position_id" not in blotter


def test_cash_is_not_a_sum_of_paper_cash_events(tmp_path, firm_db, monkeypatch, capsys) -> None:
    from core.execution import paper_cash as cash_mod

    journal = _seed(tmp_path)
    assert main(_argv(journal, tmp_path / "audit.jsonl", "--variant", "A", "--apply")) == 0
    capsys.readouterr()
    monkeypatch.setattr(cash_mod, "PAPER_CASH_PATH", journal)
    book = live_book_statement("paper", [], {})
    replay_cash = replay_events(json.loads(journal.read_text(encoding="utf-8"))["events"]).cash
    assert book["cash"] == replay_cash
    assert f"{book['cash']:.6f}" == "9781.233142"
    with session_scope() as session:
        payloads = [row.payload for row in session.scalars(select(PaperCashEvent))]
    pce_sum = sum(float(payload["net"]) for payload in payloads)
    assert book["cash"] != pytest.approx(pce_sum)
    assert load_durable_close_payloads() == []
    statement = (ROOT / "core" / "ledger" / "statement.py").read_text(encoding="utf-8")
    assert "PaperCashEvent" not in statement


def test_natural_key_matches_entry_not_a_later_twin() -> None:
    rows = {row.desktop_trade_id: row for row in load_input_rows(BACKFILL_CSV)}
    first = rows[1]
    known = [
        KnownTrade(
            cash_event_id="paper-close:other",
            symbol=first.symbol,
            side=first.side,
            entry_time=first.entry_time,
            entry_price=first.entry_price,
        )
    ]
    assert trade_exists(known, first)
    later = KnownTrade(
        cash_event_id="paper-close:other",
        symbol=first.symbol,
        side=first.side,
        entry_time=first.entry_time + timedelta(seconds=2),
        entry_price=first.entry_price,
    )
    assert not trade_exists([later], first)
    twin = rows[14]
    sgp1_like = KnownTrade(
        cash_event_id="paper-close:9:AVAXUSDT:stop_loss:99.90000000:10.29400000",
        symbol=twin.symbol,
        side=twin.side,
        entry_time=twin.entry_time - timedelta(minutes=9),
        entry_price=9.9899925,
    )
    assert not trade_exists([sgp1_like], twin)


def test_backfill_close_moves_cash_by_the_whole_net() -> None:
    """A live close does not subtract funding twice. A backfill close does once."""
    live = replay_events(
        [
            {"kind": "capital", "amount": 10_000.0},
            {"kind": "funding", "symbol": "ETHUSDT", "amount": 1.5},
            {
                "kind": "close",
                "symbol": "ETHUSDT",
                "gross_pnl": 10.0,
                "fee": 0.2,
                "entry_fee": 0.1,
                "funding": 1.5,
            },
        ]
    )
    assert live.cash == pytest.approx(10_000.0 - 1.5 + 10.0 - 0.2)
    gross = -24.043432600000028
    fees = 1.03545649207
    funding = -0.49580204404917233
    net = gross - fees - funding
    backfill = replay_events(
        [
            {"kind": "capital", "amount": 10_000.0},
            {
                "kind": "close",
                "backfill": True,
                "gross_pnl": gross,
                "fee": fees,
                "entry_fee": 0.0,
                "funding": funding,
            },
        ]
    )
    assert backfill.cash == pytest.approx(10_000.0 + net)
    assert backfill.realised_pnl == pytest.approx(net)
