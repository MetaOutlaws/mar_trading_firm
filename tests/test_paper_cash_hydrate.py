"""
F02 — paper cash / event ledger survives process restart.

``build_engine`` used to construct a fresh PaperBroker at starting equity and
hydrate only SQLite open rows. Closed-trade P&L and open-entry fees vanished,
so cash / equity / exposure jumped while positions stayed. These tests replay
the review's $9,994 → $10,000 flat-book case and the open / open+closed
invariants at identical marks.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.execution.paper import PaperBroker
from core.execution.paper_cash import KIND_CAPITAL, KIND_CLOSE, KIND_OPEN, PaperCashStore
from research.costs import FRICTIONLESS, CostModel
from tests.test_execution import StubDataSource


REVIEW_COSTS = CostModel(
    taker_fee=0.001, maker_fee=0.001, slippage=0.002, include_funding=False
)
STARTING = 10_000.0


def _broker(
    prices: dict[str, float],
    cash_store: PaperCashStore,
    costs: CostModel | None = None,
) -> PaperBroker:
    return PaperBroker(
        starting_equity=STARTING,
        costs=costs or REVIEW_COSTS,
        data_source=StubDataSource(prices),
        cash_store=cash_store,
    )


def _ledger_rows(broker: PaperBroker) -> list[SimpleNamespace]:
    """SQLite-shaped rows — the only position source hydrate may use."""
    return [
        SimpleNamespace(
            symbol=snap.symbol,
            side=snap.side,
            quantity=snap.quantity,
            entry_price=snap.entry_price,
            take_profit_price=snap.take_profit,
            stop_loss_price=snap.stop_loss,
            opened_at=None,
        )
        for snap in broker.get_positions()
    ]


def _restart(
    broker: PaperBroker,
    prices: dict[str, float],
    cash_store: PaperCashStore,
) -> PaperBroker:
    """New RAM broker, same disk journal and marks, hydrate like build_engine."""
    rows = _ledger_rows(broker)
    revived = _broker(prices, cash_store, costs=broker.costs)
    # Constructor resets cash to starting equity; hydrate must undo that.
    assert revived.cash == pytest.approx(STARTING)
    revived.hydrate(rows)
    return revived


def _snapshot(broker: PaperBroker, marks: dict[str, float]) -> tuple[float, float, float]:
    """Cash / equity / exposure at the same marks used before the restart."""
    return broker.cash, broker.get_balance(), broker.exposure(marks)


@pytest.fixture
def prices() -> dict[str, float]:
    return {"BTCUSDT": 100_000.0, "ETHUSDT": 3_000.0}


@pytest.fixture
def cash_store(tmp_path) -> PaperCashStore:
    return PaperCashStore(tmp_path / "paper_cash.json")


def test_event_ledger_persists_capital_and_fills(prices, cash_store) -> None:
    """Acceptance: cash *and* the event journal hit disk, not just RAM."""
    broker = _broker(prices, cash_store)
    broker.hydrate([])
    broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    broker.close_position("BTCUSDT")

    on_disk = PaperCashStore(cash_store.path)
    kinds = [event["kind"] for event in on_disk.events()]
    assert kinds == [KIND_CAPITAL, KIND_OPEN, KIND_CLOSE]
    state = on_disk.replay()
    assert state.cash == pytest.approx(broker.cash)
    assert state.realised_pnl == pytest.approx(broker.realised_pnl)
    assert state.contributed_capital == pytest.approx(STARTING)
    assert broker.cash == pytest.approx(9_994.0, abs=0.05)


def test_flat_book_restart_keeps_cash_equity_exposure(prices, cash_store) -> None:
    """Review reproduction: $9,994 after a round trip must not snap back to $10,000."""
    broker = _broker(prices, cash_store)
    broker.hydrate([])
    broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    broker.close_position("BTCUSDT")

    before = _snapshot(broker, prices)
    assert before[0] == pytest.approx(9_994.0, abs=0.05)
    assert before[2] == pytest.approx(0.0)

    revived = _restart(broker, prices, cash_store)
    assert _snapshot(revived, prices) == pytest.approx(before)
    assert revived.get_positions() == []
    assert revived.realised_pnl == pytest.approx(broker.realised_pnl)
    assert revived.contributed_capital == pytest.approx(STARTING)


def test_open_position_restart_keeps_cash_equity_exposure(prices, cash_store) -> None:
    """Open book: entry fee stays deducted; equity/exposure use the same marks."""
    broker = _broker(prices, cash_store)
    broker.hydrate([])
    opened = broker.place_market_order("ETHUSDT", "LONG", 1.0, expected_price=3_000.0)
    assert opened.success
    broker.set_stops("ETHUSDT", take_profit=3_150.0, stop_loss=2_910.0)
    prices["ETHUSDT"] = 3_060.0

    before = _snapshot(broker, prices)
    assert before[0] < STARTING  # entry fee is still sitting on the open
    assert before[2] == pytest.approx(3_060.0)

    revived = _restart(broker, prices, cash_store)
    assert _snapshot(revived, prices) == pytest.approx(before)
    snaps = revived.get_positions()
    assert len(snaps) == 1
    assert snaps[0].symbol == "ETHUSDT"
    assert snaps[0].quantity == pytest.approx(1.0)
    assert snaps[0].entry_price == pytest.approx(opened.fill_price)
    assert snaps[0].take_profit == pytest.approx(3_150.0)
    assert snaps[0].stop_loss == pytest.approx(2_910.0)
    assert revived.realised_pnl == pytest.approx(0.0)


def test_open_and_closed_history_restart_invariant(prices, cash_store) -> None:
    """Closed loss plus a still-open fill: both legs survive restart."""
    broker = _broker(prices, cash_store)
    broker.hydrate([])
    broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    broker.close_position("BTCUSDT")
    closed_cash = broker.cash
    assert closed_cash == pytest.approx(9_994.0, abs=0.05)

    opened = broker.place_market_order("ETHUSDT", "SHORT", 1.0, expected_price=3_000.0)
    assert opened.success
    prices["ETHUSDT"] = 2_940.0

    before = _snapshot(broker, prices)
    assert before[0] == pytest.approx(closed_cash - opened.fee)
    assert before[1] != pytest.approx(STARTING)
    assert before[2] == pytest.approx(2_940.0)
    assert broker.realised_pnl != pytest.approx(0.0)

    revived = _restart(broker, prices, cash_store)
    assert _snapshot(revived, prices) == pytest.approx(before)
    assert revived.realised_pnl == pytest.approx(broker.realised_pnl)
    assert revived.total_fees == pytest.approx(broker.total_fees)
    assert [s.symbol for s in revived.get_positions()] == ["ETHUSDT"]


def test_capital_contributions_stay_separate_from_pnl(prices, cash_store) -> None:
    """Deposits are replayed as capital, not folded into realised P&L."""
    broker = _broker(prices, cash_store)
    broker.hydrate([])
    broker.contribute_capital(1_000.0)
    broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    broker.close_position("BTCUSDT")

    assert broker.contributed_capital == pytest.approx(11_000.0)
    # Both legs of cost leave cash; realised_pnl still follows today's
    # close-only formula (entry fees are F03). Restart must preserve both.
    assert broker.cash == pytest.approx(11_000.0 - 6.0, abs=0.05)
    assert broker.realised_pnl == pytest.approx(-4.998, abs=0.05)

    revived = _restart(broker, prices, cash_store)
    assert revived.contributed_capital == pytest.approx(11_000.0)
    assert revived.realised_pnl == pytest.approx(broker.realised_pnl)
    assert revived.cash == pytest.approx(broker.cash)


def test_restart_starting_equity_arg_does_not_reseed_capital(prices, cash_store) -> None:
    """A later ``--equity 20000`` must not add a second contribution."""
    broker = _broker(prices, cash_store)
    broker.hydrate([])
    broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    broker.close_position("BTCUSDT")
    cash_before = broker.cash

    revived = PaperBroker(
        starting_equity=20_000.0,
        costs=REVIEW_COSTS,
        data_source=StubDataSource(prices),
        cash_store=cash_store,
    )
    revived.hydrate([])
    assert revived.contributed_capital == pytest.approx(STARTING)
    assert revived.cash == pytest.approx(cash_before)


def test_frictionless_open_restart_is_unchanged_at_same_marks(prices, cash_store) -> None:
    """Zero-cost open book: cash stays at capital; equity follows the mark."""
    broker = _broker(prices, cash_store, costs=FRICTIONLESS)
    broker.hydrate([])
    broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    prices["BTCUSDT"] = 105_000.0

    before = _snapshot(broker, prices)
    assert before[0] == pytest.approx(STARTING)
    assert before[1] == pytest.approx(10_050.0)
    assert before[2] == pytest.approx(1_050.0)

    revived = _restart(broker, prices, cash_store)
    assert _snapshot(revived, prices) == pytest.approx(before)


def test_build_engine_replays_cash_store_then_ledger_positions(
    tmp_path, monkeypatch, firm_db
) -> None:
    """Production wiring: attach the journal and hydrate SQLite rows."""
    from core.execution import engine as engine_mod
    from core.ledger.store import Ledger

    cash_path = tmp_path / "paper_cash.json"
    monkeypatch.setattr(engine_mod, "PAPER_CASH_PATH", cash_path)

    captured: dict[str, object] = {}

    class SpyBroker:
        mode = "paper"

        def __init__(
            self,
            starting_equity: float = 10_000.0,
            costs=None,
            data_source=None,
            cash_store=None,
        ) -> None:
            captured["cash_store"] = cash_store
            captured["starting_equity"] = starting_equity

        def hydrate(self, positions) -> None:
            captured["positions"] = list(positions)

        def close(self) -> None:
            pass

    monkeypatch.setattr(engine_mod, "PaperBroker", SpyBroker)
    monkeypatch.setattr(
        engine_mod,
        "build_plan",
        lambda require_approval=False, candidates=None: engine_mod.TradingPlan(),
    )

    ledger = Ledger(mode="paper", starting_equity=STARTING)
    ledger.open_position(
        symbol="ETHUSDT",
        side="LONG",
        quantity=0.4,
        entry_price=2472.35,
        expected_entry_price=2472.35,
        take_profit=2568.77,
        stop_loss=2420.57,
        strategy="test",
        sector="other",
        signal_score=1.0,
        signal_reason="f02",
        broker_order_id="paper-f02",
    )

    engine_mod.build_engine(starting_equity=STARTING)
    store = captured["cash_store"]
    assert isinstance(store, PaperCashStore)
    assert store.path == cash_path
    positions = captured["positions"]
    assert isinstance(positions, list)
    assert len(positions) == 1
    assert positions[0].symbol == "ETHUSDT"
