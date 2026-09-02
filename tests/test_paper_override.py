"""Operator paper override: veto a research reject for paper only."""

from __future__ import annotations

import json

from config.universe import LongParams, ShortParams, Universe
from core.execution.engine import build_plan
from core.strategy.base import SignalSide
from research.validate import SymbolVerdict, operator_paper_approve, write_approvals


def test_operator_paper_approve_does_not_unlock_live(tmp_path) -> None:
    path = tmp_path / "approved_strategies.json"
    path.write_text(
        json.dumps(
            {
                "mass_index_reversal:ETHUSDT:SHORT:4h": {
                    "approved": False,
                    "failures": ["only 47% of folds profitable (need >= 50%)"],
                    "timeframe": "4h",
                    "strategy": "mass_index_reversal",
                    "params": {"ema_len": 9, "sum_len": 25},
                    "oos_trades": 35,
                    "oos_profit_factor": 1.46,
                }
            }
        ),
        encoding="utf-8",
    )
    applied = operator_paper_approve(
        ["mass_index_reversal:ETHUSDT:SHORT:4h"],
        reason="operator veto for paper fills",
        path=path,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    rec = data[applied[0]]
    assert rec["approved"] is False
    assert rec["paper_override"] is True
    assert rec["paper_override_reason"] == "operator veto for paper fills"


def test_write_approvals_keeps_paper_override(tmp_path) -> None:
    path = tmp_path / "approved_strategies.json"
    path.write_text(
        json.dumps(
            {
                "mass_index_reversal:ETHUSDT:SHORT:4h": {
                    "approved": False,
                    "paper_override": True,
                    "paper_override_at": "2026-09-01T00:00:00+00:00",
                    "paper_override_reason": "keep me",
                    "paper_override_by": "operator",
                    "failures": ["old"],
                    "timeframe": "4h",
                    "strategy": "mass_index_reversal",
                }
            }
        ),
        encoding="utf-8",
    )
    write_approvals(
        [
            SymbolVerdict(
                symbol="ETHUSDT",
                side="SHORT",
                timeframe="4h",
                strategy="mass_index_reversal",
                failures=["only 47% of folds profitable (need >= 50%)"],
            )
        ],
        path=path,
    )
    rec = json.loads(path.read_text(encoding="utf-8"))["mass_index_reversal:ETHUSDT:SHORT:4h"]
    assert rec["approved"] is False
    assert rec["paper_override"] is True
    assert rec["paper_override_reason"] == "keep me"


def test_paper_plan_scans_override_and_live_does_not(monkeypatch) -> None:
    universe = Universe(
        long_params={"SOLUSDT": LongParams(symbol="SOLUSDT", timeframe="15min")},
        short_params={
            "BTCUSDT": ShortParams(symbol="BTCUSDT", timeframe="15min"),
            "ETHUSDT": ShortParams(symbol="ETHUSDT", timeframe="15min"),
        },
        approvals={
            "atr_channel_breakout:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
                "params": {"atr_k": 2.0},
            },
            "mama_fama_cross:BTCUSDT:SHORT:4h": {
                "approved": False,
                "paper_override": True,
                "timeframe": "4h",
                "strategy": "mama_fama_cross",
                "params": {"fastlimit": 0.5, "slowlimit": 0.05},
                "failures": ["loses money in regime(s): bull"],
            },
            "mass_index_reversal:SOLUSDT:LONG:4h": {
                "approved": False,
                "paper_override": True,
                "timeframe": "4h",
                "strategy": "mass_index_reversal",
                "params": {"ema_len": 9, "sum_len": 25},
                "failures": ["only 5 OOS trades (need >= 30)"],
            },
        },
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "bb_squeeze_breakout")
    monkeypatch.setattr("firm.research_jobs._active_job_for", lambda family: None)

    live = build_plan(require_approval=True)
    live_ids = {(e.symbol, e.side.value, e.strategy.name) for e in live.entries}
    assert live_ids == {("BTCUSDT", "SHORT", "atr_channel_breakout")}

    paper = build_plan(require_approval=False, candidates=["BTCUSDT", "SOLUSDT", "ETHUSDT"])
    paper_ids = {(e.symbol, e.side.value, e.strategy.name) for e in paper.entries}
    assert ("BTCUSDT", "SHORT", "atr_channel_breakout") in paper_ids
    assert ("BTCUSDT", "SHORT", "mama_fama_cross") in paper_ids
    assert ("SOLUSDT", "LONG", "mass_index_reversal") in paper_ids
    assert universe.is_approved("BTCUSDT", "SHORT") is True
    assert universe.is_approved("SOLUSDT", "LONG") is False
    assert universe.has_paper_override("mama_fama_cross", "BTCUSDT", "SHORT", "4h") is True
    atr_1h = {
        (e.symbol, e.side.value, e.strategy.name, e.timeframe)
        for e in paper.entries
        if e.strategy.name == "atr_channel_breakout" and e.timeframe == "1h"
    }
    assert atr_1h == {
        ("BNBUSDT", "LONG", "atr_channel_breakout", "1h"),
        ("BNBUSDT", "SHORT", "atr_channel_breakout", "1h"),
        ("XRPUSDT", "LONG", "atr_channel_breakout", "1h"),
        ("XRPUSDT", "SHORT", "atr_channel_breakout", "1h"),
        ("AVAXUSDT", "LONG", "atr_channel_breakout", "1h"),
        ("AVAXUSDT", "SHORT", "atr_channel_breakout", "1h"),
    }
    assert not any(e.timeframe == "1h" and e.strategy.name == "atr_channel_breakout" for e in live.entries)


