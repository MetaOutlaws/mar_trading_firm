"""Revalidation kit: certified survivors only, no approval stamps.

Guards the CEO LOCK kit (docs/REVALIDATION_KIT.md):
- inventory is the three approved=true book keys, not overrides
- F01/F02/F03 pytest files are the wired regressions
- deltas vs stored oos_* do not call write_approvals
- the approval book fingerprint is unchanged
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from config.universe import APPROVALS_PATH
from core.strategy.atr_channel_breakout import AtrChannelParams
from core.strategy.base import SignalSide
from core.strategy.doji_star_reversal import DojiStarParams
from research.costs import FRICTIONLESS
from research.engine import BacktestConfig
from research.revalidation import (
    CERTIFIED_SURVIVOR_KEYS,
    KIT_RESEARCH_VERSION,
    REGRESSION_TARGETS,
    ApprovalBookGuardError,
    ApprovalBookLock,
    CertifiedInventoryError,
    assert_certified_inventory,
    assert_not_stamping,
    certified_records,
    compute_metric_deltas,
    empty_report_shell,
    finalise_report,
    fingerprint_approval_book,
    load_approval_book,
    paper_override_keys,
    pin_certified_params,
    prior_snapshot,
    render_markdown,
    revalidate_survivor,
    run_regressions,
)
from research.walkforward import RESEARCH_VERSION
from research.validate import write_approvals
from tests.test_walkforward import _downtrend_hourly


REPO_ROOT = Path(__file__).resolve().parent.parent
BOOK = REPO_ROOT / "config" / "approved_strategies.json"


def _frictionless() -> BacktestConfig:
    return BacktestConfig(
        initial_capital=10_000.0,
        position_fraction=0.10,
        compound=False,
        costs=FRICTIONLESS,
    )


def test_kit_is_keyed_to_f01_research_version() -> None:
    assert RESEARCH_VERSION == "wf-f01-oos-window-v1"
    assert KIT_RESEARCH_VERSION == RESEARCH_VERSION


def test_live_book_certified_set_matches_frozen_keys() -> None:
    """Do not invent families. The book is the source; the freeze list must match."""
    payload = load_approval_book()
    found = set(certified_records(payload))
    assert found == set(CERTIFIED_SURVIVOR_KEYS)
    assert CERTIFIED_SURVIVOR_KEYS == (
        "atr_channel_breakout:BTCUSDT:SHORT:4h",
        "atr_channel_breakout:ETHUSDT:SHORT:4h",
        "doji_star_reversal:SOLUSDT:SHORT:1h",
    )
    assert_certified_inventory(payload)
    # Exploratory paper overrides exist and must not be in the certified set.
    overrides = paper_override_keys(payload)
    assert len(overrides) == 4
    assert set(overrides).isdisjoint(CERTIFIED_SURVIVOR_KEYS)


def test_regression_targets_reuse_f01_f02_f03_and_hard_gates() -> None:
    names = " ".join(REGRESSION_TARGETS)
    assert "test_walkforward.py" in names
    assert "test_paper_cash_hydrate.py" in names
    assert "test_f03_fee_funding.py" in names
    assert "test_validate_gates.py" in names
    for rel in REGRESSION_TARGETS:
        path = REPO_ROOT / rel
        assert path.is_file(), rel
        text = path.read_text(encoding="utf-8")
        if rel.endswith("test_walkforward.py"):
            assert "wf-f01-oos-window-v1" in text
        if rel.endswith("test_paper_cash_hydrate.py"):
            assert "F02" in text
        if rel.endswith("test_f03_fee_funding.py"):
            assert "F03" in text
        if rel.endswith("test_validate_gates.py"):
            assert "1.15" in text
            assert "beats random" in text.lower() or "beats_random" in text


def test_revalidation_module_does_not_import_write_approvals() -> None:
    """Fail closed: the kit must not grow an approvals writer."""
    source = (REPO_ROOT / "research" / "revalidation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert "write_approvals" not in imported
    assert_not_stamping()
    # The writer still exists on the validation module; the kit must not call it.
    assert callable(write_approvals)


def test_assert_certified_inventory_rejects_extra_approved() -> None:
    payload = json.loads(json.dumps(load_approval_book()))
    payload["new_family:BTCUSDT:LONG:4h"] = {
        "approved": True,
        "strategy": "new_family",
        "timeframe": "4h",
    }
    with pytest.raises(CertifiedInventoryError, match="extra"):
        assert_certified_inventory(payload)


def test_assert_certified_inventory_rejects_missing_approved() -> None:
    payload = json.loads(json.dumps(load_approval_book()))
    payload[CERTIFIED_SURVIVOR_KEYS[0]]["approved"] = False
    with pytest.raises(CertifiedInventoryError, match="missing"):
        assert_certified_inventory(payload)


def test_revalidate_refuses_exploratory_keys() -> None:
    candles = _downtrend_hourly(400)
    with pytest.raises(CertifiedInventoryError, match="not a certified survivor"):
        revalidate_survivor(
            "mama_fama_cross:BTCUSDT:SHORT:4h",
            {"approved": False, "paper_override": True, "params": {}},
            candles,
        )


def test_pin_certified_params_uses_book_not_family_defaults() -> None:
    book = load_approval_book()
    btc = book["atr_channel_breakout:BTCUSDT:SHORT:4h"]
    params = pin_certified_params("atr_channel_breakout", SignalSide.SHORT, btc)
    assert isinstance(params, AtrChannelParams)
    assert params.side is SignalSide.SHORT
    assert params.atr_k == 2.0
    assert params.take_profit_pct == 0.05
    assert params.stop_loss_pct == 0.03
    sol = book["doji_star_reversal:SOLUSDT:SHORT:1h"]
    doji = pin_certified_params("doji_star_reversal", SignalSide.SHORT, sol)
    assert isinstance(doji, DojiStarParams)
    assert doji.run_bars == 3
    assert doji.take_profit_pct == 0.05
    assert doji.stop_loss_pct == 0.03


def test_compute_metric_deltas_and_prior_ci_unknown() -> None:
    prior = {
        "oos_trades": 284,
        "oos_win_rate": 48.94,
        "oos_profit_factor": 1.447,
        "oos_expectancy_pct": 0.5235,
        "oos_max_drawdown_pct": 2.27,
        "ci95_low_pct": None,
    }
    current = {
        "oos_trades": 200,
        "oos_win_rate": 47.0,
        "oos_profit_factor": 1.20,
        "oos_expectancy_pct": 0.40,
        "oos_max_drawdown_pct": 3.0,
        "ci95_low_pct": 0.01,
    }
    deltas = compute_metric_deltas(prior, current)
    assert deltas["oos_trades"] == pytest.approx(-84)
    assert deltas["oos_profit_factor"] == pytest.approx(-0.247)
    assert deltas["ci95_low_pct"] is None
    assert deltas["beats_random"] is None
    snap = prior_snapshot({"approved": True, "oos_trades": 10, "params": {"atr_k": 2.0}})
    assert snap["ci95_low_pct"] is None
    assert snap["oos_entry_windows"] is None


def test_approval_book_lock_fails_closed_on_mutation(tmp_path) -> None:
    path = tmp_path / "approved_strategies.json"
    path.write_text('{"_verdict": "REJECTED"}', encoding="utf-8")
    with pytest.raises(ApprovalBookGuardError, match="FAIL CLOSED"):
        with ApprovalBookLock(path):
            path.write_text('{"_verdict": "TAMPERED"}', encoding="utf-8")


def test_survivor_rerun_writes_deltas_without_stamping(monkeypatch) -> None:
    """Synthetic ATR BTC SHORT path: report in, book bytes out unchanged."""
    book_bytes = BOOK.read_bytes()
    digest = hashlib.sha256(book_bytes).hexdigest()
    payload = json.loads(book_bytes)
    record = payload["atr_channel_breakout:BTCUSDT:SHORT:4h"]
    candles = _downtrend_hourly(40 * 24)

    def _boom(*_args, **_kwargs):
        raise AssertionError("write_approvals must not run during revalidation")

    monkeypatch.setattr("research.validate.write_approvals", _boom)

    row = revalidate_survivor(
        "atr_channel_breakout:BTCUSDT:SHORT:4h",
        record,
        candles,
        config=_frictionless(),
        train_days=10,
        test_days=5,
        warmup_bars=80,
        significance_iterations=64,
    )
    assert row["would_write_approved"] is False
    assert row["promotion"] is False
    assert row["search_space"] == {}
    assert row["research_version"] == "wf-f01-oos-window-v1"
    assert row["prior"]["oos_profit_factor"] == 1.447
    assert row["prior"]["oos_trades"] == 284
    assert "oos_profit_factor" in row["deltas"]
    assert "oos_trades" in row["deltas"]
    current = row["current"]
    assert current["approved_flag"] is False
    assert current["research_version"] == "wf-f01-oos-window-v1"
    assert current["folds"] >= 1
    assert isinstance(current["oos_entry_windows"], list)
    assert current["oos_entry_windows"], "F01 windows must be reported"
    assert BOOK.read_bytes() == book_bytes
    assert fingerprint_approval_book() == digest
    assert APPROVALS_PATH.resolve() == BOOK.resolve()


def test_run_regressions_invokes_pytest_on_f01_f02_f03_only() -> None:
    seen: list[list[str]] = []

    def fake_main(args):
        seen.append(list(args))
        return 0

    result = run_regressions(pytest_main=fake_main)
    assert result["ok"] is True
    assert result["exit_code"] == 0
    assert seen[0][0] == "-q"
    assert seen[0][1:] == list(REGRESSION_TARGETS)


def test_finalise_report_and_markdown_explain_freeze_lift() -> None:
    report = empty_report_shell(fingerprint="abc", inventory_ok=True)
    report["approval_book_unchanged"] = True
    report["regressions"] = {
        "ok": True,
        "skipped": False,
        "targets": list(REGRESSION_TARGETS),
    }
    report["survivors"] = [
        {
            "key": key,
            "classification": "certified_survivor",
            "error": None,
            "would_write_approved": False,
            "prior": {
                "oos_profit_factor": 1.4,
                "oos_trades": 100,
                "research_version": None,
            },
            "current": {
                "still_clears_gates": True,
                "oos_profit_factor": 1.3,
                "oos_trades": 90,
                "research_version": KIT_RESEARCH_VERSION,
                "ci95_low_pct": 0.01,
                "ci95_high_pct": 0.4,
                "ci_excludes_zero": True,
                "beats_random": True,
                "folds": 12,
            },
            "deltas": {"oos_profit_factor": -0.1, "oos_trades": -10},
        }
        for key in CERTIFIED_SURVIVOR_KEYS
    ]
    finalise_report(report)
    assert report["kit_green"] is True
    markdown = render_markdown(report)
    assert "How CEO / Board uses this" in markdown
    assert "never writes `approved=true`" in markdown
    assert "atr_channel_breakout:BTCUSDT:SHORT:4h" in markdown

    report["survivors"][0]["current"]["still_clears_gates"] = False
    finalise_report(report)
    assert report["kit_green"] is False


def test_kit_green_false_when_regressions_skipped() -> None:
    report = empty_report_shell(fingerprint="abc", inventory_ok=True)
    report["approval_book_unchanged"] = True
    report["regressions"] = {"ok": True, "skipped": True, "targets": []}
    report["survivors"] = [
        {
            "key": key,
            "classification": "certified_survivor",
            "error": None,
            "current": {"still_clears_gates": True},
        }
        for key in CERTIFIED_SURVIVOR_KEYS
    ]
    finalise_report(report)
    assert report["kit_green"] is False


def test_check_book_cli_does_not_mutate_approvals(tmp_path) -> None:
    """Documented command: --check-book is runnable and fail-closed on the book."""
    import subprocess
    import sys

    before = BOOK.read_bytes()
    out_dir = tmp_path / "artifacts"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_revalidation_kit.py"),
            "--check-book",
            "--output-dir",
            str(out_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert BOOK.read_bytes() == before
    latest = out_dir / "revalidation_kit_latest.json"
    assert latest.is_file()
    payload = json.loads(latest.read_text(encoding="utf-8"))
    assert payload["would_write_approved"] is False
    assert payload["promotion_blocked"] is True
    assert payload["research_version"] == "wf-f01-oos-window-v1"
    assert payload["certified_survivor_keys"] == list(CERTIFIED_SURVIVOR_KEYS)
    assert payload["inventory_ok"] is True
    assert payload["approval_book_unchanged"] is True
    md = (out_dir / "revalidation_kit_latest.md").read_text(encoding="utf-8")
    assert "freeze lift" in md.lower() or "Freeze" in md


def test_write_flag_is_refused(tmp_path) -> None:
    import subprocess
    import sys

    before = BOOK.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_revalidation_kit.py"),
            "--write",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "refuses --write" in (result.stdout + result.stderr)
    assert BOOK.read_bytes() == before


def test_offline_survivors_cli_reports_without_stamping(tmp_path) -> None:
    """Runnable path when market data is unavailable: report, no book write."""
    import subprocess
    import sys

    before = BOOK.read_bytes()
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "run_revalidation_kit.py"),
            "--survivors-only",
            "--offline",
            "--output-dir",
            str(tmp_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert BOOK.read_bytes() == before
    payload = json.loads((tmp_path / "revalidation_kit_latest.json").read_text(encoding="utf-8"))
    assert payload["would_write_approved"] is False
    assert payload["kit_green"] is False
    assert len(payload["survivors"]) == 3
    assert all(row.get("would_write_approved") is False for row in payload["survivors"])
    assert all(row.get("error") for row in payload["survivors"])
