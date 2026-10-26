"""Desk polls must not retain a new copy of telemetry or the book each cycle.

The SGP1 API grew about 50 MB/min because each append of
``f111_telemetry.jsonl`` stored another full parse. These tests drive N
polls against a fat file and against the live book reader. They do not
place orders or change a gate.
"""

from __future__ import annotations

import gc
import json
import tracemalloc
from datetime import datetime, timedelta, timezone
from pathlib import Path

from api.dashboard_cache import panel_cache
from api.desk_status import (
    _count_reasons,
    _f111_blotter,
    _gate_rows,
    _hour_floor,
    _is_gate_rejection,
    _latest_registry_block,
    clear_book_cache,
    clear_cycle_cache,
    clear_jsonl_cache,
    f111_status,
    read_cached_last_cycle,
    read_live_approval_book,
    read_telemetry,
    telemetry_cache_stats,
)
from api.why_no_trade import build_f111_why

NOW = datetime(2026, 10, 16, 15, 30, tzinfo=timezone.utc)
_PAD = 20_000


def _line(row: dict) -> str:
    return json.dumps(row) + "\n"


def _gate(symbol: str, stamp: datetime, *, reason: str = "extension_gate", pad: bool = False) -> dict:
    row = {
        "symbol": symbol,
        "side": "LONG",
        "rejection_reason": reason,
        "gate_decision": False,
        "emitted_at": stamp.isoformat(),
        "source_signal_time": stamp.isoformat(),
    }
    if pad:
        row["pad"] = "x" * _PAD
    return row


def _registry(symbol: str, *, unavailable: bool = False) -> dict:
    return {
        "record_kind": "registry",
        "symbol": symbol,
        "side": "LONG",
        "instrument_unavailable": unavailable,
        "rejection_reason": "exchange status Closed" if unavailable else "",
        "feature_values": {"exchange_status": "Closed"} if unavailable else {},
    }


def _write_history(path: Path, *, days: int = 6) -> datetime:
    """Fat rows well before the request clock, then one thin recent hour."""
    start = NOW - timedelta(days=days)
    latest = NOW - timedelta(minutes=20)
    with path.open("w", encoding="utf-8") as handle:
        for day in range(days - 1):
            for hour in range(24):
                stamp = start + timedelta(days=day, hours=hour)
                handle.write(_line(_gate(f"H{day}{hour}", stamp, pad=True)))
        handle.write(_line(_registry("OLDUSDT", unavailable=True)))
        handle.write(_line({"deploy_marker": "restart"}))
        for index in range(4):
            stamp = latest.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=index)
            handle.write(_line(_gate(f"LIVE{index}", stamp, reason="extension_gate")))
        handle.write(_line(_registry("BTCUSDT")))
        handle.write(_line(_registry("ETHUSDT", unavailable=True)))
    return latest


def test_poll_cycles_keep_telemetry_retained_rows_bounded(tmp_path) -> None:
    """N appends grow parsed_rows. The fold does not keep those objects."""
    path = tmp_path / "f111_telemetry.jsonl"
    state = tmp_path / "state.json"
    state.write_text('{"pending": [], "protection": {}}', encoding="utf-8")
    _write_history(path)
    clear_jsonl_cache()
    panel_cache.clear()
    tracemalloc.start()
    try:
        f111_status(now=NOW, telemetry_path=path, state_path=state)
        gc.collect()
        baseline = tracemalloc.get_traced_memory()[0]
        first = telemetry_cache_stats()
        assert first["files"] == 1
        assert first["parsed_rows"] > first["retained_rows"]
        retained_cap = first["retained_rows"] + 8
        for index in range(12):
            # Old fat line. A full-file cache would keep another multi-MB copy.
            stamp = NOW - timedelta(days=4, minutes=index)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(_line(_gate(f"OLD{index}", stamp, pad=True)))
            panel_cache.clear()
            f111_status(now=NOW, telemetry_path=path, state_path=state)
        gc.collect()
        after = telemetry_cache_stats()
        traced = tracemalloc.get_traced_memory()[0]
    finally:
        tracemalloc.stop()
        clear_jsonl_cache()
        panel_cache.clear()
    assert after["parsed_rows"] >= first["parsed_rows"] + 12
    assert after["retained_rows"] <= retained_cap
    assert after["files"] <= 4
    # Twelve 20 KB rows retained on top of the fold would move this by
    # hundreds of KB. The fold drops them.
    assert traced < baseline + 400_000


