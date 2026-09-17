"""
F03 — entry fees, funding parity, cash ↔ trade P&L.

The paper broker already deducted the entry taker fee from cash. The ledger
wrote TradeRecord only on close and stored the *exit* fee as ``fees``, so
closed-book cash could not equal sum(net_pnl). Paper also skipped 8h funding
that research charges through CostModel.funding_cost.

These tests pin the repair: both legs on the position/ledger path, paper
funding from the same versioned CostModel as research, and a flat book where
cash - starting == realised_pnl == TradeRecord.net_pnl.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.data.funding import FundingHistory, synthetic_funding
from core.execution.paper import PaperBroker
from core.ledger.store import Ledger
from research.costs import COST_MODEL_VERSION, DEFAULT_COSTS, CostModel
from tests.test_execution import StubDataSource

STARTING = 10_000.0
ENTRY = datetime(2024, 1, 1, tzinfo=timezone.utc)
EXIT = datetime(2024, 1, 2, tzinfo=timezone.utc)  # 24h → 3 settlements


def _costs(**overrides) -> CostModel:
    defaults = dict(
        taker_fee=0.001, maker_fee=0.001, slippage=0.002, include_funding=True
    )
    defaults.update(overrides)
    return CostModel(**defaults)


def _broker(prices: dict[str, float], costs: CostModel | None = None) -> PaperBroker:
    return PaperBroker(
        starting_equity=STARTING,
        costs=costs or _costs(),
        data_source=StubDataSource(prices),
    )


def _freeze(broker: PaperBroker, moment: datetime) -> None:
    """Replace the broker clock so funding windows are deterministic."""
    broker._now = lambda: moment  # type: ignore[method-assign]


def _open_ledger(
    ledger: Ledger,
    opened,
    *,
    side: str = "LONG",
    strategy: str = "f03",
) -> int:
    return ledger.open_position(
        symbol=opened.symbol,
        side=side,
        quantity=opened.filled_quantity,
        entry_price=opened.fill_price,
        expected_entry_price=opened.expected_price,
        take_profit=None,
        stop_loss=None,
        strategy=strategy,
        sector="majors",
        signal_score=1.0,
        signal_reason="f03",
        broker_order_id=opened.order_id,
        entry_fee=opened.fee,
    )


@pytest.fixture
def prices() -> dict[str, float]:
    return {"BTCUSDT": 100_000.0, "ETHUSDT": 3_000.0, "DOGEUSDT": 0.35}


def test_cost_model_snapshot_is_versioned_and_per_symbol() -> None:
    """Comparison runs reuse the existing CostModel, not a second schedule."""
    base = DEFAULT_COSTS.snapshot()
    assert base["version"] == COST_MODEL_VERSION
    assert base["taker_fee"] == DEFAULT_COSTS.taker_fee
    assert base["funding_included"] is True
    assert "default_funding_rate" in base

    btc = DEFAULT_COSTS.snapshot("BTCUSDT")
    doge = DEFAULT_COSTS.snapshot("DOGEUSDT")
    assert btc["slippage"] == pytest.approx(DEFAULT_COSTS.slippage)  # majors ×1
    assert doge["slippage"] == pytest.approx(DEFAULT_COSTS.slippage * 3.0)  # memes
    assert btc["version"] == doge["version"] == COST_MODEL_VERSION


def test_paper_uses_for_symbol_slippage(prices) -> None:
    """Paper fills must use the same sector multiplier research validation uses."""
    broker = _broker(prices, costs=_costs(include_funding=False))
    btc = broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    doge = broker.place_market_order("DOGEUSDT", "LONG", 20.0, expected_price=0.35)
    assert btc.success and doge.success
    # Base slippage 20 bps; BTC majors stay 20, DOGE memes are 60.
    assert btc.fill_price == pytest.approx(100_200.0)
    assert doge.fill_price == pytest.approx(0.35 * 1.006)


def test_open_stores_entry_fee_on_the_position(prices) -> None:
    broker = _broker(prices, costs=_costs(include_funding=False))
    opened = broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    assert opened.success
    pos = broker._positions["BTCUSDT"]
    assert pos.entry_fee == pytest.approx(opened.fee)
    assert opened.fee > 0
    assert broker.cash == pytest.approx(STARTING - opened.fee)


def test_paper_funding_matches_research_cost_model(prices) -> None:
    """Same CostModel, window, notional and history → same funding number."""
    costs = _costs()
    broker = _broker(prices, costs=costs)
    _freeze(broker, ENTRY)
    opened = broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    assert opened.success

    history = FundingHistory(
        "BTCUSDT", synthetic_funding(ENTRY, EXIT, rate=0.0002)
    )
    broker.set_funding_history("BTCUSDT", history)
    _freeze(broker, EXIT)
    closed = broker.close_position("BTCUSDT")

    expected = costs.for_symbol("BTCUSDT").funding_cost(
        "LONG", ENTRY, EXIT, opened.fill_price * opened.filled_quantity, history
    )
    assert closed.funding == pytest.approx(expected)
    assert expected > 0  # long pays a positive rate


def test_shorts_receive_positive_funding(prices) -> None:
    costs = _costs()
    broker = _broker(prices, costs=costs)
    _freeze(broker, ENTRY)
    opened = broker.place_market_order("ETHUSDT", "SHORT", 1.0, expected_price=3_000.0)
    _freeze(broker, EXIT)
    closed = broker.close_position("ETHUSDT")

    expected = costs.for_symbol("ETHUSDT").funding_cost(
        "SHORT", ENTRY, EXIT, opened.fill_price * opened.filled_quantity
    )
    assert closed.funding == pytest.approx(expected)
    assert expected < 0  # short receives a positive default rate


def test_funding_disabled_stays_zero(prices) -> None:
    broker = _broker(prices, costs=_costs(include_funding=False))
    _freeze(broker, ENTRY)
    broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    _freeze(broker, EXIT)
    closed = broker.close_position("BTCUSDT")
    assert closed.funding == pytest.approx(0.0)


def test_accrue_debits_cash_before_close(prices) -> None:
    """Intra-hold equity should move as settlements elapse, not only at exit."""
    broker = _broker(prices, costs=_costs())
    _freeze(broker, ENTRY)
    opened = broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    cash_after_entry = broker.cash
    _freeze(broker, EXIT)
    delta = broker.accrue_funding()
    assert delta < 0
    assert broker.cash == pytest.approx(cash_after_entry + delta)
    pos = broker._positions["BTCUSDT"]
    expected = broker.costs_for("BTCUSDT").funding_cost(
        "LONG", ENTRY, EXIT, pos.notional
    )
    assert pos.funding_accrued == pytest.approx(expected)
    # Close must not double-charge funding already sitting in cash.
    closed = broker.close_position("BTCUSDT")
    assert closed.funding == pytest.approx(expected)
    assert broker.cash == pytest.approx(
        STARTING - opened.fee + (closed.fill_price - opened.fill_price) * opened.filled_quantity
        - closed.fee - expected
    )


def test_ledger_records_entry_and_exit_fees(firm_db, prices) -> None:
    broker = _broker(prices, costs=_costs(include_funding=False))
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    opened = broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    position_id = _open_ledger(ledger, opened)
    row = ledger.find_open_position("BTCUSDT")
    assert row is not None
    assert row.entry_fee == pytest.approx(opened.fee)

    closed = broker.close_position("BTCUSDT")
    trade = ledger.close_position(
        position_id=position_id,
        exit_price=closed.fill_price,
        expected_exit_price=100_000.0,
        exit_reason="manual",
        entry_fees=opened.fee,
        exit_fees=closed.fee,
        funding=closed.funding,
    )
    assert trade is not None
    assert trade.entry_fees == pytest.approx(opened.fee)
    assert trade.exit_fees == pytest.approx(closed.fee)
    assert trade.fees == pytest.approx(opened.fee + closed.fee)
    assert opened.fee > 0 and closed.fee > 0
    assert trade.fees > closed.fee  # must not be the exit leg alone


def test_cash_reconciles_to_trade_pnl_with_fees_and_funding(firm_db, prices) -> None:
    """Acceptance: after a flat book, cash - starting == TradeRecord.net_pnl."""
    costs = _costs()
    broker = _broker(prices, costs=costs)
    ledger = Ledger(mode="paper", starting_equity=STARTING)

    _freeze(broker, ENTRY)
    opened = broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    position_id = _open_ledger(ledger, opened)

    history = FundingHistory("BTCUSDT", synthetic_funding(ENTRY, EXIT, rate=0.0002))
    broker.set_funding_history("BTCUSDT", history)
    _freeze(broker, EXIT)
    closed = broker.close_position("BTCUSDT")

    trade = ledger.close_position(
        position_id=position_id,
        exit_price=closed.fill_price,
        expected_exit_price=100_000.0,
        exit_reason="timeout",
        entry_fees=opened.fee,
        exit_fees=closed.fee,
        funding=closed.funding,
    )
    assert trade is not None
    assert broker.get_positions() == []

    expected_funding = costs.for_symbol("BTCUSDT").funding_cost(
        "LONG", ENTRY, EXIT, opened.fill_price * opened.filled_quantity, history
    )
    expected_fees = costs.for_symbol("BTCUSDT").round_trip_fees(
        opened.fill_price * opened.filled_quantity,
        closed.fill_price * closed.filled_quantity,
    )
    assert trade.funding == pytest.approx(expected_funding)
    assert trade.fees == pytest.approx(expected_fees)
    assert trade.net_pnl == pytest.approx(
        trade.gross_pnl - trade.fees - trade.funding
    )
    assert broker.realised_pnl == pytest.approx(trade.net_pnl)
    assert broker.cash - STARTING == pytest.approx(trade.net_pnl)
    assert broker.total_fees == pytest.approx(trade.fees)
    assert broker.total_funding == pytest.approx(trade.funding)


def test_two_round_trips_cash_equals_sum_of_net_pnl(firm_db, prices) -> None:
    """A second close must not drop the first trade's entry fee from cash."""
    broker = _broker(prices, costs=_costs(include_funding=False))
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    nets: list[float] = []

    for _ in range(2):
        opened = broker.place_market_order(
            "BTCUSDT", "LONG", 0.01, expected_price=100_000.0
        )
        pid = _open_ledger(ledger, opened)
        closed = broker.close_position("BTCUSDT")
        trade = ledger.close_position(
            position_id=pid,
            exit_price=closed.fill_price,
            expected_exit_price=100_000.0,
            exit_reason="manual",
            entry_fees=opened.fee,
            exit_fees=closed.fee,
            funding=closed.funding,
        )
        assert trade is not None
        nets.append(trade.net_pnl)

    assert broker.cash - STARTING == pytest.approx(sum(nets))
    assert broker.realised_pnl == pytest.approx(sum(nets))
    assert ledger.performance()["net_pnl"] == pytest.approx(round(sum(nets), 2))


