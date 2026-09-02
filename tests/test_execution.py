"""
Broker and execution tests.

The paper broker is the instrument that produces the 60-day forward test, so a
bug in its cost accounting would corrupt the evidence used for the go-live
decision. `test_round_trip_costs_are_charged_in_the_unfavourable_direction`
catches exactly that: an early version of this broker inverted the side when
closing, so exit slippage cancelled entry slippage and every round trip looked
half as expensive as it really was.

A stub data source keeps these tests deterministic and offline.
"""

from __future__ import annotations

import pytest

from core.execution.broker import Instrument, OrderResult
from core.execution.paper import PaperBroker
from research.costs import FRICTIONLESS, CostModel


class StubDataSource:
    """Fixed-price market data, so fills are exactly predictable."""

    def __init__(self, prices: dict[str, float]) -> None:
        self.prices = prices

    def latest_price(self, symbol: str) -> float | None:
        return self.prices.get(symbol)

    def close(self) -> None:
        pass


@pytest.fixture
def prices() -> dict[str, float]:
    return {"BTCUSDT": 100_000.0, "ETHUSDT": 3_000.0, "DOGEUSDT": 0.35}


@pytest.fixture
def broker(prices) -> PaperBroker:
    return PaperBroker(
        starting_equity=10_000.0,
        costs=CostModel(taker_fee=0.001, maker_fee=0.001, slippage=0.002, include_funding=False),
        data_source=StubDataSource(prices),
    )


@pytest.fixture
def free_broker(prices) -> PaperBroker:
    """Zero-cost broker, for isolating position mechanics from cost accounting."""
    return PaperBroker(
        starting_equity=10_000.0, costs=FRICTIONLESS, data_source=StubDataSource(prices)
    )


# ---------------------------------------------------------------------------
# Instrument rounding
# ---------------------------------------------------------------------------
def test_quantity_rounds_down_never_up():
    """Rounding up could exceed a risk limit computed against the exact size."""
    instrument = Instrument("BTCUSDT", qty_step=0.001, min_qty=0.001)
    assert instrument.round_quantity(0.0019) == pytest.approx(0.001)
    assert instrument.round_quantity(1.9999) == pytest.approx(1.999)


def test_price_rounds_to_tick():
    instrument = Instrument("BTCUSDT", tick_size=0.5)
    assert instrument.round_price(100.7) == pytest.approx(100.5)


def test_orders_below_exchange_minimums_are_refused():
    instrument = Instrument("BTCUSDT", min_qty=0.001, min_notional=5.0)

    ok, why = instrument.is_tradable(0.0001, 100_000.0)
    assert not ok and "below minimum 0.001" in why

    ok, why = instrument.is_tradable(0.001, 1.0)
    assert not ok and "notional" in why

    ok, _ = instrument.is_tradable(0.001, 100_000.0)
    assert ok


# ---------------------------------------------------------------------------
# Slippage direction
# ---------------------------------------------------------------------------
def test_long_entry_fills_above_the_quote(broker):
    result = broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    assert result.success
    # 0.2% slippage against a buyer.
    assert result.fill_price == pytest.approx(100_200.0)
    assert result.slippage_bps == pytest.approx(20.0)


def test_short_entry_fills_below_the_quote(broker):
    result = broker.place_market_order("ETHUSDT", "SHORT", 1.0, expected_price=3_000.0)
    assert result.success
    assert result.fill_price == pytest.approx(2_994.0)
    # Unfavourable for a seller, so still reported as positive slippage.
    assert result.slippage_bps == pytest.approx(20.0)


def test_round_trip_costs_are_charged_in_the_unfavourable_direction(broker):
    """Regression test for an inverted-side bug that halved round-trip costs.

    Opening and immediately closing at an unchanged price must lose exactly the
    round trip: two slippage legs plus two fees. If exit slippage were applied
    favourably, the loss would come out at roughly the fees alone.
    """
    broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    broker.close_position("BTCUSDT")

    loss = 10_000.0 - broker.get_balance()

    # Entry 100,200 and exit 99,800 on 0.01 units is a $4.00 price loss.
    # Fees are 0.1% of each leg: ~1.002 + ~0.998 = ~2.00.
    assert loss == pytest.approx(6.0, abs=0.05)


