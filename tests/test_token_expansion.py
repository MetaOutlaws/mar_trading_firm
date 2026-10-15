"""Token-expansion batch is display-only and fails closed.

The Research tab reads ``GET /api/research/expansion``. The Strategies table
keeps reading the mounted approval book. These tests do not write that book
and do not start a scan.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from config.settings import get_settings

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "research" / "token_expansion" / "fixtures" / "c1_sample.json"
FULL = ROOT / "research" / "token_expansion" / "data" / "token_expansion_c1_results.json"
SCHEMA = ROOT / "research" / "token_expansion" / "schema" / "token_expansion_results.schema.json"
DASHBOARD = ROOT / "api" / "static" / "index.html"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Do not leave a sealed-path Settings object cached for later tests."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _arm(monkeypatch, results: Path, sha: str, verdicts: Path | None) -> None:
    """Point the display loader at a fixture. Does not touch trading mode."""
    monkeypatch.setenv("TOKEN_EXPANSION_RESULTS_PATH", str(results))
    monkeypatch.setenv("TOKEN_EXPANSION_RESULTS_SHA256", sha)
    if verdicts is None:
        monkeypatch.setenv("TOKEN_EXPANSION_VERDICTS_PATH", "")
    else:
        monkeypatch.setenv("TOKEN_EXPANSION_VERDICTS_PATH", str(verdicts))
    get_settings.cache_clear()


def _expansion_response():
    from api.app import app

    return TestClient(app).get("/api/research/expansion")


def test_fixture_is_a_subset_of_the_sealed_batch() -> None:
    """The committed fixture is copied from the C1 file, not invented."""
    full = json.loads(FULL.read_text(encoding="utf-8"))
    sample = json.loads(FIXTURE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = schema["$defs"]["row"]["required"]
    assert full["batch"] == "C1"
    assert len(full["rows"]) == 120
    assert 0 < len(sample["rows"]) < 120
    by_identity = {
        (row["rule"], row["side"], row["clock"], row["token"]): row for row in full["rows"]
    }
    assert len(by_identity) == 120
    for row in sample["rows"]:
        identity = (row["rule"], row["side"], row["clock"], row["token"])
        assert by_identity[identity] == row
        assert set(required) <= set(row)
    assert _sha(FULL) == (
        "1f164c78ffbffa4b3531904ffda94cfc2242bd51725d9d83620368fed3b2e877"
    )


def test_hash_mismatch_fails_closed(monkeypatch) -> None:
    _arm(monkeypatch, FIXTURE, "0" * 64, None)
    from research.token_expansion.load import ExpansionSealError, load_token_expansion

    with pytest.raises(ExpansionSealError) as caught:
        load_token_expansion()
    assert caught.value.status_code == 409

    response = _expansion_response()
    assert response.status_code == 409
    body = response.json()
    assert list(body) == ["detail"]
    assert "rows" not in body
    assert "AAVEUSDT" not in response.text
    assert "pf_main" not in response.text


def test_missing_results_file_fails_closed(tmp_path, monkeypatch) -> None:
    missing = tmp_path / "missing-results.json"
    _arm(monkeypatch, missing, _sha(FIXTURE), None)
    response = _expansion_response()
    assert response.status_code == 404
    body = response.json()
    assert "rows" not in body
    assert "detail" in body
    assert body["detail"]


def test_missing_verdict_file_is_pending(tmp_path, monkeypatch) -> None:
    """No verdict file means PENDING, including rows whose PF is above 1."""
    missing = tmp_path / "verdicts-not-written.json"
    _arm(monkeypatch, FIXTURE, _sha(FIXTURE), missing)
    from research.token_expansion.load import load_token_expansion

    document = load_token_expansion()
    assert document["ok"] is True
    assert document["verdict_file_found"] is False
    assert document["verdict_source"]
    assert document["rows"]
    assert {row["verdict"] for row in document["rows"]} == {"PENDING"}
    doge = next(row for row in document["rows"] if row["token"] == "DOGEUSDT")
    assert doge["pf_main"] > 1
    assert doge["verdict"] == "PENDING"
    assert document["active_strategies"] == []
    assert document["counts"]["active"] == 0


def test_unset_verdict_path_is_pending(monkeypatch) -> None:
    _arm(monkeypatch, FIXTURE, _sha(FIXTURE), None)
    from research.token_expansion.load import load_token_expansion

    document = load_token_expansion()
    assert document["verdict_source"] is None
    assert document["verdict_file_found"] is False
    assert all(row["verdict"] == "PENDING" for row in document["rows"])


def test_artifact_verdict_is_not_used(tmp_path, monkeypatch) -> None:
    """A PASS stored inside the results file is ignored when no verdict file exists."""
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for row in document["rows"]:
        row["verdict"] = "PASS"
    path = tmp_path / "tampered-verdicts.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    _arm(monkeypatch, path, _sha(path), None)
    from research.token_expansion.load import load_token_expansion

    loaded = load_token_expansion()
    assert {row["verdict"] for row in loaded["rows"]} == {"PENDING"}
    assert loaded["active_strategies"] == []


def test_fail_and_pending_never_reach_active_strategies(tmp_path, monkeypatch) -> None:
    verdicts = {
        "verdicts": [
            {
                "rule": "bb_medium_bw_upper_reject",
                "side": "SHORT",
                "clock": "4h",
                "token": "AAVEUSDT",
                "verdict": "FAIL",
            },
            {
                "rule": "fib_extension_break",
                "side": "short",
                "clock": "4h",
                "token": "NEARUSDT",
                "verdict": "VETO",
            },
            {
                "rule": "week_open_reclaim",
                "side": "LONG",
                "clock": "4h",
                "token": "AAVEUSDT",
                "verdict": "PASS",
            },
        ]
    }
    path = tmp_path / "verdicts.json"
    path.write_text(json.dumps(verdicts), encoding="utf-8")
    _arm(monkeypatch, FIXTURE, _sha(FIXTURE), path)
    from research.token_expansion.load import (
        drop_blocked_expansion_pairs,
        load_token_expansion,
    )

    document = load_token_expansion()
    by_key = {(row["rule"], row["token"]): row["verdict"] for row in document["rows"]}
    assert by_key[("bb_medium_bw_upper_reject", "AAVEUSDT")] == "FAIL"
    assert by_key[("fib_extension_break", "NEARUSDT")] == "VETO"
    # Omitted from the verdict file. pf_main is about 1.49 and must not promote it.
    assert by_key[("doji_star_reversal", "DOGEUSDT")] == "PENDING"
    assert by_key[("week_open_reclaim", "AAVEUSDT")] == "PASS"
    assert {row["verdict"] for row in document["active_strategies"]} == {"PASS"}
    assert all(
        row["verdict"] not in {"FAIL", "VETO", "PENDING"} for row in document["active_strategies"]
    )

    from api.app import strategies

    payload = strategies()
    published = {
        (pair["strategy"], pair["symbol"], pair["side"], pair["timeframe"])
        for pair in payload["pairs"]
    }
    for row in document["rows"]:
        if row["verdict"] in {"FAIL", "VETO", "PENDING"}:
            assert (row["rule"], row["token"], row["side"], row["clock"]) not in published
    # A PASS overlay is still not copied onto the live book table.
    assert ("week_open_reclaim", "AAVEUSDT", "LONG", "4h") not in published
    assert all(pair.get("source") != "token_expansion" for pair in payload["pairs"])

    mixed = [
        {
            "strategy": "rsi_trend",
            "symbol": "BTCUSDT",
            "side": "LONG",
            "timeframe": "4h",
            "approved": True,
        },
        {
            "source": "token_expansion",
            "strategy": "bb_medium_bw_upper_reject",
            "symbol": "AAVEUSDT",
            "side": "SHORT",
            "timeframe": "4h",
            "verdict": "FAIL",
            "pf_main": 3.5,
        },
        {
            "batch": "C1",
            "strategy": "doji_star_reversal",
            "symbol": "DOGEUSDT",
            "side": "SHORT",
            "timeframe": "1h",
            "verdict": "PENDING",
            "pf_main": 1.49,
        },
        {
            "expansion_batch": "C1",
            "strategy": "fib_extension_break",
            "symbol": "NEARUSDT",
            "side": "SHORT",
            "timeframe": "4h",
            "verdict": "VETO",
        },
        {
            "source": "token_expansion",
            "strategy": "week_open_reclaim",
            "symbol": "AAVEUSDT",
            "side": "LONG",
            "timeframe": "4h",
            "verdict": "PASS",
            "pf_main": 0.2,
        },
    ]
    kept = drop_blocked_expansion_pairs(mixed)
    assert [(pair["strategy"], pair["symbol"]) for pair in kept] == [
        ("rsi_trend", "BTCUSDT"),
        ("week_open_reclaim", "AAVEUSDT"),
    ]


def test_strategies_endpoint_publishes_the_blocked_row_filter(monkeypatch) -> None:
    """``/api/strategies`` returns the filtered list, so a blocked row cannot linger."""
    from research.token_expansion import load as load_mod

    real = load_mod.drop_blocked_expansion_pairs

    def _mark(pairs):
        filtered = real(pairs)
        if not filtered:
            return filtered
        first = dict(filtered[0])
        first["expansion_gate"] = "applied"
        return [first, *filtered[1:]]

    monkeypatch.setattr(load_mod, "drop_blocked_expansion_pairs", _mark)
    from api.app import strategies

    payload = strategies()
    assert payload["pairs"]
    assert payload["pairs"][0].get("expansion_gate") == "applied"
    assert not any(pair.get("verdict") in {"FAIL", "VETO", "PENDING"} for pair in payload["pairs"])


def test_dashboard_keeps_expansion_off_the_strategies_table() -> None:
    html = DASHBOARD.read_text(encoding="utf-8")
    assert "function renderTokenExpansion(" in html
    assert "function expansionBlocked(" in html
    assert "function expansionPairBlocked(" in html
    assert 'get("/api/research/expansion")' in html
    assert "<h2>Token expansion</h2>" in html
    assert "expansionPairBlocked(p)" in html
    assert "FAIL, VETO, and PENDING never join the Strategies table." in html
    # The strategies renderer filters its own pairs. It does not append the batch.
    strategies_fn = html.split("function renderStrategies()", 1)[1].split("function renderGates()", 1)[0]
    assert "state.expansion.rows" not in strategies_fn
    assert "active_strategies" not in strategies_fn
