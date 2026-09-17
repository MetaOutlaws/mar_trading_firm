"""CEO LOCK revalidation kit — certified survivors only, no approval stamps.

This module is the measurement path for the 1-week Board lock
(``docs/BOARD_REMEDIATION_CALENDAR_2026-09-17.md``). It re-runs the three
``approved=true`` book rows under ``RESEARCH_VERSION`` and writes a deltas
report. It never calls ``write_approvals`` and never opens the approval book
for write.

Certified vs exploratory is a book fact, not an operator flag:

* **Certified survivors** — the three ``approved=true`` keys below. Candidates
  pending revalidation, not proof. This kit re-measures them.
* **Exploratory** — ``paper_override`` rows, rejected rows, coding-only
  sleeves, and any new family. Out of scope. Do not promote from this kit.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import fields, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np
import pandas as pd

from config.universe import APPROVALS_PATH, parse_approval_key
from core.strategy.base import SignalSide, StrategyParams
from research.costs import COST_MODEL_VERSION, DEFAULT_COSTS
from research.engine import BacktestConfig
from research.significance import DEFAULT_ITERATIONS, SignificanceReport, assess
from research.validate import DEFAULT_CRITERIA, _evaluate_gates, strategy_kit
from research.walkforward import RESEARCH_VERSION, WalkForwardResult, walk_forward

logger = logging.getLogger(__name__)

#: Walk-forward window/fill identity this kit is keyed to (F01).
KIT_RESEARCH_VERSION = RESEARCH_VERSION

#: The only sleeves this kit may re-run. Taken from the live approval book
#: (``approved: true``), matching the Board calendar candidates:
#: ATR channel SHORT 4h on BTC and ETH, doji_star_reversal SOLUSDT SHORT 1h.
#: Do not invent families. Do not add paper_override rows.
CERTIFIED_SURVIVOR_KEYS: tuple[str, ...] = (
    "atr_channel_breakout:BTCUSDT:SHORT:4h",
    "atr_channel_breakout:ETHUSDT:SHORT:4h",
    "doji_star_reversal:SOLUSDT:SHORT:1h",
)

#: Pytest files the kit depends on. Reuse existing F01/F02/F03 regressions
#: plus the unchanged PF / CI / beats-random gates. The kit file itself is
#: invoked separately so ``run_regressions`` cannot recurse into pytest.main.
REGRESSION_TARGETS: tuple[str, ...] = (
    "tests/test_walkforward.py",
    "tests/test_paper_cash_hydrate.py",
    "tests/test_f03_fee_funding.py",
    "tests/test_validate_gates.py",
)

KIT_TEST_TARGET = "tests/test_revalidation_kit.py"

#: Headline OOS fields stored on certified rows. Prior CI / window / research
#: version were never persisted on these pre-F01 stamps.
PRIOR_OOS_FIELDS: tuple[str, ...] = (
    "oos_trades",
    "oos_win_rate",
    "oos_profit_factor",
    "oos_expectancy_pct",
    "oos_max_drawdown_pct",
)


class ApprovalBookGuardError(RuntimeError):
    """The approval book changed, or the kit was asked to stamp it."""


class CertifiedInventoryError(RuntimeError):
    """The live book no longer matches the frozen certified survivor set."""


def approvals_path() -> Path:
    """Canonical approval-book path. Read-only for this kit."""
    return Path(APPROVALS_PATH)


def fingerprint_approval_book(path: Path | None = None) -> str:
    """SHA-256 of the raw approval-book bytes.

    Byte identity, not parsed JSON: whitespace, key order, and ``approved``
    stamps all change the digest. Used to fail closed if anything writes.
    """
    target = path or approvals_path()
    return hashlib.sha256(target.read_bytes()).hexdigest()


def load_approval_book(path: Path | None = None) -> dict[str, Any]:
    """Parse the approval book. Never writes."""
    target = path or approvals_path()
    return json.loads(target.read_text(encoding="utf-8"))


def iter_strategy_records(payload: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    """Yield (key, record) for real strategy rows, skipping ``_`` metadata."""
    for key, value in payload.items():
        if not key or key.startswith("_") or not isinstance(value, dict):
            continue
        if parse_approval_key(key) is None:
            continue
        yield key, value


def certified_records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """``approved is True`` rows. These are the only certified survivors."""
    out: dict[str, dict[str, Any]] = {}
    for key, record in iter_strategy_records(payload):
        if record.get("approved") is True:
            out[key] = record
    return out


def exploratory_records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Paper-override (not approved) and every other non-certified row.

    Overrides are isolated experiments. They are listed for the Board and
    never re-run by this kit.
    """
    certified = set(certified_records(payload))
    out: dict[str, dict[str, Any]] = {}
    for key, record in iter_strategy_records(payload):
        if key in certified:
            continue
        if record.get("paper_override") is True or record.get("approved") is not True:
            out[key] = record
    return out


