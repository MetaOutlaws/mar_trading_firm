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
    cost_rates,
)
from research.xs_spread.costs import cost_snapshot
from research.xs_spread.hashing import sha256_file, source_hashes, write_sha256sums

HOLDOUT_LOCK_MARKER = "LOCKED"


class HoldoutLockedError(RuntimeError):
    """The H2 2025 holdout was asked to run without a matching main hash."""


def countersign_path(config: CellConfig) -> Path:
    """Path of the cell's COUNTERSIGN.md. Empty means the cell has none."""
    if not config.countersign_relative:
        raise FileNotFoundError("COUNTERSIGN.md is missing; refusing to run")
    return PACKAGE_DIR / config.countersign_relative


def require_countersign(config: CellConfig) -> str:
    """Sha256 of COUNTERSIGN.md. Missing file refuses the run.

    The digest is computed from the file bytes. A hardcoded constant is not
    a substitute, and a null hash is not written.
    """
    path = countersign_path(config)
    if not path.is_file():
        raise FileNotFoundError(
            f"COUNTERSIGN.md is missing at {path}; refusing to run without countersign_sha256"
        )
    digest = sha256_file(path)
    if not isinstance(digest, str) or len(digest) != 64:
        raise FileNotFoundError("COUNTERSIGN.md sha256 is missing; refusing to run")
    return digest


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
    # The H2 holdout is always shut. xs_prospect_value_weekly also keeps the
    # 2026 veto shut until that same main hash is on file. The skew veto
    # window is not shut that way.
    prospect_veto = cell_name == "xs_prospect_value_weekly" and window == "veto"
    if window != "holdout" and not prospect_veto:
        return None
    if not main_output_hash or main_output_dir is None:
        if prospect_veto:
            raise HoldoutLockedError(
                "2026 veto is locked. Refusing to run until --main-output-hash is "
                "supplied and matches the sha256 of the main run's SHA256SUMS."
            )
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
    names = ["weights", "name_paths", "weekly_returns", "leg_trades"]
    if "scores" in tables:
        names.append("scores")
    for name in names:
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
    funding: dict | None = None,
) -> dict[str, object]:
    """Run the engine for one window and write the book. No metrics."""
    unlock = assert_holdout_allowed(
        window,
        cell_name=config.name,
        main_output_hash=main_output_hash,
        main_output_dir=main_output_dir,
    )
    countersign_sha: str | None = None
    if config.countersign_relative:
        countersign_sha = require_countersign(config)
        if not countersign_sha:
            raise FileNotFoundError("COUNTERSIGN.md sha256 is missing; refusing to run")
    tables = run_book(panel, membership, config, window, funding=funding)
    hashes = source_hashes()
    weekly = tables["weekly_returns"]
    manifest: dict[str, object] = {
        "cell": config.name,
        "window": window,
        "live": "off",
        "paper_only": True,
        "funding_included": config.funding_included,
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
    if config.signal_name == "prospect_value":
        from research.xs_spread.cells import (
            TK_BTC_SAMPLER_RT,
            TK_LOCK_SHA256,
            TK_PREREG_SHA256,
            TK_PRESTATED_SHA256,
            TK_PROPOSAL_SHA256,
            TK_PROXY_LEG_COST,
            TK_SOL_SAMPLER_RT,
        )

        if not countersign_sha:
            raise FileNotFoundError(
                "COUNTERSIGN.md is missing; refusing to run without countersign_sha256"
            )
        weekly_gaps = weekly["funding_gap_count"] if "funding_gap_count" in weekly.columns else None
        manifest["score_profile"] = "prospect_value"
        manifest["countersign_sha256"] = countersign_sha
        manifest["prereg_countersigned"] = True
        manifest["weighting"] = "equal-weight, dollar-neutral"
        manifest["mde_d"] = config.mde_d
        manifest["mde_weeks"] = config.mde_weeks
        manifest["mde_binds_gates"] = False
        manifest["grade_cap"] = "B"
        manifest["funding_zero_filled"] = False
        manifest["funding_gap_count"] = int(weekly_gaps.sum()) if weekly_gaps is not None and len(weekly) else 0
        if "long_funding_gap_count" in weekly.columns and len(weekly):
            manifest["long_funding_gap_count"] = int(weekly["long_funding_gap_count"].sum())
            manifest["short_funding_gap_count"] = int(weekly["short_funding_gap_count"].sum())
        else:
            manifest["long_funding_gap_count"] = 0
            manifest["short_funding_gap_count"] = 0
        manifest["cost"] = {
            **cost_snapshot(),
            "rates_per_leg_trade": list(cost_rates(config)),
            "official_rate_per_leg_trade": config.leg_cost_rate,
            "official_binds_gates": True,
            "measured_rt_rate_per_leg_trade": TK_PROXY_LEG_COST,
            "measured_rt_label": config.proxy_cost_label,
            "measured_rt_binds_gates": False,
            "measured_rt_sign_flip_is_a_veto": True,
            "btc_sampler_rt": TK_BTC_SAMPLER_RT,
            "sol_sampler_rt": TK_SOL_SAMPLER_RT,
            "funding_included": True,
            "funding_source": (
                "observed 8h prints on each leg; a missing print is counted "
                "and is not zero-filled. CostModel.include_funding stays off "
                "so the fee does not add a default funding rate."
            ),
        }
        manifest["documents"] = {
            "proposal_sha256": TK_PROPOSAL_SHA256,
            "lock_sha256": TK_LOCK_SHA256,
            "prereg_sha256": TK_PREREG_SHA256,
            "prestated_sha256": TK_PRESTATED_SHA256,
            "countersign_sha256": countersign_sha,
        }
        manifest["ret60_partial"] = "report-only, scored later, not a gate"
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
    names = ["weights", "name_paths", "weekly_returns", "leg_trades"]
    if (output_dir / "scores.csv").is_file():
        names.append("scores")
    for name in names:
        path = output_dir / f"{name}.csv"
        frame = pd.read_csv(path)
        for column in frame.columns:
            if column.endswith("_time") or column in {"rebalance_time", "fill_time", "entry_time"}:
                frame[column] = pd.to_datetime(frame[column], utc=True)
        tables[name] = frame
    return tables


def manifest_of(output_dir: Path) -> dict[str, object]:
    return json.loads((Path(output_dir) / "manifest.json").read_text(encoding="utf-8"))
