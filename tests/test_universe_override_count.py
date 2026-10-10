"""What the paper '12 research-approved, 56 operator paper override(s)' line counts.

The number is rows in the approvals file get_universe just read. It is not
config/sleeves, not an activation JSON, and not an env list. The six
hourly_compression_btc_connors_loweff_v1 rows stay in that count, and on the
paper plan, until they are gone from that file.
"""

from __future__ import annotations

import json
import logging

from config import universe as universe_mod
from scripts.enable_hourly_btc_connors_loweff import desired_records


LOWEFF = "hourly_compression_btc_connors_loweff_v1"


def _book() -> dict:
    payload: dict = {"_generated_at": "2026-10-10T00:00:00+00:00", "_verdict": "count"}
    for index in range(12):
        payload[f"week_open_reclaim:A{index:02d}USDT:LONG:4h"] = {
            "approved": True,
            "paper_override": False,
            "strategy": "week_open_reclaim",
            "timeframe": "4h",
            "activation_mode": "unrestricted",
        }
    for index in range(50):
        payload[f"mama_fama_cross:B{index:02d}USDT:SHORT:4h"] = {
            "approved": False,
            "paper_override": True,
            "strategy": "mama_fama_cross",
            "timeframe": "4h",
            "activation_mode": "unrestricted",
        }
    payload.update(desired_records())
    return payload


def test_override_count_is_the_approval_file_not_another_source(
    monkeypatch, tmp_path, caplog
) -> None:
    book = tmp_path / "approved_strategies.json"
    book.write_text(json.dumps(_book()), encoding="utf-8")
    # Decoys. The engine must not add sleeves from either of these.
    (tmp_path / "hourly_compression_btc_connors_loweff_v1_activation.json").write_text(
        json.dumps({"sleeves": 6, "extra": ["SHOULD-NOT-SCAN"]}),
        encoding="utf-8",
    )
    sleeves = tmp_path / "sleeves"
    sleeves.mkdir()
    (sleeves / "mar_f111_r12_extension_latefloor_v1.json").write_text(
        json.dumps({"universe": ["SHOULD-NOT-SCAN"], "paper_scan_enabled": True}),
        encoding="utf-8",
    )
    monkeypatch.setenv("PAPER_OVERRIDES", "SHOULD-NOT-SCAN")
    monkeypatch.setattr(universe_mod, "APPROVALS_PATH", book)
    universe_mod.get_universe.cache_clear()

    with caplog.at_level(logging.INFO, logger="config.universe"):
        loaded = universe_mod.get_universe()

    assert len(loaded.approved_records) == 12
    assert len(loaded.paper_override_records) == 56
    loweff = [key for key, _row in loaded.paper_override_records if key.startswith(LOWEFF + ":")]
    assert len(loweff) == 6
    assert any(
        "12 research-approved sleeve(s), 56 operator paper override(s)" in rec.getMessage()
        for rec in caplog.records
    )

    from core.execution.engine import build_plan

    plan = build_plan(require_approval=False)
    planned = {
        (entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe)
        for entry in plan.entries
    }
    expected = {
        (LOWEFF, symbol, side, "1h")
        for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT")
        for side in ("LONG", "SHORT")
    }
    assert expected <= planned
    assert all("SHOULD-NOT-SCAN" not in entry.symbol for entry in plan.entries)

    # Same file with the six rows removed. Nothing else puts them back.
    retired = _book()
    for key in list(desired_records()):
        del retired[key]
    book.write_text(json.dumps(retired), encoding="utf-8")
    universe_mod.get_universe.cache_clear()
    again = universe_mod.get_universe()
    assert len(again.approved_records) == 12
    assert len(again.paper_override_records) == 50
    quiet = build_plan(require_approval=False)
    assert all(entry.strategy.name != LOWEFF for entry in quiet.entries)
    universe_mod.get_universe.cache_clear()
