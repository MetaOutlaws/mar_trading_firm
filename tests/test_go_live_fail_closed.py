"""
§5 promotion / go-live gate must fail closed.

Review (`docs/MAR_Trading_Firm_Review_2026-09-12.md` §5) and Board DONE:
rejected OOS must not pad the sample; missing drawdown fails; a tripped kill
switch fails; paper-ledger evidence is required even under LIVE settings.
This module never writes ``approved=true`` and must not touch the approval book.
"""

from __future__ import annotations

import ast
import json
from types import SimpleNamespace

import pytest

from config.settings import PROJECT_ROOT, TradingMode, get_settings
from config.universe import APPROVALS_PATH
from core.ledger.store import Ledger
from core.risk.killswitch import KillSwitch, TripReason
from firm.memory_models import TrustLevel
from research.revalidation import fingerprint_approval_book
from scripts.check_go_live import (
    LEDGER_MODE_PAPER,
    MIN_OOS_TRADES,
    MIN_PAPER_TRADES,
    evaluate_gates,
)

REPO_ROOT = PROJECT_ROOT
CHECK_GO_LIVE = REPO_ROOT / "scripts" / "check_go_live.py"


def _gate(report: dict, name: str) -> dict:
    match = [g for g in report["gates"] if g["name"] == name]
    assert match, f"missing gate {name} in {[g['name'] for g in report['gates']]}"
    return match[0]


def _approved_row(**overrides) -> dict:
    row = {
        "approved": True,
        "oos_trades": 120,
        "oos_profit_factor": 1.45,
        "oos_max_drawdown_pct": 4.0,
        "oos_expectancy_pct": 0.4,
    }
    row.update(overrides)
    return row


def _book(*rows: tuple[str, dict]) -> dict:
    return dict(rows)


def _empty_perf(**overrides) -> dict:
    payload = {
        "mode": "paper",
        "trades": 0,
        "win_rate": 0.0,
        "profit_factor": None,
        "net_pnl": 0.0,
        "measured_slippage_bps": None,
    }
    payload.update(overrides)
    return payload


def _report(firm_db, tmp_path, *, approvals, performance=None, ledger=None, kill=None):
    """Evaluate with an isolated kill switch and empty trust records."""
    del firm_db  # fixture must run so Ledger queries hit the throwaway db
    ks = kill if kill is not None else KillSwitch(tmp_path / "killswitch.json")
    return evaluate_gates(
        approvals=approvals,
        ledger=ledger,
        kill_switch=ks,
        performance=performance if performance is not None else _empty_perf(),
        trust_records=[],
    )


