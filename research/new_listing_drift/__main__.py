"""Command line for the listing-drift harness.

The main-window command, after Garwe has countersigned the provisional
hashes, is::

    python -m research.new_listing_drift run \\
      --cell new_listing_drift_short \\
      --tape-c /workspace/research/universe96_full_history_20261016 \\
      --tape-d /workspace/research/delisted_perps_history_20261016 \\
      --tape-n /workspace/research/new_listings_perp_20261016 \\
      --window main \\
      --output /workspace/research/new_listing_drift_runs/main

That writes the book and then the scorer. Live stays off.

Until ``COUNTERSIGN.md`` exists, a path whose directory name is one of
the real tapes is refused before any bar is read. ``hash`` prints the
provisional source digests and reads no tape. ``harness`` stops before
the scorer. The holdout and the 2026 veto add ``--main-output-dir`` and
``--main-output-hash`` and refuse to start without them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research.new_listing_drift.catalog import DEFAULT_EVENTS_PATH, load_events
from research.new_listing_drift.cells import CELL_NAME, get_cell
from research.new_listing_drift.hashing import format_source_hashes
from research.new_listing_drift.tape import assert_real_tapes_closed, verify_sums

MAIN_COMMAND = (
    "python -m research.new_listing_drift run "
    "--cell new_listing_drift_short "
    "--tape-c /workspace/research/universe96_full_history_20261016 "
    "--tape-d /workspace/research/delisted_perps_history_20261016 "
    "--tape-n /workspace/research/new_listings_perp_20261016 "
    "--window main "
    "--output /workspace/research/new_listing_drift_runs/main"
)


def _add_book_args(parser: argparse.ArgumentParser, *, with_score: bool) -> None:
    parser.add_argument("--cell", default=CELL_NAME)
    parser.add_argument("--tape-c", type=Path, required=True)
    parser.add_argument("--tape-d", type=Path, required=True)
    parser.add_argument("--tape-n", type=Path, required=True)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS_PATH)
    parser.add_argument("--window", required=True, choices=("main", "holdout", "veto"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--main-output-hash", default=None)
    parser.add_argument("--main-output-dir", type=Path, default=None)
    if with_score:
        parser.add_argument("--permutations", type=int, default=None)
        parser.add_argument("--bootstrap", type=int, default=None)


def _tapes(args: argparse.Namespace) -> dict[str, Path]:
    return {"C": args.tape_c, "D": args.tape_d, "N": args.tape_n}


def _open_tapes(args: argparse.Namespace) -> tuple[dict[str, Path], list[dict[str, object]]]:
    """Verify SUMS, then refuse the real directories if Garwe has not signed.

    The name check happens before verify so the box paths are not opened
    at all. ``verify_sums`` still runs for any other directory, and a
    SUMS file that matches the real pin is refused as well.
    """
    tapes = _tapes(args)
    assert_real_tapes_closed(tapes, pins_matched=False)
    reports = [verify_sums(path, source) for source, path in tapes.items()]
    assert_real_tapes_closed(tapes, pins_matched=any(bool(r["pins_matched"]) for r in reports))
    cell = get_cell(args.cell)
    if cell.check_tape_pins and not all(bool(r["pins_matched"]) for r in reports):
        raise RuntimeError(
            "SHA256SUMS does not match the pinned tape digests "
            "(C ab447221, D 5d81bda3, N 9c9916e2)"
        )
    return tapes, reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.new_listing_drift",
        description="Paper-only new-listing drift harness. Live off.",
    )
    commands = parser.add_subparsers(dest="cmd", required=True)
    commands.add_parser("hash", help="Print provisional harness and scorer sha256. Reads no tape.")
    _add_book_args(commands.add_parser("harness", help="Write the book. Do not score."), with_score=False)
    _add_book_args(
        commands.add_parser(
            "run",
            help="Write the book and score it. Refuses real tapes until Garwe countersigns.",
        ),
        with_score=True,
    )
    score = commands.add_parser("score", help="Score an existing book. Needs the tapes for the random book.")
    score.add_argument("--book", type=Path, required=True)
    score.add_argument("--cell", default=CELL_NAME)
    score.add_argument("--tape-c", type=Path, required=True)
    score.add_argument("--tape-d", type=Path, required=True)
    score.add_argument("--tape-n", type=Path, required=True)
    score.add_argument("--events", type=Path, default=DEFAULT_EVENTS_PATH)
    score.add_argument("--permutations", type=int, default=None)
    score.add_argument("--bootstrap", type=int, default=None)
    args = parser.parse_args(argv)

    # Every invocation prints the source hashes so a run log identifies the code.
    sys.stdout.write(format_source_hashes())

    if args.cmd == "hash":
        return 0

    from research.new_listing_drift.harness import assert_closed_window_allowed, manifest_of, run_window

    if args.cmd == "score":
        from research.new_listing_drift.harness import build_trades
        from research.new_listing_drift.scorer import N_BOOTSTRAP, N_PERMUTATIONS, score_book

        # score_book repeats the closed-window check against the manifest.
        # The hash comparison itself happened when the book was written.
        manifest = manifest_of(args.book)
        window = str(manifest["window"])
        tapes, _reports = _open_tapes(args)
        events = load_events(args.events, check_pin=True)
        _trades, panels = build_trades(events, tapes, window)
        metrics = score_book(
            args.book,
            panels,
            n_perm=args.permutations or N_PERMUTATIONS,
            n_bootstrap=args.bootstrap or N_BOOTSTRAP,
        )
        print(f"verdict {metrics['verdict']}")
        print(f"hash_status {metrics['hash_status']}")
        print(f"output_sha256 {metrics['output_sha256']}")
        return 0

    cell = get_cell(args.cell)
    if not cell.runnable:
        raise NotImplementedError(cell.note)
    # The lock runs before the tape is opened, so a missing hash never reads a bar.
    assert_closed_window_allowed(
        args.window,
        cell_name=cell.name,
        main_output_hash=args.main_output_hash,
        main_output_dir=args.main_output_dir,
    )
    tapes, reports = _open_tapes(args)
    events = load_events(args.events, check_pin=True)
    result = run_window(
        events,
        tapes,
        cell,
        args.window,
        args.output,
        main_output_hash=args.main_output_hash,
        main_output_dir=args.main_output_dir,
        tape_reports=reports,
    )
    print(f"trades {result['n_trades']}")
    print(f"book_sha256 {result['output_sha256']}")
    print(f"hash_status {result['hash_status']}")
    if args.cmd == "harness":
        print("metrics_computed false")
        return 0

    from research.new_listing_drift.scorer import N_BOOTSTRAP, N_PERMUTATIONS, score_book

    metrics = score_book(
        args.output,
        result["panels"],
        n_perm=args.permutations or N_PERMUTATIONS,
        n_bootstrap=args.bootstrap or N_BOOTSTRAP,
    )
    print(f"verdict {metrics['verdict']}")
    print(f"output_sha256 {metrics['output_sha256']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI boundary, one line, non-zero exit
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
