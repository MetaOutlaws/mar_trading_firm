"""Paper book labels and the close/trade crash boundary.

Equity is cash plus marked unrealised P&L. Closed realised P&L is the net of
closed round trips. Those are not the same number once a position is open,
because open entry fees, open funding, and the mark all sit between cash and
equity. Snapshots must store the closed net and the mark. A paper close that
hits the cash journal must insert the trade in the same transaction.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from core.db import session_scope
from core.execution.paper import PaperBroker
from core.execution.paper_cash import KIND_CLOSE, PaperCashStore
from core.execution.paper_settle import (
    paper_close_event_id,
    settle_paper_close,
)
from core.ledger.models import EquitySnapshot, PaperCashEvent, TradeRecord
from core.ledger.statement import book_statement
from core.ledger.store import Ledger
from research.costs import FRICTIONLESS
from tests.test_execution import StubDataSource

ROOT = Path(__file__).resolve().parents[1]
STARTING = 10_000.0
SYMBOL = "BTCUSDT"

# October journal figures from the 3 Oct 2026 snapshot review. Used only as
# arithmetic in this test. Nothing here is written to a production database.
REVIEW_CAPITAL = 10_000.0
REVIEW_GROSS = -20.1641801300
REVIEW_ENTRY_FEE = 0.5490764454
REVIEW_EXIT_FEE = 0.5601667445
REVIEW_CLOSE_FUNDING = -0.2031509420
REVIEW_NET = -21.0702723779
REVIEW_OPEN_FEE = 0.5494423956
REVIEW_OPEN_FUNDING = -0.2020315185
REVIEW_CASH = 9978.5823167449
REVIEW_EQUITY = 9967.6660105849
REVIEW_MISLABEL = REVIEW_EQUITY - REVIEW_CAPITAL


def _review_events() -> list[dict]:
    """One closed XRP short and one still-open XRP short, journal order."""
    return [
        {"kind": "capital", "amount": REVIEW_CAPITAL},
        {
            "kind": "open",
            "symbol": "XRPUSDT",
            "side": "SHORT",
            "quantity": 670.1,
            "fill_price": 1.4898087,
            "fee": REVIEW_ENTRY_FEE,
        },
        {"kind": "funding", "symbol": "XRPUSDT", "amount": REVIEW_CLOSE_FUNDING},
        {
            "kind": "close",
            "symbol": "XRPUSDT",
            "side": "SHORT",
            "quantity": 670.1,
            "fill_price": 1.5199,
            "fee": REVIEW_EXIT_FEE,
            "entry_fee": REVIEW_ENTRY_FEE,
            "gross_pnl": REVIEW_GROSS,
            "funding": REVIEW_CLOSE_FUNDING,
        },
        {
            "kind": "open",
            "symbol": "XRPUSDT",
            "side": "SHORT",
            "quantity": 679.2,
            "fill_price": 1.4708277,
            "fee": REVIEW_OPEN_FEE,
        },
        {"kind": "funding", "symbol": "XRPUSDT", "amount": REVIEW_OPEN_FUNDING},
    ]


def _review_position(mark: float) -> SimpleNamespace:
    return SimpleNamespace(
        symbol="XRPUSDT",
        side="SHORT",
        quantity=679.2,
        entry_price=1.4708277,
        mark=mark,
    )


def test_live_book_keeps_the_six_labels_apart() -> None:
    """The review's open short: cash, closed net, and equity are three numbers."""
    cash_gap = REVIEW_EQUITY - REVIEW_CASH
    entry = 1.4708277
    quantity = 679.2
    # Short P&L is (entry - mark) * quantity. Pick the mark that matches the review.
    mark = entry - (cash_gap / quantity)
    position = _review_position(mark)
    book = book_statement(
        _review_events(),
        [position],
        {"XRPUSDT": mark},
        trades_net_pnl=0.0,
    )

    assert book["contributed_capital"] == pytest.approx(REVIEW_CAPITAL)
    assert book["cash"] == pytest.approx(REVIEW_CASH)
    assert book["closed_realised_pnl"] == pytest.approx(REVIEW_NET)
    assert book["open_entry_costs"] == pytest.approx(REVIEW_OPEN_FEE)
    assert book["accrued_funding"] == pytest.approx(REVIEW_CLOSE_FUNDING + REVIEW_OPEN_FUNDING)
    assert book["closed_funding"] == pytest.approx(REVIEW_CLOSE_FUNDING)
    assert book["open_funding"] == pytest.approx(REVIEW_OPEN_FUNDING)
    # Closed-only funding is not the accrued figure.
    assert book["accrued_funding"] != pytest.approx(book["closed_funding"])
    assert book["marked_unrealised_pnl"] == pytest.approx(cash_gap)
    assert book["equity"] == pytest.approx(book["cash"] + book["marked_unrealised_pnl"])
    assert book["equity"] == pytest.approx(REVIEW_EQUITY)
    assert book["cash_bridge"] == pytest.approx(book["cash"])
    # The stored snapshot labelled this gap as realised. The live read must not.
    assert book["closed_realised_pnl"] != pytest.approx(REVIEW_MISLABEL)
    assert book["closed_realised_pnl"] != pytest.approx(book["equity"] - book["contributed_capital"])
    assert book["cash"] - book["contributed_capital"] != pytest.approx(book["closed_realised_pnl"])
    for key in (
        "contributed_capital",
        "cash",
        "closed_realised_pnl",
        "open_entry_costs",
        "accrued_funding",
        "marked_unrealised_pnl",
    ):
        assert key in book
    assert "realised_pnl" not in book


