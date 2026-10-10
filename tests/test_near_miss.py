"""Distances on the scan card. Diagnostics must not move a gate.

These tests build telemetry rows and strategy frames. They do not place
orders, and they do not edit a threshold.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from core.strategy import f111_semantics
from core.strategy.base import Strategy
from core.strategy.f111_semantics import (
    COMPRESSION_MIN_EXCLUSIVE,
    EXTENSION_MAX_INCLUSIVE,
    HIGH_VOL_MIN_INCLUSIVE,
    gate_decision,
)
from core.strategy.gate_distance import (
    base_signal_subs,
    f111_checklist,
    f111_numeric_gates,
    rank_misses,
)
from core.strategy.hourly_compression_v1 import (
    COMPRESSION_MAX_INCLUSIVE,
    VOLUME_RATIO_MIN_INCLUSIVE,
    HourlyCompressionV1Strategy,
)
from firm.near_miss_log import MAX_ROWS, append_near_misses, read_near_misses
from firm.scan_inbox import summarise_f111_rows, summarise_sleeve_notes

NOW = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)


def _features(**overrides) -> dict:
    """A long bar that clears every base check and every F111 gate."""
    features = {
        "compression": 0.6,
        "extension_atr": 0.4,
        "prior_atr": 2.0,
        "close": 100.0,
        "open": 99.0,
        "volume_ratio": 2.0,
        "r24": 0.01,
        "close_location": 0.9,
        "boundary": 98.0,
        "true_range": 4.0,
        "filter_crsi": 40.0,
        "passes_crsi": True,
        "is_btc": True,
        "efficiency24": 0.5,
        "passes_loweff_cap": True,
    }
    features.update(overrides)
    return features


def _row(symbol: str, reason: str, features: dict, *, side: str = "LONG", gate: bool = False) -> dict:
    return {
        "symbol": symbol,
        "side": side,
        "rejection_reason": reason,
        "gate_decision": gate,
        "feature_values": features,
        "strategy": "mar_f111_r12_extension_latefloor_v1",
    }


def _gate(readings: list[dict], name: str) -> dict:
    return next(row for row in readings if row["gate"] == name or row["condition"] == name)


def test_distance_uses_each_gates_own_threshold() -> None:
    """Value, threshold, and gap come from the modules that enforce the rule."""
    features = _features(extension_atr=1.04, compression=0.47, prior_atr=0.5, close=100.0)
    readings = f111_numeric_gates(features)

    extension = _gate(readings, "extension_gate")
    assert extension["threshold"] == EXTENSION_MAX_INCLUSIVE
    assert extension["value"] == pytest.approx(1.04)
    assert extension["gap"] == pytest.approx(1.04 - EXTENSION_MAX_INCLUSIVE)
    assert extension["normalized"] == pytest.approx((1.04 - EXTENSION_MAX_INCLUSIVE) / abs(EXTENSION_MAX_INCLUSIVE))
    assert extension["units"] == "ATR"
    assert extension["passed"] is False

    compression = _gate(readings, "compression_gate")
    assert compression["threshold"] == COMPRESSION_MIN_EXCLUSIVE
    assert compression["gap"] == pytest.approx(COMPRESSION_MIN_EXCLUSIVE - 0.47)
    assert compression["normalized"] == pytest.approx(
        (COMPRESSION_MIN_EXCLUSIVE - 0.47) / abs(COMPRESSION_MIN_EXCLUSIVE)
    )
    # Equality is still a miss: the rule is strict.
    tied = _gate(f111_numeric_gates(_features(compression=COMPRESSION_MIN_EXCLUSIVE)), "compression_gate")
    assert tied["passed"] is False
    assert tied["gap"] == pytest.approx(0.0)

    high_vol = _gate(readings, "high_vol_filter")
    ratio = 0.5 / 100.0
    assert high_vol["threshold"] == HIGH_VOL_MIN_INCLUSIVE
    assert high_vol["value"] == pytest.approx(ratio)
    assert high_vol["gap"] == pytest.approx(HIGH_VOL_MIN_INCLUSIVE - ratio)
    assert high_vol["normalized"] == pytest.approx((HIGH_VOL_MIN_INCLUSIVE - ratio) / abs(HIGH_VOL_MIN_INCLUSIVE))


def test_threshold_is_read_from_the_module_not_a_copy(monkeypatch) -> None:
    """Patching the semantics constant moves the card and leaves gate_decision's default."""
    monkeypatch.setattr(f111_semantics, "EXTENSION_MAX_INCLUSIVE", 2.0)
    reading = _gate(f111_numeric_gates(_features(extension_atr=2.2)), "extension_gate")
    assert reading["threshold"] == 2.0
    assert reading["gap"] == pytest.approx(0.2)
    # The gate's default argument was bound at import. This patch must not
    # retune it. 1.5 ATR is still over the real 1.0 cap.
    passed, reason = gate_decision(compression=0.6, extension_atr=1.5, prior_atr=2.0, close=100.0)
    assert passed is False
    assert reason == "extension_gate"


