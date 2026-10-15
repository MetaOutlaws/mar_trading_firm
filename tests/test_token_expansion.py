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


TRADE_FIXTURE = (
    ROOT
    / "research"
    / "token_expansion"
    / "fixtures"
    / "trades"
    / "bb_medium_bw_upper_reject_SHORT_4h_AAVEUSDT_official_0.31.csv"
)
RULE = "bb_medium_bw_upper_reject"
TRADE_HEADER = "net_pnl,return_pct,symbol,segment\n"


def _trade_name(token: str, cost: str = "official_0.31", rule: str = RULE, side: str = "SHORT", clock: str = "4h") -> str:
    return f"trades/{rule}_{side}_{clock}_{token}_{cost}.csv"


def _trade_csv(rows: list[tuple[str, str, str, str]]) -> str:
    """rows are (net_pnl, return_pct, symbol, segment)."""
    body = "".join(f"{pnl},{ret},{symbol},{segment}\n" for pnl, ret, symbol, segment in rows)
    return TRADE_HEADER + body


def _seal_phase(root: Path, phase: str, summary: str, files: dict[str, str]) -> str:
    """Write one sealed phase. ``files`` maps manifest paths to contents."""
    directory = root / phase
    directory.mkdir(parents=True)
    (directory / "summary.csv").write_text(summary, encoding="utf-8")
    names = ["summary.csv"]
    for rel, text in files.items():
        path = directory / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        names.append(rel)
    lines = []
    for name in names:
        digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}\n")
    manifest = directory / "SHA256SUMS"
    manifest.write_text("".join(lines), encoding="utf-8")
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


def _summary(*rows: str, with_win_rate: bool = False) -> str:
    header = "cost_bar,row,token,pf,trades"
    if with_win_rate:
        header += ",win_rate"
    return header + "\n" + "".join(rows)


def test_win_rate_reads_the_sealed_trade_file_format(tmp_path) -> None:
    """Win is net_pnl > 0. Phase is the directory. fold and tail both count."""
    from research.token_expansion.ingest import (
        TRADE_LIST_COLUMNS,
        TRADE_NET_PNL_COLUMN,
        TRADE_RETURN_PCT_COLUMN,
        TRADE_SEGMENT_COLUMN,
        TRADE_SYMBOL_COLUMN,
        build_results,
        compute_win_rate,
    )

    assert TRADE_NET_PNL_COLUMN == "net_pnl"
    assert TRADE_RETURN_PCT_COLUMN == "return_pct"
    assert TRADE_SYMBOL_COLUMN == "symbol"
    assert TRADE_SEGMENT_COLUMN == "segment"
    assert TRADE_LIST_COLUMNS == ("net_pnl", "return_pct", "symbol", "segment")
    fixture = TRADE_FIXTURE.read_text(encoding="utf-8")
    assert fixture.startswith("net_pnl,return_pct,symbol,segment\n")
    assert "fold" in fixture and "tail" in fixture
    assert compute_win_rate([]) is None
    assert compute_win_rate([0.2, -0.1, 0.0]) == pytest.approx(1 / 3)
    assert compute_win_rate([-0.05]) == 0.0

    identity = f"{RULE}:x:SHORT:4h"
    aave_name = _trade_name("AAVEUSDT")
    other_cost = _trade_csv([("9", "9", "AAVEUSDT", "fold")] * 4)
    exploratory = _trade_csv([("-0.05", "-0.01", "AAVEUSDT", "fold")])
    seals = {
        "main": _seal_phase(
            tmp_path,
            "main",
            _summary(
                f"official_0.31,{identity},AAVEUSDT,1.2,3,{1/3:.10f}\n",
                f"official_0.31,{identity},NEARUSDT,,0,\n",
                f"other_cost,{identity},AAVEUSDT,9,9,1\n",
                with_win_rate=True,
            ),
            {
                aave_name: fixture,
                _trade_name("AAVEUSDT", cost="loose"): other_cost,
            },
        ),
        "holdout": _seal_phase(
            tmp_path,
            "holdout",
            _summary(
                f"official_0.31,{identity},AAVEUSDT,,0,\n",
                f"official_0.31,{identity},NEARUSDT,,0,\n",
                with_win_rate=True,
            ),
            {},
        ),
        "exploratory": _seal_phase(
            tmp_path,
            "exploratory",
            _summary(
                f"official_0.31,{identity},AAVEUSDT,0.4,1,0\n",
                f"official_0.31,{identity},NEARUSDT,,0,\n",
                with_win_rate=True,
            ),
            {_trade_name("AAVEUSDT"): exploratory},
        ),
    }
    document = build_results(str(tmp_path), seals=seals)
    by_token = {row["token"]: row for row in document["rows"]}
    assert by_token["AAVEUSDT"]["winrate_main"] == pytest.approx(1 / 3)
    assert by_token["AAVEUSDT"]["winrate_holdout"] is None
    assert by_token["AAVEUSDT"]["winrate_2026"] == 0.0
    assert by_token["AAVEUSDT"]["pf_exploratory"] == pytest.approx(0.4)
    assert "winrate_exploratory" not in by_token["AAVEUSDT"]
    assert "win_rate" not in by_token["AAVEUSDT"]
    assert by_token["NEARUSDT"]["winrate_main"] is None
    assert by_token["NEARUSDT"]["winrate_holdout"] is None
    assert by_token["NEARUSDT"]["winrate_2026"] is None
    source = (ROOT / "research" / "token_expansion" / "ingest.py").read_text(encoding="utf-8")
    assert "research.engine" not in source
    assert "core.execution" not in source


