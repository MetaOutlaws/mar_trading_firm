"""Retire superseded hourly ENTRY sleeves on the paper approval book.

F111 itself is not written into the approval book. The engine would fill that
row on the hourly close. The minute retest is ``core.execution.f111_paper``,
switched on by the versioned config plus the absence of
``data/f111_paper_scan_disabled``.

Default is a dry run. ``--apply`` rewrites only the approval book, after a
backup. It does not start a worker, reset cash, or close a position.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.execution.f111_paper import retire_hourly_entry_records  # noqa: E402
from core.strategy.f111_config import STRATEGY_ID, assert_f111_paper_only, assert_not_a_second_worker  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Rewrite the approval book.")
    parser.add_argument(
        "--book",
        type=Path,
        default=None,
        help="Approval JSON. Defaults to config/approved_strategies.json.",
    )
    args = parser.parse_args(argv)
    assert_not_a_second_worker(False)
    assert_f111_paper_only()
    from config.universe import APPROVALS_PATH

    path = (args.book or APPROVALS_PATH).resolve()
    current = json.loads(path.read_text(encoding="utf-8"))
    updated, removed = retire_hourly_entry_records(current)
    payload = {
        "status": "dry_run" if not args.apply else "applied",
        "strategy_id": STRATEGY_ID,
        "retired_entry_keys": sorted(removed),
        "f111_added_to_engine_plan": False,
        "cash_reset": False,
        "positions_closed": 0,
        "worker_started": False,
    }
    if not args.apply:
        print(json.dumps(payload, indent=2))
        return 0
    before = path.read_bytes()
    if json.loads(before) != current:
        raise RuntimeError("approval book changed during preflight")
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = path.with_name(path.name + ".before-f111-" + now)
    backup.write_bytes(before)
    raw = (json.dumps(updated, indent=2) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".f111-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        if path.read_bytes() != before:
            raise RuntimeError("approval book changed before write")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    payload["backup"] = str(backup)
    payload["approval_before_sha256"] = hashlib.sha256(before).hexdigest()
    payload["approval_after_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    payload["status"] = "entries_retired_exit_supervision_unchanged"
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
