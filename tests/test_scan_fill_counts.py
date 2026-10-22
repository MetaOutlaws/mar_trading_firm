"""Scan-summary fills and exits, and entry cash identity.

The diary counters are reporting. They must not change the order the risk
decision already approved, the fill the paper broker already computed, or
the cash balance that fill produced.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest
from sqlalchemy import select

from core.db import session_scope
from core.execution.engine import (
    PlanEntry,
    TradingEngine,
    TradingPlan,
    _remember_exit_note,
    _remember_order_note,
)
from core.execution.paper import PaperBroker
from core.execution.paper_cash import PaperCashStore, merge_cash_events, replay_events
from core.execution.paper_settle import (
    CloseSettlementError,
    link_entry_cash_event,
    load_durable_close_payloads,
    settle_paper_close,
)
from core.ledger.models import PaperCashEvent, TradeRecord
from core.ledger.store import Ledger
from core.risk.engine import RiskDecision, RiskEngine, RiskVerdict
from core.risk.killswitch import KillSwitch
from core.risk.limits import PAPER_LIMITS
from core.strategy.base import Signal, SignalSide, Strategy
from firm.memory_models import Proposal
from firm.scan_inbox import summarise_sleeve_notes
from research.costs import CostModel
from tests.test_execution import StubDataSource
from tests.test_paper_bar_eval import AlwaysLong, Clock, _at, _engine, _entry, poll_paper_book

UTC = timezone.utc
STARTING = 10_000.0
SYMBOL = "ETHUSDT"


class _Sleeve(Strategy):
    """A named sleeve so the order note has an id. It does not generate bars."""

    name = "parity_sleeve"
    min_bars = 1

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        return self.empty_signals(candles)


def _payloads() -> list[dict]:
    with session_scope() as session:
        rows = session.scalars(select(Proposal)).all()
        return [dict(row.payload) for row in rows if isinstance(row.payload, dict)]


def test_order_note_counts_a_paper_fill_and_not_an_approval(tmp_path) -> None:
    """filled defaults off. Passing it is what the summary counter reads."""
    entry = _entry(SYMBOL, SignalSide.LONG, _Sleeve(), "1h")
    bar = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
    approved: list[dict] = []
    filled: list[dict] = []
    _remember_order_note(approved, [], entry, bar, ordered=True, rejection="")
    _remember_order_note(filled, [], entry, bar, ordered=True, rejection="", filled=True)

    assert summarise_sleeve_notes(approved)["entries_opened"] == 1
    assert summarise_sleeve_notes(approved)["fills"] == 0
    assert summarise_sleeve_notes(filled)["entries_opened"] == 1
    assert summarise_sleeve_notes(filled)["fills"] == 1
    assert summarise_sleeve_notes(filled)["exits"] == 0


def test_poll_counts_the_fill_and_the_exit(tmp_path, monkeypatch, firm_db) -> None:
    """The 15s poll is the path that writes the book card. Both counters move."""
    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", tmp_path / "scan_summaries.jsonl")
    clock = Clock(_at(12, 5))
    strategy = AlwaysLong()
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("BTCUSDT", SignalSide.LONG, strategy, "1h")],
    )
    seen: list[tuple] = []
    real = engine.broker.place_market_order

    def _record(symbol, side, quantity, expected_price, reduce_only=False, **kwargs):
        seen.append((symbol, side, quantity, expected_price, reduce_only, kwargs.get("quoted_price")))
        return real(
            symbol,
            side,
            quantity,
            expected_price,
            reduce_only=reduce_only,
            **kwargs,
        )

    engine.broker.place_market_order = _record  # type: ignore[method-assign]
    decisions: list[RiskDecision] = []
    real_attempt = engine._attempt_entry

    def _attempt(signal, equity, marks):
        decision = real_attempt(signal, equity, marks)
        decisions.append(decision)
        return decision

    engine._attempt_entry = _attempt  # type: ignore[method-assign]

    assert poll_paper_book(engine) == 1
    assert len(decisions) == 1
    assert decisions[0].is_approved
    assert len(seen) == 1
    symbol, side, quantity, expected_price, reduce_only, quoted = seen[0]
    assert (symbol, side, reduce_only) == ("BTCUSDT", "LONG", False)
    # The quote is taken before the book lock and passed into the fill.
    assert quoted == pytest.approx(100_000.0)
    assert quantity == pytest.approx(decisions[0].quantity)
    assert expected_price == pytest.approx(100_000.0)
    position = engine.broker._positions["BTCUSDT"]
    assert position.quantity == pytest.approx(quantity)
    assert position.entry_price == pytest.approx(100_000.0)

    cards = _payloads()
    assert sum(int(card.get("fills") or 0) for card in cards) == 1
    assert sum(int(card.get("entries_opened") or 0) for card in cards) == 1
    assert sum(int(card.get("exits") or 0) for card in cards) == 0
    fill_rows = [
        row
        for card in cards
        for row in (card.get("sleeve_rows") or [])
        if isinstance(row, dict) and row.get("filled")
    ]
    assert len(fill_rows) == 1
    assert fill_rows[0]["ordered"] is True

    # A second poll of the same bar must not place another order.
    assert poll_paper_book(engine) == 0
    assert len(seen) == 1

    engine.broker._data.prices["BTCUSDT"] = 90_000.0
    assert engine.supervise_exits() == 1
    assert engine.broker.get_positions() == []
    cards = _payloads()
    assert sum(int(card.get("fills") or 0) for card in cards) == 1
    assert sum(int(card.get("exits") or 0) for card in cards) == 1
    # The exit row does not replace the entry row.
    assert any(
        isinstance(row, dict) and row.get("filled") and not row.get("exited")
        for card in cards
        for row in (card.get("sleeve_rows") or [])
    )
    assert any(
        isinstance(row, dict) and row.get("exited") and not row.get("filled")
        for card in cards
        for row in (card.get("sleeve_rows") or [])
    )


def _wired_engine(tmp_path, monkeypatch, prices: dict[str, float], store: PaperCashStore):
    from core.execution import engine as engine_mod

    costs = CostModel(taker_fee=0.001, maker_fee=0.001, slippage=0.002, include_funding=False)
    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=costs,
        data_source=StubDataSource(prices),
        cash_store=store,
        lock_cost_model=True,
    )
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(
            limits=PAPER_LIMITS, kill_switch=KillSwitch(tmp_path / "kill.json")
        ),
        ledger=Ledger(mode="paper", starting_equity=STARTING),
        plan=TradingPlan(
            entries=[PlanEntry(symbol=SYMBOL, side=SignalSide.LONG, strategy=_Sleeve(), timeframe="1h")]
        ),
        data_source=StubDataSource(prices),  # type: ignore[arg-type]
    )
    return engine, costs


def _signal() -> Signal:
    return Signal(
        symbol=SYMBOL,
        side=SignalSide.LONG,
        timestamp=pd.Timestamp("2026-10-15T00:00:00Z"),
        price=3_000.0,
        score=1.0,
        reason="parity",
        strategy="parity_sleeve",
        take_profit_pct=0.05,
        stop_loss_pct=0.05,
        max_holding_bars=3,
    )


def test_linking_the_entry_does_not_change_cash_or_the_decision(tmp_path, monkeypatch, firm_db) -> None:
    """The shadow broker is the old cash path: one open, then one close, no mirror.

    Stamping position_id and writing paper_cash_events must leave that cash
    number where it was, including after a restart.
    """
    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", tmp_path / "scan_summaries.jsonl")
    prices = {SYMBOL: 3_000.0}
    engine, costs = _wired_engine(tmp_path, monkeypatch, prices, PaperCashStore(tmp_path / "cash.json"))
    shadow_prices = {SYMBOL: 3_000.0}
    shadow = PaperBroker(
        starting_equity=STARTING,
        costs=costs,
        data_source=StubDataSource(shadow_prices),
        cash_store=PaperCashStore(tmp_path / "shadow.json"),
        lock_cost_model=True,
    )
    decision = RiskDecision(verdict=RiskVerdict.APPROVED, quantity=1.0, notional=3_000.0)
    signal = _signal()
    assert engine._place_order(signal, decision, stop_price=2_850.0, take_profit=3_150.0, sector="majors")
    shadow_fill = shadow.place_market_order(SYMBOL, "LONG", decision.quantity, expected_price=signal.price)
    assert shadow_fill.success

    broker = engine.broker
    assert isinstance(broker, PaperBroker)
    live = broker._positions[SYMBOL]
    quiet = shadow._positions[SYMBOL]
    # Same order in: same fill, same fee, same cash out.
    assert live.quantity == pytest.approx(quiet.quantity) == pytest.approx(decision.quantity)
    assert live.entry_price == pytest.approx(quiet.entry_price)
    assert live.entry_price == pytest.approx(costs.entry_price(signal.price, "LONG"))
    assert live.entry_fee == pytest.approx(quiet.entry_fee)
    assert broker.cash == pytest.approx(shadow.cash)
    assert broker.cash == pytest.approx(STARTING - live.entry_fee)
    cash_while_open = broker.cash

    opens = [event for event in broker._cash_store.events() if event.get("kind") == "open"]
    shadow_opens = [event for event in shadow._cash_store.events() if event.get("kind") == "open"]
    assert len(opens) == len(shadow_opens) == 1
    position = engine.ledger.find_open_position(SYMBOL)
    assert position is not None
    assert opens[0]["position_id"] == position.id
    assert opens[0]["event_id"] == f"paper-open:{position.id}:{SYMBOL}"
    assert opens[0]["fee"] == pytest.approx(shadow_opens[0]["fee"])
    assert opens[0]["cash_after"] == pytest.approx(shadow_opens[0]["cash_after"])
    assert "position_id" not in shadow_opens[0]

    with session_scope() as session:
        mirrored = session.scalars(select(PaperCashEvent)).one()
    assert mirrored.kind == "open"
    assert mirrored.position_id == position.id
    assert mirrored.event_id == opens[0]["event_id"]

    revived = PaperBroker(
        starting_equity=STARTING,
        costs=costs,
        data_source=StubDataSource(dict(prices)),
        cash_store=PaperCashStore(tmp_path / "cash.json"),
        lock_cost_model=True,
    )
    revived.hydrate(engine.ledger.open_positions())
    assert revived.cash == pytest.approx(cash_while_open)
    merged = merge_cash_events(revived._cash_store.events(), load_durable_close_payloads())
    assert sum(event.get("kind") == "open" for event in merged) == 1
    assert replay_events(merged).cash == pytest.approx(cash_while_open)

    exit_price = 2_900.0
    prices[SYMBOL] = exit_price
    shadow_prices[SYMBOL] = exit_price
    assert engine._settle_paper_exit(SYMBOL, "stop_loss", at_mark=True, mark_price=exit_price) == 1
    quoted = shadow.quote_mark_close(SYMBOL, exit_price, exit_price)
    assert quoted is not None
    shadow.apply_journal_close(shadow.build_close_payload(quoted, event_id=None, position_id=None))

    assert broker.cash == pytest.approx(shadow.cash)
    assert broker.cash == pytest.approx(cash_while_open + quoted.gross_pnl - quoted.fee)
    kinds = [event.get("kind") for event in broker._cash_store.events()]
    assert kinds.count("open") == 1
    assert kinds.count("close") == 1
    close = next(event for event in broker._cash_store.events() if event.get("kind") == "close")
    assert close["position_id"] == position.id
    assert str(close["event_id"]).startswith("paper-close:")

    with session_scope() as session:
        rows = list(session.scalars(select(PaperCashEvent).order_by(PaperCashEvent.id)))
        trade = session.scalars(select(TradeRecord)).one()
    assert [row.kind for row in rows] == ["open", "close"]
    assert trade.cash_event_id == rows[1].event_id == close["event_id"]
    assert rows[0].event_id == opens[0]["event_id"]

    flat = PaperBroker(
        starting_equity=STARTING,
        costs=costs,
        data_source=StubDataSource({SYMBOL: exit_price}),
        cash_store=PaperCashStore(tmp_path / "cash.json"),
        lock_cost_model=True,
    )
    flat.hydrate([])
    assert flat.cash == pytest.approx(broker.cash)
    merged = merge_cash_events(flat._cash_store.events(), load_durable_close_payloads())
    assert sum(event.get("kind") == "open" for event in merged) == 1
    assert sum(event.get("kind") == "close" for event in merged) == 1
    assert replay_events(merged).cash == pytest.approx(broker.cash)


def test_an_open_cash_event_is_not_a_close(tmp_path, monkeypatch, firm_db) -> None:
    """A later close of a missing position must not replay the entry as cash."""
    prices = {SYMBOL: 3_000.0}
    engine, _costs = _wired_engine(tmp_path, monkeypatch, prices, PaperCashStore(tmp_path / "cash.json"))
    signal = _signal()
    decision = RiskDecision(verdict=RiskVerdict.APPROVED, quantity=1.0, notional=3_000.0)
    assert engine._place_order(signal, decision, stop_price=2_850.0, take_profit=3_150.0, sector="majors")
    broker = engine.broker
    assert isinstance(broker, PaperBroker)
    cash_while_open = broker.cash
    position = engine.ledger.find_open_position(SYMBOL)
    assert position is not None
    engine.ledger.close_position(
        position_id=position.id,
        exit_price=2_900.0,
        expected_exit_price=2_900.0,
        exit_reason="manual",
        entry_fees=broker._positions[SYMBOL].entry_fee,
        exit_fees=0.0,
    )
    quoted = broker.quote_mark_close(SYMBOL, 2_900.0, 2_900.0)
    assert quoted is not None
    payload = broker.build_close_payload(
        quoted, event_id=f"paper-close:{position.id}:other", position_id=position.id
    )
    with pytest.raises(CloseSettlementError):
        settle_paper_close(
            ledger=engine.ledger,
            event_id=str(payload["event_id"]),
            payload=payload,
            position_id=position.id,
            exit_price=quoted.fill_price,
            expected_exit_price=quoted.fill_price,
            exit_reason="stop_loss",
            entry_fees=quoted.entry_fee,
            exit_fees=quoted.fee,
            funding=quoted.funding,
        )
    assert broker.cash == pytest.approx(cash_while_open)
    with session_scope() as session:
        rows = list(session.scalars(select(PaperCashEvent)))
    assert [row.kind for row in rows] == ["open"]


def test_exit_note_is_counted_without_an_entry(tmp_path, monkeypatch, firm_db) -> None:
    """A filled exit on its own still moves the exits counter."""
    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", tmp_path / "scan_summaries.jsonl")
    clock = Clock(_at(12, 5))
    engine = _engine(tmp_path, monkeypatch, clock, [])
    position = type(
        "Row",
        (),
        {"symbol": "XRPUSDT", "side": "SHORT", "strategy": "range_compression", "timeframe": "4h"},
    )()
    _remember_exit_note(engine, position, "stop_loss")
    cards = _payloads()
    assert sum(int(card.get("exits") or 0) for card in cards) == 1
    assert sum(int(card.get("fills") or 0) for card in cards) == 0
    assert sum(int(card.get("entries_opened") or 0) for card in cards) == 0


def test_link_is_a_no_op_without_a_journal(tmp_path, monkeypatch, firm_db) -> None:
    """No cash store means no mirrored row and no cash movement to invent."""
    prices = {SYMBOL: 3_000.0}
    from core.execution import engine as engine_mod

    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=CostModel(taker_fee=0.001, maker_fee=0.001, slippage=0.0, include_funding=False),
        data_source=StubDataSource(prices),
        lock_cost_model=True,
    )
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    before = broker.cash
    link_entry_cash_event(broker, ledger, SYMBOL, 1)
    assert broker.cash == pytest.approx(before)
    with session_scope() as session:
        assert session.scalars(select(PaperCashEvent)).all() == []