def test_missing_mark_does_not_invent_a_zero_unrealised() -> None:
    book = book_statement(
        [{"kind": "capital", "amount": 10_000.0}],
        [SimpleNamespace(symbol="XRPUSDT", side="SHORT", quantity=1.0, entry_price=1.5)],
        {"XRPUSDT": None},
    )
    assert book["marks_complete"] is False
    assert book["marked_unrealised_pnl"] is None
    assert book["equity"] is None


def test_no_journal_does_not_substitute_starting_capital() -> None:
    book = book_statement([], [], {})
    assert book["journal_present"] is False
    assert book["contributed_capital"] is None
    assert book["closed_realised_pnl"] is None
    assert book["equity"] is None


def test_snapshot_writer_stores_closed_net_and_the_mark(firm_db) -> None:
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    ledger.record_equity(
        equity=10_100.0,
        realised_pnl=0.0,
        unrealised_pnl=100.0,
        open_position_count=1,
    )
    with session_scope() as session:
        row = session.scalars(select(EquitySnapshot)).one()
    assert row.realised_pnl == pytest.approx(0.0)
    assert row.unrealised_pnl == pytest.approx(100.0)
    assert row.realised_pnl != pytest.approx(row.equity - STARTING)


def test_cycle_snapshot_uses_the_open_mark(tmp_path, monkeypatch, firm_db) -> None:
    """An open long above entry must not be filed as realised P&L."""
    from core.execution.engine import TradingEngine, TradingPlan
    from core.risk.engine import RiskEngine
    from core.risk.killswitch import KillSwitch
    from core.risk.limits import PAPER_LIMITS
    from core.execution import engine as engine_mod

    prices = {SYMBOL: 100_000.0}
    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
    )
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=PAPER_LIMITS, kill_switch=KillSwitch(tmp_path / "kill.json")),
        ledger=ledger,
        plan=TradingPlan(),
        data_source=object(),
    )
    monkeypatch.setattr(engine, "refresh_scan_plan", lambda: False)
    opened = broker.place_market_order(SYMBOL, "LONG", 0.01, expected_price=100_000.0)
    assert opened.success
    broker.set_stops(SYMBOL, take_profit=150_000.0, stop_loss=50_000.0)
    ledger.open_position(
        symbol=SYMBOL,
        side="LONG",
        quantity=opened.filled_quantity or 0.01,
        entry_price=opened.fill_price,
        expected_entry_price=100_000.0,
        take_profit=150_000.0,
        stop_loss=50_000.0,
        strategy="label-test",
        sector="other",
        signal_score=1.0,
        signal_reason="open mark",
        broker_order_id=opened.order_id or "paper-label",
        entry_fee=opened.fee or 0.0,
    )
    prices[SYMBOL] = 110_000.0

    engine.run_cycle()

    with session_scope() as session:
        row = session.scalars(
            select(EquitySnapshot).order_by(EquitySnapshot.recorded_at.desc())
        ).first()
    assert row is not None
    assert row.unrealised_pnl == pytest.approx(100.0)
    assert row.realised_pnl == pytest.approx(0.0)
    assert row.equity == pytest.approx(10_100.0)
    assert row.realised_pnl != pytest.approx(row.equity - STARTING)
    assert len(broker.get_positions()) == 1


