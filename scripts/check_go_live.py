"""
Evaluate every go-live / promotion gate against measured data.

The gates are the product. If any one fails, we stay in paper. This script is
what the dashboard's go-live panel and a human review both read; it never
flips TRADING_MODE itself and it never writes ``approved=true``.

§5 (docs/MAR_Trading_Firm_Review_2026-09-12.md, Board DONE): fail closed.
Rejected OOS is excluded; missing drawdown fails; a tripped kill switch fails;
paper-ledger evidence is used even when settings say LIVE.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from config.settings import PROJECT_ROOT, TradingMode, get_settings
from config.universe import APPROVALS_PATH, parse_approval_key
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
#: Board §5: promotion needs a real paper sample, not an empty blotter.
#: Matches research.significance.MIN_SAMPLE_FOR_INFERENCE.
MIN_PAPER_TRADES = 30
#: Promotion evidence is always the paper book. LIVE settings must not redirect
#: this script at live rows (review §5: "under LIVE settings, the claimed paper
#: checks read live records").
LEDGER_MODE_PAPER = TradingMode.PAPER.value


def _gate(name: str, passed: bool, detail: str, measured: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": passed, "detail": detail, "measured": measured}


def evaluate_gates(
    *,
    approvals: dict[str, dict[str, Any]] | None = None,
    ledger: Ledger | None = None,
    kill_switch: KillSwitch | None = None,
    performance: dict[str, Any] | None = None,
    trust_records: list[Any] | None = None,
) -> dict[str, Any]:
    """Return a structured report of every go-live gate.

    Optional keyword arguments exist so tests can inject evidence. Production
    callers (API, ``python scripts/check_go_live.py``, the paper runner) omit
    them. Injecting a non-paper ledger still fails ``paper_ledger``; paper
    metrics are then read from a paper ledger so live rows cannot sneak through.
    """
    init_db()
    if approvals is None:
        approvals = _load_approvals()
    constructed = Ledger(mode=LEDGER_MODE_PAPER) if ledger is None else ledger
    paper_ledger_ok = constructed.mode == LEDGER_MODE_PAPER
    # Paper evidence is always paper-mode, even if a live ledger was injected.
    evidence = constructed if paper_ledger_ok else Ledger(mode=LEDGER_MODE_PAPER)
    perf = performance if performance is not None else evidence.performance()
    kill = kill_switch if kill_switch is not None else KillSwitch()
    records = trust_records if trust_records is not None else all_records()

    approved = _approved_records(approvals)
    gates: list[dict[str, Any]] = []

    # Rejected / override OOS must not pad the promotion sample (review §5).
    oos_trades = sum(int(rec.get("oos_trades") or 0) for rec in approved)
    gates.append(
        _gate(
            "walk_forward_sample",
            oos_trades >= MIN_OOS_TRADES,
            f"{oos_trades} approved out-of-sample trades (need >= {MIN_OOS_TRADES})",
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

    portfolio_pf = _weighted_pf(approved)
    gates.append(
        _gate(
            "profit_factor",
            portfolio_pf is not None and portfolio_pf >= MIN_PROFIT_FACTOR,
            f"approved-set PF {portfolio_pf} (need >= {MIN_PROFIT_FACTOR} net of costs)",
            portfolio_pf,
        )
    )

    oos_dd, oos_dd_complete = _max_approved_oos_drawdown(approved)
    paper_dd = _paper_drawdown_pct(perf)
    dd_ok = (
        oos_dd_complete
        and oos_dd is not None
        and oos_dd < MAX_DRAWDOWN_PCT
        and paper_dd is not None
        and paper_dd < MAX_DRAWDOWN_PCT
    )
    dd_detail = (
        f"validation DD {oos_dd}%, paper DD {paper_dd}% (need < {MAX_DRAWDOWN_PCT}%)"
    )
    if not oos_dd_complete:
        dd_detail = (
            "missing approved OOS drawdown — fail closed "
            f"(validation DD {oos_dd}%, paper DD {paper_dd}%)"
        )
    elif paper_dd is None:
        dd_detail = (
            "missing paper max_drawdown_pct — fail closed "
            f"(validation DD {oos_dd}%)"
        )
    gates.append(
        _gate(
            "drawdown",
            bool(dd_ok),
            dd_detail,
            {"validation": oos_dd, "paper": paper_dd, "oos_complete": oos_dd_complete},
        )
    )

    paper_days = _paper_days()
    gates.append(
        _gate(
            "paper_duration",
            paper_days >= MIN_PAPER_DAYS,
            f"{paper_days} days of continuous paper trading (need >= {MIN_PAPER_DAYS})",
            paper_days,
        )
    )

    paper_trades = int(perf.get("trades") or 0)
    gates.append(
        _gate(
            "paper_sample",
            paper_trades >= MIN_PAPER_TRADES,
            f"{paper_trades} completed paper trades (need >= {MIN_PAPER_TRADES})",
            paper_trades,
        )
    )

    paper_expectancy = _optional_float(perf.get("avg_return_pct"))
    gates.append(
        _gate(
            "paper_expectancy",
            paper_expectancy is not None and paper_expectancy > 0.0,
            (
                f"paper expectancy {paper_expectancy}% per trade (need > 0)"
                if paper_expectancy is not None
                else "missing paper expectancy — fail closed"
            ),
            paper_expectancy,
        )
    )

    measured_slip = perf.get("measured_slippage_bps")
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

    # Kill switch (KS): a tripped halt fails promotion. Hardcoding True was
    # the review §5 fail-open. Missing/corrupt state still reads as not
    # tripped inside KillSwitch.read(); the trip flag is what this gate uses.
    ks_state = kill.read()
    ks_tripped = bool(ks_state.tripped)
    gates.append(
        _gate(
            "kill_switch",
            not ks_tripped,
            (
                "kill switch is clear"
                if not ks_tripped
                else (
                    f"kill switch TRIPPED ({ks_state.reason.value}: "
                    f"{ks_state.detail}) — fail closed"
                )
            ),
            {"tripped": ks_tripped, "reason": ks_state.reason.value},
        )
    )

    agents_ready = [
        r for r in records if r.level >= STARTING_LEVEL and r.decisions_logged > 0
    ]
    gates.append(
        _gate(
            "agent_track_records",
            len(agents_ready) >= 6,
            f"{len(agents_ready)} employees have a logged track record (need >= 6 at L1+)",
            [getattr(r, "agent", None) for r in agents_ready],
        )
    )

    approved_pairs = _approved_pairs(approvals)
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

    gates.append(
        _gate(
            "paper_ledger",
            paper_ledger_ok,
            (
                f"promotion evidence mode={constructed.mode} "
                f"(need {LEDGER_MODE_PAPER})"
            ),
            constructed.mode,
        )
    )

    passed = all(g["passed"] for g in gates)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "ready": passed,
        "verdict": "READY FOR LIVE" if passed else "STAY IN PAPER",
        "gates": gates,
        "approved_pairs": [f"{s}:{side}" for s, side in approved_pairs],
        "paper_performance": perf,
        "ledger_mode": constructed.mode,
        "evidence_mode": evidence.mode,
    }


def _load_approvals() -> dict[str, dict[str, Any]]:
    if not APPROVALS_PATH.exists():
        return {}
    raw = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if isinstance(v, dict) and "approved" in v}


def _approved_records(approvals: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Promotion set: ``approved is True`` only. Rejected and overrides are out."""
    return [
        rec
        for rec in approvals.values()
        if isinstance(rec, dict) and rec.get("approved") is True
    ]


