"""Consolidation backfill: DESKTOP history onto the SGP1 book.

A row missing from both the trades table and the journal gets a trade and
one close. The October XRP short is already in the journal, so it gets a
trade and no second cash event. A row that matches an SGP1 trade on
symbol, side, entry time, and entry price is left alone.

Pre-F03 fees stay as one recorded number. Entry fee and funding are not
invented. The merged-ledger CSV with the live entry prices is not in this
tree yet; these fixtures use the recon economics plus prices the test supplies.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from core.db import session_scope
from core.execution.paper_cash import KIND_CLOSE, PaperCashStore, replay_events
from core.ledger.models import PaperCashEvent, TradeRecord
from core.ledger.reconcile import reconcile_closes
from core.ledger.statement import live_book_statement
from scripts.backfill_consolidated_trades import journal_fee_fields, main
from scripts.backfill_orphan_trade import main as shim_main

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DESKTOP_CSV = FIXTURES / "desktop_trade_journal_recon.csv"
SGP1_CSV = FIXTURES / "sgp1_trade_journal_recon.csv"
GST = timezone(timedelta(hours=4))
ORPHAN_NET = -21.070272
ORPHAN_QTY = 670.1
ORPHAN_ENTRY = 1.4898087
ORPHAN_EXIT = 1.5199
# DESKTOP trade 1, pre-F03. Prices are supplied by the test CSV, not estimated.
PRE_GROSS = -23.254604
PRE_FEES = 0.531127
PRE_NET = -23.785731
PRE_ENTRY = 2500.0
PRE_EXIT = 2267.45396
PRE_QTY = 0.1


def _gst(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=GST)


def _sgp1_rows() -> list[tuple]:
    rows = []
    with SGP1_CSV.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            if raw.get("source") != "trades":
                continue
            rows.append(raw)
    return rows


def _book(tmp_path: Path) -> Path:
    """One posted SOL short, plus the journal-only XRP close."""
    sol = _sgp1_rows()[0]
    events: list[dict] = [{"kind": "capital", "amount": 10_000.0}]
    exit_time = _gst(sol["close_gst"])
    entry_time = _gst(sol["open_gst"])
    net = float(sol["trades_net"])
    events.append(
        {
            "kind": "close",
            "event_id": sol["journal_ref"],
            "symbol": sol["symbol"],
            "side": sol["side"],
            "quantity": 8.33,
            "entry_price": 121.94,
            "fill_price": 121.94,
            "gross_pnl": net,
            "fee": 0.0,
            "entry_fee": 0.0,
            "funding": 0.0,
            "ts": exit_time.astimezone(timezone.utc).isoformat(),
        }
    )
    events.append(
        {
            "kind": "close",
            "symbol": "XRPUSDT",
            "side": "SHORT",
            "quantity": ORPHAN_QTY,
            "fill_price": ORPHAN_EXIT,
            "entry_price": ORPHAN_ENTRY,
            "gross_pnl": ORPHAN_NET,
            "fee": 0.0,
            "entry_fee": 0.0,
            "funding": 0.0,
            "ts": "2026-10-02T04:21:44Z",
        }
    )
    with session_scope() as session:
        session.add(
            TradeRecord(
                symbol=sol["symbol"],
                side=sol["side"],
                mode="paper",
                strategy=sol["strategy"],
                quantity=8.33,
                notional=8.33 * 121.94,
                entry_price=121.94,
                exit_price=121.94,
                entry_time=entry_time,
                exit_time=exit_time,
                gross_pnl=net,
                fees=0.0,
                net_pnl=net,
                exit_reason=sol["exit_reason"],
                cash_event_id=sol["journal_ref"],
            )
        )
    journal = tmp_path / "paper_cash.json"
    store = PaperCashStore(journal)
    for event in events:
        store.record(dict(event))
    return journal


def _merged_csv(path: Path) -> None:
    """Three rows: an existing SGP1 trade, the orphan, and one pre-F03 trade."""
    sol = _sgp1_rows()[0]
    path.write_text(
        "\n".join(
            [
                "trade_id,symbol,side,strategy,open_gst,close_gst,exit_reason,"
                "gross,fees,entry_fees,exit_fees,funding,trades_net,"
                "quantity,entry_price,exit_price",
                (
                    f"100,{sol['symbol']},{sol['side']},{sol['strategy']},"
                    f"{sol['open_gst']},{sol['close_gst']},{sol['exit_reason']},"
                    f"{sol['trades_net']},0,0,0,0,{sol['trades_net']},8.33,121.94,121.94"
                ),
                (
                    "8,XRPUSDT,SHORT,outside_bar_fail_reversion,"
                    "2026-10-01 16:04,2026-10-02 08:21,stop_loss,"
                    f"-20.16418,1.109243,0.5490764454285001,0.5601667445,-0.203151,{ORPHAN_NET},"
                    f"{ORPHAN_QTY},{ORPHAN_ENTRY},{ORPHAN_EXIT}"
                ),
                (
                    "1,ETHUSDT,LONG,wick_rejection_reversal,"
                    "2026-08-31 21:47,2026-09-01 21:59,stop_loss,"
                    f"{PRE_GROSS},{PRE_FEES},0,0,0,{PRE_NET},"
                    f"{PRE_QTY},{PRE_ENTRY},{PRE_EXIT}"
                ),
                ""
            ]
        ),
        encoding="utf-8",
    )


def _argv(source: Path, journal: Path, audit: Path, *extra: str) -> list[str]:
    return [
        "--source", str(source),
        "--journal", str(journal),
        "--operator", "pytest",
        "--audit", str(audit),
        *extra,
    ]


def _line(output: str, prefix: str) -> str:
    matches = [line for line in output.splitlines() if line.startswith(prefix)]
    assert matches, output
    return matches[0]


def test_pre_f03_fee_fields_are_not_invented() -> None:
    from scripts.backfill_consolidated_trades import SourceRow

    row = SourceRow(
        source_trade_id=1,
        source_position_id=None,
        symbol="ETHUSDT",
        side="LONG",
        strategy="wick_rejection_reversal",
        exit_reason="stop_loss",
        entry_time=datetime(2026, 8, 31, tzinfo=timezone.utc),
        exit_time=datetime(2026, 9, 1, tzinfo=timezone.utc),
        gross_pnl=PRE_GROSS,
        fees=PRE_FEES,
        entry_fees=0.0,
        exit_fees=0.0,
        funding=0.0,
        net_pnl=PRE_NET,
        quantity=PRE_QTY,
        entry_price=PRE_ENTRY,
        exit_price=PRE_EXIT,
        notional=PRE_QTY * PRE_ENTRY,
    )
    fee, entry_fee, funding = journal_fee_fields(row)
    assert fee == pytest.approx(PRE_FEES)
    assert entry_fee == 0.0
    assert funding == 0.0
    assert PRE_GROSS - fee == pytest.approx(PRE_NET)


def test_reconcile_names_a_trade_gap_and_a_journal_orphan() -> None:
    events = [
        {"kind": "capital", "amount": 10_000.0},
        {
            "kind": "close",
            "event_id": "paper-close:1",
            "symbol": "SOLUSDT",
            "side": "SHORT",
            "gross_pnl": -20.926618,
            "ts": "2026-10-04T13:38:00Z",
        },
        {
            "kind": "close",
            "symbol": "XRPUSDT",
            "side": "SHORT",
            "quantity": ORPHAN_QTY,
            "gross_pnl": ORPHAN_NET,
            "ts": "2026-10-02T04:21:44Z",
        },
    ]
    trades = [
        {
            "id": 4,
            "cash_event_id": "paper-close:1",
            "symbol": "SOLUSDT",
            "side": "SHORT",
            "quantity": 8.33,
            "exit_time": "2026-10-04T13:38:00+00:00",
            "net_pnl": -20.926618,
        },
        {
            "id": 9,
            "cash_event_id": None,
            "symbol": "ETHUSDT",
            "side": "LONG",
            "quantity": 0.4,
            "exit_time": "2026-10-08T21:54:00+00:00",
            "net_pnl": -21.048668,
        },
    ]
    report = reconcile_closes(events, trades)
    assert report["matched"] == 1
    missing = report["trades_without_journal_close"]
    assert missing[0]["trade_id"] == 9
    assert missing[0]["net_pnl"] == pytest.approx(-21.048668)
    orphans = report["journal_closes_without_trade"]
    assert orphans[0]["symbol"] == "XRPUSDT"
    assert orphans[0]["net"] == pytest.approx(ORPHAN_NET)
    assert orphans[0]["event_id"] is None


def test_desktop_extract_does_not_invent_prices(tmp_path, firm_db, capsys) -> None:
    """The recon CSV has no entry price. Only the journalled orphan can be planned."""
    journal = _book(tmp_path)
    before = journal.read_bytes()
    audit = tmp_path / "audit.jsonl"
    code = main(_argv(DESKTOP_CSV, journal, audit))
    output = capsys.readouterr().out
    assert code == 2
    assert _line(output, "planned_trades: ") == "planned_trades: 1"
    assert _line(output, "planned_closes: ") == "planned_closes: 0"
    assert "insert source=8 XRPUSDT SHORT" in output
    assert "insert+close" not in output
    assert _line(output, "blocked: ") == "blocked: 13"
    assert "missing entry price or quantity" in output
    assert journal.read_bytes() == before
    assert not audit.exists()
    with session_scope() as session:
        assert session.scalar(select(func.count(TradeRecord.id))) == 1
        assert session.scalar(select(func.count(PaperCashEvent.id))) == 0


def test_apply_posts_the_pre_f03_close_and_skips_the_duplicate(
    tmp_path, firm_db, capsys
) -> None:
    journal = _book(tmp_path)
    source = tmp_path / "merged.csv"
    _merged_csv(source)
    audit = tmp_path / "audit.jsonl"
    cash_before = replay_events(PaperCashStore(journal).events()).cash

    code = main(_argv(source, journal, audit, "--apply"))
    output = capsys.readouterr().out
    assert code == 0
    assert _line(output, "mode: ") == "mode: apply"
    assert _line(output, "planned_trades: ") == "planned_trades: 2"
    assert _line(output, "planned_closes: ") == "planned_closes: 1"
    assert _line(output, "already: ") == "already: 1"
    assert _line(output, "posted_trades: ") == "posted_trades: 2"
    assert _line(output, "posted_closes: ") == "posted_closes: 1"
    assert "insert+close source=1 ETHUSDT LONG" in output
    assert "insert source=8 XRPUSDT SHORT" in output
    assert "cash_delta=0.000000 key=backfill-close:trade:8" in output
    assert f"cash_delta={PRE_NET:.6f}" in output
    assert "-> holds" in _line(output, "identity_after: ")
    assert audit.exists()

    with session_scope() as session:
        assert session.scalar(select(func.count(TradeRecord.id))) == 3
        event = session.scalars(select(PaperCashEvent)).one()
        assert event.event_id == "backfill-close:trade:1"
        assert event.payload["fee"] == pytest.approx(PRE_FEES)
        assert event.payload["entry_fee"] == 0.0
        assert event.payload["funding"] == 0.0
        assert event.payload["kind"] == "close"
        eth = session.scalar(
            select(TradeRecord).where(TradeRecord.cash_event_id == "backfill-close:trade:1")
        )
        assert eth is not None
        assert eth.entry_fees == 0.0
        assert eth.exit_fees == 0.0
        assert eth.funding == 0.0
        assert eth.fees == pytest.approx(PRE_FEES)
        assert eth.net_pnl == pytest.approx(PRE_NET)
        assert eth.entry_price == pytest.approx(PRE_ENTRY)
        total = float(session.scalar(select(func.sum(TradeRecord.net_pnl))) or 0.0)
    closes = [
        event for event in PaperCashStore(journal).events() if event.get("kind") == KIND_CLOSE
    ]
    assert sum(1 for event in closes if event.get("event_id") == "backfill-close:trade:1") == 1
    journal_events = PaperCashStore(journal).events()
    assert not any(
        event.get("kind") == "open" and event.get("backfill") for event in journal_events
    )
    cash_after = replay_events(PaperCashStore(journal).events()).cash
    assert cash_after == pytest.approx(cash_before + PRE_NET)
    assert cash_after == pytest.approx(10_000.0 + total)

    second = main(_argv(source, journal, audit, "--apply"))
    second_out = capsys.readouterr().out
    assert second == 0
    assert _line(second_out, "posted_trades: ") == "posted_trades: 0"
    assert _line(second_out, "posted_closes: ") == "posted_closes: 0"
    assert _line(second_out, "planned_trades: ") == "planned_trades: 0"
    assert "-> holds" in _line(second_out, "identity_after: ")
    with session_scope() as session:
        assert session.scalar(select(func.count(TradeRecord.id))) == 3
        assert session.scalar(select(func.count(PaperCashEvent.id))) == 1
    # The shim still calls the same command.
    assert shim_main(_argv(source, journal, audit)) == 0


def test_api_reconcile_lists_the_orphan(tmp_path, monkeypatch, firm_db) -> None:
    from core.execution import paper_cash as cash_mod

    journal = _book(tmp_path)
    monkeypatch.setattr(cash_mod, "PAPER_CASH_PATH", journal)
    book = live_book_statement("paper", [], {})
    orphans = book["reconcile"]["journal_closes_without_trade"]
    assert len(orphans) == 1
    assert orphans[0]["symbol"] == "XRPUSDT"
    assert orphans[0]["net"] == pytest.approx(ORPHAN_NET)
    assert book["reconcile"]["trades_without_journal_close"] == []

    from api import app as app_module

    body = TestClient(app_module.app).get("/api/risk").json()
    api_orphans = body["book"]["reconcile"]["journal_closes_without_trade"]
    assert api_orphans[0]["symbol"] == "XRPUSDT"
    assert api_orphans[0]["net"] == pytest.approx(ORPHAN_NET)

    html = (ROOT / "api" / "static" / "index.html").read_text(encoding="utf-8")
    assert "Trades with no journal close" in html
    assert "Journal closes with no trade" in html
    assert "Missing closes are not backfilled" not in html