def test_sqlite_migration_adds_fee_columns(tmp_path, monkeypatch) -> None:
    """Existing paper DBs were created before F03; create_all will not ALTER them."""
    import sqlite3

    from config.settings import get_settings
    from core.db import _migrate_sqlite_columns, get_engine, get_session_factory

    db_path = tmp_path / "pre_f03.db"
    raw = sqlite3.connect(db_path)
    raw.execute("CREATE TABLE positions (id INTEGER PRIMARY KEY, symbol VARCHAR(32))")
    raw.execute(
        "CREATE TABLE trades (id INTEGER PRIMARY KEY, symbol VARCHAR(32), fees FLOAT)"
    )
    raw.commit()
    raw.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    try:
        _migrate_sqlite_columns()
        raw = sqlite3.connect(db_path)
        pos_cols = {row[1] for row in raw.execute("PRAGMA table_info(positions)")}
        trade_cols = {row[1] for row in raw.execute("PRAGMA table_info(trades)")}
        raw.close()
    finally:
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        get_settings.cache_clear()

    assert "entry_fee" in pos_cols
    assert "entry_fees" in trade_cols
    assert "exit_fees" in trade_cols


def test_engine_close_path_passes_both_fee_legs(firm_db, prices) -> None:
    """Mirror TradingEngine._manage_open_positions kwargs without a full cycle."""
    broker = _broker(prices, costs=_costs(include_funding=False))
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    opened = broker.place_market_order("ETHUSDT", "LONG", 1.0, expected_price=3_000.0)
    pid = _open_ledger(ledger, opened, side="LONG")
    closed = broker.close_position("ETHUSDT")
    position = ledger.find_open_position("ETHUSDT")
    assert position is not None
    trade = ledger.close_position(
        position_id=position.id,
        exit_price=closed.fill_price,
        expected_exit_price=position.take_profit_price or closed.fill_price,
        exit_reason="stop_loss",
        entry_fees=float(position.entry_fee or 0.0),
        exit_fees=closed.fee or 0.0,
        funding=float(closed.funding or 0.0),
    )
    assert trade is not None
    assert pid == position.id
    assert trade.entry_fees == pytest.approx(opened.fee)
    assert trade.exit_fees == pytest.approx(closed.fee)
    assert broker.cash - STARTING == pytest.approx(trade.net_pnl)