def test_quiet_polls_do_not_parse_the_book_or_the_plan(tmp_path, monkeypatch) -> None:
    """Strategies and the cycle plan stat a quiet file instead of parsing it."""
    import api.desk_status as desk

    book = tmp_path / "approved_strategies.json"
    body = {
        "_verdict": "LIVE",
        "_generated_at": "2026-10-16T00:00:00+00:00",
        "sleeve:BTCUSDT:LONG:1h": {"approved": True, "strategy": "sleeve", "timeframe": "1h"},
    }
    book.write_text(json.dumps(body), encoding="utf-8")
    monkeypatch.setattr("config.universe.APPROVALS_PATH", book)
    clear_book_cache()
    loads = {"n": 0}
    real_loads = desk.json.loads

    def counting(text, *args, **kwargs):
        loads["n"] += 1
        return real_loads(text, *args, **kwargs)

    monkeypatch.setattr(desk.json, "loads", counting)
    first = read_live_approval_book()
    assert first["verdict"] == "LIVE"
    assert first["approvals"]["sleeve:BTCUSDT:LONG:1h"]["approved"] is True
    parsed = loads["n"]
    assert parsed >= 1
    for _ in range(8):
        again = read_live_approval_book()
        assert again["verdict"] == first["verdict"]
        assert again["approvals"] is first["approvals"]
    assert loads["n"] == parsed

    book.write_text(json.dumps({**body, "_verdict": "EDITED"}), encoding="utf-8")
    edited = read_live_approval_book()
    assert edited["verdict"] == "EDITED"
    assert loads["n"] > parsed
    parsed = loads["n"]
    # Same bytes, new mtime: hash matches, no second parse.
    raw = book.read_bytes()
    book.write_bytes(raw)
    st = book.stat()
    import os

    os.utime(book, ns=(st.st_atime_ns, st.st_mtime_ns + 2_000_000))
    touched = read_live_approval_book()
    assert touched["verdict"] == "EDITED"
    assert loads["n"] == parsed
    clear_book_cache()

    cycle = tmp_path / "last_cycle.json"
    cycle.write_text(json.dumps({"started_at": "2026-10-16T15:00:00+00:00", "plan": []}), encoding="utf-8")
    monkeypatch.setattr("core.execution.engine.LAST_CYCLE_PATH", cycle)
    clear_cycle_cache()
    before = loads["n"]
    loaded = read_cached_last_cycle()
    assert loaded is not None and loaded["started_at"].startswith("2026-10-16T15:00:00")
    mid = loads["n"]
    assert mid > before
    assert read_cached_last_cycle() is loaded
    assert loads["n"] == mid
    clear_cycle_cache()


