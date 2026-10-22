"""Command line for the xs_crowd_lsr_contrarian v2 harness.

The main-window command is::

    PYTHONHASHSEED=0 python -m research.xs_crowd_lsr_contrarian run \\
      --root /workspace/research \\
      --window main \\
      --output /workspace/research/xs_crowd_lsr_contrarian_runs/main

``PYTHONHASHSEED=0`` has to be set by the shell. Assigning it inside the
interpreter does not turn hash randomization off, and the process refuses
to run the book or the random book unless the variable is already ``0``.

``run`` writes the book and, on main, the random book. It does not score
and it does not print a metric. ``score`` is a separate invocation. The
holdout is also a separate invocation and stays shut until ``--holdout``,
``--seal-hash``, and a main directory whose verdict is PASS are all present.

There is no seed flag and no sizing flag. G = 1.18 and 0.59 per leg.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research.xs_crowd_lsr_contrarian.hashing import (
    assert_documents,
    assert_pythonhashseed,
    format_source_hashes,
)
from research.xs_crowd_lsr_contrarian.pins import MAIN_COMMAND


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m research.xs_crowd_lsr_contrarian",
        description=(
            "Research-only harness for xs_crowd_lsr_contrarian v2. "
            "Live off. No sizing knob."
        ),
    )
    commands = parser.add_subparsers(dest="cmd", required=True)
    commands.add_parser("hash", help="Print source sha256. Reads no tape.")

    run = commands.add_parser(
        "run",
        help="Write the book. On main, also write the random book. Do not score.",
    )
    run.add_argument("--root", type=Path, default=None)
    run.add_argument("--tape-c", type=Path, default=None)
    run.add_argument("--n-tape", type=Path, default=None)
    run.add_argument("--ls-tape", type=Path, default=None)
    run.add_argument("--oi-tape", type=Path, default=None)
    run.add_argument("--window", required=True, choices=("main", "holdout"))
    run.add_argument("--output", type=Path, required=True)
    run.add_argument(
        "--holdout",
        action="store_true",
        help="Required, with --seal-hash and --main-output-dir, to open H2 2025.",
    )
    run.add_argument("--seal-hash", default=None)
    run.add_argument("--main-output-dir", type=Path, default=None)

    score = commands.add_parser("score", help="Score a sealed book. Prints the verdict only.")
    score.add_argument("--book", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "hash":
        sys.stdout.write(format_source_hashes())
        return 0

    if args.cmd == "score":
        # Imported here so a blind run never loads the gate module.
        from research.xs_crowd_lsr_contrarian.scorer import score_directory

        metrics = score_directory(args.book)
        sys.stdout.write(f"verdict {metrics['verdict']}\n")
        sys.stdout.write(f"metrics_sha256 {metrics['metrics_sha256']}\n")
        return 0

    # ``run``. Hash seed and the holdout lock both happen before a tape read.
    assert_pythonhashseed()
    documents = assert_documents()

    from research.xs_crowd_lsr_contrarian.calendar import assert_dropped_monday_list
    from research.xs_crowd_lsr_contrarian.harness import (
        assert_holdout_allowed,
        print_run_hashes,
        refuse_existing_output,
        run_prepared,
    )

    seal = assert_holdout_allowed(
        args.window,
        holdout_flag=bool(args.holdout),
        seal_hash=args.seal_hash,
        main_output_dir=args.main_output_dir,
    )
    assert_dropped_monday_list(args.window)
    refuse_existing_output(args.output)
    hashes = print_run_hashes()

    from research.xs_crowd_lsr_contrarian.book import RatioStore, build_schedule
    from research.xs_crowd_lsr_contrarian.tape import load_research_tapes

    tapes = load_research_tapes(
        window=args.window,
        root=args.root,
        tape_c=args.tape_c,
        n_tape=args.n_tape,
        ls_tape=args.ls_tape,
        oi_tape=args.oi_tape,
        check_pins=True,
    )
    schedule = build_schedule(
        tapes["panel"],
        tapes["membership"],
        RatioStore.from_frame(tapes["ratios"]),
        tapes["funding"],
        tapes["status"],
        args.window,
        tapes["btc"],
    )
    result = run_prepared(
        schedule,
        window=args.window,
        output_dir=args.output,
        documents=documents,
        hashes=hashes,
        tape_report=tapes["report"],
        holdout_seal=seal,
    )
    sys.stdout.write(f"final_sha256 {result['final_sha256']}\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # CLI boundary: one line on stderr, non-zero exit
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


# Re-exported so a reader of this module sees the command the box runs.
__all__ = ["MAIN_COMMAND", "main"]