def test_funding_and_entry_fee_survive_cash_journal_restart(tmp_path, prices) -> None:
    """F02 journal + F03 funding: restart at the same clock does not double-charge."""
    from core.execution.paper_cash import KIND_FUNDING, KIND_OPEN, PaperCashStore

    store = PaperCashStore(tmp_path / "paper_cash.json")
    costs = _costs()
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=costs,
        data_source=StubDataSource(prices),
        cash_store=store,
    )
    broker.hydrate([])
    _freeze(broker, ENTRY)
    opened = broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    assert opened.success
    _freeze(broker, EXIT)
    delta = broker.accrue_funding()
    assert delta < 0
    cash_before = broker.cash
    accrued = broker._positions["BTCUSDT"].funding_accrued
    kinds = [event["kind"] for event in store.events()]
    assert KIND_OPEN in kinds
    assert KIND_FUNDING in kinds

    rows = [
        SimpleNamespace(
            symbol="BTCUSDT",
            side="LONG",
            quantity=opened.filled_quantity,
            entry_price=opened.fill_price,
            take_profit_price=None,
            stop_loss_price=None,
            opened_at=ENTRY,
            entry_fee=opened.fee,
        )
    ]
    revived = PaperBroker(
        starting_equity=STARTING,
        costs=costs,
        data_source=StubDataSource(prices),
        cash_store=store,
    )
    _freeze(revived, EXIT)
    revived.hydrate(rows)
    assert revived.cash == pytest.approx(cash_before)
    assert revived._positions["BTCUSDT"].entry_fee == pytest.approx(opened.fee)
    assert revived._positions["BTCUSDT"].funding_accrued == pytest.approx(accrued)
    # Same clock: a second accrue must not take funding twice.
    assert revived.accrue_funding() == pytest.approx(0.0)
    closed = revived.close_position("BTCUSDT")
    assert closed.funding == pytest.approx(accrued)
    assert revived.cash - STARTING == pytest.approx(revived.realised_pnl)
