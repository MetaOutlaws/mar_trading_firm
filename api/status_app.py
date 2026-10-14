"""Read-only HTTPS status page for the SGP1 paper box.

GET and HEAD only. A missing ``STATUS_PAGE_TOKEN`` refuses every request.
The process that serves this app is separate from the paper worker.
"""

from __future__ import annotations

import html
import json
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from api.status_auth import (
    SlidingWindowLimiter,
    client_key,
    configured_token,
    credentials_match,
    limiter_from_env,
)
from api.status_snapshot import build_snapshot

_NO_STORE = {"Cache-Control": "no-store"}
_AUTH_HEADER = {
    "WWW-Authenticate": 'Bearer realm="sgp1-status", Basic realm="sgp1-status"',
    "Cache-Control": "no-store",
}


def _esc(value: Any) -> str:
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def _money(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:,.2f}"
    return _esc(value)


def render_status_html(snapshot: dict[str, Any]) -> str:
    """One page, no scripts, no further requests. Values are escaped."""
    health = snapshot.get("health") or {}
    equity = snapshot.get("equity_cash") or {}
    snap = equity.get("equity_snapshot") or {}
    regime = snapshot.get("regime") or {}
    git = snapshot.get("git") or {}
    head = git.get("head") or {}
    deployed = git.get("deployed_sha") or {}
    worker = snapshot.get("worker") or {}
    scan = snapshot.get("last_scan_summary") or {}
    positions = snapshot.get("open_positions") or []
    trades = snapshot.get("recent_trades") or []
    errors = worker.get("recent_errors") or []

    position_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(row.get('symbol'))}</td>"
        f"<td>{_esc(row.get('side'))}</td>"
        f"<td>{_esc(row.get('quantity'))}</td>"
        f"<td>{_money(row.get('entry_price'))}</td>"
        f"<td>{_esc(row.get('strategy_label'))}</td>"
        f"<td>{_esc(row.get('sleeve'))}</td>"
        f"<td>{_esc(row.get('strategy_version'))}</td>"
        "</tr>"
        for row in positions
    ) or "<tr><td colspan='7'>No open positions</td></tr>"

    trade_rows = "\n".join(
        "<tr>"
        f"<td>{_esc(row.get('exit_time'))}</td>"
        f"<td>{_esc(row.get('symbol'))}</td>"
        f"<td>{_esc(row.get('side'))}</td>"
        f"<td>{_money(row.get('net_pnl'))}</td>"
        f"<td>{_esc(row.get('strategy_label'))}</td>"
        f"<td>{_esc(row.get('sleeve'))}</td>"
        f"<td>{_esc(row.get('strategy_version'))}</td>"
        "</tr>"
        for row in trades
    ) or "<tr><td colspan='7'>No closed trades</td></tr>"

    error_rows = "\n".join(
        f"<li><span class='src'>{_esc(row.get('source'))}</span> {_esc(row.get('message'))}</li>"
        for row in errors
    ) or "<li>None</li>"

    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>SGP1 status</title>