def test_certify_paper_allows_operator_overrides(tmp_path, monkeypatch) -> None:
    from firm import integrity as integrity_mod

    cycle_path = tmp_path / "last_cycle.json"
    cycle_path.write_text(
        json.dumps(
            {
                "plan": [
                    {
                        "symbol": "BTCUSDT",
                        "side": "SHORT",
                        "timeframe": "4h",
                        "strategy": "atr_channel_breakout",
                    },
                    {
                        "symbol": "BTCUSDT",
                        "side": "SHORT",
                        "timeframe": "4h",
                        "strategy": "mama_fama_cross",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    universe = Universe(
        long_params={},
        short_params={"BTCUSDT": ShortParams(symbol="BTCUSDT", timeframe="4h")},
        approvals={
            "atr_channel_breakout:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
            },
            "mama_fama_cross:BTCUSDT:SHORT:4h": {
                "approved": False,
                "paper_override": True,
                "timeframe": "4h",
                "strategy": "mama_fama_cross",
            },
        },
    )
    monkeypatch.setattr(integrity_mod, "LAST_CYCLE_PATH", cycle_path)
    monkeypatch.setattr("config.universe.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "bb_squeeze_breakout")
    report = integrity_mod.certify_paper()
    sleeve = next(c for c in report["checks"] if c["name"] == "paper_sleeve")
    assert sleeve["ok"] is True


def test_certify_paper_accepts_atr_1h_candidates(tmp_path, monkeypatch) -> None:
    from firm import integrity as integrity_mod

    cycle_path = tmp_path / "last_cycle.json"
    cycle_path.write_text(
        json.dumps(
            {
                "plan": [
                    {
                        "symbol": "BTCUSDT",
                        "side": "SHORT",
                        "timeframe": "4h",
                        "strategy": "atr_channel_breakout",
                    },
                    {
                        "symbol": "BNBUSDT",
                        "side": "LONG",
                        "timeframe": "1h",
                        "strategy": "atr_channel_breakout",
                        "paper_candidate": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    universe = Universe(
        long_params={},
        short_params={"BTCUSDT": ShortParams(symbol="BTCUSDT", timeframe="4h")},
        approvals={
            "atr_channel_breakout:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
            },
        },
    )
    monkeypatch.setattr(integrity_mod, "LAST_CYCLE_PATH", cycle_path)
    monkeypatch.setattr("config.universe.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "zero_lag_ema_cross")
    report = integrity_mod.certify_paper()
    sleeve = next(c for c in report["checks"] if c["name"] == "paper_sleeve")
    clock = next(c for c in report["checks"] if c["name"] == "paper_clock")
    assert sleeve["ok"] is True
    assert clock["ok"] is True
