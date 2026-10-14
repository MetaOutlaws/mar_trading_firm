"""Blotter Strategy column: API serialization and the dashboard markup.

Display only. These tests read closed trades and the static page. They do
not place orders, start the paper worker, or add a ledger column.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from core.ledger.store import Ledger

DASHBOARD = Path(__file__).resolve().parents[1] / "api" / "static" / "index.html"

F111_ID = "mar_f111_r12_extension_latefloor_v1"
L01_VERSION = "l01-long-f111-short-v1"


def _open_and_close(
    ledger: Ledger,
    *,
    symbol: str,
    side: str,
    strategy: str,
    strategy_params: dict | None = None,
    entry_indicators: dict | None = None,
    entry: float = 100.0,
    exit_price: float = 101.0,
) -> int:
    """Seed one closed round trip through the existing ledger API."""
    position_id = ledger.open_position(
        symbol=symbol,
        side=side,
        quantity=1.0,
        entry_price=entry,
        expected_entry_price=entry,
        take_profit=entry * 1.1,
        stop_loss=entry * 0.9,
        strategy=strategy,
        sector="other",
        signal_score=1.0,
        signal_reason="blotter display fixture",
        broker_order_id=f"fixture-{symbol}",
        strategy_params=strategy_params,
        entry_indicators=entry_indicators,
    )
    closed = ledger.close_position(
        position_id,
        exit_price=exit_price,
        expected_exit_price=exit_price,
        exit_reason="take_profit",
    )
    assert closed is not None
    return position_id


def test_trades_api_serializes_strategy_label(firm_db) -> None:
    """Sleeve id, L01 version, F111 version, and a blank row."""
    ledger = Ledger(mode="paper", starting_equity=10_000.0)
    _open_and_close(
        ledger,
        symbol="BTCUSDT",
        side="LONG",
        strategy="rsi_trend",
        strategy_params={
            "strategy_id": "rsi_trend",
            "sleeve": "BTCUSDT|1h|LONG|rsi_trend",
        },
    )
    # Production L01 shape: strategy column holds the shared F111 id, and
    # strategy_params holds the version plus entry_case. No extra keys.
    _open_and_close(
        ledger,
        symbol="ETHUSDT",
        side="LONG",
        strategy=F111_ID,
        strategy_params={
            "strategy_version": L01_VERSION,
            "entry_case": "L01",
            "configuration_sha256": "fixture",
        },
        entry=200.0,
        exit_price=210.0,
    )
    _open_and_close(
        ledger,
        symbol="XRPUSDT",
        side="SHORT",
        strategy=F111_ID,
        strategy_params={
            "strategy_version": "f111-paper-v1",
            "entry_case": "F111",
        },
        entry=1.5,
        exit_price=1.4,
    )
    _open_and_close(
        ledger,
        symbol="SOLUSDT",
        side="LONG",
        strategy="",
        strategy_params={},
        entry=50.0,
        exit_price=49.0,
    )
    # Sleeve id stored only on the indicator snapshot the trade copies.
    _open_and_close(
        ledger,
        symbol="LTCUSDT",
        side="SHORT",
        strategy="",
        entry_indicators={"sleeve_id": "LTCUSDT|4h|SHORT|prior_close_magnet_fade"},
        entry=80.0,
        exit_price=78.0,
    )

    from api.app import app

    rows = TestClient(app).get("/api/trades?limit=20").json()
    by_symbol = {row["symbol"]: row for row in rows}

    sleeve = by_symbol["BTCUSDT"]
    assert sleeve["strategy"] == "rsi_trend"
    assert sleeve["strategy_id"] == "rsi_trend"
    assert sleeve["sleeve"] == "BTCUSDT|1h|LONG|rsi_trend"
    assert sleeve["strategy_label"] == "BTCUSDT|1h|LONG|rsi_trend"
    assert sleeve["strategy_version"] == ""
    assert "agents" in sleeve

    l01 = by_symbol["ETHUSDT"]
    assert l01["strategy"] == F111_ID
    assert l01["strategy_id"] == F111_ID
    assert l01["sleeve"] == ""
    assert l01["strategy_version"] == L01_VERSION
    assert l01["strategy_label"] == (
        f"{F111_ID} · strategy_version {L01_VERSION}"
    )

    f111 = by_symbol["XRPUSDT"]
    assert f111["strategy_id"] == F111_ID
    assert f111["strategy_version"] == "f111-paper-v1"
    assert f111["strategy_label"] == F111_ID
    assert "strategy_version" not in f111["strategy_label"]

    missing = by_symbol["SOLUSDT"]
    assert missing["strategy_id"] == ""
    assert missing["sleeve"] == ""
    assert missing["strategy_label"] == "—"

    from_indicators = by_symbol["LTCUSDT"]
    assert from_indicators["sleeve"] == "LTCUSDT|4h|SHORT|prior_close_magnet_fade"
    assert from_indicators["strategy_label"] == "LTCUSDT|4h|SHORT|prior_close_magnet_fade"


def test_l01_version_alone_still_names_the_strategy() -> None:
    """A row with only the L01 version string still shows that version."""
    from types import SimpleNamespace

    from api.app import blotter_strategy_fields

    trade = SimpleNamespace(
        strategy="",
        entry_indicators={"strategy_version": L01_VERSION},
        position=None,
    )
    fields = blotter_strategy_fields(trade)
    assert fields["strategy_label"] == f"strategy_version {L01_VERSION}"
    assert fields["strategy_version"] == L01_VERSION


def test_blotter_markup_replaces_agents_with_strategy() -> None:
    """Same contract as the other dashboard checks: pin the static page."""
    html = DASHBOARD.read_text(encoding="utf-8")
    blotter = html.split("function renderBlotter()", 1)[1].split("function tradeRow(", 1)[0]
    row = html.split("function tradeRow(", 1)[1].split("function blotterStrategy(", 1)[0]
    label = html.split("function blotterStrategy(", 1)[1].split("function prettyReason(", 1)[0]

    assert '<th class="strategy">Strategy</th>' in blotter
    assert "Agents" not in blotter
    assert "blotterStrategy(t)" in row
    assert "t.agents" not in row
    assert "strategy_label" in label
    assert "—" in label
    # Open positions still attribute employees. This change is the blotter only.
    assert "<th>Opened</th><th>Strategy</th><th>Agents</th>" in html
