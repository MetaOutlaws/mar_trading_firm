"""Every paper close path posts a journal event keyed to the trade.

Stop, take-profit, and expiry all go through ``_settle_paper_exit``, which
commits ``settle_paper_close`` and then appends the same ``event_id`` to
the JSON journal. Exit supervision is that method. A path that skipped the
journal would fail these tests. The guard only logs; it does not change
the fill.
"""

from __future__ import annotations

import inspect
import logging
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from core.db import session_scope
from core.execution.engine import TradingEngine, TradingPlan, _guard_journal_has_close
from core.execution.paper import PaperBroker
from core.execution.paper_cash import KIND_CLOSE, PaperCashStore
from core.execution.paper_settle import paper_close_event_id, settle_paper_close
from core.ledger.models import PaperCashEvent, TradeRecord
from core.ledger.store import Ledger
from core.risk.engine import RiskEngine
from core.risk.killswitch import KillSwitch
from core.risk.limits import PAPER_LIMITS
from research.costs import FRICTIONLESS
from tests.test_execution import StubDataSource

STARTING = 10_000.0
SYMBOL = "BTCUSDT"


def _engine(tmp_path, monkeypatch, prices) -> tuple[TradingEngine, Path]:
    from core.execution import engine as engine_mod

    cash_path = tmp_path / "paper_cash.json"
    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
        cash_store=PaperCashStore(cash_path),
    )
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(
            limits=PAPER_LIMITS, kill_switch=KillSwitch(tmp_path / "kill.json")
        ),
        ledger=Ledger(mode="paper", starting_equity=STARTING),
        plan=TradingPlan(),
        data_source=object(),
    )
    monkeypatch.setattr(engine, "refresh_scan_plan", lambda: False)
    return engine, cash_path


def _open(engine: TradingEngine, prices: dict[str, float], **overrides: object) -> None:
    result = engine.broker.place_market_order(
        SYMBOL, "LONG", 0.01, expected_price=prices[SYMBOL]
    )
    assert result.success
    take_profit = float(overrides.get("take_profit", 150_000.0))
    stop_loss = float(overrides.get("stop_loss", 97_000.0))
    assert engine.broker.set_stops(SYMBOL, take_profit, stop_loss)
    engine.ledger.open_position(
        symbol=SYMBOL,
        side="LONG",
        quantity=result.filled_quantity or 0.01,
        entry_price=result.fill_price,
        expected_entry_price=prices[SYMBOL],
        take_profit=take_profit,
        stop_loss=stop_loss,
        strategy="journal-guard",
        sector="other",
        signal_score=1.0,
        signal_reason="seed",
        broker_order_id=result.order_id or "paper-guard",
        entry_fee=result.fee or 0.0,
        expiry_at=overrides.get("expiry_at"),  # type: ignore[arg-type]
    )


def _assert_keyed(cash_path: Path, reason: str) -> None:
    closes = [
        event
        for event in PaperCashStore(cash_path).events()
        if event.get("kind") == KIND_CLOSE
    ]
    assert len(closes) == 1
    with session_scope() as session:
        trade = session.scalars(select(TradeRecord)).one()
        durable = session.scalars(select(PaperCashEvent)).one()
    assert trade.exit_reason == reason
    assert trade.cash_event_id == durable.event_id == closes[0]["event_id"]
    assert str(trade.position_id) in str(trade.cash_event_id)
    assert reason in str(trade.cash_event_id)


def test_paper_exit_supervisor_is_the_only_close_path() -> None:
    """Stop, target, and expiry must not journal through check_stops."""
    manage = inspect.getsource(TradingEngine._manage_open_positions)
    paper, _sep, _live = manage.partition("if not getattr")
    assert "self.broker.check_stops" not in paper
    assert "broker.check_stops" not in paper
    assert "_settle_paper_exit" in paper
    settle = inspect.getsource(TradingEngine._settle_paper_exit)
    assert "settle_paper_close(" in settle
    assert "apply_journal_close(" in settle
    assert "_guard_journal_has_close(" in settle
    timeout = inspect.getsource(TradingEngine._timeout_paper_positions)
    assert "_settle_paper_exit(" in timeout
    assert "close_position(" not in timeout


def test_guard_logs_when_the_committed_close_is_missing_from_the_journal(
    tmp_path, caplog
) -> None:
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource({SYMBOL: 100_000.0}),
        cash_store=PaperCashStore(tmp_path / "paper_cash.json"),
    )
    with caplog.at_level(logging.ERROR):
        _guard_journal_has_close(broker, {"event_id": "paper-close:missing"}, SYMBOL, 7)
    assert "paper-close:missing" in caplog.text
    assert SYMBOL in caplog.text
    assert broker._cash_store is not None
    assert broker._cash_store.events() == []


@pytest.mark.parametrize(
    ("reason", "price", "expiry"),
    [
        ("stop_loss", 96_500.0, None),
        ("take_profit", 106_000.0, None),
        ("timeout", 100_000.0, datetime(2020, 1, 1, tzinfo=timezone.utc)),
    ],
)
def test_exit_supervision_journals_the_close(
    tmp_path, monkeypatch, firm_db, reason, price, expiry
) -> None:
    prices = {SYMBOL: 100_000.0}
    engine, cash_path = _engine(tmp_path, monkeypatch, prices)
    stops = {"take_profit": 105_000.0, "stop_loss": 97_000.0}
    if reason == "timeout":
        stops = {"take_profit": 150_000.0, "stop_loss": 50_000.0}
    _open(engine, prices, expiry_at=expiry, **stops)
    prices[SYMBOL] = price

    closed = engine.supervise_exits()

    assert closed == 1
    assert engine.broker.get_positions() == []
    _assert_keyed(cash_path, reason)


def test_paper_settle_keys_the_trade_and_the_journal(tmp_path, firm_db) -> None:
    prices = {SYMBOL: 100_000.0}
    cash_path = tmp_path / "paper_cash.json"
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
        cash_store=PaperCashStore(cash_path),
    )
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    opened = broker.place_market_order(SYMBOL, "LONG", 0.01, expected_price=100_000.0)
    assert opened.success
    broker.set_stops(SYMBOL, 150_000.0, 97_000.0)
    position_id = ledger.open_position(
        symbol=SYMBOL,
        side="LONG",
        quantity=opened.filled_quantity or 0.01,
        entry_price=opened.fill_price,
        expected_entry_price=100_000.0,
        take_profit=150_000.0,
        stop_loss=97_000.0,
        strategy="journal-guard",
        sector="other",
        signal_score=1.0,
        signal_reason="seed",
        broker_order_id=opened.order_id or "paper-settle",
        entry_fee=opened.fee or 0.0,
    )
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
    result = settle_paper_close(
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
    assert result.already is False
    applied = broker.apply_journal_close(result.payload)
    assert applied.success
    _guard_journal_has_close(broker, result.payload, SYMBOL, result.trade_id)
    _assert_keyed(cash_path, "stop_loss")
