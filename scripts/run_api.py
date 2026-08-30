"""Serve the Employee Floor API and dashboard."""

from __future__ import annotations

import uvicorn

from config.settings import get_settings
from core.db import init_db


def main() -> None:
    init_db()
    settings = get_settings()
    uvicorn.run("api.app:app", host=settings.api_host, port=settings.api_port, reload=False)


if __name__ == "__main__":
    main()