def paper_override_keys(payload: dict[str, Any]) -> list[str]:
    """Operator paper vetoes — exploratory, not certified."""
    keys = [
        key
        for key, record in iter_strategy_records(payload)
        if record.get("paper_override") is True and record.get("approved") is not True
    ]
    return sorted(keys)


def assert_certified_inventory(payload: dict[str, Any]) -> list[str]:
    """Require the live book to contain exactly the frozen certified set.

    Extra ``approved=true`` keys would be a new promotion. Missing keys would
    mean the book was rewritten. Either way the kit fails closed.
    """
    found = set(certified_records(payload))
    expected = set(CERTIFIED_SURVIVOR_KEYS)
    extra = sorted(found - expected)
    missing = sorted(expected - found)
    if extra or missing:
        raise CertifiedInventoryError(
            "Certified inventory mismatch "
            f"(extra={extra or 'none'}, missing={missing or 'none'}). "
            "Kit refuses to re-run or stamp. Protect the approval book."
        )
    return list(CERTIFIED_SURVIVOR_KEYS)


def assert_not_stamping() -> None:
    """Static guard: this module must not grow an approvals writer."""
    # Imported names in this file. ``write_approvals`` is intentionally absent.
    from research import revalidation as self_mod

    banned = ("write_approvals",)
    exported = set(dir(self_mod))
    for name in banned:
        if name in exported:
            raise ApprovalBookGuardError(
                f"revalidation kit must not expose {name}; fail closed"
            )


def pin_certified_params(strategy_name: str, side: SignalSide, stored: dict[str, Any]) -> StrategyParams:
    """Rebuild the sleeve params that the book actually certified.

    Revalidation is not a new grid search. Empty walk-forward ``search_space``
    then evaluates these params out of sample under F01 windows.
    """
    _factory, base, _space = strategy_kit(strategy_name, side)
    allowed = {item.name for item in fields(base)}
    updates: dict[str, Any] = {}
    raw = stored.get("params") if isinstance(stored.get("params"), dict) else stored
    for key, value in dict(raw or {}).items():
        if key not in allowed or key == "side":
            continue
        updates[key] = value
    updates["side"] = side
    return replace(base, **updates)


