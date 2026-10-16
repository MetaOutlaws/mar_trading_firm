"""Write the book. Do not score it.

Outputs, one directory per window:

* ``trades.csv`` — one spread per listing, both cost levels, funding flags
* ``manifest.json`` — cell, window, cost wrap, source hashes, tape SUMS
* ``SHA256SUMS`` — hash of those files

The sha256 of ``SHA256SUMS`` is the main-output hash. The holdout and the
2026 veto refuse to run until that hash is supplied and matches a main run
whose scorer verdict is PASS. This module does not import the scorer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from research.new_listing_drift import PACKAGE_DIR
from research.new_listing_drift.catalog import coverage_disclosure, events_for_window
from research.new_listing_drift.cells import (
    CELL_NAME,
    CLOSED_WINDOWS,
    HEDGE_SYMBOL,
    KILL_SHA256,
    LOCK_SHA256,
    PREREG_SHA256,
    PROPOSAL_SHA256,
    RULES_SHA256,
    CellConfig,
)
from research.new_listing_drift.costs import cost_snapshot
from research.new_listing_drift.engine import simulate_spread
from research.new_listing_drift.hashing import sha256_file, source_hashes, write_sha256sums
from research.new_listing_drift.tape import (
    funding_interval,
    listing_deadline,
    load_membership,
    load_symbol_bars,
    load_symbol_funding,
)

HOLDOUT_LOCK_MARKER = "LOCKED"


class HoldoutLockedError(RuntimeError):
    """Holdout or the 2026 veto was asked to run without a matching main hash."""


def _marker_text() -> str:
    return (PACKAGE_DIR / "HOLDOUT_LOCK").read_text(encoding="utf-8")


def assert_closed_window_allowed(
    window: str,
    *,
    cell_name: str,
    main_output_hash: str | None,
    main_output_dir: Path | None,
) -> str | None:
    """Open holdout and the 2026 veto only after a hashed main run has passed.

    The marker file has to still say LOCKED. The hash has to be the sha256
    of the main directory's ``SHA256SUMS``. The manifest has to be this
    cell's main window, and ``metrics.json`` has to say PASS. A FAIL or a
    veto seals the cell; neither window is opened to rescue it.
    """
    if not _marker_text().startswith(HOLDOUT_LOCK_MARKER):
        raise HoldoutLockedError("HOLDOUT_LOCK marker is not LOCKED")
    if window not in CLOSED_WINDOWS:
        return None
    label = "2026 veto" if window == "veto" else "Holdout"
    if not main_output_hash or main_output_dir is None:
        raise HoldoutLockedError(
            f"{label} is locked. Refusing to run until --main-output-hash is "
            "supplied and matches the sha256 of the main run's SHA256SUMS, "
            "and the main verdict is PASS."
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
            f"{label} stays shut: the main verdict is not PASS. A FAIL seals the cell."
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
    trades: pd.DataFrame,
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
    _frame_for_csv(trades).to_csv(
        output_dir / "trades.csv",
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return write_sha256sums(output_dir)


def build_trades(
    events: pd.DataFrame,
    tapes: dict[str, Path],
    window: str,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Simulate every catalog event whose entry falls in ``window``.

    The second return is the panel used for each symbol. The scorer needs
    it for the random-date baseline. Panels are not written to the book.
    """
    missing = [source for source in ("C", "D", "N") if source not in tapes]
    if missing:
        raise FileNotFoundError(f"tapes C, D and N are all required; missing {missing}")
    membership = {source: load_membership(path) for source, path in tapes.items()}
    btc_bars = load_symbol_bars(tapes["C"], HEDGE_SYMBOL)
    btc_funding = load_symbol_funding(tapes["C"], HEDGE_SYMBOL)
    btc_interval = funding_interval(membership["C"], HEDGE_SYMBOL)
    selected = events_for_window(events, window)
    rows: list[dict[str, Any]] = []
    panels: dict[str, dict[str, Any]] = {}
    for event in selected.itertuples(index=False):
        source = str(event.src)
        listing_bars = load_symbol_bars(tapes[source], str(event.symbol))
        listing_funding = load_symbol_funding(tapes[source], str(event.symbol))
        listing_every = funding_interval(membership[source], str(event.symbol))
        deadline, deadline_kind = listing_deadline(membership[source], str(event.symbol))
        trade = simulate_spread(
            listing_bars,
            btc_bars,
            symbol=str(event.symbol),
            launch=event.launch,
            listing_funding=listing_funding,
            btc_funding=btc_funding,
            listing_interval=listing_every,
            btc_interval=btc_interval,
            deadline=deadline,
            deadline_kind=deadline_kind,
        )
        trade["src"] = source
        trade["typ"] = str(event.typ)
        trade["catalog_entry"] = pd.Timestamp(event.entry)
        trade["catalog_exit"] = pd.Timestamp(event.exit)
        entry = trade["entry_time"]
        trade["entry_matches_catalog"] = bool(pd.notna(entry) and pd.Timestamp(entry) == pd.Timestamp(event.entry))
        rows.append(trade)
        panels[str(event.symbol)] = {
            "listing": listing_bars,
            "btc": btc_bars,
            "listing_funding": listing_funding,
            "btc_funding": btc_funding,
            "launch": pd.Timestamp(event.launch),
            "deadline": deadline,
            "deadline_kind": deadline_kind,
            "listing_interval": listing_every,
            "btc_interval": btc_interval,
            "src": source,
        }
    trades = pd.DataFrame(rows)
    return trades, panels