def test_api_book_ignores_a_mislabeled_snapshot(tmp_path, monkeypatch, firm_db) -> None:
    """The live read recomputes the six labels. It does not trust the snapshot column."""
    from api import app as app_module
    from core.execution import paper_cash as cash_mod

    cash_path = tmp_path / "paper_cash.json"
    monkeypatch.setattr(cash_mod, "PAPER_CASH_PATH", cash_path)
    store = PaperCashStore(cash_path)
    for event in _review_events():
        store.record(event)

    ledger = Ledger(mode="paper", starting_equity=STARTING)
    ledger.open_position(
        symbol="XRPUSDT",
        side="SHORT",
        quantity=679.2,
        entry_price=1.4708277,
        expected_entry_price=1.4708277,
        take_profit=1.42,
        stop_loss=1.52,
        strategy="already-open",
        sector="other",
        signal_score=1.0,
        signal_reason="fixture",
        broker_order_id="paper-open",
        entry_fee=REVIEW_OPEN_FEE,
    )
    ledger.record_equity(
        equity=REVIEW_EQUITY,
        realised_pnl=REVIEW_MISLABEL,
        unrealised_pnl=0.0,
        open_position_count=1,
    )
    mark = 1.4708277 - ((REVIEW_EQUITY - REVIEW_CASH) / 679.2)
    monkeypatch.setattr(app_module, "_ticker_marks", lambda symbols: {"XRPUSDT": mark})

    body = TestClient(app_module.app).get("/api/risk").json()
    book = body["book"]
    assert book["closed_realised_pnl"] == pytest.approx(REVIEW_NET)
    assert book["marked_unrealised_pnl"] == pytest.approx(REVIEW_EQUITY - REVIEW_CASH)
    assert book["equity"] == pytest.approx(book["cash"] + book["marked_unrealised_pnl"])
    assert book["closed_realised_pnl"] != pytest.approx(body["equity"]["realised_pnl"])
    assert set(book["definitions"]) == {
        "contributed_capital",
        "cash",
        "closed_realised_pnl",
        "open_entry_costs",
        "accrued_funding",
        "marked_unrealised_pnl",
    }
    html = (ROOT / "api" / "static" / "index.html").read_text(encoding="utf-8")
    for label in (
        "Contributed capital",
        "Closed realised",
        "Open entry costs",
        "Accrued funding",
        "Marked unrealised",
    ):
        assert label in html
    assert "not equity minus contributed capital" in html


