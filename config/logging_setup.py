"""
Rotating log configuration.

The predecessor project wrote an unbounded log file that reached 496 MB, which
made it effectively unreadable and unsearchable. Every log here is size-capped
and rotated, so disk usage is bounded no matter how long the firm runs.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys

from config.settings import get_settings

# 20 MB per file, 5 generations => at most ~100 MB per log stream.
MAX_BYTES = 20 * 1024 * 1024
BACKUP_COUNT = 5

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured: set[str] = set()


def setup_logging(name: str = "firm", level: str | None = None) -> logging.Logger:
    """Configure the root logger with a rotating file plus console output.

    Args:
        name: Log stream name; becomes `logs/<name>.log`.
        level: Override the configured level (e.g. "DEBUG").

    Returns:
        The root logger, ready to use.
    """
    settings = get_settings()
    resolved_level = (level or settings.log_level).upper()

    root = logging.getLogger()
    root.setLevel(resolved_level)

    # Idempotent: repeated calls for the same stream must not duplicate handlers.
    if name in _configured:
        return root
    _configured.add(name)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        settings.logs_dir / f"{name}.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # Third-party libraries are chatty at DEBUG and drown out our own signal.
    for noisy in ("urllib3", "pybit", "httpx", "google", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return root
