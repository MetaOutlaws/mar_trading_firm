"""F111 scan-card counters count real closes and real entry fills.

Inbox 332, the first F111 card after a paper restart, reported one exit for
every evaluated row. Blank telemetry always carries ``exit_fee`` and
``realised_net_profit``; those nulls are not a close. A no-signal, flat, or
skipped row must leave exits and fills at zero. A row counts as an exit only
after an open position is closed, and as a fill only when an entry fills.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from config.settings import get_settings
from core.execution.f111_paper import _blank_event
from firm.scan_inbox import summarise_f111_rows
from tests.test_f111_paper import T0, _broker, _pass_signal, _risk, _runtime


@pytest.fixture(autouse=True)
def _isolated_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_flat_f111_scan_counts_no_exits_and_no_fills(tmp_path: Path) -> None:
    """N evaluated rows, no open position and no signal, stay at zero.

    The rows are the runtime's own telemetry, including the null exit fields
    that the scan card used to treat as closes.
    """
    runtime = _runtime(tmp_path)
    assert runtime.broker is None
    assert runtime.protection == {}
    assert runtime.config.get("live_authorized") is False

    # no_signal: the gate is false and no reason was named. _emit writes the
    # string. Both sides, three symbols.
    for symbol in ("ADAUSDT", "DOTUSDT", "AVAXUSDT"):
        for side in ("LONG", "SHORT"):
            row = _blank_event(runtime.config_sha, runtime.run_id)
            row.update(
                {
                    "symbol": symbol,
                    "side": side,
                    "source_signal_id": f"{symbol}|{side}|no_signal",
                    "gate_decision": False,
                    "rejection_reason": None,
                }
            )
            runtime._emit(row)

    # Flat parent. The F111 gates would pass; the parent already blocked it.
    runtime.observe_signal(
        symbol="ETHUSDT",
        side="LONG",
        t0=T0,
        boundary=100.0,
        prior_atr=1.0,
        close=100.0,
        compression=0.6,
        extension_atr=0.2,
        base_passed=False,
        observed_at=T0,
    )
    # Named gate misses. Still no order.
    runtime.observe_signal(
        symbol="ETHUSDT",
        side="SHORT",
        t0=T0,
        boundary=100.0,
        prior_atr=1.0,
        close=100.0,
        compression=0.1,
        extension_atr=0.2,
        base_passed=True,
        observed_at=T0,
    )
    runtime.observe_signal(
        symbol="SOLUSDT",
        side="LONG",
        t0=T0,
        boundary=100.0,
        prior_atr=1.0,
        close=100.0,
        compression=0.6,
        extension_atr=2.0,
        base_passed=True,
        observed_at=T0,
    )
    # Skipped: the hourly bar was not available. One row per side.
    runtime._emit_data_gap("XRPUSDT", "hourly bar still forming")

    rows = [row for row in runtime.events if row.get("symbol")]
    expected = 6 + 3 + 2
    assert len(rows) == expected
    reasons = {row.get("rejection_reason") for row in rows}
    assert reasons == {
        "no_signal",
        "base_signal_blocked",
        "compression_gate",
        "extension_gate",
        "hourly bar still forming",
    }
    # The schema that inflated Inbox 332: the keys exist, the values do not.
    assert all("exit_fee" in row and row.get("exit_fee") is None for row in rows)
    assert all("realised_net_profit" in row and row.get("realised_net_profit") is None for row in rows)
    assert all(row.get("simulated_fill") is None for row in rows)
    assert runtime.protection == {}

    summary = summarise_f111_rows(rows)
    assert summary["f111_sleeves"] == expected
    assert summary["exits"] == 0
    assert summary["fills"] == 0
    assert summary["entries_opened"] == 0
    assert all(row["exited"] is False and row["filled"] is False for row in summary["sleeve_rows"])


def test_one_real_entry_and_one_real_close(tmp_path: Path) -> None:
    """One paper fill, then one close of that open position.

    Rows emitted while the position is open, and the flat rows around them,
    do not add exits. The close is one exit and is not a second fill.
    """
    prices = {"BTCUSDT": 101.0}
    broker = _broker(prices)
    runtime = _runtime(tmp_path, broker=broker, risk=_risk(tmp_path))
    assert runtime.config.get("live_authorized") is False

    _pass_signal(runtime)
    runtime.observe_minute(
        symbol="BTCUSDT",
        minute=T0,
        high=102,
        low=99,
        close=101,
        quote=101,
        quote_time=T0,
        observed_at=T0,
    )
    action = T0 + timedelta(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT",
        minute=action,
        high=102,
        low=100,
        close=101,
        quote=101,
        quote_time=action,
        observed_at=action,
    )
    assert len(broker.get_positions()) == 1
    opened = summarise_f111_rows(list(runtime.events))
    assert opened["fills"] == 1
    assert opened["entries_opened"] == 1
    assert opened["exits"] == 0
    fill_rows = [row for row in opened["sleeve_rows"] if row["filled"]]
    assert len(fill_rows) == 1
    assert fill_rows[0]["exited"] is False

    gap = action + timedelta(minutes=1)
    prices["BTCUSDT"] = 90.0
    before = len(runtime.events)
    runtime.observe_minute(
        symbol="BTCUSDT",
        minute=gap,
        high=90,
        low=90,
        close=90,
        quote=90,
        quote_time=gap,
        observed_at=gap,
        funding_fraction=0.0,
        funding_source="test",
    )
    assert broker.get_positions() == []
    assert len(runtime.events) == before + 1
    close_row = runtime.events[-1]
    assert close_row.get("rejection_reason") == "initial_stop"
    assert close_row.get("exit_fee") is not None

    closed = summarise_f111_rows(list(runtime.events))
    assert closed["fills"] == 1
    assert closed["entries_opened"] == 1
    assert closed["exits"] == 1
    exit_rows = [row for row in closed["sleeve_rows"] if row["exited"]]
    assert len(exit_rows) == 1
    assert exit_rows[0]["filled"] is False
    assert exit_rows[0]["ordered"] is False
    # The entry row is still the only fill after the close is in the same scan.
    assert sum(1 for row in closed["sleeve_rows"] if row["filled"]) == 1