def _open_ledger_long(broker: PaperBroker, ledger: Ledger) -> int:
    opened = broker.place_market_order(SYMBOL, "LONG", 0.01, expected_price=100_000.0)
    assert opened.success
    broker.set_stops(SYMBOL, take_profit=150_000.0, stop_loss=97_000.0)
    return ledger.open_position(
        symbol=SYMBOL,
        side="LONG",
        quantity=opened.filled_quantity or 0.01,
        entry_price=opened.fill_price,
        expected_entry_price=100_000.0,
        take_profit=150_000.0,
        stop_loss=97_000.0,
        strategy="crash-test",
        sector="other",
        signal_score=1.0,
        signal_reason="seed",
        broker_order_id=opened.order_id or "paper-crash",
        entry_fee=opened.fee or 0.0,
    )


def _counts() -> tuple[int, int]:
    with session_scope() as session:
        trades = int(session.scalar(select(func.count(TradeRecord.id))) or 0)
        events = int(session.scalar(select(func.count(PaperCashEvent.id))) or 0)
    return trades, events


def test_close_rolls_back_when_the_commit_crashes(tmp_path, firm_db) -> None:
    prices = {SYMBOL: 100_000.0}
    store = PaperCashStore(tmp_path / "paper_cash.json")
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
        cash_store=store,
    )
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    position_id = _open_ledger_long(broker, ledger)
    prices[SYMBOL] = 96_500.0
    quoted = broker.quote_mark_close(SYMBOL, 96_500.0, 97_000.0)
    assert quoted is not None
    event_id = paper_close_event_id(
        position_id=position_id,
        symbol=SYMBOL,
        reason="stop_loss",
        quantity=quoted.quantity,
        fill_price=quoted.fill_price,
    )
    payload = broker.build_close_payload(quoted, event_id=event_id, position_id=position_id)
    cash_before = broker.cash

    def boom() -> None:
        raise RuntimeError("crash before commit")

    with pytest.raises(RuntimeError, match="crash before commit"):
        settle_paper_close(
            ledger=ledger,
            event_id=event_id,
            payload=payload,
            position_id=position_id,
            exit_price=quoted.fill_price,
            expected_exit_price=97_000.0,
            exit_reason="stop_loss",
            entry_fees=quoted.entry_fee,
            exit_fees=quoted.fee,
            funding=quoted.funding,
            before_commit=boom,
        )

    assert _counts() == (0, 0)
    assert ledger.find_open_position(SYMBOL) is not None
    assert broker.cash == pytest.approx(cash_before)
    assert SYMBOL in broker._positions
    assert not any(event.get("kind") == KIND_CLOSE for event in store.events())


def test_replay_of_a_committed_close_does_not_double_insert(tmp_path, firm_db) -> None:
    """SQLite has the close and the trade. JSON does not, until hydrate catches up."""
    prices = {SYMBOL: 100_000.0}
    cash_path = tmp_path / "paper_cash.json"
    store = PaperCashStore(cash_path)
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
        cash_store=store,
    )
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    position_id = _open_ledger_long(broker, ledger)
    prices[SYMBOL] = 96_500.0
    quoted = broker.quote_mark_close(SYMBOL, 96_500.0, 97_000.0)
    assert quoted is not None
    event_id = paper_close_event_id(
        position_id=position_id,
        symbol=SYMBOL,
        reason="stop_loss",
        quantity=quoted.quantity,
        fill_price=quoted.fill_price,
    )
    payload = broker.build_close_payload(quoted, event_id=event_id, position_id=position_id)
    cash_before_apply = broker.cash

    first = settle_paper_close(
        ledger=ledger,
        event_id=event_id,
        payload=payload,
        position_id=position_id,
        exit_price=quoted.fill_price,
        expected_exit_price=97_000.0,
        exit_reason="stop_loss",
        entry_fees=quoted.entry_fee,
        exit_fees=quoted.fee,
        funding=quoted.funding,
    )
    assert first.already is False
    # Crash window: committed, RAM and JSON not yet updated.
    assert broker.cash == pytest.approx(cash_before_apply)
    assert SYMBOL in broker._positions
    assert not any(event.get("kind") == KIND_CLOSE for event in store.events())
    assert _counts() == (1, 1)
    assert ledger.find_open_position(SYMBOL) is None

    second = settle_paper_close(
        ledger=ledger,
        event_id=event_id,
        payload=payload,
        position_id=position_id,
        exit_price=quoted.fill_price,
        expected_exit_price=97_000.0,
        exit_reason="stop_loss",
        entry_fees=quoted.entry_fee,
        exit_fees=quoted.fee,
        funding=quoted.funding,
    )
    assert second.already is True
    assert second.trade_id == first.trade_id
    assert _counts() == (1, 1)

    expected_cash = STARTING + quoted.gross_pnl - quoted.fee
    revived = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
        cash_store=PaperCashStore(cash_path),
    )
    revived.hydrate([])
    assert revived.cash == pytest.approx(expected_cash)
    assert revived.realised_pnl == pytest.approx(quoted.gross_pnl - quoted.entry_fee - quoted.fee - quoted.funding)
    assert revived.get_positions() == []

    again = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
        cash_store=PaperCashStore(cash_path),
    )
    again.hydrate([])
    assert again.cash == pytest.approx(revived.cash)
    closes = [event for event in PaperCashStore(cash_path).events() if event.get("kind") == KIND_CLOSE]
    assert len(closes) == 1
    assert closes[0]["event_id"] == event_id
    with session_scope() as session:
        trade = session.scalars(select(TradeRecord)).one()
    assert trade.cash_event_id == event_id
    assert trade.strategy == "crash-test"
    assert trade.exit_reason == "stop_loss"
    assert trade.net_pnl == pytest.approx(revived.realised_pnl)


