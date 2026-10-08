"""Synthetic, outcome-free tests for the expansion data and run-state gates."""
import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd

import data_gate as gate
from data_gate import audit_symbol, safe_relative, validate_membership, verify_collector_manifest
from run_state import claim, read_record, transition


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_control(root: Path) -> dict:
    catalog = {"instruments": [{"symbol": "AAAUSDT"}, {"symbol": "BTCUSDT"}, {"symbol": "ETHUSDT"}, {"symbol": "SOLUSDT"}]}
    membership = [{"month": "2025-01", "symbol": "AAAUSDT", "rank": 1, "selected": True}]
    (root / "catalog.json").write_text(json.dumps(catalog))
    (root / "membership.json").write_text(json.dumps(membership))
    freeze = {
        "membership_sha256": digest(root / "membership.json"),
        "catalog_sha256": digest(root / "catalog.json"),
        "historical_universe_complete": False,
        "classification_history_verified": False,
        "selected_union": ["AAAUSDT"],
    }
    (root / "universe_freeze.json").write_text(json.dumps(freeze))
    (root / "STATUS.json").write_text(json.dumps({"status": "acquired_needs_audit", "scores_2026": False}))
    names = ["catalog.json", "membership.json", "universe_freeze.json"]
    (root / "FILES_SHA256.json").write_text(json.dumps({name: digest(root / name) for name in names}))
    return freeze


def test_safe_manifest_paths() -> None:
    assert safe_relative("minutes/AAAUSDT/2025-01.csv.gz").as_posix() == "minutes/AAAUSDT/2025-01.csv.gz"
    for bad in ["", "/absolute", "../escape", "minutes/../../escape"]:
        try:
            safe_relative(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(bad)


def test_control_hash_and_membership_gate() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        freeze = make_control(root)
        verified, observed = verify_collector_manifest(root)
        assert len(verified) == 3 and observed == freeze
        rows, symbols = validate_membership(root, freeze)
        assert len(rows) == 1 and symbols == ["AAAUSDT"]
        (root / "membership.json").write_text("[]")
        try:
            verify_collector_manifest(root)
        except ValueError as exc:
            assert "hash mismatch" in str(exc) or "freeze mismatch" in str(exc)
        else:
            raise AssertionError("changed membership passed")


def test_reserved_2026_and_reference_membership_rejected() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        freeze = make_control(root)
        bad = [{"month": "2026-01", "symbol": "BTCUSDT", "rank": 1}]
        (root / "membership.json").write_text(json.dumps(bad))
        freeze["selected_union"] = ["BTCUSDT"]
        try:
            validate_membership(root, freeze)
        except ValueError:
            pass
        else:
            raise AssertionError("reserved/reference membership passed")


def test_atomic_independent_run_claim() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "RUN_RECORD.json"
        first = claim(path, "a" * 64, "b" * 64)
        assert first["status"] == "claimed" and read_record(path)["owner"] == "codex_independent"
        try:
            claim(path, "a" * 64, "b" * 64)
        except RuntimeError as exc:
            assert "already recorded" in str(exc)
        else:
            raise AssertionError("duplicate run claim passed")
        transition(path, "claimed", "preflight", reference_parity=False)
        final = transition(path, "preflight", "blocked", reason="synthetic")
        assert final["status"] == "blocked" and final["scores_2026"] is False


def test_execution_grid_and_funding_audit() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        out = root / "out"
        (source / "minutes" / "AAAUSDT").mkdir(parents=True)
        (source / "funding").mkdir()
        (out / "funding").mkdir(parents=True)
        old_begin, old_end = gate.BEGIN, gate.END
        gate.BEGIN = pd.Timestamp("2025-01-01 00:00", tz="UTC")
        gate.END = pd.Timestamp("2025-01-01 00:03", tz="UTC")
        try:
            stamps = [int(value.timestamp() * 1000) for value in pd.date_range(gate.BEGIN, periods=3, freq="min")]
            candles = pd.DataFrame(
                {
                    "timestamp_ms": stamps,
                    "open": [100.0, 101.0, 102.0],
                    "high": [101.0, 102.0, 103.0],
                    "low": [99.0, 100.0, 101.0],
                    "close": [100.5, 101.5, 102.5],
                    "volume": [1.0, 1.0, 1.0],
                    "turnover": [100.0, 101.0, 102.0],
                }
            )
            candles.to_csv(source / "minutes" / "AAAUSDT" / "2025-01.csv.gz", index=False, compression="gzip")
            funding = pd.DataFrame(
                {"timestamp_ms": [stamps[0], stamps[-1]], "funding_rate": [0.0001, -0.0001]}
            )
            funding.to_csv(source / "funding" / "AAAUSDT.csv.gz", index=False, compression="gzip")
            coverage, hashes = audit_symbol(source, out, "AAAUSDT", {"launchTime": "0", "deliveryTime": "0"})
            assert coverage["candles"] == 3 and coverage["scores_2026"] is False
            assert sorted(hashes) == ["AAAUSDT_1m.parquet", "funding/AAAUSDT_funding.parquet"]
        finally:
            gate.BEGIN, gate.END = old_begin, old_end


if __name__ == "__main__":
    tests = [
        test_safe_manifest_paths,
        test_control_hash_and_membership_gate,
        test_reserved_2026_and_reference_membership_rejected,
        test_atomic_independent_run_claim,
        test_execution_grid_and_funding_audit,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
