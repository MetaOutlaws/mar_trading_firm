"""
Runnable CEO LOCK revalidation kit.

Keyed to RESEARCH_VERSION ``wf-f01-oos-window-v1``. Re-measures the three
certified book survivors (ATR BTC/ETH 4h SHORT, doji SOL 1h SHORT), runs the
F01–F03 regressions this kit depends on, and writes a Board deltas report.

This script **never** writes ``config/approved_strategies.json``. There is no
``--write`` / ``--stamp`` flag. Exploratory sleeves are listed and skipped.

Usage:
    python scripts/run_revalidation_kit.py
    python scripts/run_revalidation_kit.py --regressions-only
    python scripts/run_revalidation_kit.py --survivors-only
    python scripts/run_revalidation_kit.py --check-book
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from config.logging_setup import setup_logging
from config.settings import PROJECT_ROOT, get_settings
from core.data.funding import FundingRates
from research.costs import DEFAULT_COSTS
from research.datasets import DatasetLoader
from research.engine import BacktestConfig
from research.revalidation import (
    CERTIFIED_SURVIVOR_KEYS,
    KIT_TEST_TARGET,
    ApprovalBookGuardError,
    ApprovalBookLock,
    CertifiedInventoryError,
    assert_certified_inventory,
    assert_not_stamping,
    empty_report_shell,
    exploratory_records,
    finalise_report,
    fingerprint_approval_book,
    load_approval_book,
    paper_override_keys,
    render_markdown,
    revalidate_survivor,
    run_regressions,
    write_report_artifacts,
)
from research.walkforward import RESEARCH_VERSION

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-book",
        action="store_true",
        help="Inventory + fingerprint only. No pytest, no walk-forward.",
    )
    parser.add_argument(
        "--regressions-only",
        action="store_true",
        help="Run F01–F03 (+ gate) pytest hooks; skip survivor walk-forward.",
    )
    parser.add_argument(
        "--survivors-only",
        action="store_true",
        help="Re-run certified survivors; skip pytest.",
    )
    parser.add_argument(
        "--include-kit-tests",
        action="store_true",
        help="Also collect tests/test_revalidation_kit.py with the regressions.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for JSON/MD artifacts (default: research/artifacts).",
    )
    parser.add_argument(
        "--train-days",
        type=int,
        default=180,
        help="Walk-forward train window; must match the original certified runs.",
    )
    parser.add_argument(
        "--test-days",
        type=int,
        default=60,
        help="Walk-forward OOS window / roll step.",
    )
    parser.add_argument(
        "--significance-iterations",
        type=int,
        default=0,
        help="Override bootstrap iterations (0 = research default). Tests may lower this.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not fetch candles/funding; survivor rows are marked blocked if cache misses.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help=argparse.SUPPRESS,  # trap: kit must never stamp
    )
    parser.add_argument(
        "--stamp",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def _output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir is not None:
        return Path(args.output_dir)
    return get_settings().artifacts_dir


def _run_survivor_block(
    args: argparse.Namespace,
    payload: dict,
    report: dict,
) -> None:
    """Load candles for certified keys only and append measurement rows."""
    from research.significance import DEFAULT_ITERATIONS

    iterations = args.significance_iterations or DEFAULT_ITERATIONS
    report["exploratory_skipped"] = paper_override_keys(payload)

    if args.offline:
        for key in CERTIFIED_SURVIVOR_KEYS:
            record = payload[key]
            report["survivors"].append(
                {
                    "key": key,
                    "classification": "certified_survivor",
                    "promotion": False,
                    "would_write_approved": False,
                    "error": "offline: survivor walk-forward skipped (no fetch)",
                    "prior": {
                        "oos_trades": record.get("oos_trades"),
                        "oos_profit_factor": record.get("oos_profit_factor"),
                        "oos_expectancy_pct": record.get("oos_expectancy_pct"),
                        "oos_win_rate": record.get("oos_win_rate"),
                        "oos_max_drawdown_pct": record.get("oos_max_drawdown_pct"),
                        "research_version": record.get("research_version"),
                    },
                    "current": {"still_clears_gates": False, "research_version": RESEARCH_VERSION},
                    "deltas": {},
                }
            )
        logger.warning("Offline mode: survivor walk-forward skipped.")
        return

    loaders: dict[str, DatasetLoader] = {}
    funding_source: FundingRates | None = None
    try:
        if not args.offline:
            funding_source = FundingRates()
        for key in CERTIFIED_SURVIVOR_KEYS:
            record = payload[key]
            timeframe = str(record.get("timeframe") or "4h")
            symbol = key.split(":")[1]
            if timeframe not in loaders:
                loaders[timeframe] = DatasetLoader(timeframe=timeframe)
            loader = loaders[timeframe]
            try:
                candles = loader.load(symbol)
            except Exception as exc:
                logger.warning("%s: candle load failed: %s", key, exc)
                report["survivors"].append(
                    {
                        "key": key,
                        "classification": "certified_survivor",
                        "promotion": False,
                        "would_write_approved": False,
                        "error": f"candle load failed: {exc}",
                        "prior": {
                            "oos_trades": record.get("oos_trades"),
                            "oos_profit_factor": record.get("oos_profit_factor"),
                        },
                        "current": {"still_clears_gates": False},
                        "deltas": {},
                    }
                )
                continue

            if candles is None or candles.empty:
                report["survivors"].append(
                    {
                        "key": key,
                        "classification": "certified_survivor",
                        "promotion": False,
                        "would_write_approved": False,
                        "error": "no candles available",
                        "prior": {"oos_trades": record.get("oos_trades")},
                        "current": {"still_clears_gates": False},
                        "deltas": {},
                    }
                )
                continue

            history = None
            if funding_source is not None:
                try:
                    history = funding_source.get(
                        symbol,
                        candles.index[0].to_pydatetime(),
                        candles.index[-1].to_pydatetime(),
                    )
                except Exception as exc:
                    logger.warning("%s: funding load failed: %s", key, exc)

            config = BacktestConfig(
                initial_capital=10_000.0,
                position_fraction=0.10,
                compound=True,
                pessimistic_intrabar=True,
                costs=DEFAULT_COSTS.for_symbol(symbol),
            )
            logger.info(
                "Revalidating %s (%s %s %s, %d bars) under %s — params pinned, no grid.",
                key,
                symbol,
                key.split(":")[2],
                timeframe,
                len(candles),
                RESEARCH_VERSION,
            )
            row = revalidate_survivor(
                key,
                record,
                candles,
                config=config,
                funding=history,
                train_days=args.train_days,
                test_days=args.test_days,
                significance_iterations=iterations,
            )
            report["survivors"].append(row)
            logger.info(
                "  %s PF %s trades %s clears_gates=%s (not stamped)",
                key,
                (row.get("current") or {}).get("oos_profit_factor"),
                (row.get("current") or {}).get("oos_trades"),
                (row.get("current") or {}).get("still_clears_gates"),
            )
    finally:
        for loader in loaders.values():
            loader.close()
        if funding_source is not None:
            funding_source.close()

    skipped_n = len(exploratory_records(payload))
    logger.info(
        "Skipped %d exploratory rows (paper_override + rejected). Not promotions.",
        skipped_n,
    )


def main() -> int:
    args = parse_args()
    setup_logging("revalidation")
    if args.write or args.stamp:
        logger.error(
            "FAIL CLOSED: revalidation kit refuses --write/--stamp. "
            "Output is a report artifact; it does not stamp approved=true."
        )
        return 2
    if RESEARCH_VERSION != "wf-f01-oos-window-v1":
        logger.error(
            "Kit is keyed to wf-f01-oos-window-v1; research.walkforward.RESEARCH_VERSION "
            "is %r. Fail closed.",
            RESEARCH_VERSION,
        )
        return 2

    assert_not_stamping()

    try:
        with ApprovalBookLock() as lock:
            payload = load_approval_book()
            try:
                assert_certified_inventory(payload)
                inventory_ok = True
                inventory_error = None
            except CertifiedInventoryError as exc:
                inventory_ok = False
                inventory_error = str(exc)
                logger.error("%s", exc)

            report = empty_report_shell(
                fingerprint=lock.before, inventory_ok=inventory_ok
            )
            if inventory_error:
                report["inventory_error"] = inventory_error

            run_survivors = not args.check_book and not args.regressions_only
            run_pytest = not args.check_book and not args.survivors_only

            if run_pytest:
                extra = [KIT_TEST_TARGET] if args.include_kit_tests else []
                logger.info("Running kit regressions: %s", extra or "F01/F02/F03/gates")
                report["regressions"] = run_regressions(extra)
            else:
                report["regressions"] = {
                    "ok": True,
                    "exit_code": 0,
                    "targets": [],
                    "skipped": True,
                }

            if run_survivors and inventory_ok:
                _run_survivor_block(args, payload, report)
            elif run_survivors and not inventory_ok:
                logger.error("Skipping survivor re-run because inventory failed.")

            report["approval_book_sha256_after"] = fingerprint_approval_book()
            report["approval_book_unchanged"] = (
                report["approval_book_sha256_after"] == lock.before
            )
            finalise_report(report)

            out_dir = _output_dir(args)
            json_path, md_path = write_report_artifacts(report, out_dir)
            logger.info("Report JSON: %s", json_path)
            logger.info("Report MD:   %s", md_path)
            sys.stdout.write(render_markdown(report))
            sys.stdout.write(f"\nArtifacts:\n  {json_path}\n  {md_path}\n")

            # Fail closed: regressions red, inventory mismatch, or book mutation.
            # Negative survivor deltas still produce a report (exit 0) so the
            # Board can read them; kit_green in the artifact is the freeze signal.
            if not report["approval_book_unchanged"]:
                return 3
            if not inventory_ok:
                return 4
            if run_pytest and not (report.get("regressions") or {}).get("ok"):
                return 5
            return 0
    except ApprovalBookGuardError as exc:
        logger.error("%s", exc)
        return 3


if __name__ == "__main__":
    # Repo-root relative pytest paths in run_regressions().
    if Path.cwd() != PROJECT_ROOT:
        try:
            import os

            os.chdir(PROJECT_ROOT)
        except OSError:
            pass
    raise SystemExit(main())
