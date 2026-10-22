"""Manual paper closes requested by a file in data/close_requests."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from config.settings import TradingMode
from core.db import session_scope
from core.execution.engine import TradingEngine, TradingPlan
from core.execution.paper import PaperBroker
from core.execution.paper_cash import PaperCashStore
from core.execution.paper_close_requests import (
    MANUAL_CLOSE_REASON,
    process_paper_close_requests,
)
from core.ledger.models import TradeRecord
from core.ledger.store import Ledger
from core.risk.engine import RiskEngine
from core.risk.killswitch import KillSwitch
from core.risk.limits import PAPER_LIMITS
from research.costs import CostModel

ENTRY = datetime(2026, 10, 21, tzinfo=timezone.utc)
EXIT = datetime(2026, 10, 22, tzinfo=timezone.utc)
COSTS = CostModel(
    taker_fee=0.001,
    maker_fee=0.001,
    slippage=0.001,
    include_funding=True,
    default_funding_rate=0.0001,
)


class StubPrices:
    def __init__(self, prices: dict[str, float]) -> None:
        self.prices = prices

    def latest_price(self, symbol: str) -> float | None:
        return self.prices.get(symbol)

    def close(self) -> None:
        pass


class RecordingGuard:
    """Stand-in for BookGuard. Records whether the quote ran inside the lock."""

    def __init__(self) -> None:
        self.depth = 0
        self.quote_inside = False
        self.settle_inside = False
        self.events: list[tuple[str, int]] = []

    def __enter__(self) -> "RecordingGuard":
        self.depth += 1
        self.events.append(("enter", self.depth))
        return self

    def __exit__(self, *exc: object) -> bool:
        self.events.append(("exit", self.depth))
        self.depth -= 1
        return False


@pytest.fixture
def prices() -> dict[str, float]:
    return {}


@pytest.fixture
def engine(tmp_path, monkeypatch, firm_db, prices):
    """Paper engine whose close-request directory is the test tmp dir."""
    monkeypatch.setattr(
        "core.execution.paper_close_requests.get_settings",
        lambda: SimpleNamespace(trading_mode=TradingMode.PAPER),
    )
    broker = PaperBroker(
        starting_equity=10_000.0,
        costs=COSTS,
        data_source=StubPrices(prices),
        cash_store=PaperCashStore(tmp_path / "paper_cash.json"),
        lock_cost_model=True,
    )
    ledger = Ledger(mode="paper", starting_equity=10_000.0)
    built = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=PAPER_LIMITS, kill_switch=KillSwitch(tmp_path / "kill.json")),
        ledger=ledger,
        plan=TradingPlan(),
        data_source=MagicMock(),
    )
    built.paper_close_requests_dir = tmp_path / "close_requests"
    built.paper_close_requests_dir.mkdir()
    monkeypatch.setattr(built, "refresh_scan_plan", lambda: False)
    return built


def _freeze(broker: PaperBroker, moment: datetime) -> None:
    broker._now = lambda now=moment: now


def _open(
    engine: TradingEngine,
    symbol: str,
    *,
    qty: float,
    quote: float,
    stop: float | None = None,
) -> int:
    engine.broker._data.prices[symbol] = quote
    result = engine.broker.place_market_order(symbol, "LONG", qty, expected_price=quote)
    assert result.success, result.error
    if stop is not None:
        assert engine.broker.set_stops(symbol, take_profit=None, stop_loss=stop)
    return engine.ledger.open_position(
        symbol=symbol,
        side="LONG",
        quantity=float(result.filled_quantity),
        entry_price=float(result.fill_price),
        expected_entry_price=quote,
        take_profit=None,
        stop_loss=stop,
        strategy="manual-close-test",
        sector="other",
        signal_score=1.0,
        signal_reason="seed",
        broker_order_id=result.order_id or "paper",
        entry_fee=float(result.fee or 0.0),
    )


def _write(engine: TradingEngine, name: str, body: dict) -> Path:
    path = engine.paper_close_requests_dir / name
    path.write_text(json.dumps(body), encoding="utf-8")
    return path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _trades(engine: TradingEngine) -> list[TradeRecord]:
    with session_scope() as session:
        rows = list(
            session.scalars(
                select(TradeRecord)
                .where(TradeRecord.mode == engine.ledger.mode)
                .order_by(TradeRecord.id)
            )
        )
        for row in rows:
            session.expunge(row)
        return rows


def _close_events(engine: TradingEngine) -> list[dict]:
    return [event for event in engine.broker._cash_store.events() if event.get("kind") == "close"]


def _flat(engine: TradingEngine) -> None:
    cash_gap = (engine.broker.cash - engine.broker._contributed_capital) - engine.broker.realised_pnl
    assert abs(cash_gap) < 1e-6


def test_close_one_position(engine: TradingEngine) -> None:
    pid = _open(engine, "XRPUSDT", qty=10, quote=1.0)
    engine.broker._data.prices["XRPUSDT"] = 1.2
    path = _write(engine, "one.json", {"request_id": "close-xrp", "symbols": ["XRPUSDT"]})

    assert engine.supervise_exits() == 1

    done = _read(Path(str(path) + ".done"))
    assert not path.exists()
    assert done["request_id"] == "close-xrp"
    item = done["items"][0]
    assert item["status"] == "closed"
    assert item["symbol"] == "XRPUSDT"
    assert item["position_id"] == pid
    trades = _trades(engine)
    assert len(trades) == 1
    assert trades[0].exit_reason == MANUAL_CLOSE_REASON
    assert trades[0].position_id == pid
    assert item["pnl"] == pytest.approx(trades[0].net_pnl)
    assert item["fees"] == pytest.approx(trades[0].fees)
    assert item["funding"] == pytest.approx(trades[0].funding)
    assert engine.ledger.find_open_position("XRPUSDT") is None
    assert "XRPUSDT" not in engine.broker._positions
    assert len(_close_events(engine)) == 1
    _flat(engine)


def test_close_several_by_symbol_and_by_id(engine: TradingEngine) -> None:
    xrp = _open(engine, "XRPUSDT", qty=10, quote=1.0)
    chz = _open(engine, "CHZUSDT", qty=10, quote=1.0)
    jup = _open(engine, "JUPUSDT", qty=10, quote=1.0)
    for symbol in ("XRPUSDT", "CHZUSDT", "JUPUSDT"):
        engine.broker._data.prices[symbol] = 1.15
    path = _write(
        engine,
        "batch.json",
        {
            "request_id": "manual-close-xrp-chz-jup",
            "symbols": ["XRPUSDT", "CHZUSDT"],
            "position_ids": [jup, xrp],
        },
    )

    assert engine.supervise_exits() == 3

    items = _read(Path(str(path) + ".done"))["items"]
    by_key = [(item["symbol"], item["position_id"], item["status"]) for item in items]
    assert by_key == [
        ("XRPUSDT", xrp, "closed"),
        ("CHZUSDT", chz, "closed"),
        ("JUPUSDT", jup, "closed"),
        ("XRPUSDT", xrp, "already_closed"),
    ]
    trades = _trades(engine)
    assert sorted(trade.symbol for trade in trades) == ["CHZUSDT", "JUPUSDT", "XRPUSDT"]
    assert {trade.exit_reason for trade in trades} == {MANUAL_CLOSE_REASON}
    assert len(_close_events(engine)) == 3
    _flat(engine)


def test_idempotent_rerun_already_closed_and_unknown(engine: TradingEngine, caplog) -> None:
    _open(engine, "XRPUSDT", qty=10, quote=1.0)
    engine.broker._data.prices["XRPUSDT"] = 0.9
    first = _write(engine, "once.json", {"request_id": "once", "symbols": ["XRPUSDT"]})

    assert engine.supervise_exits() == 1
    assert engine.supervise_exits() == 0
    assert not first.exists()
    assert len(_trades(engine)) == 1
    assert len(list(engine.paper_close_requests_dir.glob("*.json"))) == 0

    caplog.set_level(logging.INFO)
    again = _write(
        engine,
        "again.json",
        {
            "request_id": "once-again",
            "symbols": ["XRPUSDT", "NOTEXISTUSDT"],
            "position_ids": [999_999],
        },
    )
    assert engine.supervise_exits() == 0

    items = _read(Path(str(again) + ".done"))["items"]
    assert [item["status"] for item in items] == ["already_closed", "not_found", "not_found"]
    assert items[1]["symbol"] == "NOTEXISTUSDT"
    assert items[2]["position_id"] == 999_999
    assert len(_trades(engine)) == 1
    assert "already_closed" in caplog.text
    assert "not_found" in caplog.text
    _flat(engine)


def test_malformed_file_is_archived_and_the_loop_continues(engine: TradingEngine) -> None:
    _open(engine, "XRPUSDT", qty=10, quote=1.0)
    eth = _open(engine, "ETHUSDT", qty=0.2, quote=100.0, stop=97.0)
    engine.broker._data.prices["XRPUSDT"] = 1.1
    engine.broker._data.prices["ETHUSDT"] = 96.0
    bad_json = engine.paper_close_requests_dir / "bad-json.json"
    bad_json.write_text("{not json", encoding="utf-8")
    bad_shape = _write(engine, "bad-shape.json", {"symbols": ["XRPUSDT"]})
    good = _write(engine, "good.json", {"request_id": "good", "symbols": ["XRPUSDT"]})

    assert engine.supervise_exits() == 2

    json_error = _read(Path(str(bad_json) + ".error"))
    shape_error = _read(Path(str(bad_shape) + ".error"))
    assert not bad_json.exists()
    assert not bad_shape.exists()
    assert "malformed JSON" in json_error["error"]
    assert "request_id" in shape_error["error"]
    assert _read(Path(str(good) + ".done"))["items"][0]["status"] == "closed"
    trades = _trades(engine)
    assert {trade.symbol: trade.exit_reason for trade in trades} == {
        "XRPUSDT": MANUAL_CLOSE_REASON,
        "ETHUSDT": "stop_loss",
    }
    assert eth
    assert len(_close_events(engine)) == 2
    _flat(engine)


def test_stop_and_manual_request_in_one_cycle_close_once(engine: TradingEngine) -> None:
    _open(engine, "XRPUSDT", qty=10, quote=1.0, stop=0.97)
    engine.broker._data.prices["XRPUSDT"] = 0.90
    path = _write(engine, "race.json", {"request_id": "race", "symbols": ["XRPUSDT"]})

    assert engine.supervise_exits() == 1

    item = _read(Path(str(path) + ".done"))["items"][0]
    assert item["status"] == "already_closed"
    trades = _trades(engine)
    assert len(trades) == 1
    assert trades[0].exit_reason == "stop_loss"
    assert len(_close_events(engine)) == 1
    assert engine.ledger.find_open_position("XRPUSDT") is None
    _flat(engine)


def test_pnl_fees_funding_and_cash_match_a_direct_settle(engine: TradingEngine) -> None:
    _freeze(engine.broker, ENTRY)
    _open(engine, "XRPUSDT", qty=10, quote=1.0)
    _freeze(engine.broker, EXIT)
    engine.broker._data.prices["XRPUSDT"] = 1.25
    cash_before = engine.broker.cash
    fees_before = engine.broker.total_fees
    funding_before = engine.broker.total_funding
    path = _write(engine, "xrp.json", {"request_id": "acct-xrp", "symbols": ["XRPUSDT"]})

    assert engine.supervise_exits() == 1
    manual = _trades(engine)[0]
    manual_cash = engine.broker.cash - cash_before
    manual_fees = engine.broker.total_fees - fees_before
    manual_funding_total = engine.broker.total_funding - funding_before
    done = _read(Path(str(path) + ".done"))["items"][0]

    _freeze(engine.broker, ENTRY)
    _open(engine, "CHZUSDT", qty=10, quote=1.0)
    _freeze(engine.broker, EXIT)
    engine.broker._data.prices["CHZUSDT"] = 1.25
    cash_before = engine.broker.cash
    fees_before = engine.broker.total_fees
    funding_before = engine.broker.total_funding
    assert (
        engine._settle_paper_exit(
            "CHZUSDT",
            MANUAL_CLOSE_REASON,
            at_mark=False,
            mark_price=1.25,
        )
        == 1
    )
    direct = _trades(engine)[1]

    assert manual.funding > 0
    assert manual.fees > 0
    assert manual.net_pnl == pytest.approx(direct.net_pnl)
    assert manual.gross_pnl == pytest.approx(direct.gross_pnl)
    assert manual.fees == pytest.approx(direct.fees)
    assert manual.entry_fees == pytest.approx(direct.entry_fees)
    assert manual.exit_fees == pytest.approx(direct.exit_fees)
    assert manual.funding == pytest.approx(direct.funding)
    assert manual.exit_reason == direct.exit_reason == MANUAL_CLOSE_REASON
    assert manual_cash == pytest.approx(engine.broker.cash - cash_before)
    assert manual_fees == pytest.approx(engine.broker.total_fees - fees_before)
    assert manual_funding_total == pytest.approx(engine.broker.total_funding - funding_before)
    assert done["pnl"] == pytest.approx(direct.net_pnl)
    assert done["fees"] == pytest.approx(direct.fees)
    assert done["funding"] == pytest.approx(direct.funding)
    _flat(engine)


def test_manual_close_updates_the_loss_streak(engine: TradingEngine) -> None:
    assert engine.ledger.consecutive_losses() == 0

    _open(engine, "XRPUSDT", qty=10, quote=1.0)
    engine.broker._data.prices["XRPUSDT"] = 0.4
    _write(engine, "loss.json", {"request_id": "loss", "symbols": ["XRPUSDT"]})
    assert engine.supervise_exits() == 1
    loss = _trades(engine)[0]
    assert loss.exit_reason == MANUAL_CLOSE_REASON
    assert loss.net_pnl < 0
    assert engine.ledger.consecutive_losses() == 1

    _open(engine, "CHZUSDT", qty=10, quote=1.0)
    engine.broker._data.prices["CHZUSDT"] = 1.8
    _write(engine, "win.json", {"request_id": "win", "symbols": ["CHZUSDT"]})
    assert engine.supervise_exits() == 1
    win = _trades(engine)[1]
    assert win.exit_reason == MANUAL_CLOSE_REASON
    assert win.net_pnl > 0
    assert engine.ledger.consecutive_losses() == 0


def test_quote_is_outside_book_guard_and_settle_is_inside(engine: TradingEngine) -> None:
    """The caller does not hold the lock across the quote or the funding read.

    ``_settle_paper_exit`` is entered with the lock released, then takes it
    for the ledger commit. One request closes each named position once.
    """
    guard = RecordingGuard()
    engine.book_guard = guard
    _open(engine, "XRPUSDT", qty=10, quote=1.0)
    _open(engine, "CHZUSDT", qty=10, quote=1.0)
    engine.broker._data.prices["XRPUSDT"] = 1.2
    engine.broker._data.prices["CHZUSDT"] = 1.2
    original_price = engine.broker.get_price
    original_settle = engine._settle_paper_exit

    def get_price(symbol: str, timeout: float | None = None) -> float | None:
        del timeout
        if guard.depth:
            guard.quote_inside = True
        guard.events.append(("quote", guard.depth))
        return original_price(symbol)

    def settle(*args, **kwargs):
        guard.events.append(("settle", guard.depth))
        assert guard.depth == 0
        return original_settle(*args, **kwargs)

    engine.broker.get_price = get_price
    engine._settle_paper_exit = settle
    _write(
        engine,
        "guard.json",
        {"request_id": "guard", "symbols": ["XRPUSDT", "CHZUSDT"]},
    )

    assert engine.supervise_exits() == 2
    assert guard.quote_inside is False
    quotes = [depth for kind, depth in guard.events if kind == "quote"]
    settles = [depth for kind, depth in guard.events if kind == "settle"]
    assert quotes
    assert all(depth == 0 for depth in quotes)
    assert settles == [0, 0]
    commits = [depth for kind, depth in guard.events if kind == "enter"]
    assert len(commits) >= 2
    assert len(_trades(engine)) == 2


@pytest.mark.parametrize("mode", [TradingMode.TESTNET, TradingMode.LIVE])
def test_live_and_testnet_ignore_close_requests(engine: TradingEngine, monkeypatch, mode) -> None:
    monkeypatch.setattr(
        "core.execution.paper_close_requests.get_settings",
        lambda: SimpleNamespace(trading_mode=mode),
    )
    _open(engine, "XRPUSDT", qty=10, quote=1.0)
    engine.broker._data.prices["XRPUSDT"] = 1.3
    path = _write(engine, "ignored.json", {"request_id": "ignored", "symbols": ["XRPUSDT"]})

    assert engine.supervise_exits() == 0

    assert path.is_file()
    assert not Path(str(path) + ".done").exists()
    assert engine.ledger.find_open_position("XRPUSDT") is not None
    assert "XRPUSDT" in engine.broker._positions
    assert _trades(engine) == []


def test_non_paper_broker_does_not_read_the_directory(engine: TradingEngine) -> None:
    path = _write(engine, "skip.json", {"request_id": "skip", "symbols": ["XRPUSDT"]})
    engine.broker = SimpleNamespace()

    assert process_paper_close_requests(engine) == 0

    assert path.is_file()
    assert not Path(str(path) + ".done").exists()
