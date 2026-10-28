"""Blotter paging: total, offset, and a filter that sees the whole book.

Read-only. These tests insert closed trades, then only GET /api/trades.
They do not place orders or change the schema.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

DASHBOARD = Path(__file__).resolve().parents[1] / "api" / "static" / "index.html"

# Keys the desk already consumed. A new wrapper must not add or drop these.
ROW_KEYS = {
    "id",
    "symbol",
    "side",
    "quantity",
    "notional",
    "entry_price",
    "exit_price",
    "gross_pnl",
    "net_pnl",
    "return_pct",
    "fees",
    "entry_fees",
    "exit_fees",
    "funding",
    "exit_reason",
    "strategy",
    "strategy_id",
    "sleeve",
    "strategy_version",
    "strategy_label",
    "agents",
    "entry_slippage_bps",
    "exit_slippage_bps",
    "mode",
    "entry_time",
    "exit_time",
}

_BASE = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _client() -> TestClient:
    from api.app import app

    return TestClient(app)


def _insert(
    session,
    *,
    i: int,
    symbol: str = "BTCUSDT",
    side: str = "LONG",
    strategy: str = "bulk",
    exit_reason: str = "take_profit",
    entry_indicators: dict | None = None,
    position_id: int | None = None,
) -> None:
    """One closed row. ``i`` is both the age key and the exit order."""
    from core.ledger.models import TradeRecord

    when = _BASE + timedelta(seconds=i)
    session.add(
        TradeRecord(
            symbol=symbol,
            side=side,
            mode="paper",
            strategy=strategy,
            quantity=1.0,
            notional=100.0,
            entry_price=100.0,
            exit_price=101.0,
            entry_time=when,
            exit_time=when,
            gross_pnl=1.0,
            fees=0.1,
            entry_fees=0.05,
            exit_fees=0.05,
            funding=0.0,
            net_pnl=0.9,
            return_pct=0.01,
            exit_reason=exit_reason,
            entry_slippage_bps=0.0,
            exit_slippage_bps=0.0,
            contributing_agents=[],
            entry_indicators=entry_indicators or {},
            position_id=position_id,
        )
    )


def _seed_history(firm_db) -> dict[str, int]:
    """123 closes. The three interesting ones are older than the newest 100.

    firm_db is unused apart from switching on the throwaway database. The
    fixture has already pointed the engine at that file.
    """
    del firm_db
    from core.db import session_scope
    from core.ledger.models import Position

    with session_scope() as session:
        position = Position(
            symbol="BTCUSDT",
            side="LONG",
            quantity=1.0,
            entry_price=100.0,
            notional=100.0,
            status="closed",
            mode="paper",
            strategy="",
            strategy_params={"sleeve": "NEEDLE-PARAMS-OLD"},
        )
        session.add(position)
        session.flush()
        # i=0 is the oldest exit. The newest 100 are plain BTC longs.
        _insert(session, i=0, symbol="OLDCOIN", strategy="rare_old_strategy")
        _insert(
            session,
            i=1,
            side="SHORT",
            entry_indicators={"sleeve_id": "NEEDLE-SLEEVE-OLD"},
        )
        _insert(session, i=2, strategy="", position_id=position.id)
        for i in range(3, 123):
            _insert(session, i=i)
    return {"total": 123}


def test_default_trades_response_stays_a_list(firm_db) -> None:
    """No with_total: a JSON list, default 50, same row keys, newest first."""
    _seed_history(firm_db)
    client = _client()

    body = client.get("/api/trades").json()
    assert isinstance(body, list)
    assert len(body) == 50
    assert set(body[0]) == ROW_KEYS
    assert "total" not in body[0]
    exits = [row["exit_time"] for row in body]
    assert exits == sorted(exits, reverse=True)
    assert body[0]["symbol"] == "BTCUSDT"

    page = client.get("/api/trades", params={"limit": 20}).json()
    assert isinstance(page, list)
    assert len(page) == 20
    assert set(page[0]) == ROW_KEYS

    explicit = client.get("/api/trades", params={"with_total": 0, "limit": 5}).json()
    assert isinstance(explicit, list)
    assert len(explicit) == 5


def test_count_endpoint_and_with_total_follow_the_filter(firm_db) -> None:
    """Total is the whole book, and the filtered total is the match count."""
    _seed_history(firm_db)
    client = _client()

    assert client.get("/api/trades/count").json() == {"total": 123}

    wrapped = client.get("/api/trades", params={"with_total": 1, "limit": 10}).json()
    assert set(wrapped) == {"total", "rows"}
    assert wrapped["total"] == 123
    assert isinstance(wrapped["rows"], list)
    assert len(wrapped["rows"]) == 10
    assert set(wrapped["rows"][0]) == ROW_KEYS

    assert client.get("/api/trades/count", params={"q": "OLDCOIN"}).json() == {"total": 1}
    filtered = client.get(
        "/api/trades",
        params={"with_total": 1, "q": "oldcoin", "limit": 10},
    ).json()
    assert filtered["total"] == 1
    assert len(filtered["rows"]) == 1
    assert filtered["rows"][0]["symbol"] == "OLDCOIN"
    assert filtered["rows"][0]["strategy"] == "rare_old_strategy"


def test_offset_pages_do_not_overlap_and_cover_the_book(firm_db) -> None:
    """offset skips the newer rows. The two pages meet and do not repeat."""
    _seed_history(firm_db)
    client = _client()

    first = client.get("/api/trades", params={"limit": 10, "offset": 0}).json()
    second = client.get("/api/trades", params={"limit": 10, "offset": 10}).json()
    assert isinstance(first, list) and isinstance(second, list)
    assert len(first) == 10 and len(second) == 10
    first_ids = [row["id"] for row in first]
    second_ids = [row["id"] for row in second]
    assert set(first_ids).isdisjoint(second_ids)
    assert first[-1]["exit_time"] >= second[0]["exit_time"]

    past = client.get(
        "/api/trades",
        params={"with_total": 1, "limit": 10, "offset": 10_000},
    ).json()
    assert past["rows"] == []
    assert past["total"] == 123


def test_limit_above_500_is_clamped_and_negatives_are_rejected(firm_db) -> None:
    """510 closes. A request for 9999 rows still returns 500, then the rest."""
    del firm_db
    from core.db import session_scope

    with session_scope() as session:
        for i in range(510):
            _insert(session, i=i, symbol="BTCUSDT", strategy="cap")

    client = _client()
    capped = client.get("/api/trades", params={"limit": 9999}).json()
    assert isinstance(capped, list)
    assert len(capped) == 500
    rest = client.get("/api/trades", params={"limit": 9999, "offset": 500}).json()
    assert len(rest) == 10
    assert {row["id"] for row in capped}.isdisjoint({row["id"] for row in rest})
    assert capped[-1]["exit_time"] >= rest[0]["exit_time"]
    assert client.get("/api/trades/count").json() == {"total": 510}

    # The clamp is 500, not an error. Exactly 500 is the full page.
    exact = client.get("/api/trades", params={"limit": 500}).json()
    assert len(exact) == 500

    assert client.get("/api/trades", params={"limit": -1}).status_code == 422
    assert client.get("/api/trades", params={"offset": -5}).status_code == 422
    assert client.get("/api/trades", params={"with_total": -1}).status_code == 422
    assert client.get("/api/trades/count").status_code == 200


def test_filter_finds_rows_older_than_the_newest_100(firm_db) -> None:
    """A filter searches the full history, then the page is cut from that."""
    _seed_history(firm_db)
    client = _client()

    newest = client.get("/api/trades", params={"limit": 100}).json()
    assert len(newest) == 100
    assert all(row["symbol"] == "BTCUSDT" for row in newest)
    assert all(row["strategy"] == "bulk" for row in newest)
    assert all(row["side"] == "LONG" for row in newest)

    by_symbol = client.get("/api/trades", params={"q": "OLDCOIN", "limit": 100}).json()
    assert [row["symbol"] for row in by_symbol] == ["OLDCOIN"]

    by_strategy = client.get(
        "/api/trades",
        params={"q": "rare_old_strategy", "limit": 50},
    ).json()
    assert len(by_strategy) == 1
    assert by_strategy[0]["symbol"] == "OLDCOIN"

    by_indicator = client.get(
        "/api/trades",
        params={"q": "NEEDLE-SLEEVE-OLD", "limit": 100},
    ).json()
    assert len(by_indicator) == 1
    assert by_indicator[0]["sleeve"] == "NEEDLE-SLEEVE-OLD"
    assert by_indicator[0]["side"] == "SHORT"

    by_params = client.get(
        "/api/trades",
        params={"q": "NEEDLE-PARAMS-OLD", "limit": 100},
    ).json()
    assert len(by_params) == 1
    assert by_params[0]["sleeve"] == "NEEDLE-PARAMS-OLD"

    shorts = client.get("/api/trades/count", params={"side": "short"}).json()
    assert shorts == {"total": 1}
    short_rows = client.get("/api/trades", params={"side": "SHORT", "limit": 100}).json()
    assert len(short_rows) == 1
    assert short_rows[0]["sleeve"] == "NEEDLE-SLEEVE-OLD"

    # A quote and a wildcard are literal text, not a match-everything clause.
    assert client.get("/api/trades/count", params={"q": "%"}).json() == {"total": 0}
    injected = client.get("/api/trades/count", params={"q": "' OR 1=1 --"}).json()
    assert injected == {"total": 0}


def test_filtered_offset_pages_inside_the_match_set(firm_db) -> None:
    """limit/offset apply after the filter, so page 2 is the next match."""
    del firm_db
    from core.db import session_scope

    with session_scope() as session:
        for i in range(30):
            _insert(session, i=i, symbol="ETHUSDT", strategy="paged_match")
        for i in range(30, 150):
            _insert(session, i=i, symbol="BTCUSDT", strategy="bulk")

    client = _client()
    page = client.get(
        "/api/trades",
        params={"with_total": 1, "q": "paged_match", "limit": 10, "offset": 10},
    ).json()
    assert page["total"] == 30
    assert len(page["rows"]) == 10
    assert {row["strategy"] for row in page["rows"]} == {"paged_match"}
    # offset 10 of the matches, newest first: exits 19 .. 10 (i=29 is newest match).
    exits = [row["exit_time"] for row in page["rows"]]
    assert exits == sorted(exits, reverse=True)
    newest_match = client.get(
        "/api/trades",
        params={"q": "paged_match", "limit": 1},
    ).json()[0]
    assert newest_match["exit_time"] > page["rows"][0]["exit_time"]


def test_blotter_markup_shows_the_total_and_pages_on_the_server() -> None:
    """Header, sidebar badge, and the fetch all use the full closed-trade count."""
    html = DASHBOARD.read_text(encoding="utf-8")
    nav = html.split("function renderNav()", 1)[1].split("function go(", 1)[0]
    blotter = html.split("function renderBlotter()", 1)[1].split("function tradeRow(", 1)[0]
    query = html.split("function blotterQuery()", 1)[1].split("function blotterServerSlice(", 1)[0]

    assert "Number(state.tradesTotal)" in nav
    assert "(state.trades || []).length" not in nav
    assert "showing ${shown} of ${total} closed trades" in blotter
    assert "state.trades" in blotter
    assert 'params.set("with_total", "1")' in query
    assert 'params.set("offset"' in query
    assert 'params.set("q", q)' in query
    assert 'params.set("side", side)' in query
    assert 'get("/api/trades/count")' in html
    assert 'get("/api/trades?limit=100")' not in html
