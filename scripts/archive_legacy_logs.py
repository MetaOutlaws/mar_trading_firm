"""
Archive the predecessor project's unbounded log files.

`../mar_trading_bot/trading_bot_2.log` grew to ~496 MB because it had no
rotation. Rather than deleting history outright, this keeps the tail (the only
part with diagnostic value) plus a gzip of the whole file, then truncates the
original.

Usage:
    python scripts/archive_legacy_logs.py            # dry run, shows what it would do
    python scripts/archive_legacy_logs.py --execute   # actually archive
"""

from __future__ import annotations

import argparse
import gzip
import shutil
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from config.settings import PROJECT_ROOT

LEGACY_PROJECT = PROJECT_ROOT.parent / "mar_trading_bot"
LEGACY_LOGS = ("trading_bot_2.log", "long_discovery.log", "short_discovery.log")

# Keeping the last 20k lines preserves recent behaviour without the bulk.
TAIL_LINES = 20_000


def human_size(num_bytes: int) -> str:
    """Format a byte count for display."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def archive_log(path: Path, archive_dir: Path, execute: bool) -> None:
    """Gzip a log, save its tail, and truncate the original."""
    size = path.stat().st_size
    print(f"\n{path.name}: {human_size(size)}")

    if not execute:
        print("  [dry run] would gzip, save tail, and truncate")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    gz_target = archive_dir / f"{path.stem}_{stamp}.log.gz"
    tail_target = archive_dir / f"{path.stem}_{stamp}_tail.log"

    # Full compressed copy. Streamed so a multi-GB file never lands in memory.
    with path.open("rb") as src, gzip.open(gz_target, "wb", compresslevel=6) as dst:
        shutil.copyfileobj(src, dst, length=8 * 1024 * 1024)
    print(f"  compressed -> {gz_target.name} ({human_size(gz_target.stat().st_size)})")

    # Readable tail. A bounded deque keeps memory flat regardless of file size.
    with path.open("r", encoding="utf-8", errors="replace") as src:
        tail = deque(src, maxlen=TAIL_LINES)
    tail_target.write_text("".join(tail), encoding="utf-8")
    print(f"  tail ({len(tail)} lines) -> {tail_target.name}")

    # Truncate in place rather than delete, so anything still holding the handle
    # (an editor, a stale process) keeps a valid file descriptor.
    with path.open("w", encoding="utf-8") as fh:
        fh.write(
            f"# Archived {stamp} UTC to {gz_target.name} "
            f"({human_size(size)} original). Truncated by archive_legacy_logs.py\n"
        )
    print(f"  truncated original ({human_size(size)} reclaimed)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the archive. Without this flag the script only reports.",
    )
    args = parser.parse_args()

    if not LEGACY_PROJECT.exists():
        print(f"Legacy project not found at {LEGACY_PROJECT} - nothing to do.")
        return 0

    archive_dir = PROJECT_ROOT / "logs" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    print(f"Legacy project: {LEGACY_PROJECT}")
    print(f"Archive target: {archive_dir}")

    found = False
    for name in LEGACY_LOGS:
        path = LEGACY_PROJECT / name
        if path.exists() and path.stat().st_size > 0:
            found = True
            archive_log(path, archive_dir, args.execute)

    if not found:
        print("\nNo non-empty legacy logs found.")
    elif not args.execute:
        print("\nRe-run with --execute to apply.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
