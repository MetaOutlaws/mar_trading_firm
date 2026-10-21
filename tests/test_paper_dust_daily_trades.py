"""Paper dust fills do not consume max_daily_trades.

The cap stays 20. A paper fill is dust when its filled notional is strictly
below max(0.10 * max_position_pct * sizer equity, $25). The classification
is stored on the position and the daily counter reads that flag. Live
counting is unchanged. Small entries still open.

Oct 20 reference equity is $19,800 (Munha: the floor is about $198). The
nine sub-0.10 fills from the 64-fill census are the dust rows.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from core.db import session_scope
from core.execution.broker import Instrument
from core.execution.engine import TradingEngine, TradingPlan
from core.execution.paper import PaperBroker
from core.ledger.models import Position
from core.ledger.store import Ledger
from core.risk.engine import OpenPosition, PortfolioState, RiskEngine, RiskVerdict, TradeIntent
from core.risk.limits import (
    INITIAL_LIVE_LIMITS,
    PAPER_DUST_ABSOLUTE_FLOOR_USDT,
    PAPER_DUST_FRACTION_OF_NORMAL_SIZE,
    PAPER_LIMITS,
    RiskLimits,
    paper_dust_floor_usdt,
    paper_fill_counts_toward_daily_trades,
)
from core.strategy.base import Signal, SignalSide
from research.costs import FRICTIONLESS
from tests.test_execution import StubDataSource

# Sizer equity used for the Oct 20 classification in Munha's note.
OCT20_EQUITY = 19_800.0
OCT20_PCT = 0.10  # PAPER_LIMITS.max_position_pct

# The nine fills below 0.10 of normal size, all on Oct 20. Tsuro's "8 dust"
# list omitted AAVE $122. Dollars are the filled notionals from the census.
OCT20_DUST = (
    ("POPCATUSDT", 8.0),
    ("DYDXUSDT", 19.0),
    ("GMTUSDT", 6.0),
    ("OPUSDT", 55.0),
    ("AAVEUSDT", 122.0),
    ("ARPAUSDT", 60.0),
    ("AXSUSDT", 30.0),
    ("CFXUSDT", 15.0),
    ("LDOUSDT", 7.0),
)

# Half-size cluster a 2.5%-of-equity cut would have called dust. At 1% they
# sit above the floor and still count. WAVES is the Oct 21 fill.
ABOVE_FLOOR = (
    ("FLOKIUSDT", 246.0),
    ("GALAUSDT", 486.0),
    ("1000BONKUSDT", 494.0),
    ("WAVESUSDT", 472.0),
)


def _floor(equity: float = OCT20_EQUITY, pct: float = OCT20_PCT) -> float:
    return paper_dust_floor_usdt(equity, pct)


def _open(
    ledger: Ledger,
    symbol: str,
    notional: float,
    *,
    equity: float | None = OCT20_EQUITY,
    sector: str = "other",
    pct: float | None = OCT20_PCT,
    price: float = 100.0,
) -> int:
    """Open a paper/live row whose filled notional is exactly ``notional``."""
    return ledger.open_position(
        symbol=symbol,
        side="LONG",
        quantity=notional / price,
        entry_price=price,
        expected_entry_price=price,
        take_profit=price * 1.05,
        stop_loss=price * 0.97,
        strategy="range_compression_volume_thrust",
        sector=sector,
        signal_score=1.0,
        signal_reason="dust-test",
        broker_order_id=f"dust-{symbol}-{notional}",
        entry_equity=equity,
        max_position_pct=pct,
    )


def _row(position_id: int) -> Position:
    with session_scope() as session:
        row = session.get(Position, position_id)
        assert row is not None
        # Touch every field the assertions read before the session closes.
        _ = (
            row.notional,
            row.entry_equity,
            row.dust_floor_usdt,
            row.counts_toward_daily_trades,
            row.daily_trade_at,
            row.status,
            row.quantity,
            row.symbol,
        )
        return row


def _close_as_wins(ledger: Ledger, price: float = 100.0) -> None:
    """Close every open row at a profit so the loss halt stays quiet.

    trades_today counts opens, including ones that have since closed. Closing
    them lets the next risk check see the daily counter without also tripping
    max_open.
    """
    for position in ledger.open_positions():
        ledger.close_position(
            position.id,
            exit_price=price * 1.01,
            expected_exit_price=price * 1.01,
            exit_reason="test",
            fees=0.0,
            entry_fees=0.0,
            exit_fees=0.0,
        )


def _intent(symbol: str = "LINKUSDT", sector: str = "majors") -> TradeIntent:
    entry = 100.0
    return TradeIntent(
        symbol=symbol,
        side="LONG",
        entry_price=entry,
        stop_price=entry * 0.97,
        take_profit_price=entry * 1.06,
        strategy="range_compression_volume_thrust",
        sector=sector,
    )


def test_floor_is_ten_percent_of_normal_size_or_25_dollars() -> None:
    """0.10 * max_position_pct 0.10 is 1% of equity. $25 binds below $2,500."""
    assert PAPER_DUST_FRACTION_OF_NORMAL_SIZE == 0.10
    assert PAPER_DUST_ABSOLUTE_FLOOR_USDT == 25.0
    assert PAPER_LIMITS.max_position_pct == 0.10
    assert PAPER_LIMITS.max_daily_trades == 20
    assert PAPER_LIMITS.max_concurrent_positions == 15
    # Not a RiskLimits field. The dataclass pin stays the pre-dust snapshot.
    assert "dust" not in RiskLimits().to_dict()
    assert "entry_equity" not in RiskLimits().to_dict()

    at_topup = _floor(OCT20_EQUITY)
    assert at_topup == pytest.approx(198.0)
    assert at_topup == pytest.approx(0.01 * OCT20_EQUITY)

    # Below $2,500 the absolute floor is the one that binds.
    assert _floor(2_000.0) == 25.0
    assert 0.10 * 0.10 * 2_000.0 == pytest.approx(20.0)
    assert _floor(2_499.0) == 25.0
    # At $2,500 the two terms meet. Above that, the equity term is higher.
    assert _floor(2_500.0) == pytest.approx(25.0)
    assert _floor(10_000.0) == pytest.approx(100.0)


def test_absolute_floor_binds_below_2500_equity(firm_db) -> None:
    """A $22 fill is above 1% of $2,000 and still dust, because of the $25 floor."""
    ledger = Ledger(mode="paper")
    dust_id = _open(ledger, "GMTUSDT", 22.0, equity=2_000.0, sector="majors")
    counted_id = _open(ledger, "ETHUSDT", 25.0, equity=2_000.0, sector="majors")

    dust = _row(dust_id)
    counted = _row(counted_id)
    assert dust.dust_floor_usdt == pytest.approx(25.0)
    assert dust.counts_toward_daily_trades is False
    assert counted.dust_floor_usdt == pytest.approx(25.0)
    assert counted.counts_toward_daily_trades is True
    assert ledger.trades_today() == 1

    # At $10k the $25 backstop does not bind: $30 is dust because 1% is $100.
    before = ledger.trades_today()
    wide_id = _open(ledger, "SOLUSDT", 30.0, equity=10_000.0, sector="layer1")
    wide = _row(wide_id)
    assert wide.dust_floor_usdt == pytest.approx(100.0)
    assert wide.counts_toward_daily_trades is False
    assert ledger.trades_today() == before


def test_boundary_equal_to_the_floor_counts(firm_db) -> None:
    """Dust is strictly below the floor. Equal counts."""
    ledger = Ledger(mode="paper")
    floor = _floor()
    below = math.nextafter(floor, 0.0)
    assert below < floor

    dust_id = _open(ledger, "LDOUSDT", below)
    exact_id = _open(ledger, "FLOKIUSDT", floor, sector="memes")
    dust = _row(dust_id)
    exact = _row(exact_id)
    assert dust.counts_toward_daily_trades is False
    assert exact.counts_toward_daily_trades is True
    assert exact.dust_floor_usdt == pytest.approx(floor)
    assert exact.notional == pytest.approx(floor)
    assert ledger.trades_today() == 1

    # The same rule on the pure function, so a stored flag can be replayed.
    counts_below, floor_below = paper_fill_counts_toward_daily_trades(
        below, OCT20_EQUITY, OCT20_PCT
    )
    counts_exact, floor_exact = paper_fill_counts_toward_daily_trades(
        floor, OCT20_EQUITY, OCT20_PCT
    )
    assert counts_below is False and floor_below == pytest.approx(floor)
    assert counts_exact is True and floor_exact == pytest.approx(floor)


def test_oct20_nine_dust_fills_leave_the_count_at_11(firm_db) -> None:
    """20 opens, 9 of them the census dust sizes. The counter reports 11.

    The 21st normal entry is then allowed: the daily cap is 20 and only 11
    slots were used. The positions are closed first so max_open is not what
    decides the 21st.
    """
    ledger = Ledger(mode="paper")
    floor = _floor()
    for symbol, notional in OCT20_DUST:
        assert notional < floor
        position_id = _open(ledger, symbol, notional)
        row = _row(position_id)
        assert row.counts_toward_daily_trades is False
        assert row.entry_equity == pytest.approx(OCT20_EQUITY)
        assert row.dust_floor_usdt == pytest.approx(floor)
        assert row.notional == pytest.approx(notional)
        assert row.status == "open"

    for index in range(11):
        position_id = _open(
            ledger,
            f"FULL{index:02d}USDT",
            1_980.0,
            sector=f"sector{index % 6}",
        )
        assert _row(position_id).counts_toward_daily_trades is True

    assert ledger.trades_today() == 11
    assert len(ledger.open_positions()) == 20

    # A later, smaller equity must not reclassify the stored rows.
    # At $1,000 the floor would be $25 and AAVE $122 would count.
    reread = ledger.portfolio_state(1_000.0)
    assert reread.equity == pytest.approx(1_000.0)
    assert reread.trades_today == 11

    _close_as_wins(ledger)
    assert ledger.trades_today() == 11
    state = ledger.portfolio_state(OCT20_EQUITY)
    decision = RiskEngine(limits=PAPER_LIMITS).evaluate(_intent("LINKUSDT", "majors"), state)
    assert decision.is_approved, decision.reasons


def test_twenty_non_dust_opens_reject_the_next(firm_db) -> None:
    ledger = Ledger(mode="paper")
    for index in range(20):
        _open(ledger, f"NORM{index:02d}USDT", 1_980.0, sector=f"sector{index}")
    assert ledger.trades_today() == 20
    _close_as_wins(ledger)
    state = ledger.portfolio_state(OCT20_EQUITY)
    decision = RiskEngine(limits=PAPER_LIMITS).evaluate(_intent(), state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("trades today" in reason for reason in decision.reasons)


def test_live_counting_includes_every_fill(firm_db) -> None:
    """INITIAL_LIVE_LIMITS still counts dust. The cap value is still 10."""
    assert INITIAL_LIVE_LIMITS.max_daily_trades == 10
    assert INITIAL_LIVE_LIMITS.max_concurrent_positions == 3
    assert INITIAL_LIVE_LIMITS.max_position_pct == 0.05
    live = Ledger(mode="live")
    for symbol, notional in OCT20_DUST:
        position_id = _open(live, symbol, notional)
        row = _row(position_id)
        # Live does not store a paper classification. The row still counts.
        assert row.counts_toward_daily_trades is True
        assert row.dust_floor_usdt is None
        assert row.entry_equity is None
    assert live.trades_today() == len(OCT20_DUST)

    # One more dust fill brings the live counter to the live cap of 10.
    _open(live, "XRPUSDT", 7.0, sector="majors")
    assert live.trades_today() == 10
    state = live.portfolio_state(OCT20_EQUITY)
    decision = RiskEngine(limits=INITIAL_LIVE_LIMITS).evaluate(_intent("ADAUSDT", "layer1"), state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("trades today" in reason for reason in decision.reasons)

    # The same ten dust notionals on a paper book consume no daily slots.
    paper = Ledger(mode="paper")
    for symbol, notional in list(OCT20_DUST) + [("XRPUSDT", 7.0)]:
        _open(paper, symbol, notional, sector="layer1" if symbol == "XRPUSDT" else "other")
    assert paper.trades_today() == 0


def test_missing_equity_counts_the_fill(firm_db, caplog) -> None:
    ledger = Ledger(mode="paper")
    with caplog.at_level(logging.INFO, logger="core.ledger.store"):
        position_id = _open(ledger, "LDOUSDT", 7.26, equity=None, pct=OCT20_PCT)
    row = _row(position_id)
    assert row.counts_toward_daily_trades is True
    assert row.entry_equity is None
    assert row.dust_floor_usdt is None
    assert row.daily_trade_at is not None
    assert ledger.trades_today() == 1
    assert any(
        "fail closed" in record.message and "LDOUSDT" in record.message
        for record in caplog.records
    )

    # A usable equity with no position cap is the same fail-closed outcome.
    no_cap = _open(ledger, "GMTUSDT", 6.0, equity=OCT20_EQUITY, pct=None)
    assert _row(no_cap).counts_toward_daily_trades is True
    assert ledger.trades_today() == 2


def test_dust_fill_still_opens_and_is_logged(firm_db, caplog, tmp_path, monkeypatch) -> None:
    """Nothing is skipped. The broker position exists; only the counter ignores it."""
    from core.execution import engine as engine_mod
    from core.risk.engine import RiskDecision

    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    symbol = "ARPAUSDT"
    prices = {symbol: 100.0}
    broker = PaperBroker(
        starting_equity=OCT20_EQUITY,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
    )
    broker._instruments[symbol] = Instrument(
        symbol, tick_size=0.0, qty_step=0.0, min_qty=0.0, min_notional=0.0
    )
    ledger = Ledger(mode="paper", starting_equity=OCT20_EQUITY)
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=PAPER_LIMITS),
        ledger=ledger,
        plan=TradingPlan(entries=[]),
        data_source=StubDataSource(prices),  # type: ignore[arg-type]
    )
    signal = Signal(
        symbol=symbol,
        side=SignalSide.LONG,
        timestamp=pd.Timestamp("2026-10-20T16:00:00Z"),
        price=100.0,
        score=1.0,
        reason="dust",
        strategy="range_compression_volume_thrust",
        take_profit_pct=0.05,
        stop_loss_pct=0.03,
        max_holding_bars=4,
    )
    # Headroom-sized dust: the risk engine would still approve $60. This
    # decision is that approval, handed to the same order path.
    decision = RiskDecision(
        verdict=RiskVerdict.APPROVED_REDUCED,
        quantity=0.60,
        notional=60.0,
    )
    with caplog.at_level(logging.INFO, logger="core.ledger.store"):
        engine._place_order(
            signal,
            decision,
            stop_price=97.0,
            take_profit=105.0,
            sector="other",
            entry_equity=OCT20_EQUITY,
        )

    assert symbol in broker._positions
    assert len(ledger.open_positions()) == 1
    assert ledger.trades_today() == 0
    opened = ledger.open_positions()[0]
    assert opened.notional == pytest.approx(60.0)
    row = _row(opened.id)
    assert row.counts_toward_daily_trades is False
    assert row.entry_equity == pytest.approx(OCT20_EQUITY)
    assert row.dust_floor_usdt == pytest.approx(198.0)
    matched = [
        record.message
        for record in caplog.records
        if "excluded from max_daily_trades" in record.message
    ]
    assert matched
    message = matched[0]
    assert "ARPAUSDT" in message
    assert "60.0000" in message
    assert "19800.0000" in message
    assert "198.0000" in message


def test_attempt_entry_stores_the_sizer_equity(firm_db, tmp_path, monkeypatch) -> None:
    """The equity passed into the risk check is the equity stored on the fill."""
    from core.execution import engine as engine_mod

    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    symbol = "BTCUSDT"
    prices = {symbol: 100.0}
    broker = PaperBroker(
        starting_equity=OCT20_EQUITY,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
    )
    broker._instruments[symbol] = Instrument(
        symbol, tick_size=0.0, qty_step=0.0, min_qty=0.0, min_notional=0.0
    )
    ledger = Ledger(mode="paper", starting_equity=OCT20_EQUITY)
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=PAPER_LIMITS),
        ledger=ledger,
        plan=TradingPlan(entries=[]),
        data_source=StubDataSource(prices),  # type: ignore[arg-type]
    )
    signal = Signal(
        symbol=symbol,
        side=SignalSide.LONG,
        timestamp=pd.Timestamp("2026-10-20T16:00:00Z"),
        price=100.0,
        score=1.0,
        reason="full",
        strategy="ema_adx_trend",
        take_profit_pct=0.05,
        stop_loss_pct=0.03,
        max_holding_bars=4,
    )
    decision = engine._attempt_entry(signal, OCT20_EQUITY, {symbol: 100.0})
    assert decision.is_approved
    # 10% of $19,800. The stop is wide enough that the position cap binds.
    assert decision.notional == pytest.approx(1_980.0, rel=0.001)
    assert symbol in broker._positions
    row = _row(ledger.open_positions()[0].id)
    assert row.entry_equity == pytest.approx(OCT20_EQUITY)
    assert row.notional == pytest.approx(1_980.0, rel=0.001)
    assert row.counts_toward_daily_trades is True
    assert row.dust_floor_usdt == pytest.approx(198.0)
    assert ledger.trades_today() == 1


def test_sizer_still_approves_a_headroom_dust_size() -> None:
    """The dust rule is not an entry filter. $60 under the gross cap is approved."""
    equity = OCT20_EQUITY
    room = 60.0
    state = PortfolioState(equity=equity, peak_equity=equity)
    state.open_positions = [
        OpenPosition(
            symbol="CHZUSDT",
            side="SHORT",
            quantity=(equity * 0.50 - room) / 100.0,
            entry_price=100.0,
            notional=equity * 0.50 - room,
            sector="other",
        )
    ]
    decision = RiskEngine(limits=PAPER_LIMITS).evaluate(_intent("NEARUSDT", "layer1"), state)
    assert decision.is_approved
    assert decision.verdict is RiskVerdict.APPROVED_REDUCED
    assert decision.notional == pytest.approx(room, abs=0.05)
    assert decision.notional < _floor(equity)


def test_scale_in_counts_once_cumulative_notional_crosses(firm_db, caplog) -> None:
    """Partial adds use cumulative notional. The slot is taken on the crossing fill."""
    ledger = Ledger(mode="paper")
    floor = _floor()
    position_id = _open(ledger, "AAVEUSDT", 100.0, sector="defi")
    assert ledger.trades_today() == 0
    assert _row(position_id).dust_floor_usdt == pytest.approx(floor)

    with caplog.at_level(logging.INFO, logger="core.ledger.store"):
        still_dust = ledger.record_additional_fill(position_id, 50.0)
    assert still_dust is False
    assert ledger.trades_today() == 0
    mid = _row(position_id)
    assert mid.notional == pytest.approx(150.0)
    assert mid.counts_toward_daily_trades is False
    # Equity and floor stay the ones stored at open.
    assert mid.entry_equity == pytest.approx(OCT20_EQUITY)
    assert mid.dust_floor_usdt == pytest.approx(floor)
    assert any(
        "excluded from max_daily_trades" in record.message and "150.0000" in record.message
        for record in caplog.records
    )

    crossed = ledger.record_additional_fill(position_id, floor - 150.0)
    assert crossed is True
    assert ledger.trades_today() == 1
    done = _row(position_id)
    assert done.notional == pytest.approx(floor)
    assert done.counts_toward_daily_trades is True
    assert done.entry_equity == pytest.approx(OCT20_EQUITY)
    assert done.dust_floor_usdt == pytest.approx(floor)
    assert done.status == "open"

    # A further add does not consume a second slot.
    assert ledger.record_additional_fill(position_id, 10.0) is False
    assert ledger.trades_today() == 1
    assert _row(position_id).notional == pytest.approx(floor + 10.0)


def test_scale_in_that_crosses_on_a_later_day_counts_that_day(firm_db) -> None:
    ledger = Ledger(mode="paper")
    position_id = _open(ledger, "CFXUSDT", 15.0, sector="layer1")
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    with session_scope() as session:
        row = session.get(Position, position_id)
        assert row is not None
        row.opened_at = yesterday
    assert ledger.trades_today() == 0

    assert ledger.record_additional_fill(position_id, 200.0) is True
    assert ledger.trades_today() == 1
    updated = _row(position_id)
    assert updated.opened_at < datetime.now(timezone.utc) - timedelta(hours=12)
    assert updated.daily_trade_at is not None
    assert updated.daily_trade_at.date() == datetime.now(timezone.utc).date()


def test_dust_still_consumes_sector_cap_and_max_open(firm_db) -> None:
    """Only the daily counter changes. Sector, max_open and exposure still see dust."""
    ledger = Ledger(mode="paper")
    _open(ledger, "ARPAUSDT", 60.0, sector="other")
    _open(ledger, "CHZUSDT", 55.0, sector="other")
    assert ledger.trades_today() == 0

    state = ledger.portfolio_state(OCT20_EQUITY)
    assert state.trades_today == 0
    assert state.total_exposure == pytest.approx(115.0)
    assert state.positions_in_sector("other") == 2

    blocked = RiskEngine(limits=PAPER_LIMITS).evaluate(_intent("PUMPFUNUSDT", "other"), state)
    assert blocked.verdict is RiskVerdict.REJECTED
    assert any("sector" in reason for reason in blocked.reasons)
    assert not any("trades today" in reason for reason in blocked.reasons)

    # A different sector is still allowed: the daily cap did not bind.
    allowed = RiskEngine(limits=PAPER_LIMITS).evaluate(_intent("NEARUSDT", "layer1"), state)
    assert allowed.is_approved

    # Fifteen dust opens, each in its own sector, fill max_open. The daily
    # counter stays at 0, so the rejection is the concurrent-position cap.
    # Close the two sector-cap rows first; they share this paper book.
    _close_as_wins(ledger)
    assert ledger.trades_today() == 0
    book = ledger
    for index in range(PAPER_LIMITS.max_concurrent_positions):
        _open(
            book,
            f"DUST{index:02d}USDT",
            10.0,
            sector=f"sector{index}",
        )
    assert book.trades_today() == 0
    full = book.portfolio_state(OCT20_EQUITY)
    assert len(full.open_positions) == 15
    assert full.total_exposure == pytest.approx(150.0)
    rejected = RiskEngine(limits=PAPER_LIMITS).evaluate(_intent("WLDUSDT", "ai"), full)
    assert rejected.verdict is RiskVerdict.REJECTED
    assert any("open positions" in reason for reason in rejected.reasons)
    assert not any("trades today" in reason for reason in rejected.reasons)


def test_observed_ladder_at_19800(firm_db) -> None:
    """$7 through $122 are dust. $246, $486, $494 and $472 count.

    That is the 1% cut. A 2.5%-of-equity cut ($495 at this equity) would
    have classified the whole half-size cluster as dust.
    """
    ledger = Ledger(mode="paper")
    floor = _floor()
    two_and_a_half = 0.25 * OCT20_PCT * OCT20_EQUITY
    assert two_and_a_half == pytest.approx(495.0)
    assert floor < 246.0 < two_and_a_half

    for symbol, notional in (
        ("POPCATUSDT", 8.0),
        ("LDOUSDT", 7.0),
        ("CFXUSDT", 15.0),
        ("AXSUSDT", 30.0),
        ("OPUSDT", 60.0),
        ("AAVEUSDT", 122.0),
    ):
        position_id = _open(ledger, symbol, notional, sector=symbol)
        assert _row(position_id).counts_toward_daily_trades is False

    for symbol, notional in ABOVE_FLOOR:
        # All four are real size under the 1% rule and would be dust at 2.5%.
        assert floor <= notional < two_and_a_half
        position_id = _open(ledger, symbol, notional, sector=symbol)
        assert _row(position_id).counts_toward_daily_trades is True

    # 6 dust + 4 counted.
    assert ledger.trades_today() == 4


def test_sqlite_migration_defaults_old_rows_to_counting(tmp_path, monkeypatch) -> None:
    """Rows written before the dust columns exist keep counting (fail closed)."""
    import sqlite3

    from config.settings import get_settings
    from core.db import _migrate_sqlite_columns, get_engine, get_session_factory

    db_path = tmp_path / "pre_dust.db"
    raw = sqlite3.connect(db_path)
    raw.execute(
        "CREATE TABLE positions (id INTEGER PRIMARY KEY, symbol VARCHAR(32), notional FLOAT)"
    )
    raw.execute("INSERT INTO positions (symbol, notional) VALUES ('LDOUSDT', 7.26)")
    raw.commit()
    raw.close()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    try:
        _migrate_sqlite_columns()
        raw = sqlite3.connect(db_path)
        columns = {row[1] for row in raw.execute("PRAGMA table_info(positions)")}
        flag = raw.execute("SELECT counts_toward_daily_trades FROM positions").fetchone()[0]
        equity = raw.execute("SELECT entry_equity FROM positions").fetchone()[0]
        raw.close()
    finally:
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        get_settings.cache_clear()

    assert "entry_equity" in columns
    assert "dust_floor_usdt" in columns
    assert "counts_toward_daily_trades" in columns
    assert "daily_trade_at" in columns
    assert flag == 1
    assert equity is None


def test_pre_rule_row_with_null_timestamp_still_counts_on_its_open_day(firm_db) -> None:
    """Migration leaves daily_trade_at null. The open day is the fallback."""
    ledger = Ledger(mode="paper")
    position_id = _open(ledger, "ETHUSDT", 1_980.0, sector="majors")
    with session_scope() as session:
        row = session.get(Position, position_id)
        assert row is not None
        row.daily_trade_at = None
        row.counts_toward_daily_trades = True
    assert ledger.trades_today() == 1