def _approved_pairs(approvals: dict[str, dict[str, Any]]) -> list[tuple[str, str]]:
    """Unique (symbol, side) among approved=True keys. Same rule as Universe."""
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for key, rec in sorted(approvals.items()):
        if not isinstance(rec, dict) or rec.get("approved") is not True:
            continue
        parsed = parse_approval_key(key)
        if parsed is None:
            continue
        _strategy, symbol, side = parsed
        pair = (symbol, side)
        if pair not in seen:
            seen.add(pair)
            out.append(pair)
    return out


def _optional_float(value: Any) -> float | None:
    """Return a float, or None when the measurement is missing / unusable.

    ``or 0.0`` is fail-open for drawdown: a missing field becomes a perfect
    0% DD. None must stay None so the gate can fail closed.
    """
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _max_approved_oos_drawdown(
    approved: list[dict[str, Any]],
) -> tuple[float | None, bool]:
    """Max OOS DD across approved rows. Incomplete if any row is missing DD."""
    if not approved:
        return None, False
    values: list[float] = []
    for rec in approved:
        dd = _optional_float(rec.get("oos_max_drawdown_pct"))
        if dd is None:
            return None, False
        values.append(dd)
    return max(values), True


def _paper_drawdown_pct(performance: dict[str, Any]) -> float | None:
    """Paper DD from performance, else max snapshot drawdown. Missing → None."""
    measured = _optional_float(performance.get("max_drawdown_pct"))
    if measured is not None:
        return measured
    return _max_snapshot_drawdown()


def _max_snapshot_drawdown() -> float | None:
    """Worst paper-mode equity-snapshot drawdown, or None if none recorded."""
    from sqlalchemy import func, select

    from core.db import session_scope
    from core.ledger.models import EquitySnapshot

    with session_scope() as session:
        value = session.scalar(
            select(func.max(EquitySnapshot.drawdown_pct)).where(
                EquitySnapshot.mode == LEDGER_MODE_PAPER
            )
        )
    if value is None:
        return None
    return float(value)


def _regime_coverage(_approvals: dict[str, dict[str, Any]]) -> dict[str, Any]:
    # Shared report is still the source; pair-level coverage is a P1 follow-up.
    report = PROJECT_ROOT / "research" / "artifacts" / "validation_report.json"
    if not report.exists():
        return {"distinct": 0, "has_bear": False}
    payload = json.loads(report.read_text(encoding="utf-8"))
    regimes = payload.get("regimes") or {}
    by = regimes.get("by_regime") or {}
    distinct = sum(1 for names in by.values() if names)
    return {"distinct": distinct, "has_bear": bool(by.get("bear")), "by_regime": by}


def _weighted_pf(approved: list[dict[str, Any]]) -> float | None:
    if not approved:
        return None
    # Without per-trade lists here, use the minimum approved PF: the portfolio
    # cannot be healthier than its weakest cleared sleeve.
    pfs = [
        pf
        for rec in approved
        if (pf := _optional_float(rec.get("oos_profit_factor"))) is not None
    ]
    return min(pfs) if pfs else None


def _paper_days() -> int:
    from sqlalchemy import func, select

    from core.db import session_scope
    from core.ledger.models import EquitySnapshot

    with session_scope() as session:
        first = session.scalar(
            select(func.min(EquitySnapshot.recorded_at)).where(
                EquitySnapshot.mode == LEDGER_MODE_PAPER
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
