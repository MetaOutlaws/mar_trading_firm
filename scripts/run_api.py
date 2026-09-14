"""Serve the Employee Floor API and dashboard."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from config.settings import get_settings
from core.db import init_db


def bind_host(
    configured: str,
    *,
    in_docker: bool | None = None,
    in_cursor_agent: bool | None = None,
) -> str:
    """Host uvicorn actually binds.

    API_HOST=127.0.0.1 is correct on a laptop: the browser and the process
    share loopback. Docker port-publish and Cursor's preview sidecar dial the
    *container IP* (and sometimes [::1]), not 127.0.0.1. A loopback-only bind
    then looks healthy from inside the VM while the operator's browser gets
    ERR_CONNECTION_REFUSED.
    """
    if in_docker is None:
        in_docker = Path("/.dockerenv").exists()
    if in_cursor_agent is None:
        in_cursor_agent = os.environ.get("CURSOR_AGENT") == "1"
    if not (in_docker or in_cursor_agent):
        return configured
    if configured in {"127.0.0.1", "localhost", "::1", "0.0.0.0"}:
        # Dual-stack. These VMs have bindv6only=0 so IPv4 still works.
        return "::" if in_cursor_agent else "0.0.0.0"
    return configured


def main() -> None:
    init_db()
    settings = get_settings()
    host = bind_host(settings.api_host)
    port = settings.api_port
    # Print the operator URL so Cursor's port detector can auto-forward it.
    print(f"MAR Desk: http://127.0.0.1:{port}/", flush=True)
    uvicorn.run("api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