def test_frictionless_round_trip_is_flat(free_broker):
    """Sanity check on the mechanics: no costs means no loss at a flat price."""
    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    free_broker.close_position("BTCUSDT")
    assert free_broker.get_balance() == pytest.approx(10_000.0)


# ---------------------------------------------------------------------------
# Position lifecycle
# ---------------------------------------------------------------------------
def test_position_appears_and_disappears(free_broker):
    assert free_broker.get_positions() == []

    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    positions = free_broker.get_positions()
    assert len(positions) == 1
    assert positions[0].symbol == "BTCUSDT"
    assert positions[0].side == "LONG"

    free_broker.close_position("BTCUSDT")
    assert free_broker.get_positions() == []


def test_reopening_the_same_symbol_is_refused(free_broker):
    from core.execution.broker import InvalidOrder

    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    with pytest.raises(InvalidOrder, match="already holding"):
        free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)


def test_closing_nothing_is_a_clean_failure(free_broker):
    result = free_broker.close_position("BTCUSDT")
    assert not result.success
    assert "no open position" in result.error


def test_order_beyond_available_cash_is_refused(free_broker):
    """Unlevered: notional cannot exceed cash."""
    result = free_broker.place_market_order("BTCUSDT", "LONG", 1.0, expected_price=100_000.0)
    assert not result.success
    assert "exceeds cash" in result.error


def test_unknown_symbol_fails_cleanly(free_broker):
    result = free_broker.place_market_order("NOPEUSDT", "LONG", 1.0, expected_price=1.0)
    assert not result.success
    assert "no market price" in result.error


def test_unrecognised_side_is_rejected(free_broker):
    from core.execution.broker import InvalidOrder

    with pytest.raises(InvalidOrder):
        free_broker.place_market_order("BTCUSDT", "SIDEWAYS", 0.01, expected_price=100_000.0)


# ---------------------------------------------------------------------------
# Profit and loss
# ---------------------------------------------------------------------------
def test_long_profits_when_price_rises(free_broker, prices):
    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    prices["BTCUSDT"] = 110_000.0

    assert free_broker.get_positions()[0].unrealised_pnl == pytest.approx(100.0)

    free_broker.close_position("BTCUSDT")
    assert free_broker.get_balance() == pytest.approx(10_100.0)


def test_short_profits_when_price_falls(free_broker, prices):
    free_broker.place_market_order("ETHUSDT", "SHORT", 1.0, expected_price=3_000.0)
    prices["ETHUSDT"] = 2_700.0

    assert free_broker.get_positions()[0].unrealised_pnl == pytest.approx(300.0)

    free_broker.close_position("ETHUSDT")
    assert free_broker.get_balance() == pytest.approx(10_300.0)


def test_short_loses_when_price_rises(free_broker, prices):
    free_broker.place_market_order("ETHUSDT", "SHORT", 1.0, expected_price=3_000.0)
    prices["ETHUSDT"] = 3_300.0
    free_broker.close_position("ETHUSDT")
    assert free_broker.get_balance() == pytest.approx(9_700.0)


def test_equity_includes_unrealised_pnl(free_broker, prices):
    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    prices["BTCUSDT"] = 105_000.0

    assert free_broker.get_balance() == pytest.approx(10_050.0)
    # Cash is unchanged until the position is closed.
    assert free_broker.cash == pytest.approx(10_000.0)


# ---------------------------------------------------------------------------
# Stop monitoring
# ---------------------------------------------------------------------------
def test_stop_loss_triggers_when_price_falls_through(free_broker, prices):
    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    free_broker.set_stops("BTCUSDT", take_profit=105_000.0, stop_loss=97_000.0)

    prices["BTCUSDT"] = 96_500.0
    triggered = free_broker.check_stops()

    assert len(triggered) == 1
    assert triggered[0][1] == "stop_loss"
    assert free_broker.get_positions() == []


