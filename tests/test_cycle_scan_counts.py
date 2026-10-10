"""Labeled cycle counts and the Soko file behind /api/regime.

Display only. build_plan is called to prove the 50 = 56 - 6 relationship.
Nothing here changes who is scanned.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from config import universe as universe_mod


LOWEFF = "hourly_compression_btc_connors_loweff_v1"


def _book() -> dict:
    """12 approved, 50 unrestricted overrides, 6 chop-gated overrides."""
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
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        for side in ("LONG", "SHORT"):
            payload[f"{LOWEFF}:{symbol}:{side}:1h"] = {
                "strategy": LOWEFF,
                "timeframe": "1h",
                "approved": False,
                "paper_override": True,
                "activation_mode": "regime_gated",
                "blocked_regimes": ["chop"],
                "regime_activation_filter": [],
                "params": {},
            }
    return payload


def _persisted_plan(plan, universe) -> dict:
    """Same flags persist_last_cycle writes. This test does not call it."""
    return {
        "symbols_scanned": len(plan.entries),
        "signals_found": 0,
        "orders_placed": 0,
        "rejections": 0,
        "soko_trend": plan.soko_trend,
        "regime_sitouts": list(plan.regime_sitouts),
        "plan": [
            {
                "symbol": entry.symbol,
                "side": entry.side.value,
                "timeframe": entry.timeframe,
                "strategy": entry.strategy.name,
                "approved": universe.is_approved(entry.symbol, entry.side.value),
                "paper_override": universe.has_paper_override(
                    entry.strategy.name,
                    entry.symbol,
                    entry.side.value,
                    entry.timeframe,
                ),
            }
            for entry in plan.entries
        ],
    }


def test_active_overrides_are_book_minus_regime_sitouts(monkeypatch, tmp_path) -> None:
    """50 on the scan is the 56 book overrides minus 6 chop sit-outs."""
    from core.data import soko_trend as soko_mod
    from core.execution import engine as engine_mod
    from api.app import last_cycle
    from api.desk_status import cycle_scan_counts

    book = tmp_path / "approved_strategies.json"
    book.write_text(json.dumps(_book()), encoding="utf-8")
    trend = tmp_path / "last_soko_trend.json"
    trend.write_text(
        json.dumps(
            {
                "trend": "chop",
                "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ),
        encoding="utf-8",
    )
    # A fresh bull snapshot must not win. If the plan used it, chop would
    # not be blocked and the six overrides would be scanned.
    fresh = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        "firm.memory.latest_regime",
        lambda: {
            "recorded_at": fresh,
            "regime": "bull",
            "btc_trend": "bull",
            "volatility_bucket": "normal",
            "reasoning": "must not become the scan trend",
            "confidence": 0.2,
            "permitted_strategies": [],
            "metrics": {},
        },
    )
    monkeypatch.setattr(universe_mod, "APPROVALS_PATH", book)
    monkeypatch.setattr(soko_mod, "LAST_SOKO_TREND_PATH", trend)
    universe_mod.get_universe.cache_clear()
    try:
        from core.execution.engine import build_plan

        universe = universe_mod.get_universe()
        assert len(universe.approved_records) == 12
        assert len(universe.paper_override_records) == 56

        plan = build_plan(require_approval=False)
        assert plan.soko_trend == "chop"
        assert len(plan.regime_sitouts) == 6
        assert {row["strategy"] for row in plan.regime_sitouts} == {LOWEFF}
        assert all(row["key"].startswith(LOWEFF + ":") for row in plan.regime_sitouts)
        scanned_overrides = [
            entry
            for entry in plan.entries
            if universe.has_paper_override(
                entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe
            )
            and not universe.is_approved(entry.symbol, entry.side.value)
        ]
        scanned_approved = [
            entry
            for entry in plan.entries
            if universe.is_approved(entry.symbol, entry.side.value)
        ]
        assert len(scanned_approved) == 12
        assert len(scanned_overrides) == 50
        assert all(entry.strategy.name != LOWEFF for entry in plan.entries)
        assert 50 == 56 - 6

        cycle = _persisted_plan(plan, universe)
        counts = cycle_scan_counts(cycle)
        assert counts["book_approved"] == 12
        assert counts["book_overrides"] == 56
        assert counts["sitting_out_regime"] == 6
        assert counts["sitting_out_overrides"] == 6
        assert counts["active_approved"] == 12
        assert counts["active_overrides"] == 50
        assert counts["active"] == "12+50"
        assert counts["soko_trend"] == "chop"
        assert counts["reconciles"] is True
        assert counts["book_overrides"] == (
            counts["active_overrides"] + counts["sitting_out_overrides"]
        )

        cycle_path = tmp_path / "last_cycle.json"
        cycle_path.write_text(json.dumps(cycle), encoding="utf-8")
        monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", cycle_path)
        payload = last_cycle()
        assert payload["scan_counts"]["active"] == "12+50"
        assert payload["scan_counts"]["book_overrides"] == 56
        assert payload["scan_counts"]["sitting_out_regime"] == 6
        text = " ".join(payload["quiet_reasons"])
        assert "Book overrides 56." in text
        assert "Sitting out (regime) 6." in text
        assert "Active 12+50." in text
    finally:
        universe_mod.get_universe.cache_clear()


def test_regime_endpoint_reads_the_soko_file(firm_db, monkeypatch, tmp_path) -> None:
    """The live label is the Soko file. The Oct 7 LLM row is legacy only."""
    from core.data import soko_trend as soko_mod
    from core.db import session_scope
    from firm.memory import latest_regime, record_regime
    from firm.memory_models import RegimeSnapshot
    from api.app import regime

    record_regime(
        regime="bull",
        volatility_bucket="normal",
        btc_trend="bull",
        permitted_strategies=["week_open_reclaim"],
        reasoning="Oct 7 LLM record",
        confidence=0.4,
    )
    with session_scope() as session:
        row = session.scalars(select(RegimeSnapshot)).one()
        row.recorded_at = datetime(2026, 10, 7, 15, 0, tzinfo=timezone.utc)

    stored = latest_regime()
    assert stored is not None
    assert stored["regime"] == "bull"
    assert str(stored["recorded_at"]).startswith("2026-10-07")

    dest = tmp_path / "last_soko_trend.json"
    dest.write_text(
        json.dumps(
            {
                "trend": "chop",
                "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": "sgp1_auto",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(soko_mod, "LAST_SOKO_TREND_PATH", dest)

    payload = regime()
    assert payload["label"] == "chop"
    assert payload["source"] == "file"
    assert payload["as_of"]
    assert isinstance(payload["age_seconds"], int)
    assert str(payload["path"]).endswith("last_soko_trend.json")
    assert payload["legacy_llm"]["regime"] == "bull"
    assert str(payload["legacy_llm"]["recorded_at"]).startswith("2026-10-07")
    assert payload.get("regime") != "bull"
    assert payload["label"] != payload["legacy_llm"]["regime"]

    # A fresh LLM snapshot must not fill in when the file is gone. The engine
    # hook would; this endpoint must not.
    with session_scope() as session:
        row = session.scalars(select(RegimeSnapshot)).one()
        row.recorded_at = datetime.now(timezone.utc)
    dest.unlink()
    dark = regime()
    assert dark["label"] is None
    assert dark["source"] == "missing"
    assert dark["legacy_llm"]["regime"] == "bull"
    assert dark.get("regime") != "bull"