def test_summary_win_rate_mismatch_fails_closed(tmp_path) -> None:
    from research.token_expansion.ingest import build_results

    identity = f"{RULE}:x:SHORT:4h"
    trades = _trade_csv([("0.2", "0.02", "AAVEUSDT", "fold"), ("-0.1", "-0.01", "AAVEUSDT", "tail")])
    seals = {}
    for phase in ("main", "holdout", "exploratory"):
        files = {}
        if phase == "main":
            summary = _summary(
                f"official_0.31,{identity},AAVEUSDT,1.2,2,0.9\n",
                with_win_rate=True,
            )
            files[_trade_name("AAVEUSDT")] = trades
        else:
            summary = _summary(f"official_0.31,{identity},AAVEUSDT,1.2,0\n")
        seals[phase] = _seal_phase(tmp_path, phase, summary, files)
    with pytest.raises(SystemExit) as caught:
        build_results(str(tmp_path), seals=seals)
    assert "summary win_rate" in str(caught.value)


def test_bad_segment_symbol_or_legacy_file_fails_closed(tmp_path) -> None:
    """fold|tail and the filename identity are required. The old single CSV is not read."""
    from research.token_expansion.ingest import build_results

    identity = f"{RULE}:x:SHORT:4h"
    summary = _summary(f"official_0.31,{identity},AAVEUSDT,1,1\n")
    empty = {phase: _summary(f"official_0.31,{identity},AAVEUSDT,1,0\n") for phase in ("holdout", "exploratory")}

    bad_segment = _seal_phase(
        tmp_path,
        "main",
        summary,
        {_trade_name("AAVEUSDT"): _trade_csv([("0.2", "0.02", "AAVEUSDT", "main")])},
    )
    seals = {"main": bad_segment, "holdout": _seal_phase(tmp_path, "holdout", empty["holdout"], {}), "exploratory": _seal_phase(tmp_path, "exploratory", empty["exploratory"], {})}
    with pytest.raises(SystemExit) as caught:
        build_results(str(tmp_path), seals=seals)
    assert "fold or tail" in str(caught.value)

    bad_symbol_root = tmp_path / "symbol"
    seals = {
        "main": _seal_phase(
            bad_symbol_root,
            "main",
            summary,
            {_trade_name("AAVEUSDT"): _trade_csv([("0.2", "0.02", "ETHUSDT", "fold")])},
        ),
        "holdout": _seal_phase(bad_symbol_root, "holdout", empty["holdout"], {}),
        "exploratory": _seal_phase(bad_symbol_root, "exploratory", empty["exploratory"], {}),
    }
    with pytest.raises(SystemExit) as caught:
        build_results(str(bad_symbol_root), seals=seals)
    assert "symbol" in str(caught.value)

    legacy_root = tmp_path / "legacy"
    seals = {
        "main": _seal_phase(
            legacy_root,
            "main",
            summary,
            {"per_token_trades.csv": "token,row,segment,cost_bar,net_return\nAAVEUSDT,x,main,official_0.31,0.2\n"},
        ),
        "holdout": _seal_phase(legacy_root, "holdout", empty["holdout"], {}),
        "exploratory": _seal_phase(legacy_root, "exploratory", empty["exploratory"], {}),
    }
    with pytest.raises(SystemExit) as caught:
        build_results(str(legacy_root), seals=seals)
    assert "trade-list N" in str(caught.value)