def test_rejected_oos_trades_are_excluded_from_promotion_sample(firm_db, tmp_path) -> None:
    """A rejected sleeve with a huge OOS count must not clear the sample gate."""
    approvals = _book(
        ("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row(oos_trades=50)),
        (
            "rsi_trend:ETHUSDT:LONG:15m",
            {
                "approved": False,
                "oos_trades": MIN_OOS_TRADES + 4000,
                "oos_profit_factor": 3.0,
                "oos_max_drawdown_pct": 1.0,
            },
        ),
        (
            "mass_index_reversal:SOLUSDT:LONG:4h",
            {
                "approved": False,
                "paper_override": True,
                "oos_trades": MIN_OOS_TRADES + 9000,
                "oos_profit_factor": 2.5,
                "oos_max_drawdown_pct": 1.0,
            },
        ),
    )
    report = _report(firm_db, tmp_path, approvals=approvals)
    sample = _gate(report, "walk_forward_sample")
    assert sample["measured"] == 50
    assert sample["passed"] is False
    assert report["ready"] is False
    # If rejected rows were pooled, 50 + 4300 + 9300 would pass MIN_OOS_TRADES.
    pooled = 50 + (MIN_OOS_TRADES + 4000) + (MIN_OOS_TRADES + 9000)
    assert pooled >= MIN_OOS_TRADES


def test_missing_paper_drawdown_fails_the_gate(firm_db, tmp_path) -> None:
    approvals = _book(
        ("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()),
    )
    # Ledger.performance() historically omitted max_drawdown_pct; missing must
    # not be treated as 0% (the review's fail-open).
    perf = _empty_perf(trades=40, avg_return_pct=0.25, profit_factor=1.4)
    assert "max_drawdown_pct" not in perf
    report = _report(firm_db, tmp_path, approvals=approvals, performance=perf)
    dd = _gate(report, "drawdown")
    assert dd["passed"] is False
    assert dd["measured"]["paper"] is None
    assert "missing paper" in dd["detail"].lower()
    assert report["ready"] is False


def test_missing_oos_drawdown_on_approved_row_fails_the_gate(firm_db, tmp_path) -> None:
    approvals = _book(
        (
            "atr_channel_breakout:BTCUSDT:SHORT:4h",
            _approved_row(oos_max_drawdown_pct=None),
        ),
    )
    # Explicit None — JSON null — must not coerce to 0.0 and pass.
    assert approvals["atr_channel_breakout:BTCUSDT:SHORT:4h"]["oos_max_drawdown_pct"] is None
    perf = _empty_perf(trades=40, avg_return_pct=0.25, max_drawdown_pct=3.0)
    report = _report(firm_db, tmp_path, approvals=approvals, performance=perf)
    dd = _gate(report, "drawdown")
    assert dd["passed"] is False
    assert dd["measured"]["oos_complete"] is False
    assert "missing approved oos drawdown" in dd["detail"].lower()
    assert report["ready"] is False


def test_tripped_kill_switch_fails_the_gate(firm_db, tmp_path) -> None:
    approvals = _book(("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()))
    ks = KillSwitch(tmp_path / "killswitch.json")
    ks.trip(TripReason.MANUAL, detail="desk halt", tripped_by="test")
    report = _report(firm_db, tmp_path, approvals=approvals, kill=ks)
    ks_gate = _gate(report, "kill_switch")
    assert ks_gate["passed"] is False
    assert ks_gate["measured"]["tripped"] is True
    assert "TRIPPED" in ks_gate["detail"]
    assert report["ready"] is False


def test_clear_kill_switch_does_not_hardcode_pass_when_other_gates_fail(
    firm_db, tmp_path
) -> None:
    """A clear KS is necessary, not sufficient — unlike the old hardcoded True."""
    approvals = _book(("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()))
    report = _report(firm_db, tmp_path, approvals=approvals)
    assert _gate(report, "kill_switch")["passed"] is True
    assert report["ready"] is False


def test_injected_live_ledger_fails_paper_ledger_gate(firm_db, tmp_path) -> None:
    approvals = _book(("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()))
    live = Ledger(mode=TradingMode.LIVE.value, starting_equity=10_000.0)
    report = _report(firm_db, tmp_path, approvals=approvals, ledger=live)
    paper = _gate(report, "paper_ledger")
    assert paper["passed"] is False
    assert paper["measured"] == "live"
    assert report["ledger_mode"] == "live"
    assert report["evidence_mode"] == LEDGER_MODE_PAPER
    assert report["ready"] is False


def test_evaluate_gates_uses_paper_ledger_even_if_env_says_live(
    monkeypatch, firm_db, tmp_path
) -> None:
    """LIVE env must not redirect promotion evidence at live rows."""
    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("GO_LIVE_CONFIRMED", "I_ACCEPT_THE_RISK")
    monkeypatch.setenv("BYBIT_LIVE_API_KEY", "x")
    monkeypatch.setenv("BYBIT_LIVE_API_SECRET", "y")
    get_settings.cache_clear()
    try:
        approvals = _book(("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()))
        report = _report(firm_db, tmp_path, approvals=approvals)
        assert report["ledger_mode"] == LEDGER_MODE_PAPER
        assert report["evidence_mode"] == LEDGER_MODE_PAPER
        assert _gate(report, "paper_ledger")["passed"] is True
        assert report["ready"] is False
    finally:
        get_settings.cache_clear()


def test_live_trades_do_not_count_as_paper_sample(firm_db, tmp_path) -> None:
    """Paper sample/expectancy gates read paper rows, not a live ledger."""
    live = Ledger(mode=TradingMode.LIVE.value, starting_equity=10_000.0)
    pid = live.open_position(
        symbol="BTCUSDT",
        side="SHORT",
        quantity=0.01,
        entry_price=100_000.0,
        expected_entry_price=100_000.0,
        take_profit=None,
        stop_loss=None,
        strategy="sneak",
        sector="majors",
        signal_score=1.0,
        signal_reason="live sneak",
        broker_order_id="live-1",
    )
    live.close_position(
        pid,
        exit_price=99_000.0,
        expected_exit_price=99_000.0,
        exit_reason="target",
        fees=0.0,
    )
    live_perf = live.performance()
    assert live_perf["trades"] == 1
    approvals = _book(("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()))
    # Do not inject performance: evidence must come from the paper book.
    ks = KillSwitch(tmp_path / "killswitch.json")
    report = evaluate_gates(
        approvals=approvals,
        ledger=live,
        kill_switch=ks,
        trust_records=[],
    )
    assert _gate(report, "paper_ledger")["passed"] is False
    assert _gate(report, "paper_sample")["measured"] == 0
    assert _gate(report, "paper_sample")["passed"] is False
    assert report["ready"] is False


def test_missing_paper_expectancy_fails_closed(firm_db, tmp_path) -> None:
    approvals = _book(("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()))
    perf = _empty_perf(trades=MIN_PAPER_TRADES)
    assert "avg_return_pct" not in perf
    report = _report(firm_db, tmp_path, approvals=approvals, performance=perf)
    exp = _gate(report, "paper_expectancy")
    assert exp["passed"] is False
    assert "missing paper expectancy" in exp["detail"].lower()
    assert _gate(report, "paper_sample")["passed"] is True
    assert report["ready"] is False


def test_nonpositive_paper_expectancy_fails_closed(firm_db, tmp_path) -> None:
    approvals = _book(("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()))
    perf = _empty_perf(trades=MIN_PAPER_TRADES, avg_return_pct=0.0)
    report = _report(firm_db, tmp_path, approvals=approvals, performance=perf)
    assert _gate(report, "paper_expectancy")["passed"] is False
    assert report["ready"] is False


def test_committed_book_is_not_ready_for_live(firm_db, tmp_path) -> None:
    """Board verification: evaluate_gates()['ready'] is false on committed data."""
    before = fingerprint_approval_book()
    ks = KillSwitch(tmp_path / "killswitch.json")
    report = evaluate_gates(kill_switch=ks, trust_records=[])
    assert report["ready"] is False
    assert report["verdict"] == "STAY IN PAPER"
    assert report["ledger_mode"] == LEDGER_MODE_PAPER
    # Three certified survivors clear the 300-trade OOS floor; readiness still
    # fails on paper DD / paper sample / duration — that is the point.
    assert fingerprint_approval_book() == before


def test_committed_oos_sample_excludes_rejected_rows(firm_db, tmp_path) -> None:
    """On the real book, rejected rsi_trend rows must not inflate OOS trades."""
    raw = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    all_trades = sum(
        int(v.get("oos_trades") or 0)
        for v in raw.values()
        if isinstance(v, dict) and "approved" in v
    )
    approved_trades = sum(
        int(v.get("oos_trades") or 0)
        for v in raw.values()
        if isinstance(v, dict) and v.get("approved") is True
    )
    assert all_trades > approved_trades
    ks = KillSwitch(tmp_path / "killswitch.json")
    report = evaluate_gates(kill_switch=ks, trust_records=[])
    assert _gate(report, "walk_forward_sample")["measured"] == approved_trades
    assert _gate(report, "walk_forward_sample")["measured"] != all_trades


def test_snapshot_drawdown_is_used_when_performance_omits_the_field(
    firm_db, tmp_path
) -> None:
    """Fail-closed prefers a real snapshot DD over inventing 0%."""
    paper = Ledger(mode=LEDGER_MODE_PAPER, starting_equity=10_000.0)
    paper.record_equity(10_000.0)
    paper.record_equity(8_500.0)  # 15% from peak
    approvals = _book(("atr_channel_breakout:BTCUSDT:SHORT:4h", _approved_row()))
    ks = KillSwitch(tmp_path / "killswitch.json")
    report = evaluate_gates(
        approvals=approvals,
        ledger=paper,
        kill_switch=ks,
        performance=_empty_perf(trades=40, avg_return_pct=0.2),
        trust_records=[],
    )
    dd = _gate(report, "drawdown")
    assert dd["measured"]["paper"] == pytest.approx(15.0)
    # 15% is not < 15%, so this still fails — boundary is fail-closed.
    assert dd["passed"] is False


def test_evaluate_gates_does_not_write_approvals_or_import_writer() -> None:
    source = CHECK_GO_LIVE.read_text(encoding="utf-8")
    assert "write_approvals" not in source
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert "write_approvals" not in imported
    assert "settings.trading_mode" not in source


def test_evaluate_gates_does_not_mutate_approval_book(firm_db, tmp_path) -> None:
    before = fingerprint_approval_book()
    before_bytes = APPROVALS_PATH.read_bytes()
    ks = KillSwitch(tmp_path / "killswitch.json")
    evaluate_gates(kill_switch=ks, trust_records=[])
    assert APPROVALS_PATH.read_bytes() == before_bytes
    assert fingerprint_approval_book() == before


def test_trust_records_injection_does_not_promote(firm_db, tmp_path) -> None:
    """Even with a full agent desk, empty paper evidence keeps ready false."""
    agents = [
        SimpleNamespace(agent=f"a{i}", level=TrustLevel.ADVISOR, decisions_logged=3)
        for i in range(6)
    ]
    approvals = _book(
        (
            "atr_channel_breakout:BTCUSDT:SHORT:4h",
            _approved_row(oos_trades=400),
        ),
        (
            "atr_channel_breakout:ETHUSDT:SHORT:4h",
            _approved_row(oos_trades=400),
        ),
    )
    ks = KillSwitch(tmp_path / "killswitch.json")
    report = evaluate_gates(
        approvals=approvals,
        kill_switch=ks,
        performance=_empty_perf(),
        trust_records=agents,
    )
    assert _gate(report, "agent_track_records")["passed"] is True
    assert _gate(report, "paper_sample")["passed"] is False
    assert report["ready"] is False
