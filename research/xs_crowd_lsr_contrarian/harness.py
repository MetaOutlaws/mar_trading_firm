"""Write the book. Do not score it, and do not print a metric.

Blind order, fixed:

1. Refuse unless the process was started with ``PYTHONHASHSEED=0``.
2. Check every shipped document against its pin. Countersign is hashed
   from the file bytes.
3. Holdout stays shut unless this invocation passed ``--holdout``, a seal
   hash, and a main directory whose verdict is PASS. That check happens
   before any tape is opened.
4. Build the schedule. A held name with no 1h price raises ``BlockedRun``
   here, before the output directory is created.
5. Write the book and a preliminary manifest. Funding coverage must say
   ``leg_mean_fill`` is false before the null is drawn.
6. On the main window, draw the 1,000-path random book at seed 20261016.
7. Write the final manifest, then ``SHA256SUMS``. ``FINAL_HASH`` is the
   sha256 of that file and is not itself inside the seal. ``metrics.json``
   is also outside the seal; scoring writes it later and must not rewrite
   ``SHA256SUMS``.

Stdout from a run is the harness hash, the scorer hash, random-book
progress, and the final seal. No mean, profit factor, drawdown, or verdict.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.xs_crowd_lsr_contrarian.book import (
    Schedule,
    funding_coverage,
    proxy_weekly,
    run_strategy,
    simulation_frames,
    skips_frame,
    survivor_split,
)
from research.xs_crowd_lsr_contrarian.calendar import WindowError
from research.xs_crowd_lsr_contrarian.costs import cost_snapshot
from research.xs_crowd_lsr_contrarian.hashing import (
    assert_documents,
    assert_pythonhashseed,
    bundle_sha256,
    sha256_file,
    source_hashes,
    write_sha256sums,
)
from research.xs_crowd_lsr_contrarian.pins import (
    CELL,
    GROSS,
    HARNESS_FILES,
    LEG,
    MAIN_COMMAND,
    MAX_DRAWDOWN,
    N_RANDOM_DRAWS,
    PROPOSAL_STATUS_FIX_SHA256,
    RANDOM_SEED,
    SCORER_FILES,
)
from research.xs_crowd_lsr_contrarian.random_book import random_book_means

# Sealed with the book, before the random book exists. The final manifest
# is written afterwards and is not part of this digest.
BOOK_STAGE_FILES: tuple[str, ...] = (
    "eligible.csv",
    "funding_coverage.json",
    "leg_trades.csv",
    "manifest_book.json",
    "name_paths.csv",
    "name_pnl.csv",
    "skips.csv",
    "survivor_split.json",
    "weekly_returns.csv",
    "weights.csv",
)

# Kept out of SHA256SUMS. FINAL_HASH is the seal itself. metrics.json is
# written by the scorer after the seal, and writing it must not move the seal.
SEAL_EXCLUDE = frozenset({"FINAL_HASH", "metrics.json"})

_WEEKLY_COLUMNS = (
    "rebalance_time",
    "iso_year",
    "iso_week",
    "n_long",
    "n_short",
    "n_valid",
    "k",
    "regime",
    "fresh_entry",
    "flatten",
    "gross_price",
    "funding",
    "traded_notional",
    "cost",
    "net_return",
    "funding_gap_count",
    "funding_missing_names",
    "off_grid_prints",
    "n_entries",
    "n_exits",
    "n_stops",
    "n_delist",
    "n_rebalance",
    "n_leg_trades",
    "w_long",
    "w_short",
    "equity_start",
    "equity_end",
    "rate",
    "net_return_proxy",
    "cost_proxy",
    "traded_notional_proxy",
)

_TRADE_COLUMNS = (
    "rebalance_time",
    "symbol",
    "side",
    "action",
    "notional",
    "weight",
    "cost_rate",
    "cost",
)
_WEIGHT_COLUMNS = (
    "rebalance_time",
    "symbol",
    "side",
    "weight",
    "L",
    "regime",
    "status",
)
_PATH_COLUMNS = (
    "rebalance_time",
    "symbol",
    "side",
    "L",
    "entry_time",
    "entry_open",
    "exit_time",
    "exit_price",
    "reason",
    "underlying_return",
    "price_ratio",
    "funding_sum",
    "funding_gaps",
    "funding_missing_name",
    "weight",
    "status",
)
_ELIGIBLE_COLUMNS = ("rebalance_time", "symbol", "L", "status")
_PNL_COLUMNS = (
    "rebalance_time",
    "symbol",
    "weight",
    "status",
    "price",
    "funding",
    "cost",
    "pnl",
)


class HoldoutLockedError(RuntimeError):
    """H2 2025 was asked to run without a sealed main PASS."""


def assert_holdout_allowed(
    window: str,
    *,
    holdout_flag: bool,
    seal_hash: str | None,
    main_output_dir: Path | None,
) -> str | None:
    """Open the holdout only after a sealed main run has passed.

    The flag is ``--holdout`` plus ``--seal-hash`` plus ``--main-output-dir``.
    The hash has to be the sha256 of that directory's ``SHA256SUMS``, the
    manifest has to be this cell's main window, and ``metrics.json`` has to
    say PASS. A FAIL seals the cell. This does not import the scorer and
    does not read a price.
    """
    if window not in {"main", "holdout"}:
        raise WindowError(
            f"refusing window {window!r}. Runnable windows are main and holdout. "
            "2026 is not touched."
        )
    if window != "holdout":
        if holdout_flag or seal_hash or main_output_dir is not None:
            raise HoldoutLockedError(
                "the main window does not take --holdout, --seal-hash, or "
                "--main-output-dir"
            )
        return None
    if not holdout_flag:
        raise HoldoutLockedError(
            "Holdout is locked. Refusing to run unless --holdout is set, "
            "together with --seal-hash and --main-output-dir of a main run "
            "whose verdict is PASS."
        )
    if not seal_hash or main_output_dir is None:
        raise HoldoutLockedError(
            "Holdout is locked. --holdout requires --seal-hash and --main-output-dir."
        )
    main_dir = Path(main_output_dir)
    sums = main_dir / "SHA256SUMS"
    manifest_path = main_dir / "manifest.json"
    metrics_path = main_dir / "metrics.json"
    if not sums.is_file() or not manifest_path.is_file() or not metrics_path.is_file():
        raise HoldoutLockedError(
            "main output is missing SHA256SUMS, manifest.json, or metrics.json"
        )
    digest = sha256_file(sums)
    supplied = seal_hash.strip().lower()
    if digest != supplied:
        raise HoldoutLockedError(
            f"seal hash mismatch: supplied {supplied} != sha256(SHA256SUMS) {digest}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("window") != "main" or manifest.get("cell") != CELL:
        raise HoldoutLockedError("main-output-dir is not this cell's main window")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics.get("verdict") != "PASS":
        raise HoldoutLockedError(
            "Holdout stays shut: the main verdict is not PASS. A FAIL seals the cell."
        )
    return digest


def refuse_existing_output(output_dir: Path) -> None:
    """A directory that already has files is left alone.

    That covers a finished seal and a partial write. A second pass does not
    clobber either one.
    """
    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"{output_dir} is not empty; refusing to overwrite a run"
        )


def stage_digest(directory: Path, names: tuple[str, ...]) -> str:
    """Same NUL-separated bundle hash the source bundles use."""
    return bundle_sha256(names, root=directory)


def _json_ready(value: object) -> object:
    """Plain JSON values. Non-finite floats become null rather than NaN tokens."""
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_ready(item) for item in value.tolist()]
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not np.isfinite(number):
            return None
        return number
    if isinstance(value, Path):
        return str(value)
    return value


def _write_json(path: Path, payload: dict) -> None:
    text = json.dumps(_json_ready(payload), indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")


def _frame_for_csv(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[column]):
            stamps = pd.to_datetime(out[column], utc=True)
            out[column] = stamps.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def _with_columns(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=list(columns))
    missing = [column for column in columns if column not in frame.columns]
    out = frame.copy()
    for column in missing:
        out[column] = np.nan
    return out


def _progress(done: int, total: int) -> None:
    # Counts only. The means stay in the file.
    sys.stdout.write(f"random_book {done}/{total}\n")
    sys.stdout.flush()


def _base_manifest(
    *,
    window: str,
    schedule: Schedule,
    weekly: pd.DataFrame,
    coverage: dict[str, object],
    documents: dict[str, str],
    hashes: dict[str, object],
    tape_report: dict[str, object] | None,
    holdout_seal: str | None,
    pythonhashseed: str,
) -> dict[str, object]:
    n_leg = int(weekly["n_leg_trades"].sum()) if len(weekly) else 0
    return {
        "cell": CELL,
        "window": window,
        "live": "off",
        "paper_only": True,
        "approved": False,
        "metrics_computed": False,
        "pythonhashseed": pythonhashseed,
        "command": MAIN_COMMAND,
        "rebalance": "Monday 00:00 UTC",
        "fill": "next_open",
        "gross": GROSS,
        "leg": LEG,
        "sizing_knob": False,
        "max_drawdown_rule": f"MDD < {MAX_DRAWDOWN}",
        "stop": "12% on 1h closes, exit at the next 1h open, no redistribution",
        "n_weeks": int(len(weekly)),
        "n_skips": len(schedule.skips),
        "n_leg_trades": n_leg,
        "cost": cost_snapshot(),
        "documents": {
            **documents,
            "proposal_status_fix_sha256": PROPOSAL_STATUS_FIX_SHA256,
            "proposal_status_fix_bytes_in_checkout": False,
        },
        "harness_sha256": hashes["harness_sha256"],
        "scorer_sha256": hashes["scorer_sha256"],
        "funding_coverage": coverage,
        "tape": tape_report or {},
        "holdout_unlocked_with_seal": holdout_seal,
        "random_book_draws": N_RANDOM_DRAWS if window == "main" else 0,
        "random_book_seed": RANDOM_SEED if window == "main" else None,
    }


def run_prepared(
    schedule: Schedule,
    *,
    window: str,
    output_dir: Path,
    documents: dict[str, str] | None = None,
    hashes: dict[str, object] | None = None,
    tape_report: dict[str, object] | None = None,
    holdout_seal: str | None = None,
) -> dict[str, object]:
    """Simulate ``schedule`` and seal the directory. No gate is evaluated.

    The main window draws the random book. The holdout does not. Calling
    this with ``window='holdout'`` and no seal is refused, so a book cannot
    be written by skipping the lock. The lock itself (PASS, matching hash)
    is ``assert_holdout_allowed`` and runs before the tape is read.
    """
    if window not in {"main", "holdout"}:
        raise WindowError(f"refusing window {window!r}")
    if window == "holdout" and not holdout_seal:
        raise HoldoutLockedError(
            "Holdout is locked. Refusing to write a holdout book without a seal."
        )
    # Read, do not assign. An in-process assignment would not disable hashing.
    pythonhashseed = assert_pythonhashseed()
    output_dir = Path(output_dir)
    refuse_existing_output(output_dir)
    pinned_docs = documents if documents is not None else assert_documents()
    code_hashes = hashes if hashes is not None else source_hashes()

    official = run_strategy(schedule)
    proxy = proxy_weekly(schedule)
    frames = simulation_frames(official, proxy)
    frames["weekly_returns"] = _with_columns(frames["weekly_returns"], _WEEKLY_COLUMNS)
    frames["leg_trades"] = _with_columns(frames["leg_trades"], _TRADE_COLUMNS)
    frames["weights"] = _with_columns(frames["weights"], _WEIGHT_COLUMNS)
    frames["name_paths"] = _with_columns(frames["name_paths"], _PATH_COLUMNS)
    frames["eligible"] = _with_columns(frames["eligible"], _ELIGIBLE_COLUMNS)
    frames["name_pnl"] = _with_columns(frames["name_pnl"], _PNL_COLUMNS)
    frames["skips"] = skips_frame(schedule.skips)
    coverage = funding_coverage(frames["name_pnl"], schedule)
    # Countersign: no leg-mean fill, and a name with no prints books 0.
    # Checked before the null so a bad booking cannot be sealed.
    if coverage.get("leg_mean_fill") is not False or coverage.get("missing_books_zero") is not True:
        raise RuntimeError(
            "funding coverage is not the countersign rule "
            "(leg_mean_fill must be false, missing names book 0)"
        )
    split = survivor_split(frames["name_pnl"], frames["leg_trades"])
    manifest = _base_manifest(
        window=window,
        schedule=schedule,
        weekly=frames["weekly_returns"],
        coverage=coverage,
        documents=pinned_docs,
        hashes=code_hashes,
        tape_report=tape_report,
        holdout_seal=holdout_seal,
        pythonhashseed=pythonhashseed,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_names = {
        "weights": frames["weights"],
        "name_paths": frames["name_paths"],
        "weekly_returns": frames["weekly_returns"],
        "leg_trades": frames["leg_trades"],
        "eligible": frames["eligible"],
        "name_pnl": frames["name_pnl"],
        "skips": frames["skips"],
    }
    for name, frame in csv_names.items():
        _frame_for_csv(frame).to_csv(
            output_dir / f"{name}.csv",
            index=False,
            lineterminator="\n",
            float_format="%.17g",
        )
    _write_json(output_dir / "funding_coverage.json", coverage)
    _write_json(output_dir / "survivor_split.json", split)
    book_manifest = {**manifest, "stage": "book"}
    _write_json(output_dir / "manifest_book.json", book_manifest)
    book_hash = stage_digest(output_dir, BOOK_STAGE_FILES)

    random_hash: str | None = None
    if window == "main":
        # Second check, immediately before the draws. Same rule, same value.
        assert_pythonhashseed()
        if schedule.trades:
            means = random_book_means(schedule, progress=_progress)
        else:
            means = np.empty(0, dtype="float64")
        if schedule.trades and int(means.size) != N_RANDOM_DRAWS:
            raise RuntimeError(
                f"random book produced {means.size} means, not {N_RANDOM_DRAWS}"
            )
        payload = {
            "cell": CELL,
            "window": "main",
            "n_draws": int(means.size),
            "seed": RANDOM_SEED,
            "means": [float(value) for value in means],
        }
        random_path = output_dir / "random_book.json"
        _write_json(random_path, payload)
        random_hash = sha256_file(random_path)

    final = {
        **manifest,
        "stage": "final",
        "book_stage_sha256": book_hash,
        "book_stage_files": list(BOOK_STAGE_FILES),
        "random_book_sha256": random_hash,
        "random_book_ran": window == "main" and bool(schedule.trades),
        "metrics_computed": False,
    }
    if window == "main":
        # Record what was actually drawn. A book with no kept week does not
        # claim a thousand phantom means.
        final["random_book_draws"] = int(means.size)
    _write_json(output_dir / "manifest.json", final)
    seal = write_sha256sums(output_dir, exclude=SEAL_EXCLUDE)
    # Written after the seal so the seal does not include itself.
    (output_dir / "FINAL_HASH").write_text(seal + "\n", encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "final_sha256": seal,
        "harness_sha256": code_hashes["harness_sha256"],
        "scorer_sha256": code_hashes["scorer_sha256"],
        "book_stage_sha256": book_hash,
    }


def print_run_hashes() -> dict[str, object]:
    """The two bundle hashes Garwe seals. Nothing about a result."""
    hashes = source_hashes()
    # Recompute from the file lists so a stale dict cannot be printed.
    harness = bundle_sha256(HARNESS_FILES)
    scorer = bundle_sha256(SCORER_FILES)
    if harness != hashes["harness_sha256"] or scorer != hashes["scorer_sha256"]:
        raise RuntimeError("bundle hash changed while it was being printed")
    sys.stdout.write(f"harness_sha256 {harness}\n")
    sys.stdout.write(f"scorer_sha256 {scorer}\n")
    sys.stdout.flush()
    return hashes
