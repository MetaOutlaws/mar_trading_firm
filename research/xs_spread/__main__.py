"""Command line for the weekly cross-sectional harness.

The main-window command, after Garwe has ACKed the harness and scorer
hashes, is::

    python -m research.xs_spread run \\
      --cell xs_realized_skew_weekly \\
      --tape /workspace/research/universe96_full_history_20261016 \\
      --window main \\
      --output /workspace/research/xs_spread_runs/xs_realized_skew_weekly_main

That writes the book and then the scorer. It does not touch
``config/approved_strategies.json``. Live stays off.

``harness`` stops before the scorer. ``hash`` prints the source digests
and reads no tape. The holdout adds ``--main-output-dir`` and
``--main-output-hash`` (the sha256 of the main run's SHA256SUMS) and
refuses to start without them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research.xs_spread.cells import get_cell
from research.xs_spread.hashing import format_source_hashes
from research.xs_spread.tape import load_tape

MAIN_COMMAND = (
    "python -m research.xs_spread run "
    "--cell xs_realized_skew_weekly "
    "--tape /workspace/research/universe96_full_history_20261016 "
    "--window main "
    "--output /workspace/research/xs_spread_runs/xs_realized_skew_weekly_main"
)


def _add_book_args(parser: argparse.ArgumentParser, *, with_score: bool) -> None:
    parser.add_argument("--cell", required=True)
    parser.add_argument("--tape", type=Path, required=True)
    parser.add_argument("--window", required=True, choices=("main", "holdout", "veto"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--main-output-hash", default=None)
    parser.add_argument("--main-output-dir", type=Path, default=None)
    if with_score:
        parser.add_argument("--permutations", type=int, default=None)
        parser.add_argument("--bootstrap", type=int, default=None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m research.xs_spread",
        description="Paper-only weekly dollar-neutral spread harness. Live off.",
    )
    commands = parser.add_subparsers(dest="cmd", required=True)
    commands.add_parser("hash", help="Print harness and scorer sha256. Reads no tape.")
    _add_book_args(commands.add_parser("harness", help="Write the book. Do not score."), with_score=False)
    _add_book_args(
        commands.add_parser(
            "run",
            help="Write the book and score it. Wait for Garwe's ACK of the source hashes.",
        ),
        with_score=True,
    )
    score = commands.add_parser("score", help="Score an existing book directory.")
    score.add_argument("--book", type=Path, required=True)
    score.add_argument("--permutations", type=int, default=None)
    score.add_argument("--bootstrap", type=int, default=None)
    args = parser.parse_args(argv)

    # Every invocation prints the source hashes so a run log identifies the code.
    sys.stdout.write(format_source_hashes())

    if args.cmd == "hash":
        return 0

    if args.cmd == "score":
        from research.xs_spread.scorer import N_BOOTSTRAP, N_PERMUTATIONS, score_book

        metrics = score_book(
            args.book,
            n_perm=args.permutations or N_PERMUTATIONS,
            n_bootstrap=args.bootstrap or N_BOOTSTRAP,
        )
        print(f"verdict {metrics['verdict']}")
        print(f"output_sha256 {metrics['output_sha256']}")
        return 0

    from research.xs_spread.harness import assert_holdout_allowed, run_window

    cell = get_cell(args.cell)
    if not cell.runnable:
        raise NotImplementedError(cell.note)
    # The holdout lock runs before the tape is opened, so a missing hash
    # never reads a bar.
    assert_holdout_allowed(
        args.window,
        cell_name=cell.name,
        main_output_hash=args.main_output_hash,
        main_output_dir=args.main_output_dir,
    )
    panel, membership, tape_report = load_tape(args.tape, check_pins=cell.check_tape_pins)
    funding = None
    if cell.funding_included:
        from research.xs_spread.tape import load_funding

        funding = load_funding(args.tape)
    result = run_window(
        panel,
        membership,
        cell,
        args.window,
        args.output,
        main_output_hash=args.main_output_hash,
        main_output_dir=args.main_output_dir,
        tape_report=tape_report,
        funding=funding,
    )
    print(f"weeks {result['n_weeks']}")
    print(f"book_sha256 {result['output_sha256']}")
    if args.cmd == "harness":
        print("metrics_computed false")
        return 0

    from research.xs_spread.scorer import N_BOOTSTRAP, N_PERMUTATIONS, score_book

    metrics = score_book(
        args.output,
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