<style>
  body {{
    font: 15px/1.4 ui-sans-serif, system-ui, sans-serif;
    margin: 1.5rem; color: #1c1917; background: #fafaf9;
  }}
  h1 {{ font-size: 1.25rem; margin: 0 0 0.25rem; }}
  h2 {{ font-size: 1rem; margin: 1.5rem 0 0.4rem; }}
  p.meta {{ color: #57534e; margin: 0; }}
  .ok {{ color: #166534; }} .degraded {{ color: #9a3412; }}
  dl {{ display: grid; grid-template-columns: 12rem 1fr; gap: 0.2rem 1rem; margin: 0; }}
  dt {{ color: #57534e; }} dd {{ margin: 0; font-variant-numeric: tabular-nums; }}
  table {{ border-collapse: collapse; width: 100%; background: white; }}
  th, td {{
    border: 1px solid #e7e5e4; padding: 0.3rem 0.5rem;
    text-align: left; vertical-align: top;
  }}
  th {{ background: #f5f5f4; font-weight: 600; }}
  code {{ font-family: ui-monospace, monospace; font-size: 0.9em; }}
  .src {{ color: #57534e; }}
</style>
</head>
<body>
<h1>SGP1 paper status</h1>
<p class="meta">Read-only. Generated {_esc(snapshot.get('generated_at'))}.
Mode {_esc(snapshot.get('mode'))}.</p>
<p class="meta">JSON: <code>GET /api/status</code></p>

<h2>Health</h2>
<dl>
  <dt>Status</dt><dd class="{_esc(health.get('status'))}">{_esc(health.get('status'))}</dd>
  <dt>Database</dt><dd>{_esc(health.get('database'))}</dd>
  <dt>Worker</dt><dd>{_esc(health.get('worker'))}</dd>
</dl>

<h2>Equity / cash</h2>
<dl>
  <dt>Cash</dt><dd>{_money(equity.get('cash'))}</dd>
  <dt>Contributed capital</dt><dd>{_money(equity.get('contributed_capital'))}</dd>
  <dt>Closed realised P&amp;L</dt><dd>{_money(equity.get('closed_realised_pnl'))}</dd>
  <dt>Equity snapshot</dt><dd>{_money(snap.get('equity') if isinstance(snap, dict) else None)}</dd>
  <dt>Snapshot time</dt><dd>{_esc(snap.get('recorded_at') if isinstance(snap, dict) else None)}</dd>
  <dt>Journal</dt><dd>{_esc(equity.get('journal_path'))}</dd>
</dl>

<h2>Open positions ({len(positions)})</h2>
<table>
  <thead><tr>
    <th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th>
    <th>Strategy</th><th>Sleeve</th><th>Version</th>
  </tr></thead>
  <tbody>
  {position_rows}
  </tbody>
</table>

<h2>Recent trades</h2>
<table>
  <thead><tr>
    <th>Exit</th><th>Symbol</th><th>Side</th><th>Net</th>
    <th>Strategy</th><th>Sleeve</th><th>Version</th>
  </tr></thead>
  <tbody>
  {trade_rows}
  </tbody>
</table>

<h2>Last scan summary</h2>
<dl>
  <dt>When</dt><dd>{_esc(scan.get('logged_at'))}</dd>
  <dt>Type</dt><dd>{_esc(scan.get('scan_type'))}</dd>
  <dt>Bar</dt><dd>{_esc(scan.get('bar_time'))}</dd>
  <dt>Summary</dt><dd>{_esc(scan.get('summary') or scan.get('rationale'))}</dd>
  <dt>Signals / entries / fills / exits</dt>
  <dd>{_esc(scan.get('signals'))} / {_esc(scan.get('entries_opened'))}
  / {_esc(scan.get('fills'))} / {_esc(scan.get('exits'))}</dd>
</dl>

<h2>Regime</h2>
<dl>
  <dt>Label</dt><dd>{_esc(regime.get('label'))}</dd>
  <dt>As of</dt><dd>{_esc(regime.get('as_of'))}</dd>
  <dt>Age (seconds)</dt><dd>{_esc(regime.get('age_seconds'))}</dd>
  <dt>Source</dt><dd>{_esc(regime.get('source'))}</dd>
</dl>

<h2>HEAD and DEPLOYED_SHA</h2>
<dl>
  <dt>HEAD</dt><dd><code>{_esc(head.get('sha'))}</code> ({_esc(head.get('source'))})</dd>
  <dt>DEPLOYED_SHA</dt>
  <dd><code>{_esc(deployed.get('sha'))}</code> ({_esc(deployed.get('path'))})</dd>
</dl>

<h2>Worker</h2>
<dl>
  <dt>Liveness</dt><dd>{_esc(worker.get('state'))}</dd>
  <dt>Last heartbeat</dt>
  <dd>{_esc(worker.get('last_heartbeat_at'))} ({_esc(worker.get('heartbeat_source'))})</dd>
  <dt>Age (seconds)</dt><dd>{_esc(worker.get('age_seconds'))}</dd>
  <dt>Stale after (seconds)</dt><dd>{_esc(worker.get('stale_after_seconds'))}</dd>
  <dt>Last cycle</dt><dd>{_esc(worker.get('last_cycle_at'))}</dd>
  <dt>Cycle age (seconds)</dt><dd>{_esc(worker.get('last_cycle_age_seconds'))}</dd>
</dl>
<h2>Recent errors</h2>
<ul>
  {error_rows}
</ul>
</body>
</html>
"""
    return body


def create_status_app(*, limiter: SlidingWindowLimiter | None = None) -> FastAPI:
    """Status app. Routes are registered as GET. The guard rejects every other method."""
    app = FastAPI(
        title="SGP1 status",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.limiter = limiter or limiter_from_env()
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def status_page() -> HTMLResponse:
        page = render_status_html(build_snapshot())
        return HTMLResponse(page, headers=_NO_STORE)

    @router.get("/api/status")
    def status_json() -> JSONResponse:
        return JSONResponse(build_snapshot(), headers=_NO_STORE)

    @app.middleware("http")
    async def guard(request: Request, call_next):  # noqa: ANN001
        peer = request.client.host if request.client else None
        key = client_key(peer, request.headers.get("x-real-ip"))
        decision = app.state.limiter.check(key)
        if not decision.allowed:
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={
                    "Retry-After": str(decision.retry_after),
                    "Cache-Control": "no-store",
                },
            )
        if request.method not in {"GET", "HEAD"}:
            return JSONResponse(
                {"detail": "method not allowed"},
                status_code=405,
                headers={"Allow": "GET, HEAD", "Cache-Control": "no-store"},
            )
        # Fail closed: a missing token never reaches the snapshot.
        expected = configured_token()
        if not expected:
            return JSONResponse(
                {"detail": "status page disabled"},
                status_code=503,
                headers=_NO_STORE,
            )
        if not credentials_match(request.headers.get("authorization"), expected):
            return JSONResponse({"detail": "unauthorized"}, status_code=401, headers=_AUTH_HEADER)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(router)
    app.state.status_router = router
    return app


app = create_status_app()


def snapshot_json(snapshot: dict[str, Any]) -> str:
    """Stable JSON for tests that compare a rendered page with the document."""
    return json.dumps(snapshot, default=str)