def test_base_signal_names_the_closest_failed_subcondition() -> None:
    """Volume is 0.1 short of its own minimum. The bar direction is further away."""
    features = _features(volume_ratio=VOLUME_RATIO_MIN_INCLUSIVE - 0.1, open=101.0, close=100.0)
    subs = base_signal_subs(features, side="LONG")
    failed = [row for row in subs if row["passed"] is False]
    assert {row["condition"] for row in failed} >= {"base_volume", "base_bar_direction"}
    volume = _gate(subs, "base_volume")
    assert volume["threshold"] == VOLUME_RATIO_MIN_INCLUSIVE
    assert volume["gap"] == pytest.approx(0.1)
    closest = min(failed, key=lambda row: row["normalized"])
    assert closest["condition"] == "base_volume"
    # A compression of 0.80 fails the base cap and clears the F111 floor.
    assert _gate(base_signal_subs(_features(compression=0.8), side="LONG"), "base_compression")["threshold"] == (
        COMPRESSION_MAX_INCLUSIVE
    )


def test_low_efficiency_or_uses_the_closer_side() -> None:
    from core.strategy.hourly_compression_btc_connors_loweff_v1 import (
        EFFICIENCY_FLOOR_INCLUSIVE,
        LOW_EFFICIENCY_EXTENSION_MAX_INCLUSIVE,
    )

    both_fail = _features(efficiency24=0.20, extension_atr=1.1, passes_loweff_cap=False)
    row = _gate(base_signal_subs(both_fail, side="LONG"), "base_low_efficiency")
    assert row["passed"] is False
    # Extension is 0.1 over a limit of 1. Efficiency is 0.10 under 0.30.
    # 0.1/1 is closer than 0.1/0.3, so the card shows the extension side.
    assert row["threshold"] == LOW_EFFICIENCY_EXTENSION_MAX_INCLUSIVE
    assert row["gap"] == pytest.approx(1.1 - LOW_EFFICIENCY_EXTENSION_MAX_INCLUSIVE)
    cleared = _features(efficiency24=EFFICIENCY_FLOOR_INCLUSIVE, extension_atr=3.0, passes_loweff_cap=True)
    assert _gate(base_signal_subs(cleared, side="LONG"), "base_low_efficiency")["passed"] is True


def test_ranking_is_normalized_distance_and_keeps_ten() -> None:
    rows = []
    for index, extension in enumerate((1.01, 1.5, 3.0, 1.2, 1.8, 2.2, 1.05, 4.0, 1.3, 1.7, 6.0, 1.02)):
        rows.append(
            _row(
                f"S{index}USDT",
                "extension_gate",
                _features(extension_atr=extension),
            )
        )
    summary = summarise_f111_rows(rows)
    misses = summary["near_misses"]
    assert len(misses) == 10
    norms = [item["normalized"] for item in misses]
    assert norms == sorted(norms)
    assert misses[0]["value"] == pytest.approx(1.01)
    assert misses[-1]["value"] != pytest.approx(6.0)
    again = rank_misses(misses, limit=10)
    assert [item["symbol"] for item in again] == [item["symbol"] for item in misses]


def test_all_but_one_lists_only_a_single_failed_gate() -> None:
    only_extension = _row("SOLUSDT", "extension_gate", _features(extension_atr=1.05))
    two_gates = _row(
        "ETHUSDT",
        "extension_gate",
        _features(extension_atr=1.2, compression=0.4),
    )
    clean = _row("BTCUSDT", "", _features(), gate=True)
    summary = summarise_f111_rows([only_extension, two_gates, clean])
    listed = summary["all_but_one"]
    assert listed["count"] == 1
    assert [item["symbol"] for item in listed["sleeves"]] == ["SOLUSDT"]
    assert listed["sleeves"][0]["gate"] == "extension_gate"
    assert listed["sleeves"][0]["value"] == pytest.approx(1.05)
    assert listed["sleeves"][0]["threshold"] == EXTENSION_MAX_INCLUSIVE


