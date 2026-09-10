"""Floor workflow snapshot is display-only process state.

Does not start walk-forwards or write approved_strategies.json.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar

from firm.workflow import WORKFLOW_STAGES, high_level_progress, workflow_snapshot


class _Universe:
    approved_pairs: ClassVar[list] = [("BTCUSDT", "SHORT"), ("ETHUSDT", "SHORT")]
    paper_override_records: ClassVar[list] = [("SOLUSDT", {"family": "demo"})]


def _fake_universe():
    return _Universe()


def _isolate(monkeypatch) -> None:
    _fake_universe.cache_clear = lambda: None
    monkeypatch.setattr("config.universe.get_universe", _fake_universe)
    monkeypatch.setattr("firm.research_jobs.open_code_mandates", list)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: None)
    monkeypatch.setattr("firm.workflow._inbox_rows", list)
    monkeypatch.setattr("firm.workflow._quant_is_running", lambda: False)
    monkeypatch.setattr(
        "core.risk.killswitch.KillSwitch",
        lambda: SimpleNamespace(read=lambda: SimpleNamespace(tripped=False)),
    )
    monkeypatch.setattr("firm.pipeline_state.load_state", dict)


def test_workflow_stage_owners_match_ceo_contract() -> None:
    owners = {s["id"]: (s["label"], s["owner"]) for s in WORKFLOW_STAGES}
    assert owners["hyp"] == ("Hypothesis", "Shumba")
    assert owners["score"] == ("Score", "Munha")
    assert owners["coo"] == ("COO ONE", "Marcus")
    assert owners["ceo"] == ("CEO YES", "Brian")
    assert owners["stamp"] == ("Stamp", "Garwe")
    assert owners["code"] == ("Code", "Chiremba")
    assert owners["walk"] == ("Walk", "Mukanya")
    assert owners["harvest"] == ("Harvest", "Mukanya")
    assert owners["review"] == ("Review", "Marcus")
    assert owners["book"] == ("Book", "paper")
    assert owners["activate"] == ("Activate", "Soko")
    assert [s["id"] for s in WORKFLOW_STAGES] == [
        "hyp",
        "score",
        "coo",
        "ceo",
        "stamp",
        "code",
        "walk",
        "harvest",
        "review",
        "book",
        "activate",
    ]


def test_high_level_progress_strips_cell_dump() -> None:
    job = {
        "family": "rolling_va_extreme_reject",
        "status": "running",
        "side": "BOTH",
        "symbols": ["BTCUSDT"] * 6,
    }
    bar = {
        "progress": 41,
        "progress_label": "5/12 pair verdicts · VERDICT: BTCUSDT SHORT REJECT Fetching 1h",
        "stalled": False,
    }
    out = high_level_progress(job, bar)
    assert out["progress"] == 41
    assert out["progress_label"] == "5/12 pairs"
    assert "VERDICT" not in out["progress_label"]
    assert "Fetching" not in out["progress_label"]


def test_running_walk_is_current_with_next_then_buffer(monkeypatch) -> None:
    _isolate(monkeypatch)
    jobs = [
        {
            "id": 90,
            "family": "rolling_va_extreme_reject",
            "status": "running",
            "clock": "4h/4h",
            "side": "BOTH",
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT"],
            "detail": "Validator pid 28016 on rolling_va_extreme_reject",
            "log_path": "/tmp/missing-validator.log",
        }
    ]
    remaining = [
        {"family": "lvn_fill_reject", "clock": "4h/4h", "side": "BOTH", "coded": True},
        {"family": "inside_bar_break_fail", "clock": "4h/4h", "side": "BOTH", "coded": True},
    ]
    monkeypatch.setattr(
        "firm.research_jobs.walkforward_progress",
        lambda job: {
            "progress": 33,
            "progress_label": "4/12 pair verdicts · VERDICT: ETHUSDT LONG REJECT",
            "stalled": False,
        },
    )
    snap = workflow_snapshot(jobs=jobs, remaining=remaining)
    walk = next(s for s in snap["stages"] if s["id"] == "walk")
    assert walk["current"] is True
    assert walk["state"] == "active"
    assert walk["owner"] == "Mukanya"
    assert snap["current"]["family"] == "rolling_va_extreme_reject"
    assert snap["current"]["clock"] == "4h/4h"
    assert snap["current"]["side"] == "BOTH"
    assert snap["current"]["progress"] == 33
    assert snap["current"]["progress_label"] == "4/12 pairs"
    assert "pid" not in str(snap["current"])
    assert "VERDICT" not in str(snap["current"])
    assert snap["next"]["family"] == "lvn_fill_reject"
    assert snap["next"]["slot"] == "NEXT"
    assert snap["next"]["letter"] == "E"
    assert snap["then"]["family"] == "inside_bar_break_fail"
    assert snap["then"]["slot"] == "THEN"
    assert snap["book"]["approved_count"] == 2
    assert snap["book"]["paper_override_count"] == 1
    assert snap["book"]["live"] == "OFF"
    assert snap["blockers"] == []
    activate = next(s for s in snap["stages"] if s["id"] == "activate")
    assert activate["state"] == "wait"
    assert activate["owner"] == "Soko"
    assert any(w["owner"] == "Soko" for w in snap["who_waits"])


def test_uncoded_mandate_is_blocker_not_progress(monkeypatch) -> None:
    _isolate(monkeypatch)
    monkeypatch.setattr(
        "firm.research_jobs.open_code_mandates",
        lambda: [{"family": "lvn_fill_reject", "phase": "implement", "clock": "4h/4h", "side": "BOTH"}],
    )
    snap = workflow_snapshot(jobs=[], remaining=[])
    code = next(s for s in snap["stages"] if s["id"] == "code")
    assert code["current"] is True
    assert code["state"] == "bad"
    assert snap["blockers"]
    assert "not coded" in snap["blockers"][0]["text"]
    assert snap["current"]["family"] == "lvn_fill_reject"
    assert snap["current"]["progress_label"] == "coding"