def test_engine_stop_writes_one_trade_and_one_journal_close(tmp_path, monkeypatch, firm_db) -> None:
    from core.execution import engine as engine_mod
    from core.execution.engine import TradingEngine, TradingPlan
    from core.risk.engine import RiskEngine
    from core.risk.killswitch import KillSwitch
    from core.risk.limits import PAPER_LIMITS

    prices = {SYMBOL: 100_000.0}
    cash_path = tmp_path / "paper_cash.json"
    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
        cash_store=PaperCashStore(cash_path),
    )
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=PAPER_LIMITS, kill_switch=KillSwitch(tmp_path / "kill.json")),
        ledger=ledger,
        plan=TradingPlan(),
        data_source=object(),
    )
    monkeypatch.setattr(engine, "refresh_scan_plan", lambda: False)
    _open_ledger_long(broker, ledger)
    prices[SYMBOL] = 96_500.0

    report = engine.run_cycle()
    assert report.positions_closed == 1
    assert broker.get_positions() == []
    assert ledger.open_positions() == []
    assert _counts() == (1, 1)
    closes = [event for event in PaperCashStore(cash_path).events() if event.get("kind") == KIND_CLOSE]
    assert len(closes) == 1
    with session_scope() as session:
        trade = session.scalars(select(TradeRecord)).one()
        durable = session.scalars(select(PaperCashEvent)).one()
    assert trade.cash_event_id == durable.event_id == closes[0]["event_id"]
    assert trade.net_pnl == pytest.approx(broker.realised_pnl)

    engine.run_cycle()
    assert _counts() == (1, 1)
    closes_again = [
        event for event in PaperCashStore(cash_path).events() if event.get("kind") == KIND_CLOSE
    ]
    assert len(closes_again) == 1


def test_source_does_not_label_equity_minus_capital_as_realised() -> None:
    """Fail if a writer again stores equity minus starting capital as realised."""
    patterns = (
        re.compile(r"realised_pnl\s*=\s*equity\s*-"),
        re.compile(r'"realised_pnl"\s*:\s*equity\s*-'),
        re.compile(r"realised_pnl=equity\s*-"),
    )
    roots = [ROOT / "core", ROOT / "api", ROOT / "scripts", ROOT / "firm"]
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                if pattern.search(text):
                    offenders.append(f"{path.relative_to(ROOT)} matches {pattern.pattern}")
    assert offenders == []