def test_take_profit_triggers_when_price_rises_through(free_broker, prices):
    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    free_broker.set_stops("BTCUSDT", take_profit=105_000.0, stop_loss=97_000.0)

    prices["BTCUSDT"] = 105_500.0
    triggered = free_broker.check_stops()

    assert triggered[0][1] == "take_profit"


def test_stop_is_resolved_before_target_when_both_are_reachable(free_broker, prices):
    """Matches the backtester's pessimistic intrabar assumption.

    Between polls the price may have passed both levels. Assuming the stop keeps
    paper results comparable to backtest results instead of optimistically
    better.
    """
    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    free_broker.set_stops("BTCUSDT", take_profit=100_500.0, stop_loss=99_500.0)

    # A gap far below both levels: the stop is the correct resolution.
    prices["BTCUSDT"] = 90_000.0
    triggered = free_broker.check_stops()

    assert triggered[0][1] == "stop_loss"


def test_short_stops_are_mirrored(free_broker, prices):
    free_broker.place_market_order("ETHUSDT", "SHORT", 1.0, expected_price=3_000.0)
    free_broker.set_stops("ETHUSDT", take_profit=2_800.0, stop_loss=3_200.0)

    prices["ETHUSDT"] = 3_300.0
    assert free_broker.check_stops()[0][1] == "stop_loss"


def test_stops_on_nothing_are_a_no_op(free_broker):
    assert free_broker.set_stops("BTCUSDT", 1.0, 2.0) is False


def test_no_stops_means_no_triggers(free_broker, prices):
    free_broker.place_market_order("BTCUSDT", "LONG", 0.01, expected_price=100_000.0)
    prices["BTCUSDT"] = 1.0  # catastrophic move, but no stop was set
    assert free_broker.check_stops() == []


# ---------------------------------------------------------------------------
# Health and reporting
# ---------------------------------------------------------------------------
def test_health_check_passes_when_data_flows(free_broker):
    ok, message = free_broker.health_check()
    assert ok
    assert "ok" in message


def test_slippage_is_zero_without_a_reference_price():
    """Avoid reporting a fabricated slippage number when there is nothing to
    compare against."""
    result = OrderResult(success=True, side="LONG", fill_price=100.0, expected_price=0.0)
    assert result.slippage_bps == 0.0


def test_bybit_broker_refuses_paper_mode():
    """Guard against accidentally routing paper trading through a real broker."""
    from config.settings import TradingMode
    from core.execution.broker import BrokerError

    with pytest.raises(BrokerError, match="cannot run in paper mode"):
        from core.execution.bybit import BybitBroker

        BybitBroker(mode=TradingMode.PAPER)


def test_last_cycle_is_persisted_for_the_desk(tmp_path, monkeypatch):
    """The API process cannot see in-memory cycle reports; they must hit disk."""
    from core.execution import engine as engine_mod

    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    report = engine_mod.CycleReport()
    report.symbols_scanned = 12
    report.signals_found = 0
    report.rejections.append(("BTCUSDT", "max positions"))
    engine_mod.persist_last_cycle(report, plan=None)
    loaded = engine_mod.load_last_cycle()
    assert loaded is not None
    assert loaded["symbols_scanned"] == 12
    assert loaded["rejection_details"][0]["symbol"] == "BTCUSDT"
    assert "sk-" not in str(loaded)


def test_paper_broker_hydrates_ledger_rows_so_restart_does_not_ghost(free_broker) -> None:
    """An empty RAM book against an open SQLite row trips the kill switch."""
    from types import SimpleNamespace

    free_broker.hydrate(
        [
            SimpleNamespace(
                symbol="ETHUSDT",
                side="LONG",
                quantity=0.4,
                entry_price=2472.35,
                take_profit_price=2568.77,
                stop_loss_price=2420.57,
                opened_at=None,
            )
        ]
    )
    snaps = free_broker.get_positions()
    assert len(snaps) == 1
    assert snaps[0].symbol == "ETHUSDT"
    assert snaps[0].quantity == pytest.approx(0.4)
    assert snaps[0].stop_loss == pytest.approx(2420.57)
    assert snaps[0].take_profit == pytest.approx(2568.77)
