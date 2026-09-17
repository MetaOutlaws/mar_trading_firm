"""
F04 — research/paper execution contract and golden tape.

Review: research filled at next-bar open with TP/SL from the slipped fill and
enforced ``max_holding_bars``; paper derived levels from the signal close,
submitted later at a sampled mark, skipped holding expiry, and added extra
exit slippage on stops.

These tests lock the shared contract (``core.execution.contract``) with
deterministic fixtures. ``BacktestEngine`` and ``run_paper_replay`` must both
match the tape. Live sampled marks are not the tape.

Does not stamp approved=true. Does not enable live.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from core.execution.broker import Instrument
from core.execution.contract import (
    EXECUTION_CONTRACT_VERSION,
    ExitReason,
    contract_snapshot,
    exit_fill_price,
    expiry_at,
    risk_levels,
)
from core.execution.engine import PlanEntry, TradingEngine, TradingPlan
from core.execution.paper import PaperBroker
from core.execution.replay import result_tape_rows, run_paper_replay
from core.ledger.store import Ledger
from core.risk.engine import RiskDecision, RiskEngine, RiskVerdict
from core.risk.limits import PAPER_LIMITS
from core.strategy.base import Signal, SignalSide, StrategyParams
from research.costs import COST_MODEL_VERSION, FRICTIONLESS, CostModel
from research.engine import BacktestConfig, BacktestEngine
from tests.test_engine import ScriptedStrategy
from tests.test_execution import StubDataSource

TAPE_DIR = Path(__file__).resolve().parent / "fixtures" / "golden_tapes"
SYMBOL = "BTCUSDT"  # majors: for_symbol slippage multiplier is 1.0


def _config_from_tape(tape: dict) -> BacktestConfig:
    costs_blob = tape.get("costs") or {}
    if costs_blob.get("frictionless"):
        costs = FRICTIONLESS
    else:
        costs = CostModel(
            taker_fee=float(costs_blob.get("taker_fee", 0.0)),
            maker_fee=float(costs_blob.get("maker_fee", 0.0)),
            slippage=float(costs_blob.get("slippage", 0.0)),
            include_funding=bool(costs_blob.get("include_funding", False)),
            default_funding_rate=float(costs_blob.get("default_funding_rate", 0.0001)),
        )
    run = tape.get("run") or {}
    return BacktestConfig(
        initial_capital=float(run.get("initial_capital", 10_000.0)),
        position_fraction=float(run.get("position_fraction", 1.0)),
        compound=bool(run.get("compound", False)),
        pessimistic_intrabar=bool(run.get("pessimistic_intrabar", True)),
        costs=costs,
    )


def _candles_from_tape(tape: dict) -> pd.DataFrame:
    rows = tape["candles"]
    index = pd.DatetimeIndex([pd.Timestamp(row["ts"]) for row in rows], name="timestamp")
    return pd.DataFrame(
        {
            "open": [row["open"] for row in rows],
            "high": [row["high"] for row in rows],
            "low": [row["low"] for row in rows],
            "close": [row["close"] for row in rows],
            "volume": [row.get("volume", 1000.0) for row in rows],
            "turnover": [row.get("turnover", 100_000.0) for row in rows],
        },
        index=index,
    )


def _strategy_from_tape(tape: dict) -> ScriptedStrategy:
    blob = tape["strategy"]
    params = StrategyParams(
        take_profit_pct=float(blob["params"]["take_profit_pct"]),
        stop_loss_pct=float(blob["params"]["stop_loss_pct"]),
        max_holding_bars=int(blob["params"]["max_holding_bars"]),
    )
    entries = {int(k): int(v) for k, v in blob["entries"].items()}
    return ScriptedStrategy(entries, params)


def _run_both(tape: dict) -> tuple:
    candles = _candles_from_tape(tape)
    strategy = _strategy_from_tape(tape)
    config = _config_from_tape(tape)
    symbol = tape.get("symbol", SYMBOL)
    research = BacktestEngine(config).run(symbol, candles, strategy)
    paper = run_paper_replay(symbol, candles, strategy, config)
    return research, paper


def _tape_paths() -> list[Path]:
    paths = sorted(TAPE_DIR.glob("*.json"))
    assert paths, f"no golden tapes in {TAPE_DIR}"
    return paths


@pytest.mark.parametrize("path", _tape_paths(), ids=lambda p: p.stem)
def test_golden_tape_research_matches_fixture(path: Path) -> None:
    tape = json.loads(path.read_text(encoding="utf-8"))
    assert tape["contract_version"] == EXECUTION_CONTRACT_VERSION
    research, _paper = _run_both(tape)
    assert result_tape_rows(research) == tape["expected"]["trades"]
    assert research.signals_generated == tape["expected"]["signals_generated"]
    assert research.final_equity == pytest.approx(tape["expected"]["final_equity"])


@pytest.mark.parametrize("path", _tape_paths(), ids=lambda p: p.stem)
def test_golden_tape_paper_replay_matches_fixture(path: Path) -> None:
    tape = json.loads(path.read_text(encoding="utf-8"))
    _research, paper = _run_both(tape)
    assert result_tape_rows(paper) == tape["expected"]["trades"]
    assert paper.signals_generated == tape["expected"]["signals_generated"]
    assert paper.final_equity == pytest.approx(tape["expected"]["final_equity"])


@pytest.mark.parametrize("path", _tape_paths(), ids=lambda p: p.stem)
def test_golden_tape_research_and_paper_do_not_drift(path: Path) -> None:
    """The regression: if research vs paper diverge on a taped scenario, fail."""
    tape = json.loads(path.read_text(encoding="utf-8"))
    research, paper = _run_both(tape)
    assert result_tape_rows(research) == result_tape_rows(paper)
    assert research.final_equity == pytest.approx(paper.final_equity)
    assert research.signals_generated == paper.signals_generated


def test_timeout_tape_fires_at_max_holding_bars() -> None:
    path = TAPE_DIR / "timeout_max_holding.json"
    tape = json.loads(path.read_text(encoding="utf-8"))
    research, paper = _run_both(tape)
    assert research.trades[0].exit_reason is ExitReason.TIMEOUT
    assert paper.trades[0].exit_reason is ExitReason.TIMEOUT
    holding = int(tape["strategy"]["params"]["max_holding_bars"])
    assert research.trades[0].bars_held == holding
    assert paper.trades[0].bars_held == holding


def test_contract_version_is_the_f04_stamp() -> None:
    snap = contract_snapshot()
    assert snap["execution_contract"] == "exec-f04-v1"
    assert snap["cost_model_version"] == COST_MODEL_VERSION
    assert snap["next_bar_open_entry"] is True
    assert snap["tp_sl_from_fill"] is True
    assert snap["stop_loss_extra_exit_slippage"] is False
    assert snap["max_holding_enforced"] is True
    assert snap["one_position_per_symbol"] is True


def test_risk_levels_use_fill_not_signal_close() -> None:
    """The documented F04 bug: levels from close 100 vs fill 100.1."""
    tp_from_close, sl_from_close = risk_levels(100.0, "LONG", 0.05, 0.05)
    tp_from_fill, sl_from_fill = risk_levels(100.1, "LONG", 0.05, 0.05)
    assert tp_from_close == pytest.approx(105.0)
    assert sl_from_close == pytest.approx(95.0)
    assert tp_from_fill == pytest.approx(105.105)
    assert sl_from_fill == pytest.approx(95.095)
    assert tp_from_fill != tp_from_close


def test_stop_loss_does_not_take_a_second_exit_slip() -> None:
    costs = CostModel(taker_fee=0.0, maker_fee=0.0, slippage=0.01, include_funding=False)
    assert exit_fill_price(costs, 95.0, "LONG", ExitReason.STOP_LOSS) == pytest.approx(95.0)
    assert exit_fill_price(costs, 105.0, "LONG", ExitReason.TAKE_PROFIT) == pytest.approx(103.95)
    assert exit_fill_price(costs, 100.0, "LONG", ExitReason.TIMEOUT) == pytest.approx(99.0)


def test_wrong_tp_origin_would_miss_the_tape() -> None:
    """If paper still used signal-close levels, the costed TP tape would drift."""
    tape = json.loads((TAPE_DIR / "costed_take_profit.json").read_text(encoding="utf-8"))
    candles = _candles_from_tape(tape)
    config = _config_from_tape(tape)
    costs = config.costs
    entry_quote = float(candles["open"].iloc[1])
    fill = costs.entry_price(entry_quote, "LONG")
    tp_fill, _sl = risk_levels(fill, "LONG", 0.05, 0.05)
    tp_close, _ = risk_levels(entry_quote, "LONG", 0.05, 0.05)
    assert tp_fill != pytest.approx(tp_close)
    # The tape's high (106) clears both, but the *fill* is what the contract books.
    assert tape["expected"]["trades"][0]["exit_reason"] == "take_profit"
    expected_exit = exit_fill_price(costs, tp_fill, "LONG", ExitReason.TAKE_PROFIT)
    assert tape["expected"]["trades"][0]["exit_price"] == pytest.approx(expected_exit)


def test_place_order_rebuilds_stops_from_fill(firm_db, tmp_path, monkeypatch) -> None:
    """Runtime used to attach TP/SL from signal.price; F04 rebuilds from fill."""
    from core.execution import engine as engine_mod

    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    prices = {SYMBOL: 110.0}  # sampled mark ≠ signal close 100
    broker = PaperBroker(
        starting_equity=10_000.0,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
    )
    broker._instruments[SYMBOL] = Instrument(
        SYMBOL, tick_size=0.0, qty_step=0.0, min_qty=0.0, min_notional=0.0
    )
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=PAPER_LIMITS),
        ledger=Ledger(mode="paper", starting_equity=10_000.0),
        plan=TradingPlan(
            entries=[
                PlanEntry(
                    symbol=SYMBOL,
                    side=SignalSide.LONG,
                    strategy=ScriptedStrategy({}),
                    timeframe="1h",
                )
            ]
        ),
        data_source=StubDataSource(prices),  # type: ignore[arg-type]
    )
    signal = Signal(
        symbol=SYMBOL,
        side=SignalSide.LONG,
        timestamp=pd.Timestamp("2024-01-01T00:00:00Z"),
        price=100.0,
        score=1.0,
        reason="f04",
        strategy="scripted",
        take_profit_pct=0.05,
        stop_loss_pct=0.05,
        max_holding_bars=3,
    )
    decision = RiskDecision(verdict=RiskVerdict.APPROVED, quantity=10.0, notional=1100.0)
    engine._place_order(signal, decision, stop_price=95.0, take_profit=105.0, sector="majors")

    pos = broker._positions[SYMBOL]
    assert pos.entry_price == pytest.approx(110.0)
    # Fill-based: 110 * 1.05 / 0.95. Signal-close would have been 105 / 95.
    assert pos.take_profit == pytest.approx(115.5)
    assert pos.stop_loss == pytest.approx(104.5)
    row = engine.ledger.find_open_position(SYMBOL)
    assert row is not None
    assert row.execution_contract == EXECUTION_CONTRACT_VERSION
    assert row.timeframe == "1h"
    assert row.max_holding_bars == 3
    assert row.expiry_at is not None
    assert row.take_profit_price == pytest.approx(115.5)
    assert row.stop_loss_price == pytest.approx(104.5)


def test_paper_timeout_closes_after_expiry(firm_db, tmp_path, monkeypatch) -> None:
    """Live paper must honour max_holding once expiry_at is stored."""
    from core.execution import engine as engine_mod

    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    prices = {SYMBOL: 100.0}
    broker = PaperBroker(
        starting_equity=10_000.0,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
    )
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=PAPER_LIMITS),
        ledger=Ledger(mode="paper", starting_equity=10_000.0),
        plan=TradingPlan(),
        data_source=StubDataSource(prices),  # type: ignore[arg-type]
    )
    opened = broker.place_market_order(SYMBOL, "LONG", 1.0, expected_price=100.0)
    assert opened.success
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    engine.ledger.open_position(
        symbol=SYMBOL,
        side="LONG",
        quantity=opened.filled_quantity,
        entry_price=opened.fill_price,
        expected_entry_price=100.0,
        take_profit=200.0,
        stop_loss=1.0,
        strategy="f04",
        sector="majors",
        signal_score=1.0,
        signal_reason="timeout",
        broker_order_id=opened.order_id,
        entry_fee=opened.fee,
        execution_contract=EXECUTION_CONTRACT_VERSION,
        timeframe="1h",
        max_holding_bars=3,
        expiry_at=past,
    )
    closed = engine.supervise_exits()
    assert closed == 1
    assert broker.get_positions() == []
    trades = engine.ledger.performance()
    assert trades["trades"] == 1


def test_expiry_at_is_open_plus_holding_bars() -> None:
    opened = datetime(2024, 1, 1, tzinfo=timezone.utc)
    stamp = expiry_at(opened, "1h", 3)
    assert stamp == datetime(2024, 1, 1, 3, tzinfo=timezone.utc)


def test_sqlite_migration_adds_contract_columns(tmp_path, monkeypatch) -> None:
    """Existing paper DBs were created before F04; create_all will not ALTER them."""
    import sqlite3

    from config.settings import get_settings
    from core.db import _migrate_sqlite_columns, get_engine, get_session_factory

    db_path = tmp_path / "pre_f04.db"
    raw = sqlite3.connect(db_path)
    raw.execute("CREATE TABLE positions (id INTEGER PRIMARY KEY, symbol VARCHAR(32))")
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
        raw.close()
    finally:
        get_engine.cache_clear()
        get_session_factory.cache_clear()
        get_settings.cache_clear()

    assert "execution_contract" in pos_cols
    assert "strategy_params" in pos_cols
    assert "timeframe" in pos_cols
    assert "max_holding_bars" in pos_cols
    assert "expiry_at" in pos_cols


def test_no_live_and_no_approval_stamp() -> None:
    from config.settings import TradingMode, get_settings

    assert get_settings().trading_mode is not TradingMode.LIVE
    assert EXECUTION_CONTRACT_VERSION.startswith("exec-f04-")
