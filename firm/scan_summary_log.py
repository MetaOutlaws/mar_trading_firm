"""Permanent append-only log of scan-summary Inbox cards.

One JSON object per line at ``data/scan_summaries.jsonl``, under the firm
state directory next to ``firm.db``, ``paper_cash.json``, and
``near_miss_log.jsonl``. The file is never rewritten and never pruned.
See ``docs/runbooks/scan_summary_log.md``.

A failure here is logged and swallowed. It must not change a scan, a gate,
or an order.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

# App-root state dir. On the paper host this is the mounted state directory
# (typically ``/data/state/data/scan_summaries.jsonl``).
LOG_PATH = PROJECT_ROOT / "data" / "scan_summaries.jsonl"


def append_scan_summary(record: dict[str, Any], *, path: Path | None = None) -> None:
    """Append one card. Never raises. Never truncates the file."""
    try:
        _append(record, path or LOG_PATH)
    except Exception:
        logger.exception("Scan summary log was not written; the Inbox row stands")


def _append(record: dict[str, Any], path: Path) -> None:
    if not isinstance(record, dict):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":"), default=str, ensure_ascii=False) + "\n"
    # O_APPEND so a second writer cannot truncate a line the first one wrote.
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
