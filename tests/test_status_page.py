"""Read-only SGP1 status page.

These tests do not start the paper worker, place an order, or write the
cash journal. They check auth, the rate limit, the GET-only route table,
and that a snapshot can be built from the book and the state files.
"""

from __future__ import annotations

import ast
import base64
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from config.settings import get_settings
from core.ledger.store import Ledger

TOKEN = "status-test-token-0123456789abcdef"
HEAD_SHA = "a" * 40
DEPLOYED_SHA = "b" * 40
ROOT = Path(__file__).resolve().parents[1]
F111_ID = "mar_f111_r12_extension_latefloor_v1"
L01_VERSION = "l01-long-f111-short-v1"


@pytest.fixture
def status_env(monkeypatch):
    """Token configured, paper mode, predictable rate limit."""
    monkeypatch.setenv("STATUS_PAGE_TOKEN", TOKEN)
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("STATUS_PAGE_RATE_LIMIT", "30")
    monkeypatch.setenv("STATUS_PAGE_RATE_WINDOW_SECONDS", "60")
    monkeypatch.delenv("GIT_SHA", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _app():
    from api.status_app import create_status_app

    return create_status_app()


def _bearer(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _basic(token: str = TOKEN, username: str = "status") -> dict[str, str]:
    raw = base64.b64encode(f"{username}:{token}".encode()).decode("ascii")
    return {"Authorization": f"Basic {raw}"}


def _route_methods(app) -> list[set[str]]:
    found: list[set[str]] = []
    sources = [app, app.state.status_router]
    for source in sources:
        for route in source.routes:
            methods = getattr(route, "methods", None)
            if not methods:
                continue
            found.append(set(methods))
    return found


def test_status_app_has_no_non_get_routes(status_env) -> None:
    """The status app and its router expose GET and HEAD only."""
    app = _app()
    methods = _route_methods(app)
    assert methods, "status app registered no routes"
    for route_methods in methods:
        assert route_methods <= {"GET", "HEAD"}
        assert "GET" in route_methods
    paths = {getattr(route, "path", None) for route in app.state.status_router.routes}
    assert paths == {"/", "/api/status"}


def test_non_get_methods_are_rejected(status_env) -> None:
    app = _app()
    with TestClient(app) as client:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            response = client.request(method, "/api/status", headers=_bearer())
            assert response.status_code == 405
            assert response.json()["detail"] == "method not allowed"


def test_missing_token_disables_the_page(monkeypatch, firm_db) -> None:
    """Fail closed: no token means 503, and the book is not read."""
    monkeypatch.setenv("STATUS_PAGE_TOKEN", "   ")
    monkeypatch.setenv("TRADING_MODE", "paper")
    get_settings.cache_clear()

    def _boom(**_kwargs):
        raise AssertionError("snapshot was built while the page is disabled")

    monkeypatch.setattr("api.status_app.build_snapshot", _boom)
    app = _app()
    with TestClient(app) as client:
        response = client.get("/api/status", headers=_bearer(TOKEN))
    assert response.status_code == 503
    assert response.json() == {"detail": "status page disabled"}
    assert TOKEN not in response.text
    assert "BTCUSDT" not in response.text
    get_settings.cache_clear()


def test_bearer_and_basic_auth(status_env) -> None:
    app = _app()
    with TestClient(app) as client:
        denied = client.get("/api/status")
        assert denied.status_code == 401
        wrong = client.get("/api/status", headers=_bearer("not-the-token"))
        assert wrong.status_code == 401
        query = client.get(f"/api/status?token={TOKEN}")
        assert query.status_code == 401
        ok = client.get("/api/status", headers=_bearer())
        assert ok.status_code == 200
        basic = client.get("/", headers=_basic(username="someone-else"))
        assert basic.status_code == 200
        assert "SGP1 paper status" in basic.text


def test_token_compare_is_constant_time(status_env, monkeypatch) -> None:
    """Both sides are hashed, then compared with hmac.compare_digest."""
    calls: list[tuple[bytes, bytes]] = []
    real = hmac.compare_digest

    def _spy(left: bytes, right: bytes) -> bool:
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr("api.status_auth.hmac.compare_digest", _spy)
    app = _app()
    with TestClient(app) as client:
        client.get("/api/status", headers=_bearer("short"))
        client.get("/api/status", headers=_bearer())
    assert len(calls) >= 2
    for left, right in calls:
        assert len(left) == len(right) == 32
        assert TOKEN.encode() not in (left, right)
    source = (ROOT / "api" / "status_auth.py").read_text(encoding="utf-8")
    assert "compare_digest" in source
    assert "presented ==" not in source
    assert "== expected" not in source


def test_token_is_not_logged_or_rendered(status_env, caplog) -> None:
    import logging

    app = _app()
    with caplog.at_level(logging.DEBUG):
        with TestClient(app) as client:
            response = client.get("/api/status", headers=_bearer())
    assert response.status_code == 200
    assert TOKEN not in response.text
    assert TOKEN not in caplog.text
    get_settings.cache_clear()
    assert TOKEN not in repr(get_settings())


def test_rate_limit_is_per_ip(status_env, monkeypatch) -> None:
    monkeypatch.setenv("STATUS_PAGE_RATE_LIMIT", "2")
    monkeypatch.setenv("STATUS_PAGE_RATE_WINDOW_SECONDS", "60")
    get_settings.cache_clear()
    app = _app()
    with TestClient(app) as client:
        first = {"X-Real-IP": "203.0.113.10"}
        second = {"X-Real-IP": "203.0.113.11"}
        assert client.get("/api/status", headers={**_bearer(), **first}).status_code == 200
        assert client.get("/api/status", headers={**_bearer(), **first}).status_code == 200
        blocked = client.get("/api/status", headers={**_bearer(), **first})
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]
        assert blocked.json()["detail"] == "rate limit exceeded"
        # A different address still has its own window.
        assert client.get("/api/status", headers={**_bearer(), **second}).status_code == 200
    get_settings.cache_clear()


def test_sliding_window_expires_and_public_peers_are_not_spoofed() -> None:
    from api.status_auth import SlidingWindowLimiter, client_key

    now = {"t": 0.0}
    limiter = SlidingWindowLimiter(2, 60, clock=lambda: now["t"])
    assert limiter.check("203.0.113.5").allowed
    now["t"] = 10
    assert limiter.check("203.0.113.5").allowed
    now["t"] = 11
    denied = limiter.check("203.0.113.5")
    assert not denied.allowed
    assert denied.retry_after >= 1
    now["t"] = 70
    assert limiter.check("203.0.113.5").allowed
    # Other keys are independent.
    assert limiter.check("203.0.113.6").allowed

    assert client_key("8.8.8.8", "203.0.113.9") == "8.8.8.8"
    assert client_key("172.18.0.2", "203.0.113.9") == "203.0.113.9"
    assert client_key("testclient", "203.0.113.9") == "203.0.113.9"
    assert client_key("203.0.113.4", "not-an-ip") == "203.0.113.4"


def test_readonly_engine_reads_wal_when_the_directory_cannot_be_written(tmp_path) -> None:
    """SGP1 mounts state read-only. WAL ``mode=ro`` cannot create ``-shm`` there."""
    import sqlite3

    from api.status_snapshot import readonly_engine

    db = tmp_path / "firm.db"
    writer = sqlite3.connect(db)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("CREATE TABLE marks (id INTEGER)")
    writer.execute("INSERT INTO marks VALUES (1)")
    writer.commit()
    writer.execute("INSERT INTO marks VALUES (2)")
    writer.commit()
    writer.close()
    for path in tmp_path.iterdir():
        path.chmod(0o444)
    tmp_path.chmod(0o555)
    engine = readonly_engine(f"sqlite:///{db}")
    try:
        with engine.connect() as opened:
            rows = opened.execute(text("SELECT id FROM marks ORDER BY id")).fetchall()
            assert [row[0] for row in rows] == [1, 2]
            with pytest.raises(Exception):
                opened.execute(text("INSERT INTO marks VALUES (9)"))
    finally:
        engine.dispose()
        tmp_path.chmod(0o755)
        for path in tmp_path.iterdir():
            path.chmod(0o644)


def test_readonly_engine_rejects_writes(firm_db) -> None:
    from api.status_snapshot import readonly_engine

    engine = readonly_engine(f"sqlite:///{firm_db}")
    try:
        with engine.connect() as conn:
            with pytest.raises(Exception):
                conn.execute(text("CREATE TABLE status_should_not_write (id INTEGER)"))
                conn.commit()
    finally:
        engine.dispose()


def _open_and_close(ledger: Ledger) -> None:
    position_id = ledger.open_position(
        symbol="ETHUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=100.0,
        expected_entry_price=100.0,
        take_profit=110.0,
        stop_loss=90.0,
        strategy=F111_ID,
        sector="other",
        signal_score=1.0,
        signal_reason="status page fixture",
        broker_order_id="status-eth",
        strategy_params={
            "strategy_version": L01_VERSION,
            "entry_case": "L01",
            "sleeve": "ETHUSDT|1h|LONG|l01",
        },
    )
    assert ledger.close_position(
        position_id,
        exit_price=101.0,
        expected_exit_price=101.0,
        exit_reason="take_profit",
    )


def _seed_state(tmp_path: Path, monkeypatch, token: str) -> dict[str, datetime]:
    """Point every status read at throwaway files. Does not touch production state.

    The cycle and scan stamps are a minute old so the worker heartbeat is
    fresh. A pid file is written and then ignored: liveness is not that pid.
    """
    from api import status_snapshot

    moment = datetime.now(timezone.utc).replace(microsecond=0)
    cycle_at = moment - timedelta(seconds=90)
    scan_at = moment - timedelta(seconds=30)
    cycle = tmp_path / "last_cycle.json"
    cycle.write_text(
        json.dumps(
            {
                "started_at": cycle_at.isoformat(),
                "errors": ["reconciliation failed: fixture"],
                "halted": False,
                "halt_reason": "",
            }
        ),
        encoding="utf-8",
    )
    log_path = tmp_path / "paper_trading.log"
    log_path.write_text(
        "2026-10-14 12:00:01 | ERROR    | paper | feed down "
        f"STATUS_PAGE_TOKEN={token}\n"
        "2026-10-14 12:00:02 | INFO     | paper | quiet\n",
        encoding="utf-8",
    )
    scan = tmp_path / "scan_summaries.jsonl"
    scan.write_text(
        json.dumps(
            {
                "logged_at": scan_at.isoformat(),
                "action": "inserted",
                "title": "book scan",
                "rationale": "entries opened 0, fills 0, exits 0",
                "payload": {
                    "summary": "book scan quiet",
                    "scan_type": "book",
                    "bar_time": cycle_at.isoformat(),
                    "signals": 2,
                    "entries_opened": 0,
                    "fills": 0,
                    "exits": 0,
                    "rejection_counts": {"no_signal": 2},
                    "dedupe_key": f"book|{cycle_at.isoformat()}",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    soko = tmp_path / "last_soko_trend.json"
    soko.write_text(
        json.dumps({"trend": "bear", "as_of": "2026-10-14T11:00:00+00:00"}),
        encoding="utf-8",
    )
    cash = tmp_path / "paper_cash.json"
    cash.write_text(
        json.dumps(
            {
                "version": 1,
                "events": [
                    {"kind": "capital", "amount": 10000},
                    {"kind": "close", "gross_pnl": 10, "fee": 1, "entry_fee": 1, "funding": 0},
                ],
            }
        ),
        encoding="utf-8",
    )
    git_file = tmp_path / "GIT_SHA"
    git_file.write_text(HEAD_SHA + "\n", encoding="utf-8")
    deployed = tmp_path / "DEPLOYED_SHA"
    deployed.write_text(DEPLOYED_SHA + "\n", encoding="utf-8")
    pid = tmp_path / "paper.pid"
    pid.write_text(str(os.getpid()), encoding="utf-8")

    monkeypatch.setattr(status_snapshot, "LAST_CYCLE_PATH", cycle)
    monkeypatch.setattr(status_snapshot, "PAPER_BAR_STATE_PATH", tmp_path / "no-poll.json")
    monkeypatch.setattr(status_snapshot, "PAPER_LOG_PATH", log_path)
    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", scan)
    monkeypatch.setattr("core.data.soko_trend.LAST_SOKO_TREND_PATH", soko)
    monkeypatch.setattr("core.execution.paper_cash.PAPER_CASH_PATH", cash)
    monkeypatch.setattr("firm.locks.PAPER_PID_PATH", pid)
    monkeypatch.setattr(status_snapshot, "head_candidates", lambda _root: [git_file])
    monkeypatch.setattr(status_snapshot, "deployed_sha_candidates", lambda _root: [deployed])
    return {"cycle_at": cycle_at, "scan_at": scan_at}


def test_snapshot_reports_book_scan_regime_shas_and_worker(
    status_env, firm_db, tmp_path, monkeypatch
) -> None:
    ledger = Ledger(mode="paper", starting_equity=10_000.0)
    ledger.open_position(
        symbol="BTCUSDT",
        side="SHORT",
        quantity=0.5,
        entry_price=200.0,
        expected_entry_price=200.0,
        take_profit=180.0,
        stop_loss=220.0,
        strategy="rsi_trend",
        sector="other",
        signal_score=1.0,
        signal_reason="status page open fixture",
        broker_order_id="status-btc",
        strategy_params={"sleeve": "BTCUSDT|1h|SHORT|rsi_trend", "strategy_id": "rsi_trend"},
    )
    _open_and_close(ledger)
    ledger.record_equity(
        10050.0,
        realised_pnl=8.0,
        unrealised_pnl=0.0,
        exposure=100.0,
        open_position_count=1,
    )
    seeded = _seed_state(tmp_path, monkeypatch, TOKEN)
    monkeypatch.setenv("GIT_SHA", "c" * 40)
    get_settings.cache_clear()

    from core.execution.paper_cash import PaperCashStore

    def _refuse_write(self, _event) -> None:  # noqa: ANN001
        raise AssertionError("status page wrote the cash journal")

    monkeypatch.setattr(PaperCashStore, "record", _refuse_write)

    def _refuse_init() -> None:
        raise AssertionError("status page called init_db")

    monkeypatch.setattr("core.db.init_db", _refuse_init)

    def _refuse_engine(*_args, **_kwargs) -> None:
        raise AssertionError("status page constructed a trading engine")

    monkeypatch.setattr("core.execution.engine.build_engine", _refuse_engine)

    before_db = firm_db.read_bytes()
    cash_path = tmp_path / "paper_cash.json"
    before_cash = cash_path.read_bytes()

    app = _app()
    with TestClient(app) as client:
        response = client.get("/api/status", headers=_bearer())
        page = client.get("/", headers=_bearer())
    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True
    assert body["health"]["status"] == "ok"
    assert body["health"]["database"] == "ok"
    assert body["health"]["worker"] == "alive"
    assert body["equity_cash"]["cash"] == pytest.approx(10009.0)
    assert body["equity_cash"]["contributed_capital"] == pytest.approx(10000.0)
    assert body["equity_cash"]["closed_realised_pnl"] == pytest.approx(8.0)
    assert body["equity_cash"]["equity_snapshot"]["equity"] == pytest.approx(10050.0)

    assert len(body["open_positions"]) == 1
    assert body["open_positions"][0]["symbol"] == "BTCUSDT"
    assert body["open_positions"][0]["strategy_label"] == "BTCUSDT|1h|SHORT|rsi_trend"

    trade = body["recent_trades"][0]
    assert trade["sleeve"] == "ETHUSDT|1h|LONG|l01"
    assert trade["strategy_version"] == L01_VERSION
    assert trade["strategy_label"] == f"ETHUSDT|1h|LONG|l01 · strategy_version {L01_VERSION}"

    scan = body["last_scan_summary"]
    assert scan["present"] is True
    assert scan["summary"] == "book scan quiet"
    assert scan["scan_type"] == "book"
    assert scan["signals"] == 2

    assert body["regime"]["label"] == "bear"
    # Env GIT_SHA is HEAD. The deployed file is the other value. Both show.
    assert body["git"]["head"]["sha"] == "c" * 40
    assert body["git"]["head"]["source"] == "env"
    assert body["git"]["deployed_sha"]["sha"] == DEPLOYED_SHA
    assert body["git"]["deployed_sha"]["source"] == "file"

    assert body["worker"]["alive"] is True
    assert body["worker"]["state"] == "alive"
    assert body["worker"]["heartbeat_source"] == "scan_summary"
    assert body["worker"]["last_heartbeat_at"] == seeded["scan_at"].isoformat()
    assert body["worker"]["age_seconds"] < 120
    assert "pid" not in body["worker"]
    assert "uptime_seconds" not in body["worker"]
    assert body["worker"]["last_cycle_at"] == seeded["cycle_at"].isoformat()
    messages = [row["message"] for row in body["worker"]["recent_errors"]]
    assert any("reconciliation failed: fixture" in message for message in messages)
    assert any("feed down" in message for message in messages)
    assert TOKEN not in response.text
    assert all(TOKEN not in message for message in messages)

    assert page.status_code == 200
    assert "book scan quiet" in page.text
    assert DEPLOYED_SHA in page.text
    assert "c" * 40 in page.text
    assert TOKEN not in page.text

    assert firm_db.read_bytes() == before_db
    assert cash_path.read_bytes() == before_cash


def test_missing_database_stays_read_only(status_env, monkeypatch, tmp_path) -> None:
    missing = tmp_path / "missing.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{missing}")
    get_settings.cache_clear()
    app = _app()
    with TestClient(app) as client:
        response = client.get("/api/status", headers=_bearer())
    assert response.status_code == 200
    body = response.json()
    assert body["health"]["database"] == "unavailable"
    assert body["health"]["status"] == "degraded"
    assert missing.exists() is False
    get_settings.cache_clear()


def test_head_file_and_deployed_sha_are_independent(tmp_path, monkeypatch) -> None:
    from api.status_snapshot import git_status

    git_file = tmp_path / "GIT_SHA"
    deployed = tmp_path / "DEPLOYED_SHA"
    git_file.write_text(HEAD_SHA + "\n", encoding="utf-8")
    deployed.write_text(DEPLOYED_SHA + "\n", encoding="utf-8")
    monkeypatch.delenv("GIT_SHA", raising=False)
    monkeypatch.setattr("api.status_snapshot.head_candidates", lambda _root: [git_file])
    monkeypatch.setattr("api.status_snapshot.deployed_sha_candidates", lambda _root: [deployed])
    payload = git_status(tmp_path)
    assert payload["head"]["sha"] == HEAD_SHA
    assert payload["head"]["source"] == "file"
    assert payload["deployed_sha"]["sha"] == DEPLOYED_SHA
    assert payload["head"]["sha"] != payload["deployed_sha"]["sha"]


def test_cycle_path_matches_the_engine_constant() -> None:
    """The status reader uses the files the paper process already writes."""
    from core.execution.engine import LAST_CYCLE_PATH as engine_path
    from core.execution.paper_bar_eval import PAPER_BAR_STATE_PATH as poll_path

    from api.status_snapshot import LAST_CYCLE_PATH, PAPER_BAR_STATE_PATH

    assert LAST_CYCLE_PATH == engine_path
    assert PAPER_BAR_STATE_PATH == poll_path


def test_status_modules_do_not_import_the_paper_worker() -> None:
    banned_modules = {"scripts.run_paper_trading", "core.execution.engine"}
    banned_names = {"run_paper_trading", "build_engine", "init_db"}
    files = [
        ROOT / "api" / "status_app.py",
        ROOT / "api" / "status_auth.py",
        ROOT / "api" / "status_snapshot.py",
        ROOT / "scripts" / "run_status_page.py",
    ]
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in banned_modules
                imported = {alias.name for alias in node.names}
                assert imported.isdisjoint(banned_names)
            elif isinstance(node, ast.Import):
                modules = {alias.name for alias in node.names}
                assert modules.isdisjoint(banned_modules)


def test_desk_app_does_not_grow_a_status_route() -> None:
    from api.app import app as desk

    paths = {getattr(route, "path", None) for route in desk.routes}
    assert "/api/status" not in paths


def test_ufw_script_only_adds_allow_rules() -> None:
    script = ROOT / "scripts" / "ufw_status_443.sh"
    text = script.read_text(encoding="utf-8")
    for line in text.splitlines():
        code = line.split("#", 1)[0]
        for forbidden in (
            "ufw enable",
            "ufw reset",
            "ufw delete",
            "ufw --force",
            "default deny",
            "ufw reload",
        ):
            assert forbidden not in code
    assert "ufw allow" in text
    assert "443/tcp" in text
    completed = __import__("subprocess").run(
        ["bash", str(script), "--dry-run"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "443/tcp" in completed.stdout
    assert "operator ssh" in completed.stdout
    assert "would not turn the firewall on" in completed.stdout


def test_status_module_does_not_need_settings_changes(monkeypatch) -> None:
    """STATUS_* is read in the status module. settings.py has no status fields.

    A cached Settings object is not consulted, so seeing a new token does
    not require ``get_settings.cache_clear()`` or a settings.py edit.
    """
    settings_src = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")
    assert "status_page" not in settings_src.lower()
    assert "STATUS_PAGE" not in settings_src
    assert "STATUS_TLS" not in settings_src

    from config.settings import Settings, get_settings

    status_fields = {
        "status_page_token",
        "status_page_host",
        "status_page_port",
        "status_page_rate_limit",
        "status_page_rate_window_seconds",
    }
    assert status_fields.isdisjoint(Settings.model_fields)

    get_settings.cache_clear()
    cached_before = get_settings()
    monkeypatch.setenv("STATUS_PAGE_TOKEN", "fresh-token-not-in-settings")
    monkeypatch.setenv("STATUS_PAGE_HOST", "0.0.0.0")
    monkeypatch.setenv("STATUS_PAGE_PORT", "9099")
    monkeypatch.setenv("STATUS_PAGE_RATE_LIMIT", "7")
    monkeypatch.setenv("STATUS_PAGE_RATE_WINDOW_SECONDS", "15")
    # The cache is still the object built before these env writes.
    assert get_settings() is cached_before
    for field_name in status_fields:
        assert not hasattr(cached_before, field_name)

    from api.status_auth import (
        configured_token,
        limiter_from_env,
        status_page_host,
        status_page_port,
    )

    assert configured_token() == "fresh-token-not-in-settings"
    assert status_page_host() == "0.0.0.0"
    assert status_page_port() == 9099
    limiter = limiter_from_env()
    assert limiter.limit == 7
    assert limiter.window_seconds == 15.0
    assert "fresh-token-not-in-settings" not in repr(cached_before)

    for path in (ROOT / "api" / "status_auth.py", ROOT / "scripts" / "run_status_page.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "config.settings"
            elif isinstance(node, ast.Import):
                assert all(alias.name != "config.settings" for alias in node.names)
    auth_src = (ROOT / "api" / "status_auth.py").read_text(encoding="utf-8")
    assert "os.environ" in auth_src
    assert "STATUS_PAGE_TOKEN" in auth_src


# Container environment keys the status compose files may set. Anything else
# in the host env file, including exchange keys and API_TOKEN, stays out.
_STATUS_ENV_ALLOWLIST = frozenset(
    {
        "PYTHONPATH",
        "STATUS_PAGE_TOKEN",
        "STATUS_PAGE_HOST",
        "STATUS_PAGE_PORT",
        "STATUS_PAGE_RATE_LIMIT",
        "STATUS_PAGE_RATE_WINDOW_SECONDS",
        "STATUS_PAGE_DOMAIN",
        "STATUS_TLS_EMAIL",
        "STATUS_TLS_SAN",
        "DATABASE_URL",
        "TRADING_MODE",
        "GIT_SHA",
        "STATUS_WORKER_STALE_SECONDS",
    }
)
_STATUS_SERVICE_REQUIRED = frozenset(
    {
        "PYTHONPATH",
        "STATUS_PAGE_TOKEN",
        "STATUS_PAGE_HOST",
        "STATUS_PAGE_PORT",
        "DATABASE_URL",
        "TRADING_MODE",
        "GIT_SHA",
        "STATUS_WORKER_STALE_SECONDS",
    }
)
_CADDY_ENV_ALLOWLIST = frozenset(
    {"STATUS_PAGE_DOMAIN", "STATUS_TLS_EMAIL", "STATUS_TLS_SAN"}
)
_SECRET_NAME_MARKERS = (
    "API_KEY",
    "API_SECRET",
    "API_TOKEN",
    "SECRET",
    "PASSWORD",
    "CREDENTIAL",
    "BYBIT",
    "OPENAI",
    "ANTHROPIC",
    "GEMINI",
    "DEEPSEEK",
    "XAI_",
)


def _unquoted(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _compose_environments(text: str) -> dict[str, dict[str, str]]:
    """Parse `environment:` mappings. Comments are not keys."""
    services: dict[str, dict[str, str]] = {}
    current: str | None = None
    in_env = False
    for raw in text.splitlines():
        code = raw.split("#", 1)[0].rstrip()
        if not code.strip():
            continue
        indent = len(code) - len(code.lstrip(" "))
        stripped = code.strip()
        if "env_file" in stripped:
            raise AssertionError(f"env_file is set: {stripped}")
        if indent == 2 and stripped.endswith(":") and not stripped.startswith("-"):
            current = stripped[:-1].strip()
            services.setdefault(current, {})
            in_env = False
            continue
        if current is None:
            continue
        if indent == 4 and stripped == "environment:":
            in_env = True
            continue
        if not in_env:
            continue
        if indent <= 4:
            in_env = False
            continue
        key, sep, value = stripped.partition(":")
        assert sep, stripped
        services[current][key.strip()] = _unquoted(value)
    return services


def _interpolated_names(text: str) -> set[str]:
    """`${NAME` and `${NAME:-default}` references outside comments."""
    import re

    names: set[str] = set()
    for raw in text.splitlines():
        code = raw.split("#", 1)[0]
        names.update(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", code))
    return names


def test_run_status_page_imports_from_another_cwd(tmp_path: Path) -> None:
    """The entrypoint imports `api` when cwd is not the repo and PYTHONPATH is unset.

    Running the file as a script puts `scripts/` on sys.path. An editable
    install would hide that, so the probe removes the checkout from sys.path
    before executing the file.
    """
    import subprocess
    import sys

    script = ROOT / "scripts" / "run_status_page.py"
    probe = """
import os
import sys
from pathlib import Path

script = Path(sys.argv[1]).resolve()
root = script.parent.parent
os.chdir(sys.argv[2])
kept = []
for entry in sys.path:
    if not entry:
        kept.append(entry)
        continue
    try:
        resolved = Path(entry).resolve()
    except OSError:
        kept.append(entry)
        continue
    if resolved == root or root in resolved.parents:
        continue
    kept.append(entry)
sys.path = kept
sys.path.insert(0, str(script.parent))


def _finder_uses_checkout(finder):
    module = sys.modules.get(getattr(finder, "__module__", ""))
    mapping = getattr(module, "MAPPING", None)
    if not isinstance(mapping, dict):
        return False
    for value in mapping.values():
        try:
            if Path(str(value)).resolve().is_relative_to(root):
                return True
        except (OSError, ValueError):
            continue
    return False


sys.meta_path = [finder for finder in sys.meta_path if not _finder_uses_checkout(finder)]
os.environ.pop("PYTHONPATH", None)
try:
    import api  # noqa: F401
except ModuleNotFoundError:
    pass
else:
    raise SystemExit("api was importable before the entrypoint ran")
namespace = {"__name__": "run_status_page_probe", "__file__": str(script)}
exec(compile(script.read_text(encoding="utf-8"), str(script), "exec"), namespace)
print("status-entrypoint-imported")
"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [sys.executable, "-c", probe, str(script), str(tmp_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "status-entrypoint-imported" in completed.stdout
    assert "ModuleNotFoundError" not in completed.stderr
    source = script.read_text(encoding="utf-8")
    assert "sys.path.insert" in source


def test_status_compose_env_is_an_allowlist() -> None:
    """Status compose files pass an allowlist. They do not load an env file."""
    paths = [
        ROOT / "deploy" / "status" / "docker-compose.sgp1.yml",
        ROOT / "docker-compose.status.yml",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        envs = _compose_environments(text)
        assert set(envs) >= {"status", "caddy"}
        status_env = envs["status"]
        caddy_env = envs["caddy"]
        assert set(status_env) <= _STATUS_ENV_ALLOWLIST
        assert _STATUS_SERVICE_REQUIRED <= set(status_env)
        assert set(caddy_env) <= _CADDY_ENV_ALLOWLIST
        assert "STATUS_PAGE_TOKEN" not in caddy_env
        assert status_env["PYTHONPATH"] == "/app"
        assert "STATUS_PAGE_TOKEN" in status_env["STATUS_PAGE_TOKEN"]
        for key in (*status_env, *caddy_env):
            upper = key.upper()
            assert not any(marker in upper for marker in _SECRET_NAME_MARKERS), key
        interpolated = _interpolated_names(text)
        # The local override mounts state with this host path. It is not a
        # container environment variable and it is not a credential.
        interpolated.discard("STATUS_STATE_DIR")
        assert interpolated <= _STATUS_ENV_ALLOWLIST
        for name in interpolated:
            upper = name.upper()
            assert not any(marker in upper for marker in _SECRET_NAME_MARKERS), name


def test_sgp1_compose_is_a_standalone_project() -> None:
    """The SGP1 file is its own project and uses the host paths."""
    text = (ROOT / "deploy" / "status" / "docker-compose.sgp1.yml").read_text(encoding="utf-8")
    assert "\nname: sgp1-status\n" in text
    assert "\n  paper:" not in text
    assert "\n  api:" not in text
    assert "\n  status:" in text
    assert "\n  caddy:" in text
    assert "context: /data/app" in text
    assert "dockerfile: deploy/status/Dockerfile" in text
    assert "/data/app:/app" in text
    assert "/data/state/data:/app/data:ro" in text
    assert "/data/env/.env" in text
    assert "IP:178.128.215.94" in text
    assert "name: mo-paper" not in text
    assert "-p mo-paper" not in text or "Do not pass" in text
    caddy = text.split("\n  caddy:", 1)[1]
    assert "env_file" not in caddy
    assert "STATUS_PAGE_TOKEN" not in caddy
    assert "run_paper_trading" not in text

    runbook = (ROOT / "docs" / "runbooks" / "status_page.md").read_text(encoding="utf-8")
    assert "/opt/mo-paper" in runbook
    assert "-p sgp1-status" in runbook
    assert "-f /data/app/deploy/status/docker-compose.sgp1.yml" in runbook
    assert "--env-file /data/env/.env" in runbook
    assert "IP:178.128.215.94" in runbook
    assert "/data/state/data" in runbook
    assert "up -d --build" in runbook
    # The runbook must tell the operator not to join the paper project.
    assert "-p mo-paper" in runbook
    assert "mo-paper-paper-1" in runbook
    assert "mo-paper-api-1" in runbook


def test_compose_override_adds_only_status_and_caddy() -> None:
    text = (ROOT / "docker-compose.status.yml").read_text(encoding="utf-8")
    assert "run_paper_trading" not in text
    assert "\n  paper:" not in text
    assert "\n  api:" not in text
    assert "\n  status:" in text
    assert "\n  caddy:" in text
    assert '"443:443"' in text or "443:443" in text
    caddy = text.split("\n  caddy:", 1)[1]
    assert "env_file" not in caddy
    # The token is not interpolated into the caddy service.
    assert "STATUS_PAGE_TOKEN" not in caddy
    assert "STATUS_PAGE_DOMAIN" in caddy


def test_caddy_entrypoint_covers_tls_and_does_not_read_the_token() -> None:
    script = (ROOT / "deploy" / "caddy" / "entrypoint.sh").read_text(encoding="utf-8")
    caddyfile = (ROOT / "deploy" / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    assert ":443" in script
    assert "Let's Encrypt" in script
    assert "SHA256 Fingerprint" in script
    assert "sha256//" in script
    assert "STATUS_PAGE_TOKEN" not in script
    assert "reverse_proxy" in caddyfile
    assert "443" in caddyfile
    runbook = (ROOT / "docs" / "runbooks" / "status_page.md").read_text(encoding="utf-8")
    assert "openssl rand -hex 32" in runbook
    assert "SGP1_STATUS_TOKEN" in runbook
    assert "SGP1_STATUS_URL" in runbook
    assert "SGP1_STATUS_CERT_SHA256" in runbook
    assert "--pinnedpubkey" in runbook
    assert "--no-deps" in runbook


def test_cert_fingerprint_script(tmp_path) -> None:
    cert = tmp_path / "status.crt"
    key = tmp_path / "status.key"
    completed = __import__("subprocess").run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-sha256",
            "-days",
            "2",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-subj",
            "/CN=sgp1-status",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    del completed
    printed = __import__("subprocess").run(
        ["sh", str(ROOT / "scripts" / "status_cert_fingerprint.sh"), str(cert)],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line.strip() for line in printed.stdout.splitlines() if line.strip()]
    assert lines[0].lower().startswith("sha256 fingerprint=")
    assert lines[1].startswith("sha256//")
    assert key.read_text(encoding="utf-8") not in printed.stdout


def _isolate_worker_files(tmp_path: Path, monkeypatch) -> Path:
    """Point heartbeat reads at tmp. A pid file of 1 must not count."""
    cycle = tmp_path / "last_cycle.json"
    monkeypatch.setattr("api.status_snapshot.LAST_CYCLE_PATH", cycle)
    monkeypatch.setattr("api.status_snapshot.PAPER_BAR_STATE_PATH", tmp_path / "poll.json")
    monkeypatch.setattr("api.status_snapshot.PAPER_LOG_PATH", tmp_path / "missing.log")
    monkeypatch.setattr("firm.scan_summary_log.LOG_PATH", tmp_path / "scan.jsonl")
    pid = tmp_path / "paper.pid"
    pid.write_text("1\n", encoding="utf-8")
    monkeypatch.setattr("firm.locks.PAPER_PID_PATH", pid)
    monkeypatch.delenv("STATUS_WORKER_STALE_SECONDS", raising=False)
    return cycle


def test_fresh_heartbeat_means_the_worker_is_alive(tmp_path, monkeypatch) -> None:
    from api.status_snapshot import worker_status

    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    cycle = _isolate_worker_files(tmp_path, monkeypatch)
    fresh = now - timedelta(seconds=100)
    cycle.write_text(
        json.dumps({"started_at": fresh.isoformat(), "errors": []}),
        encoding="utf-8",
    )
    payload = worker_status(now=now)
    assert payload["alive"] is True
    assert payload["state"] == "alive"
    assert payload["age_seconds"] == 100
    assert payload["last_heartbeat_at"] == fresh.isoformat()
    assert payload["heartbeat_source"] == "last_cycle"
    assert payload["stale_after_seconds"] == 1920
    assert "pid" not in payload
    assert "uptime_seconds" not in payload


def test_stale_heartbeat_means_the_worker_is_dead(tmp_path, monkeypatch) -> None:
    from api.status_snapshot import worker_status

    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    cycle = _isolate_worker_files(tmp_path, monkeypatch)
    # age == threshold is not alive. Two cycles plus the margin, exactly.
    stale = now - timedelta(seconds=1920)
    cycle.write_text(
        json.dumps({"started_at": stale.isoformat(), "errors": []}),
        encoding="utf-8",
    )
    payload = worker_status(now=now)
    assert payload["alive"] is False
    assert payload["state"] == "dead"
    assert payload["age_seconds"] == 1920
    assert payload["last_heartbeat_at"] == stale.isoformat()


def test_missing_heartbeat_is_unknown(tmp_path, monkeypatch) -> None:
    from api.status_snapshot import worker_status

    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    _isolate_worker_files(tmp_path, monkeypatch)
    payload = worker_status(now=now)
    assert payload["alive"] is False
    assert payload["state"] == "unknown"
    assert payload["last_heartbeat_at"] is None
    assert payload["age_seconds"] is None
    assert "pid" not in payload
    assert "uptime_seconds" not in payload


def test_newer_poll_heartbeat_beats_an_older_cycle(tmp_path, monkeypatch) -> None:
    from api.status_snapshot import worker_status

    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    cycle = _isolate_worker_files(tmp_path, monkeypatch)
    old = now - timedelta(seconds=3000)
    fresh = now - timedelta(seconds=20)
    cycle.write_text(
        json.dumps({"started_at": old.isoformat(), "errors": []}),
        encoding="utf-8",
    )
    poll = tmp_path / "poll.json"
    poll.write_text(
        json.dumps(
            {
                "version": 1,
                "sleeves": {
                    "BTCUSDT|1h|LONG": {"evaluated_at": fresh.isoformat(), "signal": "flat"},
                },
            }
        ),
        encoding="utf-8",
    )
    payload = worker_status(now=now)
    assert payload["alive"] is True
    assert payload["heartbeat_source"] == "poll"
    assert payload["last_heartbeat_at"] == fresh.isoformat()
    assert payload["age_seconds"] == 20
    assert payload["last_cycle_at"] == old.isoformat()


def test_stale_threshold_is_env_configurable(tmp_path, monkeypatch) -> None:
    from api.status_snapshot import worker_status

    now = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    cycle = _isolate_worker_files(tmp_path, monkeypatch)
    fresh = now - timedelta(seconds=100)
    cycle.write_text(
        json.dumps({"started_at": fresh.isoformat(), "errors": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("STATUS_WORKER_STALE_SECONDS", "50")
    payload = worker_status(now=now)
    assert payload["alive"] is False
    assert payload["state"] == "dead"
    assert payload["stale_after_seconds"] == 50
    assert payload["age_seconds"] == 100