def test_blocked_after_gates_keeps_the_exact_reason_and_is_actionable() -> None:
    rows = [
        _row("AVAXUSDT", "position_already_open", _features(), gate=True),
        _row("DOTUSDT", "4 open positions >= limit 3", _features(), gate=True),
        _row("DOGEUSDT", "regime sit-out: chop is blocked for sleeve", _features(), gate=True),
        _row("LINKUSDT", "stale_signal_not_backfilled", _features(), gate=True),
        {
            "symbol": "BNBUSDT",
            "side": "LONG",
            "rejection_reason": "Contract not found",
            "instrument_unavailable": True,
            "gate_decision": False,
            "feature_values": _features(compression=0.2),
        },
        {
            "symbol": "XRPUSDT",
            "side": "SHORT",
            "rejection_reason": "stale_signal_not_backfilled",
            "gate_decision": False,
            "feature_values": _features(),
        },
    ]
    summary = summarise_f111_rows(rows)
    blocked = summary["blocked_after_gates"]
    assert [item["symbol"] for item in blocked] == ["AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT"]
    assert all(item["actionable"] is True for item in blocked)
    avax = next(item for item in blocked if item["symbol"] == "AVAXUSDT")
    assert avax["reason"] == "position_already_open"
    assert avax["bucket"] == "existing position"
    assert summary["freshness"]["stale_bar"] == 2
    assert summary["freshness"]["unavailable_instrument"] == 1
    assert "BNBUSDT" not in {item["symbol"] for item in blocked}
    assert "XRPUSDT" not in {item["symbol"] for item in blocked}


def test_book_hook_distance_and_reason_only_fallback() -> None:
    """A triple is a distance. No hook leaves the reason and no invented gap."""
    measured = summarise_sleeve_notes(
        [
            {
                "sleeve_id": "SOLUSDT|1h|LONG|prior_close_magnet_fade",
                "symbol": "SOLUSDT",
                "side": "LONG",
                "strategy": "prior_close_magnet_fade",
                "signal": False,
                "ordered": False,
                "rejection": "no_signal",
                "diagnostics": [("stretch", 1.2, 1.0)],
            }
        ]
    )
    miss = measured["near_misses"][0]
    assert miss["strategy"] == "prior_close_magnet_fade"
    assert miss["condition"] == "stretch"
    assert miss["value"] == pytest.approx(1.2)
    assert miss["threshold"] == pytest.approx(1.0)
    assert miss["gap"] == pytest.approx(0.2)
    assert measured["all_but_one"]["count"] == 0

    checklist = summarise_sleeve_notes(
        [
            {
                "sleeve_id": "ETHUSDT|1h|SHORT|example",
                "symbol": "ETHUSDT",
                "side": "SHORT",
                "strategy": "example",
                "signal": False,
                "rejection": "no_signal",
                "diagnostics": [
                    {"condition": "width", "value": 0.4, "threshold": 0.5, "passed": False},
                    {"condition": "volume", "value": 2.0, "threshold": 1.5, "passed": True},
                ],
            }
        ]
    )
    assert checklist["all_but_one"]["count"] == 1
    assert checklist["all_but_one"]["sleeves"][0]["condition"] == "width"

    plain = summarise_sleeve_notes(
        [
            {
                "sleeve_id": "BTCUSDT|1h|LONG|unnamed",
                "rejection": "no_signal",
                "signal": False,
            }
        ]
    )
    assert plain["near_misses"] == []
    assert plain["rejection_counts"] == {"no_signal": 1}
    assert plain["all_but_one"]["count"] == 0


def test_near_miss_log_prunes_after_24h_and_stays_bounded(tmp_path: Path) -> None:
    path = tmp_path / "near_miss_log.jsonl"
    old = {
        "symbol": "OLDUSDT",
        "side": "LONG",
        "strategy": "f111",
        "gate": "extension_gate",
        "condition": "extension_atr",
        "value": 1.2,
        "threshold": 1.0,
        "gap": 0.2,
        "normalized": 0.2,
        "logged_at": (NOW - timedelta(hours=25)).isoformat(),
        "scan_type": "f111",
        "bar_time": (NOW - timedelta(hours=25)).isoformat(),
    }
    path.write_text(__import__("json").dumps(old) + "\n", encoding="utf-8")
    fresh = {
        "symbol": "SOLUSDT",
        "side": "LONG",
        "strategy": "f111",
        "gate": "extension_gate",
        "condition": "extension_atr",
        "value": 1.01,
        "threshold": 1.0,
        "gap": 0.01,
        "normalized": 0.01,
    }
    kept = append_near_misses([fresh], scan_type="f111", bar_time=NOW, now=NOW, path=path)
    assert kept == 1
    loaded = read_near_misses(now=NOW, path=path)
    assert loaded["count"] == 1
    assert loaded["rows"][0]["symbol"] == "SOLUSDT"
    assert loaded["retention_hours"] == 24

    # Same bar again replaces the line instead of appending a second copy.
    fresh["gap"] = 0.02
    fresh["normalized"] = 0.02
    append_near_misses([fresh], scan_type="f111", bar_time=NOW, now=NOW + timedelta(minutes=5), path=path)
    replaced = read_near_misses(now=NOW, path=path)
    assert replaced["count"] == 1
    assert replaced["rows"][0]["gap"] == pytest.approx(0.02)

    flood = [
        {
            "symbol": f"N{index}",
            "side": "LONG",
            "condition": "extension_atr",
            "gate": "extension_gate",
            "value": 1.1,
            "threshold": 1.0,
            "gap": 0.1,
            "normalized": 0.1,
        }
        for index in range(MAX_ROWS + 25)
    ]
    bounded = append_near_misses(
        flood,
        scan_type="book",
        bar_time=NOW,
        now=NOW,
        path=path,
    )
    assert bounded == MAX_ROWS
    assert read_near_misses(now=NOW, path=path, limit=5)["count"] == MAX_ROWS


