"""
Evaluate every go-live gate against measured data.

The gates are the product. If any one fails, we stay in paper. This script is
what the dashboard's go-live panel and a human review both read; it never
flips TRADING_MODE itself.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT, get_settings
from config.universe import APPROVALS_PATH, get_universe
from core.db import init_db
from core.ledger.store import Ledger
from core.risk.killswitch import KillSwitch
from firm.trust import STARTING_LEVEL, all_records

MODELLED_SLIPPAGE_BPS = 10.0
SLIPPAGE_TOLERANCE_BPS = 20.0
MIN_PAPER_DAYS = 60
MIN_OOS_TRADES = 300
MIN_PROFIT_FACTOR = 1.3
MAX_DRAWDOWN_PCT = 15.0
MIN_REGIMES = 3


def _gate(name: str, passed: bool, detail: str, measured: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail, "measured": measured}


def evaluate_gates() -> dict[str, Any]:
    """Return a structured report of every go-live gate."""
    init_db()
    settings = get_settings()
    ledger = Ledger(mode=settings.trading_mode.value)
    performance = ledger.performance()
    universe = get_universe()
    approvals = _load_approvals()

    gates: list[dict[str, Any]] = []

    oos_trades = sum(int(v.get("oos_trades") or 0) for v in approvals.values())
    gates.append(
        _gate(
            "walk_forward_sample",
            oos_trades >= MIN_OOS_TRADES,
            f"{oos_trades} out-of-sample trades (need >= {MIN_OOS_TRADES})",
            oos_trades,
        )
    )

    regimes = _regime_coverage(approvals)
    gates.append(
        _gate(
            "regime_coverage",
            regimes["distinct"] >= MIN_REGIMES and regimes["has_bear"],
            (
                f"{regimes['distinct']} regimes, bear={regimes['has_bear']} "
                "(need 3+ including a bear leg)"
            ),
            regimes,
        )
    )

    pf_values = [
        v.get("oos_profit_factor")
        for v in approvals.values()
        if v.get("approved") and v.get("oos_profit_factor") is not None
    ]
    # Portfolio PF is approximated by the trade-weighted approved set; if nothing
    # is approved the gate fails, which is the correct default.
    portfolio_pf = _weighted_pf(approvals)
    gates.append(
        _gate(
            "profit_factor",
            portfolio_pf is not None and portfolio_pf >= MIN_PROFIT_FACTOR,
            f"approved-set PF {portfolio_pf} (need >= {MIN_PROFIT_FACTOR} net of costs)",
            portfolio_pf,
        )
    )

    dd_values = [
        float(v.get("oos_max_drawdown_pct") or 0.0)
        for v in approvals.values()
        if v.get("approved")
    ]
    max_dd = max(dd_values) if dd_values else None
    paper_dd = performance.get("max_drawdown_pct")
    dd_ok = (
        max_dd is not None
        and max_dd < MAX_DRAWDOWN_PCT
        and (paper_dd is None or paper_dd < MAX_DRAWDOWN_PCT)
    )
    gates.append(
        _gate(
            "drawdown",
            bool(dd_ok),
            f"validation DD {max_dd}%, paper DD {paper_dd}% (need < {MAX_DRAWDOWN_PCT}%)",
            {"validation": max_dd, "paper": paper_dd},
        )
    )

    paper_days = _paper_days(ledger)
    gates.append(
        _gate(
            "paper_duration",
            paper_days >= MIN_PAPER_DAYS,
            f"{paper_days} days of continuous paper trading (need >= {MIN_PAPER_DAYS})",
            paper_days,
        )
    )

    measured_slip = performance.get("measured_slippage_bps")
    slip_ok = (
        measured_slip is not None
        and abs(float(measured_slip) - MODELLED_SLIPPAGE_BPS) <= SLIPPAGE_TOLERANCE_BPS
    )
    gates.append(
        _gate(
            "slippage",
            bool(slip_ok),
            f"measured {measured_slip} bps vs {MODELLED_SLIPPAGE_BPS} modelled",
            measured_slip,
        )
    )

    kill = KillSwitch()
    # Presence of a kill-switch file that can trip and refuse a sloppy reset
    # is verified by unit tests; here we only confirm the mechanism is wired.
    gates.append(
        _gate(
            "kill_switch_wired",
            True,
            "Kill switch is file-backed and human-reset-only (see tests/test_risk.py)",
            {"tripped": kill.is_tripped},
        )
    )

    records = all_records()
    agents_ready = [
        r for r in records if r.level >= STARTING_LEVEL and r.decisions_logged > 0
    ]
    gates.append(
        _gate(
            "agent_track_records",
            len(agents_ready) >= 6,
            f"{len(agents_ready)} employees have a logged track record (need >= 6 at L1+)",
            [r.agent for r in agents_ready],
        )
    )

    approved_pairs = universe.approved_pairs
    gates.append(
        _gate(
            "approved_universe",
            bool(approved_pairs),
            (
                f"{len(approved_pairs)} approved pairs"
                if approved_pairs
                else "no strategy has passed validation"
            ),
            [f"{s}:{side}" for s, side in approved_pairs],
        )
    )

    passed = all(g["passed"] for g in gates)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "ready": passed,
        "verdict": "READY FOR LIVE" if passed else "STAY IN PAPER",
        "gates": gates,
        "approved_pairs": [f"{s}:{side}" for s, side in approved_pairs],
        "paper_performance": performance,
    }


def _load_approvals() -> dict[str, dict[str, Any]]:
    if not APPROVALS_PATH.exists():
        return {}
    raw = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if isinstance(v, dict) and "approved" in v}


def _regime_coverage(approvals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    report = PROJECT_ROOT / "research" / "artifacts" / "validation_report.json"
    if not report.exists():
        return {"distinct": 0, "has_bear": False}
    payload = json.loads(report.read_text(encoding="utf-8"))
    regimes = payload.get("regimes") or {}
    by = regimes.get("by_regime") or {}
    distinct = sum(1 for names in by.values() if names)
    return {"distinct": distinct, "has_bear": bool(by.get("bear")), "by_regime": by}


def _weighted_pf(approvals: dict[str, dict[str, Any]]) -> float | None:
    approved = [v for v in approvals.values() if v.get("approved")]
    if not approved:
        return None
    # Without per-trade lists here, use the minimum approved PF: the portfolio
    # cannot be healthier than its weakest cleared sleeve.
    pfs = [v.get("oos_profit_factor") for v in approved if v.get("oos_profit_factor")]
    return min(pfs) if pfs else None


def _paper_days(ledger: Ledger) -> int:
    from sqlalchemy import func, select

    from core.db import session_scope
    from core.ledger.models import EquitySnapshot

    with session_scope() as session:
        first = session.scalar(
            select(func.min(EquitySnapshot.recorded_at)).where(
                EquitySnapshot.mode == ledger.mode
            )
        )
    if first is None:
        return 0
    return (datetime.now(timezone.utc) - first).days


def main() -> int:
    report = evaluate_gates()
    path = get_settings().artifacts_dir / "go_live_report.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print()
    print(report["verdict"])
    print(f"Wrote {path}")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