def test_risk_journal_is_not_reparsed_on_a_quiet_poll(tmp_path, monkeypatch) -> None:
    """``/api/risk`` reads the cash journal. A second poll does not parse it."""
    import core.execution.paper_cash as paper_cash
    from core.ledger.statement import clear_journal_cache, load_journal_events

    journal = tmp_path / "paper_cash.json"
    journal.write_text(
        json.dumps(
            {
                "version": 1,
                "events": [{"kind": "capital", "amount": 10, "event_id": "seed"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(paper_cash, "PAPER_CASH_PATH", journal)
    monkeypatch.setattr(
        "core.execution.paper_settle.load_durable_close_payloads",
        lambda: [],
    )
    clear_journal_cache()
    loads = {"n": 0}
    real_loads = paper_cash.json.loads

    def counting(text, *args, **kwargs):
        loads["n"] += 1
        return real_loads(text, *args, **kwargs)

    monkeypatch.setattr(paper_cash.json, "loads", counting)
    first = load_journal_events()
    assert first[0]["event_id"] == "seed"
    parsed = loads["n"]
    assert parsed >= 1
    for _ in range(6):
        assert load_journal_events()[0]["event_id"] == "seed"
    assert loads["n"] == parsed
    clear_journal_cache()


def test_folded_f111_matches_a_full_file_walk(tmp_path) -> None:
    """The incremental fold returns the same panel the whole-file walk did."""
    path = tmp_path / "f111_telemetry.jsonl"
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"pending": [{"status": "watching"}], "protection": {"BTCUSDT": {}}}),
        encoding="utf-8",
    )
    old = NOW - timedelta(hours=30)
    recent = NOW - timedelta(minutes=15)
    older_hour = NOW - timedelta(hours=3)
    rows = [
        _registry("OLDUSDT", unavailable=True),
        _gate("OLD", old, reason="compression_gate"),
        {"deploy_marker": "restart", "emitted_at": older_hour.isoformat()},
        _gate("A", older_hour, reason="compression_gate"),
        _gate("B", recent, reason="extension_gate"),
        _gate(
            "C",
            recent + timedelta(minutes=1),
            reason="extension_gate",
        ),
        {
            "symbol": "EXIT",
            "side": "SHORT",
            "realised_net_profit": 1.5,
            "quantity": 1,
            "entry_price": 10,
            "simulated_fill": 11,
            "quote_time": recent.isoformat(),
            "emitted_at": recent.isoformat(),
            "rejection_reason": "target",
        },
        _registry("BTCUSDT"),
        _registry("DOWNUSDT", unavailable=True),
    ]
    # One more exit so the sum is every exit, not only the last 30.
    for index in range(35):
        rows.append(
            {
                "symbol": f"X{index}",
                "side": "LONG",
                "realised_net_profit": 0.25,
                "emitted_at": (recent + timedelta(seconds=index)).isoformat(),
                "quote_time": recent.isoformat(),
            }
        )
    path.write_text("".join(_line(row) for row in rows), encoding="utf-8")
    clear_jsonl_cache()
    panel_cache.clear()
    panel = f111_status(now=NOW, telemetry_path=path, state_path=state)

    loaded: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            loaded.append(payload)
    census = _latest_registry_block(loaded)
    available = sum(1 for row in census if not row.get("instrument_unavailable"))
    closed_by: dict[str, int] = {}
    for row in census:
        if row.get("instrument_unavailable"):
            from api.desk_status import _rejection_reason

            reason = _rejection_reason(row)
            closed_by[reason] = closed_by.get(reason, 0) + 1
    stamped = [
        (row, stamp)
        for row, stamp in _gate_rows(loaded)
        if _is_gate_rejection(row) and stamp is not None
    ]
    latest_hour = _hour_floor(max(stamp for _row, stamp in stamped))
    latest_rows = [
        row
        for row, stamp in stamped
        if latest_hour <= stamp < latest_hour + timedelta(hours=1)
    ]
    day_start = NOW - timedelta(hours=24)
    day_rows = [row for row, stamp in stamped if stamp >= day_start]
    blotter = _f111_blotter(loaded)
    realised = [row["net_pnl"] for row in blotter]
    why = build_f111_why(loaded, census)
    got_why = dict(panel["why_no_trade"])
    got_why.pop("computed_at", None)
    got_why.pop("age", None)

    assert panel["registry"]["evaluated"] == len(census)
    assert panel["registry"]["available"] == available
    assert panel["registry"]["closed_by_reason"] == dict(
        sorted(closed_by.items(), key=lambda item: (-item[1], item[0]))
    )
    assert panel["rejections"]["latest_hour"]["rows"] == len(latest_rows)
    assert panel["rejections"]["latest_hour"]["by_reason"] == _count_reasons(latest_rows)
    assert panel["rejections"]["last_24h"]["rows"] == len(day_rows)
    assert panel["rejections"]["last_24h"]["by_reason"] == _count_reasons(day_rows)
    assert panel["blotter"] == blotter[-30:]
    assert panel["paper_pnl"]["realized_usdt"] == sum(realised)
    assert panel["pending_retests"] == 1
    assert panel["protection"] == 1
    assert got_why == why
    clear_jsonl_cache()
    panel_cache.clear()