def test_api_returns_the_rolling_log(tmp_path: Path, monkeypatch, firm_db) -> None:
    path = tmp_path / "near_miss_log.jsonl"
    monkeypatch.setattr("firm.near_miss_log.LOG_PATH", path)
    append_near_misses(
        [
            {
                "symbol": "SOLUSDT",
                "side": "SHORT",
                "strategy": "mar_f111_r12_extension_latefloor_v1",
                "gate": "compression_gate",
                "condition": "compression",
                "value": 0.49,
                "threshold": 0.5,
                "gap": 0.01,
                "normalized": 0.02,
            }
        ],
        scan_type="f111",
        bar_time=NOW,
        now=NOW,
        path=path,
    )
    from api.app import app

    client = TestClient(app)
    response = client.get("/api/near-misses")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["rows"][0]["symbol"] == "SOLUSDT"
    assert body["retention_hours"] == 24


def test_diagnostics_do_not_change_gate_decision() -> None:
    """The same inputs, with the distance card run in between, decide the same way."""
    samples = [
        dict(compression=0.6, extension_atr=0.2, prior_atr=1.0, close=100.0),
        dict(compression=0.5, extension_atr=0.2, prior_atr=1.0, close=100.0),
        dict(compression=0.6, extension_atr=1.0 + 1e-9, prior_atr=1.0, close=100.0),
        dict(compression=0.6, extension_atr=0.2, prior_atr=0.5, close=100.0),
        dict(compression=float("nan"), extension_atr=0.2, prior_atr=1.0, close=100.0),
        dict(compression=0.8, extension_atr=0.2, prior_atr=2.0, close=100.0),
    ]
    before = [gate_decision(**sample) for sample in samples]
    for sample in samples:
        f111_checklist(dict(sample), side="LONG", base_blocked=False)
        f111_numeric_gates(dict(sample))
    after = [gate_decision(**sample) for sample in samples]
    assert after == before

    from tests.test_hourly_compression_v1 import tape

    rule = HourlyCompressionV1Strategy()
    frame = tape()
    first = rule.generate_signals(frame)
    signal = first["signal"].tolist()
    side = first["side"].tolist()
    reason = first["reason"].tolist()
    rule.gate_diagnostics(frame, first)
    assert first["signal"].tolist() == signal
    assert first["side"].tolist() == side
    assert first["reason"].tolist() == reason
    second = rule.generate_signals(frame)
    assert second["signal"].tolist() == signal
    assert second["side"].tolist() == side


def test_a_mutating_hook_cannot_change_the_signal() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="h", tz="UTC")
    candles = pd.DataFrame(
        {"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0, "volume": 1.0},
        index=index,
    )

    class Flat(Strategy):
        name = "flat_diag"
        min_bars = 1

        def generate_signals(self, frame):
            return self.empty_signals(frame)

    class Evil(Flat):
        def gate_diagnostics(self, frame, signals):
            signals.loc[:, "signal"] = 1
            signals.loc[:, "side"] = "LONG"
            signals.loc[:, "score"] = 9.0
            signals.loc[:, "reason"] = "forced"
            return [("stretch", 1.2, 1.0)]

    evil = Evil()
    assert evil.latest_signal("BTCUSDT", candles) is None
    assert evil._last_gate_diagnostics is None
    assert int(evil.generate_signals(candles)["signal"].iloc[-1]) == 0

    class Honest(Flat):
        def gate_diagnostics(self, frame, signals):
            return [{"condition": "stretch", "value": 1.2, "threshold": 1.0, "passed": False}]

    honest = Honest()
    assert honest.latest_signal("BTCUSDT", candles) is None
    assert honest._last_gate_diagnostics[0]["condition"] == "stretch"
    assert int(honest.generate_signals(candles)["signal"].iloc[-1]) == 0
