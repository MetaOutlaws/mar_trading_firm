"""Cheap checks that SGP1's paper overlay still fits feat's #155-#158 book.

SGP1's own tests cover the diary and the cash link on the pre-dust ledger.
These tests are the join: ``opened_at`` from the F111 repair is stored on
the same row as the #157 dust columns, and the near-miss hook still records
a rejection without placing an order.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from core.db import session_scope
from core.execution.engine import _remember_exit_note, _remember_order_note
from core.execution.paper_cash import PaperCashStore
from core.execution.paper_settle import link_entry_cash_event
from core.ledger.models import PaperCashEvent, Position
from core.ledger.store import Ledger
from core.risk.engine import RiskVerdict
from core.risk.limits import PAPER_LIMITS, paper_dust_floor_usdt
from core.strategy.base import SignalSide
from tests.test_capacity_near_miss import (
    EQUITY,
    _engine as _near_miss_engine,
    _position,
    _rows,
    _signal as _near_miss_signal,
    _state,
)
from tests.test_f111_execution_repair import SYMBOL as F111_SYMBOL
from tests.test_f111_execution_repair import candles, open_position, response, setup
from tests.test_f111_paper import T0, _pass_signal
from tests.test_paper_bar_eval import Clock, _at, _engine as _bar_engine, _entry
from tests.test_scan_fill_counts import (
    STARTING,
    SYMBOL,
    _Sleeve,
    _signal,
    _wired_engine,
)

UTC = timezone.utc
# A clock that is not "now", so a default utcnow() cannot satisfy the assert.
OBSERVED = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
OCT20_EQUITY = 19_800.0
OCT20_PCT = 0.10


def _loaded(position_id: int) -> Position:
    """Read the row inside the session. A detached row would expire the fields."""
    with session_scope() as session:
        row = session.get(Position, position_id)
        assert row is not None
        session.expunge(row)
        return row


def test_observed_open_stores_dust_columns_on_the_same_row(firm_db) -> None:
    """The F111 clock and the #157 dust flag are one ledger write.

    A sub-floor notional stays out of the daily counter. A notional on the
    floor counts. Both rows keep the observed open time, not a later default.
    """
    floor = paper_dust_floor_usdt(OCT20_EQUITY, OCT20_PCT)
    assert floor == pytest.approx(198.0)
    ledger = Ledger(mode="paper", starting_equity=OCT20_EQUITY)
    price = 100.0

    dust_id = ledger.open_position(
        symbol="GMTUSDT",
        side="LONG",
        quantity=8.0 / price,
        entry_price=price,
        expected_entry_price=price,
        take_profit=price * 1.05,
        stop_loss=price * 0.97,
        strategy="range_compression_volume_thrust",
        sector="majors",
        signal_score=1.0,
        signal_reason="observed-dust",
        broker_order_id="observed-dust",
        entry_equity=OCT20_EQUITY,
        max_position_pct=OCT20_PCT,
        opened_at=OBSERVED,
    )
    dust = _loaded(dust_id)
    assert dust.opened_at == OBSERVED
    assert dust.entry_equity == pytest.approx(OCT20_EQUITY)
    assert dust.dust_floor_usdt == pytest.approx(floor)
    assert dust.counts_toward_daily_trades is False
    assert dust.daily_trade_at is None
    assert ledger.trades_today() == 0

    counted_id = ledger.open_position(
        symbol="ETHUSDT",
        side="LONG",
        quantity=246.0 / price,
        entry_price=price,
        expected_entry_price=price,
        take_profit=price * 1.05,
        stop_loss=price * 0.97,
        strategy="range_compression_volume_thrust",
        sector="majors",
        signal_score=1.0,
        signal_reason="observed-counted",
        broker_order_id="observed-counted",
        entry_equity=OCT20_EQUITY,
        max_position_pct=OCT20_PCT,
        opened_at=OBSERVED,
    )
    counted = _loaded(counted_id)
    assert counted.opened_at == OBSERVED
    assert counted.counts_toward_daily_trades is True
    assert counted.daily_trade_at is not None
    assert counted.dust_floor_usdt == pytest.approx(floor)
    # The counter uses daily_trade_at, which is stamped when the row starts
    # counting. opened_at stays the observed clock and does not move the day.
    assert ledger.trades_today() == 1


def test_engine_links_the_entry_cash_event_to_the_position(tmp_path, monkeypatch, firm_db) -> None:
    """The book path stamps the open cash row and stores the sizer equity."""
    prices = {SYMBOL: 3_000.0}
    engine, _costs = _wired_engine(
        tmp_path, monkeypatch, prices, PaperCashStore(tmp_path / "cash.json")
    )
    signal = _signal()
    from core.risk.engine import RiskDecision

    decision = RiskDecision(verdict=RiskVerdict.APPROVED, quantity=1.0, notional=3_000.0)
    assert engine._place_order(
        signal,
        decision,
        stop_price=2_850.0,
        take_profit=3_150.0,
        sector="majors",
        entry_equity=STARTING,
    )
    position = engine.ledger.find_open_position(SYMBOL)
    assert position is not None
    opens = [
        event
        for event in engine.broker._cash_store.events()  # type: ignore[attr-defined]
        if event.get("kind") == "open"
    ]
    assert len(opens) == 1
    assert opens[0]["position_id"] == position.id
    with session_scope() as session:
        mirrored = session.scalars(select(PaperCashEvent)).one()
    assert mirrored.kind == "open"
    assert mirrored.position_id == position.id
    assert mirrored.event_id == opens[0]["event_id"]
    stored = _loaded(position.id)
    # 3_000 is well above the paper dust floor at $10k, so the fill counts.
    assert stored.entry_equity == pytest.approx(STARTING)
    assert stored.dust_floor_usdt == pytest.approx(
        paper_dust_floor_usdt(STARTING, PAPER_LIMITS.max_position_pct)
    )
    assert stored.counts_toward_daily_trades is True
    assert stored.opened_at is not None


def test_f111_links_the_entry_and_keeps_the_observed_open(tmp_path, firm_db, monkeypatch) -> None:
    """The F111 minute step writes opened_at, the dust columns, and the cash link."""
    from types import SimpleNamespace

    from core.execution import f111_paper

    ledger = Ledger(mode="paper", starting_equity=10_000.0)
    runtime, broker, data, clock = setup(tmp_path, ledger=ledger)
    _pass_signal(runtime)
    runtime.last_registry_at = T0
    runtime.last_signal_hour = T0
    data.fetch_latest = lambda *args, **kwargs: candles()
    monkeypatch.setattr(f111_paper, "_ATTACHED", runtime)
    monkeypatch.setattr("httpx.get", lambda *args, **kwargs: response([]))
    engine = SimpleNamespace(broker=broker, risk=runtime.risk, ledger=ledger)
    clock[0] = T0 + timedelta(minutes=1, seconds=15)
    f111_paper.run_attached_minute_step(engine, data=data, now=clock[0])

    position = ledger.find_open_position(F111_SYMBOL)
    assert position is not None
    stored = _loaded(position.id)
    assert stored.opened_at == clock[0]
    # The sizer reads the balance before the fill. That is the starting cash.
    assert stored.entry_equity == pytest.approx(10_000.0)
    assert stored.dust_floor_usdt == pytest.approx(
        paper_dust_floor_usdt(10_000.0, PAPER_LIMITS.max_position_pct)
    )
    assert stored.counts_toward_daily_trades is True
    with session_scope() as session:
        event = session.scalars(select(PaperCashEvent)).one()
    assert event.kind == "open"
    assert event.position_id == position.id
    assert event.symbol == F111_SYMBOL


def test_f111_close_replay_skips_an_entry_payload(tmp_path, firm_db) -> None:
    """An open cash row shares the position id. Replaying it must not move cash."""
    ledger = Ledger(mode="paper", starting_equity=10_000.0)
    runtime, broker, data, clock = setup(tmp_path, ledger=ledger)
    open_position(runtime, broker, data, clock, ledger=ledger)
    position = ledger.find_open_position(F111_SYMBOL)
    assert position is not None
    link_entry_cash_event(broker, ledger, F111_SYMBOL, int(position.id))
    cash_while_open = broker.cash
    ledger.close_position(
        position.id,
        exit_price=96.0,
        expected_exit_price=96.0,
        exit_reason="test",
        entry_fees=0.0,
        exit_fees=0.0,
    )
    assert ledger.find_open_position(F111_SYMBOL) is None
    result = runtime._close_at_quote(F111_SYMBOL, 96.0, True)
    assert result.success is False
    assert result.error == "open ledger position missing"
    assert broker.cash == pytest.approx(cash_while_open)
    with session_scope() as session:
        kinds = [row.kind for row in session.scalars(select(PaperCashEvent))]
    assert kinds == ["open"]


def test_scan_diary_counts_a_fill_and_an_exit(tmp_path, monkeypatch, firm_db) -> None:
    """filled and exited are diary counters. They do not place or close."""
    from firm.memory_models import Proposal
    from firm.scan_inbox import summarise_sleeve_notes

    entry = _entry(SYMBOL, SignalSide.LONG, _Sleeve(), "1h")
    bar = datetime(2026, 10, 15, 0, 0, tzinfo=UTC)
    notes: list[dict] = []
    _remember_order_note(notes, [], entry, bar, ordered=True, rejection="", filled=True)
    summary = summarise_sleeve_notes(notes)
    assert summary["fills"] == 1
    assert summary["exits"] == 0

    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", tmp_path / "scan_summaries.jsonl")
    clock = Clock(_at(12, 5))
    engine = _bar_engine(tmp_path, monkeypatch, clock, [])
    position = type(
        "Row",
        (),
        {"symbol": "XRPUSDT", "side": "SHORT", "strategy": "range_compression", "timeframe": "4h"},
    )()
    _remember_exit_note(engine, position, "stop_loss")
    with session_scope() as session:
        payloads = [
            dict(row.payload)
            for row in session.scalars(select(Proposal))
            if isinstance(row.payload, dict)
        ]
    assert sum(int(card.get("exits") or 0) for card in payloads) == 1
    assert sum(int(card.get("fills") or 0) for card in payloads) == 0


def test_sector_near_miss_still_records_without_an_order(tmp_path, monkeypatch) -> None:
    """#158 stays report-only: a full sector writes a row and does not order."""
    state = _state(
        open_positions=[
            _position("SOLUSDT", "other", 100.0),
            _position("AVAXUSDT", "other", 100.0),
        ]
    )
    engine = _near_miss_engine(state, tmp_path, monkeypatch)
    decision = engine._attempt_entry(_near_miss_signal(), EQUITY, {})
    assert decision.verdict is RiskVerdict.REJECTED
    assert decision.notional == 0
    assert engine.broker.orders == []  # type: ignore[attr-defined]
    rows = _rows(tmp_path)
    assert len(rows) == 1
    assert rows[0]["reasons"] == ["sector_cap"]
    assert rows[0]["proposed_notional"] == pytest.approx(EQUITY * PAPER_LIMITS.max_position_pct)