def run_window(
    events: pd.DataFrame,
    tapes: dict[str, Path],
    config: CellConfig,
    window: str,
    output_dir: Path,
    *,
    main_output_hash: str | None = None,
    main_output_dir: Path | None = None,
    tape_reports: list[dict[str, object]] | None = None,
    panels_out: dict[str, dict[str, Any]] | None = None,
) -> dict[str, object]:
    """Run the engine for one window and write the book. No metrics."""
    unlock = assert_closed_window_allowed(
        window,
        cell_name=config.name,
        main_output_hash=main_output_hash,
        main_output_dir=main_output_dir,
    )
    trades, panels = build_trades(events, tapes, window)
    if panels_out is not None:
        panels_out.update(panels)
    hashes = source_hashes()
    taken = trades.loc[trades["exit_reason"] != "no_trade"] if len(trades) else trades
    manifest: dict[str, object] = {
        "cell": config.name or CELL_NAME,
        "window": window,
        "live": "off",
        "paper_only": True,
        "funding_included": True,
        "funding_zero_filled": False,
        "metrics_computed": False,
        "hash_status": hashes["hash_status"],
        "garwe_ack": hashes["garwe_ack"],
        "fill": "next_open",
        "entry": "next_open after the first full 1h bar closing at or after launch+24h",
        "stop": "-12% spread on 1h closes, fill at the next open, no intrabar fill",
        "hold": "14 days, or the last tradable bar before delivery or delist",
        "n_events": int(len(trades)),
        "n_trades": int(len(taken)),
        "n_funding_missing": int(taken["funding_missing"].sum()) if len(taken) else 0,
        "n_truncated": int(taken["truncated"].sum()) if len(taken) else 0,
        "n_catalog_entry_mismatches": int((~taken["entry_matches_catalog"]).sum()) if len(taken) else 0,
        "cost": cost_snapshot(),
        "coverage": coverage_disclosure(),
        "documents": {
            "proposal_sha256": PROPOSAL_SHA256,
            "rules_sha256": RULES_SHA256,
            "lock_sha256": LOCK_SHA256,
            "prereg_sha256": PREREG_SHA256,
            "kill_sha256": KILL_SHA256,
            "countersign_sha256": hashes["countersign_sha256"],
        },
        "harness_sha256": hashes["harness_sha256"],
        "scorer_sha256": hashes["scorer_sha256"],
        "tapes": tape_reports,
        "closed_window_unlocked_with_main_hash": unlock,
    }
    output_hash = write_outputs(Path(output_dir), trades, manifest)
    return {
        "output_dir": str(output_dir),
        "output_sha256": output_hash,
        "n_trades": manifest["n_trades"],
        "harness_sha256": hashes["harness_sha256"],
        "scorer_sha256": hashes["scorer_sha256"],
        "hash_status": hashes["hash_status"],
        "trades": trades,
        "panels": panels,
    }


def load_book(output_dir: Path) -> pd.DataFrame:
    """Read trades.csv back. Used by the scorer and by tests."""
    frame = pd.read_csv(Path(output_dir) / "trades.csv")
    for column in frame.columns:
        if column.endswith("_time") or column.endswith("_open") or column in {
            "launch",
            "catalog_entry",
            "catalog_exit",
            "signal_open",
            "stop_trigger_open",
        }:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    return frame


def manifest_of(output_dir: Path) -> dict[str, object]:
    return json.loads((Path(output_dir) / "manifest.json").read_text(encoding="utf-8"))