def prior_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    """Stored ``oos_*`` plus the certified param set. CI was never persisted."""
    return {
        "approved_flag": record.get("approved") is True,
        "params": dict(record.get("params") or {}),
        "timeframe": record.get("timeframe"),
        "validated_at": record.get("validated_at"),
        "research_version": record.get("research_version"),
        "oos_trades": record.get("oos_trades"),
        "oos_win_rate": record.get("oos_win_rate"),
        "oos_profit_factor": record.get("oos_profit_factor"),
        "oos_expectancy_pct": record.get("oos_expectancy_pct"),
        "oos_max_drawdown_pct": record.get("oos_max_drawdown_pct"),
        "ci95_low_pct": None,
        "ci95_high_pct": None,
        "beats_random": None,
        "permutation_p_value": None,
        "oos_entry_windows": None,
        "note": (
            "Prior certified rows predate RESEARCH_VERSION; CI and fold windows "
            "were not stored. Compare oos_* only, and treat windowing as F01-new."
        ),
    }


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def compute_metric_deltas(prior: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Numeric deltas for PF / trades / expectancy / DD / win rate.

    ``None`` on either side yields a null delta rather than inventing zero.
    """
    deltas: dict[str, Any] = {}
    for field_name in PRIOR_OOS_FIELDS:
        before = _finite_or_none(prior.get(field_name))
        after = _finite_or_none(current.get(field_name))
        if before is None or after is None:
            deltas[field_name] = None
        else:
            deltas[field_name] = round(after - before, 6)
    deltas["ci95_low_pct"] = None  # prior CI unknown
    deltas["beats_random"] = None
    return deltas


def current_snapshot(
    wf: WalkForwardResult,
    significance: SignificanceReport | None,
    failures: list[str],
    params: dict[str, Any],
) -> dict[str, Any]:
    """New OOS evidence under ``KIT_RESEARCH_VERSION``. Not an approval record."""
    bootstrap = significance.bootstrap if significance else None
    permutation = significance.permutation if significance else None
    pf = wf.oos_profit_factor
    if np.isfinite(pf):
        pf_out: float | str | None = round(pf, 3)
    elif pf == float("inf"):
        pf_out = "inf"
    else:
        pf_out = None
    windows = [fold.summary()["oos_entry_window"] for fold in wf.folds]
    return {
        "approved_flag": False,  # kit never stamps; this is a measurement
        "params": params,
        "research_version": wf.research_version,
        "oos_trades": wf.total_oos_trades,
        "oos_win_rate": round(wf.oos_win_rate, 2),
        "oos_profit_factor": pf_out,
        "oos_expectancy_pct": round(wf.oos_expectancy_pct, 4),
        "oos_max_drawdown_pct": round(wf.oos_max_drawdown_pct, 2),
        "profitable_fold_ratio": round(wf.profitable_fold_ratio, 1),
        "folds": len(wf.folds),
        "valid_folds": sum(1 for fold in wf.folds if fold.is_valid),
        "ci95_low_pct": (
            round(bootstrap.ci_low, 4) if bootstrap is not None else None
        ),
        "ci95_high_pct": (
            round(bootstrap.ci_high, 4) if bootstrap is not None else None
        ),
        "ci_excludes_zero": (
            bool(bootstrap.is_significant) if bootstrap is not None else None
        ),
        "beats_random": (
            bool(permutation.beats_random) if permutation is not None else None
        ),
        "permutation_p_value": (
            round(permutation.p_value, 4) if permutation is not None else None
        ),
        "oos_entry_windows": windows,
        "gate_failures": list(failures),
        "still_clears_gates": not failures,
        "walk_forward": wf.summary(),
        "significance": significance.summary() if significance else None,
    }


def blocked_survivor_row(key: str, record: dict[str, Any], error: str) -> dict[str, Any]:
    """Report row when candles cannot be loaded. Still does not stamp."""
    parsed = parse_approval_key(key)
    strategy_name, symbol, side_label = parsed if parsed else ("", "", "")
    prior = prior_snapshot(record)
    current = {
        "approved_flag": False,
        "params": dict(record.get("params") or {}),
        "research_version": KIT_RESEARCH_VERSION,
        "error": error,
        "gate_failures": [error],
        "still_clears_gates": False,
        "oos_trades": None,
        "oos_profit_factor": None,
        "oos_expectancy_pct": None,
        "oos_win_rate": None,
        "oos_max_drawdown_pct": None,
        "ci95_low_pct": None,
        "ci95_high_pct": None,
        "ci_excludes_zero": None,
        "beats_random": None,
        "permutation_p_value": None,
        "oos_entry_windows": None,
        "folds": None,
    }
    return {
        "key": key,
        "classification": "certified_survivor",
        "strategy": strategy_name or record.get("strategy"),
        "symbol": symbol,
        "side": side_label,
        "timeframe": record.get("timeframe"),
        "research_version": KIT_RESEARCH_VERSION,
        "promotion": False,
        "would_write_approved": False,
        "error": error,
        "prior": prior,
        "current": current,
        "deltas": compute_metric_deltas(prior, current),
    }


def revalidate_survivor(
    key: str,
    record: dict[str, Any],
    candles: pd.DataFrame,
    *,
    config: BacktestConfig | None = None,
    funding: Any = None,
    train_days: int = 180,
    test_days: int = 60,
    warmup_bars: int = 300,
    significance_iterations: int = DEFAULT_ITERATIONS,
) -> dict[str, Any]:
    """Re-measure one certified survivor. Does not stamp the book.

    Uses the stored certified params with an empty search grid so this cannot
    become a new promotion / re-optimisation.
    """
    if key not in CERTIFIED_SURVIVOR_KEYS:
        raise CertifiedInventoryError(
            f"{key} is not a certified survivor; kit refuses exploratory re-runs"
        )
    parsed = parse_approval_key(key)
    if parsed is None:
        raise CertifiedInventoryError(f"unparseable approval key {key!r}")
    strategy_name, symbol, side_label = parsed
    side = SignalSide(side_label)
    timeframe = str(record.get("timeframe") or key.rsplit(":", 1)[-1])
    params = pin_certified_params(strategy_name, side, record)
    factory, _base, _space = strategy_kit(strategy_name, side)
    cfg = config or BacktestConfig(
        initial_capital=10_000.0,
        position_fraction=0.10,
        compound=True,
        pessimistic_intrabar=True,
        costs=DEFAULT_COSTS.for_symbol(symbol),
    )

    error: str | None = None
    wf: WalkForwardResult | None = None
    significance: SignificanceReport | None = None
    failures: list[str] = []
    try:
        # Empty search_space: evaluate certified params only (not a new grid).
        wf = walk_forward(
            symbol=symbol,
            candles=candles,
            strategy_factory=factory,
            base_params=params,
            search_space={},
            config=cfg,
            train_days=train_days,
            test_days=test_days,
            warmup_bars=warmup_bars,
            funding=funding,
        )
        significance = assess(
            wf.oos_trades,
            candles=candles,
            position_fraction=cfg.position_fraction,
            iterations=significance_iterations,
        )
        failures = _evaluate_gates(wf, significance, DEFAULT_CRITERIA)
    except Exception as exc:  # surface in the report; never stamp
        logger.exception("Revalidation failed for %s", key)
        error = f"{type(exc).__name__}: {exc}"

    prior = prior_snapshot(record)
    if wf is None:
        current = {
            "approved_flag": False,
            "params": dict(record.get("params") or {}),
            "research_version": KIT_RESEARCH_VERSION,
            "error": error,
            "gate_failures": [error] if error else ["walk-forward produced no result"],
            "still_clears_gates": False,
        }
        deltas = compute_metric_deltas(prior, current)
    else:
        current = current_snapshot(wf, significance, failures, params.to_dict())
        if error:
            current["error"] = error
            current["still_clears_gates"] = False
        deltas = compute_metric_deltas(prior, current)

    return {
        "key": key,
        "classification": "certified_survivor",
        "strategy": strategy_name,
        "symbol": symbol,
        "side": side_label,
        "timeframe": timeframe,
        "research_version": KIT_RESEARCH_VERSION,
        "cost_model_version": COST_MODEL_VERSION,
        "search_space": {},
        "promotion": False,
        "would_write_approved": False,
        "prior": prior,
        "current": current,
        "deltas": deltas,
        "error": error,
    }


def run_regressions(
    extra: Sequence[str] = (),
    *,
    pytest_main: Callable[..., int] | None = None,
) -> dict[str, Any]:
    """Run the F01/F02/F03 (+ gate) pytest files the kit depends on."""
    import pytest

    runner = pytest_main or pytest.main
    targets = list(REGRESSION_TARGETS) + [str(item) for item in extra]
    code = int(runner(["-q", *targets]))
    return {
        "exit_code": code,
        "ok": code == 0,
        "targets": targets,
    }


class ApprovalBookLock:
    """Fingerprint the approval book around a kit run; fail if it changes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or approvals_path()
        self.before: str = ""
        self.after: str = ""

    def __enter__(self) -> "ApprovalBookLock":
        self.before = fingerprint_approval_book(self.path)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.after = fingerprint_approval_book(self.path)
        if self.after != self.before:
            raise ApprovalBookGuardError(
                "FAIL CLOSED: config/approved_strategies.json changed during "
                f"revalidation (before={self.before} after={self.after}). "
                "Kit does not stamp approvals and will not rewrite the book."
            )


def empty_report_shell(*, fingerprint: str, inventory_ok: bool) -> dict[str, Any]:
    """Board-facing report skeleton. ``promotion_blocked`` is always true."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "generated_at": now,
        "kit": "revalidation",
        "research_version": KIT_RESEARCH_VERSION,
        "cost_model_version": COST_MODEL_VERSION,
        "promotion_blocked": True,
        "would_write_approved": False,
        "live": "off",
        "pipeline_auto_advance": "off",
        "job_133": "not_revived",
        "approval_book": str(approvals_path()),
        "approval_book_sha256": fingerprint,
        "approval_book_unchanged": True,
        "certified_survivor_keys": list(CERTIFIED_SURVIVOR_KEYS),
        "inventory_ok": inventory_ok,
        "regressions": None,
        "survivors": [],
        "exploratory_skipped": [],
        "kit_green": False,
        "board": {
            "freeze_new_approved_true": True,
            "eng_self_unfreeze": False,
            "how_to_use": (
                "CEO/Board lifts the freeze only after reading this report: "
                "book fingerprint unchanged, F01–F03 regressions green, and "
                "each certified survivor still clears PF≥1.15 / CI / "
                "beats-random under wf-f01-oos-window-v1. Eng never stamps "
                "approved=true from this kit."
            ),
        },
    }


def finalise_report(report: dict[str, Any]) -> dict[str, Any]:
    """Compute ``kit_green`` from regressions + survivor gate results."""
    regressions = report.get("regressions") or {}
    survivors = report.get("survivors") or []
    ran = [row for row in survivors if row.get("classification") == "certified_survivor"]
    all_ran = len(ran) == len(CERTIFIED_SURVIVOR_KEYS) and all(
        not row.get("error") for row in ran
    )
    all_clear = all(
        bool((row.get("current") or {}).get("still_clears_gates")) for row in ran
    )
    regressions_ran_and_passed = bool(
        regressions.get("ok")
        and not regressions.get("skipped")
        and regressions.get("targets")
    )
    report["kit_green"] = bool(
        report.get("inventory_ok")
        and report.get("approval_book_unchanged")
        and regressions_ran_and_passed
        and all_ran
        and all_clear
    )
    report["survivors_ran"] = len(ran)
    report["survivors_clear_gates"] = sum(
        1 for row in ran if (row.get("current") or {}).get("still_clears_gates")
    )
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """Human report for Board review. Not an approval stamp."""
    green = "GREEN" if report.get("kit_green") else "NOT GREEN"
    lines = [
        "# Revalidation kit report",
        "",
        f"- Generated: `{report.get('generated_at')}`",
        f"- RESEARCH_VERSION: `{report.get('research_version')}`",
        f"- Cost model: `{report.get('cost_model_version')}`",
        f"- Kit verdict: **{green}**",
        f"- Promotion blocked: `{report.get('promotion_blocked')}` "
        "(this report never writes `approved=true`)",
        f"- Approval book SHA-256: `{report.get('approval_book_sha256')}`",
        f"- Book unchanged: `{report.get('approval_book_unchanged')}`",
        f"- Inventory ok: `{report.get('inventory_ok')}`",
        "",
        "## Certified vs exploratory",
        "",
        "Certified survivors (re-run by this kit):",
        "",
    ]
    for key in report.get("certified_survivor_keys") or []:
        lines.append(f"- `{key}`")
    skipped = report.get("exploratory_skipped") or []
    lines.extend(
        [
            "",
            "Exploratory (not re-run): paper_override rows, rejected rows, "
            "coding-only sleeves, new families.",
            "",
        ]
    )
    if skipped:
        lines.append("Paper-override keys skipped:")
        lines.append("")
        for key in skipped:
            lines.append(f"- `{key}`")
        lines.append("")
    regressions = report.get("regressions") or {}
    lines.extend(
        [
            "## F01–F03 regressions",
            "",
            f"- ok: `{regressions.get('ok')}`",
            f"- exit_code: `{regressions.get('exit_code')}`",
            f"- targets: `{', '.join(regressions.get('targets') or [])}`",
            "",
            "## Survivor deltas vs stored `oos_*`",
            "",
        ]
    )
    for row in report.get("survivors") or []:
        prior = row.get("prior") or {}
        current = row.get("current") or {}
        deltas = row.get("deltas") or {}
        lines.append(f"### `{row.get('key')}`")
        lines.append("")
        if row.get("error"):
            lines.append(f"- **error:** {row['error']}")
        lines.append(
            f"- still clears PF≥1.15 / CI / beats-random: "
            f"`{current.get('still_clears_gates')}`"
        )
        lines.append(
            f"- trades: prior `{prior.get('oos_trades')}` → "
            f"current `{current.get('oos_trades')}` "
            f"(Δ `{deltas.get('oos_trades')}`)"
        )
        lines.append(
            f"- PF: prior `{prior.get('oos_profit_factor')}` → "
            f"current `{current.get('oos_profit_factor')}` "
            f"(Δ `{deltas.get('oos_profit_factor')}`)"
        )
        lines.append(
            f"- expectancy %: prior `{prior.get('oos_expectancy_pct')}` → "
            f"current `{current.get('oos_expectancy_pct')}` "
            f"(Δ `{deltas.get('oos_expectancy_pct')}`)"
        )
        lines.append(
            f"- win rate: prior `{prior.get('oos_win_rate')}` → "
            f"current `{current.get('oos_win_rate')}` "
            f"(Δ `{deltas.get('oos_win_rate')}`)"
        )
        lines.append(
            f"- max DD %: prior `{prior.get('oos_max_drawdown_pct')}` → "
            f"current `{current.get('oos_max_drawdown_pct')}` "
            f"(Δ `{deltas.get('oos_max_drawdown_pct')}`)"
        )
        lines.append(
            f"- CI 95%: prior unknown → "
            f"`[{current.get('ci95_low_pct')}, {current.get('ci95_high_pct')}]` "
            f"(excludes zero: `{current.get('ci_excludes_zero')}`)"
        )
        lines.append(
            f"- beats-random: prior unknown → `{current.get('beats_random')}` "
            f"(p=`{current.get('permutation_p_value')}`)"
        )
        lines.append(
            f"- window: prior `research_version={prior.get('research_version')}` → "
            f"current `{current.get('research_version')}` "
            f"half-open `[test_start, test_end)` (F01); {current.get('folds')} folds"
        )
        lines.append(f"- would_write_approved: `{row.get('would_write_approved')}`")
        lines.append("")
    board = report.get("board") or {}
    lines.extend(
        [
            "## How CEO / Board uses this to decide freeze lift",
            "",
            str(board.get("how_to_use") or ""),
            "",
            "Checklist:",
            "",
            "1. `approval_book_unchanged` is true (12+56 / book contents protected).",
            "2. F01 OOS window, F02 paper cash, F03 fees/funding regressions are green.",
            "3. Each certified survivor was re-run under `wf-f01-oos-window-v1`.",
            "4. Read PF / CI / trades / window deltas. A worse PF or a CI that "
            "includes zero is evidence against lifting the freeze.",
            "5. If `kit_green` is true, the Board *may* lift the freeze. Eng does "
            "not self-unfreeze and this kit does not stamp `approved=true`.",
            "6. If `kit_green` is false, the freeze stays. No new promotions.",
            "",
            "*Not a go-live recommendation. Live stays off. Auto-advance stays off.*",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report_artifacts(report: dict[str, Any], directory: Path) -> tuple[Path, Path]:
    """Persist JSON + markdown under ``research/artifacts/`` (gitignored)."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = directory / f"revalidation_kit_{stamp}.json"
    md_path = directory / f"revalidation_kit_{stamp}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    latest_json = directory / "revalidation_kit_latest.json"
    latest_md = directory / "revalidation_kit_latest.md"
    latest_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
    latest_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    return json_path, md_path
