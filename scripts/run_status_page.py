"""Serve the read-only SGP1 status page.

This process does not import the paper worker, does not call ``init_db``,
and does not start a trading cycle. Restarting it leaves the paper loop
running.

The token is read from ``STATUS_PAGE_TOKEN``. This script never prints it.
A blank token still binds the port and answers 503, so a remote client can
tell the page is off without receiving the book.
"""

from __future__ import annotations

import logging
import sys

import uvicorn

from config.settings import get_settings


def main() -> int:
    from config.logging_setup import setup_logging

    setup_logging("status_page")
    log = logging.getLogger("status_page")
    settings = get_settings()
    if not settings.status_page_token.strip():
        log.warning(
            "STATUS_PAGE_TOKEN is unset. The status page is disabled and "
            "will refuse every request."
        )
    uvicorn.run(
        "api.status_app:app",
        host=settings.status_page_host,
        port=settings.status_page_port,
        reload=False,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
