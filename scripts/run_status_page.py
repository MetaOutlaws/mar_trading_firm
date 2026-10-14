"""Serve the read-only SGP1 status page.

This process does not import the paper worker, does not call ``init_db``,
and does not start a trading cycle. Restarting it leaves the paper loop
running.

Bind address, port, and token come from ``STATUS_*`` via ``api.status_auth``.
This script does not read those values from ``config.settings``. It never
prints the token. A blank token still binds the port and answers 503, so a
remote client can tell the page is off without receiving the book.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import uvicorn

# `python scripts/run_status_page.py` puts this file's directory on sys.path,
# not the checkout root, so `import api` raises ModuleNotFoundError. The
# compose files also set PYTHONPATH=/app. Inserting the root here covers a
# host run that did not.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT_STR = str(_REPO_ROOT)
if _REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, _REPO_ROOT_STR)

from api.status_auth import configured_token, status_page_host, status_page_port  # noqa: E402


def main() -> int:
    from config.logging_setup import setup_logging

    setup_logging("status_page")
    log = logging.getLogger("status_page")
    if not configured_token():
        log.warning(
            "STATUS_PAGE_TOKEN is unset. The status page is disabled and "
            "will refuse every request."
        )
    uvicorn.run(
        "api.status_app:app",
        host=status_page_host(),
        port=status_page_port(),
        reload=False,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
