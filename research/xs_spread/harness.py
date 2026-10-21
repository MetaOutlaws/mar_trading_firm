"""Write the book. Do not score it.

Outputs, one directory per window:

* ``weights.csv`` — signed equal-weight tercile book
* ``name_paths.csv`` — next-open entry and the long and short exit path
* ``weekly_returns.csv`` — gross spread, cost, net spread, turnover
* ``leg_trades.csv`` — every entry, exit, stop and delist
* ``manifest.json`` — cell, window, cost wrap, source hashes
* ``SHA256SUMS`` — hash of those files

The sha256 of ``SHA256SUMS`` is the main-output hash. The holdout refuses
to run until that hash is supplied and matches a main run whose scorer
verdict is PASS. This module does not import the scorer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research.xs_spread import PACKAGE_DIR
from research.xs_spread.book import run_book
from research.xs_spread.cells import (
    COUNTERSIGN_SHA256,
    LOCK_SHA256,
    PREREG_SHA256,
    PROPOSAL_SHA256,
    CellConfig,
)
from research.xs_spread.costs import cost_snapshot
from research.xs_spread.hashing import sha256_file, source_hashes, write_sha256sums

HOLDOUT_LOCK_MARKER = "LOCKED"


class HoldoutLockedError(RuntimeError):
    """The H2 2025 holdout was asked to run without a matching main hash."""


def _marker_text() -> str:
    return (PACKAGE_DIR / "HOLDOUT_LOCK").read_text(encoding="utf-8")


def assert_holdout_allowed(
    window: str,
    *,
    cell_name: str,
    main_output_hash: str | None,
    main_output_dir: Path | None,
) -> str | None:
    """Open the holdout only after a hashed main run has passed.

    The marker file has to still say LOCKED. The flag is
    ``--main-output-hash`` plus ``--main-output-dir``. The hash has to be
    the sha256 of that directory's ``SHA256SUMS``, the manifest has to be
    the same cell's main window, and ``metrics.json`` has to say PASS.
    """
    if not _marker_text().startswith(HOLDOUT_LOCK_MARKER):
        raise HoldoutLockedError("HOLDOUT_LOCK marker is not LOCKED")
    if window != "holdout":
        return None
    if not main_output_hash or main_output_dir is None:
        raise HoldoutLockedError(
            "Holdout is locked. Refusing to run until --main-output-hash is "
            "supplied and matches the sha256 of the main run's SHA256SUMS."
        )
    main_dir = Path(main_output_dir)
    sums = main_dir / "SHA256SUMS"
    manifest_path = main_dir / "manifest.json"
    metrics_path = main_dir / "metrics.json"
    if not sums.is_file() or not manifest_path.is_file() or not metrics_path.is_file():
        raise HoldoutLockedError(
            "main output is missing SHA256SUMS, manifest.json or metrics.json"
        )
    digest = sha256_file(sums)
    supplied = main_output_hash.strip().lower()
    if digest != supplied:
        raise HoldoutLockedError(
            f"main-output hash mismatch: supplied {supplied} != {digest}"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("window") != "main" or manifest.get("cell") != cell_name:
        raise HoldoutLockedError("main-output-dir is not this cell's main window")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if metrics.get("verdict") != "PASS":
        raise HoldoutLockedError(
            "Holdout stays shut: the main verdict is not PASS. A FAIL seals the cell."
        )
    return digest


def _frame_for_csv(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[column]):
            stamps = pd.to_datetime(out[column], utc=True)
            out[column] = stamps.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def write_outputs(
    output_dir: Path,
    tables: dict[str, pd.DataFrame],
    manifest: dict[str, object],
) -> str:
    """Write the book and return the sha256 of SHA256SUMS.

    Refuses to overwrite a directory that already has SHA256SUMS, so a
    hashed main run cannot be clobbered by a second pass.
    """
    output_dir = Path(output_dir)
    if (output_dir / "SHA256SUMS").is_file():
        raise FileExistsError(
            f"{output_dir} already has SHA256SUMS; refusing to overwrite a hashed run"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in ("weights", "name_paths", "weekly_returns", "leg_trades"):
        _frame_for_csv(tables[name]).to_csv(
            output_dir / f"{name}.csv",
            index=False,
            lineterminator="\n",
            float_format="%.17g",
        )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return write_sha256sums(output_dir)


def run_window(
    panel: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
    config: CellConfig,
    window: str,
    output_dir: Path,
    *,
    main_output_hash: str | None = None,
    main_output_dir: Path | None = None,
    tape_report: dict[str, object] | None = None,
) -> dict[str, object]:
    """Run the engine for one window and write the book. No metrics."""
    unlock = assert_holdout_allowed(
        window,
        cell_name=config.name,
        main_output_hash=main_output_hash,
        main_output_dir=main_output_dir,
    )
    tables = run_book(panel, membership, config, window)
    hashes = source_hashes()
    weekly = tables["weekly_returns"]
    manifest: dict[str, object] = {
        "cell": config.name,
        "window": window,
        "live": "off",
        "paper_only": True,
        "funding_included": False,
        "metrics_computed": False,
        "rebalance": "Monday 00:00 UTC",
        "fill": "next_open",
        "stop": "12% per coin, exit at next_open, no intrabar fill",
        "n_weeks": int(len(weekly)),
        "n_leg_trades": int(weekly["n_leg_trades"].sum()) if len(weekly) else 0,
        "cost": cost_snapshot(),
        "signal": config.signal_name,
        "long_side": config.long_side,
        "documents": {
            "proposal_sha256": PROPOSAL_SHA256,
            "lock_sha256": LOCK_SHA256,
            "prereg_sha256": PREREG_SHA256,
            "countersign_sha256": COUNTERSIGN_SHA256,
        },
        "harness_sha256": hashes["harness_sha256"],
        "scorer_sha256": hashes["scorer_sha256"],
        "tape": tape_report,
        "holdout_unlocked_with_main_hash": unlock,
    }
    output_hash = write_outputs(Path(output_dir), tables, manifest)
    return {
        "output_dir": str(output_dir),
        "output_sha256": output_hash,
        "n_weeks": manifest["n_weeks"],
        "harness_sha256": hashes["harness_sha256"],
        "scorer_sha256": hashes["scorer_sha256"],
        "tables": tables,
    }


def load_book(output_dir: Path) -> dict[str, pd.DataFrame]:
    """Read a harness directory back. Used by the scorer and by tests."""
    output_dir = Path(output_dir)
    tables = {}
    for name in ("weights", "name_paths", "weekly_returns", "leg_trades"):
        path = output_dir / f"{name}.csv"
        frame = pd.read_csv(path)
        for column in frame.columns:
            if column.endswith("_time") or column in {"rebalance_time", "fill_time", "entry_time"}:
                frame[column] = pd.to_datetime(frame[column], utc=True)
        tables[name] = frame
    return tables


def manifest_of(output_dir: Path) -> dict[str, object]:
    return json.loads((Path(output_dir) / "manifest.json").read_text(encoding="utf-8"))