def test_trade_list_count_mismatch_fails_closed(tmp_path) -> None:
    from research.token_expansion.ingest import build_results

    identity = f"{RULE}:x:SHORT:4h"
    seals = {}
    for phase in ("main", "holdout", "exploratory"):
        files = {}
        if phase == "main":
            summary = _summary(f"official_0.31,{identity},AAVEUSDT,1,2\n")
            files[_trade_name("AAVEUSDT")] = _trade_csv([("0.1", "0.01", "AAVEUSDT", "tail")])
        else:
            summary = _summary(f"official_0.31,{identity},AAVEUSDT,1,0\n")
        seals[phase] = _seal_phase(tmp_path, phase, summary, files)
    with pytest.raises(SystemExit) as caught:
        build_results(str(tmp_path), seals=seals)
    assert "FAIL CLOSED" in str(caught.value)


def test_manifest_mismatch_fails_before_trade_lists(tmp_path) -> None:
    from research.token_expansion.ingest import build_results

    seals = {
        phase: _seal_phase(tmp_path, phase, "cost_bar,row,token,pf,trades\n", {})
        for phase in ("main", "holdout", "exploratory")
    }
    seals["main"] = "0" * 64
    with pytest.raises(SystemExit) as caught:
        build_results(str(tmp_path), seals=seals)
    assert "manifest mismatch" in str(caught.value)


def test_old_results_file_leaves_win_rate_blank(monkeypatch) -> None:
    """The committed C1 file has no winrate fields and keeps its sha."""
    _arm(monkeypatch, FIXTURE, _sha(FIXTURE), None)
    from research.token_expansion.load import load_token_expansion

    document = load_token_expansion()
    assert document["rows"]
    for row in document["rows"]:
        assert row["winrate_main"] is None
        assert row["winrate_holdout"] is None
        assert row["winrate_2026"] is None
        assert row["pf_2026"] == row["pf_exploratory"]
    full = json.loads(FULL.read_text(encoding="utf-8"))
    assert "winrate_main" not in full["rows"][0]
    assert "winrate_2026" not in full["rows"][0]
    assert _sha(FULL) == (
        "1f164c78ffbffa4b3531904ffda94cfc2242bd51725d9d83620368fed3b2e877"
    )
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    required = schema["$defs"]["row"]["required"]
    properties = schema["$defs"]["row"]["properties"]
    assert "winrate_main" not in required
    assert "winrate_holdout" not in required
    assert "winrate_2026" not in required
    assert "pf_exploratory" in required
    assert "winrate_main" in properties


def test_win_rate_out_of_range_fails_closed(tmp_path, monkeypatch) -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for row in document["rows"]:
        row["winrate_main"] = 1.5
        row["winrate_holdout"] = None
        row["winrate_2026"] = 0.25
    path = tmp_path / "bad-winrate.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    _arm(monkeypatch, path, _sha(path), None)
    response = _expansion_response()
    assert response.status_code == 422
    assert "rows" not in response.json()
    assert "AAVEUSDT" not in response.text


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
    assert "sortExpansion" not in strategies_fn
    assert "expansionFilteredRows" not in strategies_fn
    assert "resetExpansionFilters" not in strategies_fn
    # Card filters are display-only. They do not feed the strategies table.
    assert "PF = gross profit / gross loss" in html
    assert "N = trade count" in html
    assert "WR = winning trades / N" in html
    assert "Holdout = H2 2025, scored once" in html
    assert "2026 = exploratory, veto-only" in html
    assert "showing ${filtered.length} of ${rows.length} rows" in html
    assert "Main WR %" in html
    assert "Main PF" in html
    assert "2026 WR %" in html
    assert "2026 PF" in html
    assert 'expansionNum("expansionWrMainMin", "Main WR %"' in html
    assert 'expansionNum("expansionPfMainMin", "Main PF"' in html
    assert 'expansionNum("expansionWr2026Min", "2026 WR %"' in html
    assert 'expansionNum("expansionPf2026Min", "2026 PF"' in html
    assert ">Reset</button>" in html
    assert "function sortExpansion(" in html
    assert "winrate_main" in html
    assert "Nulls stay last" in html
    assert "A set minimum drops nulls" in html
    for gone in (
        "expansionBatch",
        "expansionRule",
        "expansionSide",
        "expansionToken",
        'expansionSelect("expansionVerdict"',
        "expansionPfMainMax",
        "expansionPfHoldMin",
        "expansionWrHoldMin",
        "expansionNMainMin",
        "function expansionSelect(",
    ):
        assert gone not in html
