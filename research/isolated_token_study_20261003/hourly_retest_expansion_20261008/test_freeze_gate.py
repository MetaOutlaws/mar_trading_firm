"""Synthetic outcome-blind tests for the immutable freeze gate."""
import hashlib
import json
import tempfile
from pathlib import Path

import pandas as pd

import freeze_gate as gate


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root: Path) -> tuple[Path, Path, Path]:
    cache = root / "cache"
    signals = root / "signals"
    cache.mkdir()
    signals.mkdir()
    (cache / "membership.json").write_text("[]")
    (cache / "catalog.json").write_text("{}")
    output_hashes = {
        name: digest(cache / name) for name in ["membership.json", "catalog.json"]
    }
    (cache / "audit.json").write_text(
        json.dumps(
            {
                "status": "usable_provisional",
                "scores_2026": False,
                "outcomes_scored": False,
                "new_token_symbols": [],
                "output_hashes": output_hashes,
            }
        )
    )
    pd.DataFrame({"signal_time": pd.DatetimeIndex([], tz="UTC")}).to_parquet(
        signals / "frozen_signals.parquet", index=False
    )
    pd.DataFrame({"signal_time": pd.DatetimeIndex([], tz="UTC")}).to_parquet(
        signals / "signal_contexts.parquet", index=False
    )
    (signals / "VERIFICATION.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "symbols": [],
                "selected_signals": 0,
                "scores_2026": False,
                "trade_outcomes_scored": False,
            }
        )
    )
    runner = root / "runner.py"
    runner.write_text("# frozen synthetic runner\n")
    return cache, signals, runner


def test_hash_and_closed_outcome_gate() -> None:
    with tempfile.TemporaryDirectory() as directory:
        cache, signals, _ = fixture(Path(directory))
        _, hashes = gate.audited_input_hashes(cache)
        assert set(hashes) == {"audit.json", "catalog.json", "membership.json"}
        (cache / "catalog.json").write_text('{"changed": true}')
        try:
            gate.audited_input_hashes(cache)
        except ValueError as exc:
            assert "hash mismatch" in str(exc)
        else:
            raise AssertionError("changed audited input passed")
        audit = json.loads((cache / "audit.json").read_text())
        audit["scores_2026"] = True
        (cache / "audit.json").write_text(json.dumps(audit))
        try:
            gate.audited_input_hashes(cache)
        except ValueError as exc:
            assert "closed outcome" in str(exc)
        else:
            raise AssertionError("opened 2026 audit passed")


def test_signal_inventory_boundary() -> None:
    with tempfile.TemporaryDirectory() as directory:
        _, signals, _ = fixture(Path(directory))
        verification, hashes = gate.signal_inventory_hashes(signals)
        assert verification["selected_signals"] == 0 and len(hashes) == 3
        pd.DataFrame({"signal_time": [pd.Timestamp("2026-01-01", tz="UTC")]}).to_parquet(
            signals / "frozen_signals.parquet", index=False
        )
        verification["selected_signals"] = 1
        (signals / "VERIFICATION.json").write_text(json.dumps(verification))
        try:
            gate.signal_inventory_hashes(signals)
        except ValueError as exc:
            assert "reserved 2026" in str(exc)
        else:
            raise AssertionError("reserved 2026 signal passed")


def test_source_hash_change() -> None:
    with tempfile.TemporaryDirectory() as directory:
        _, _, runner = fixture(Path(directory))
        first = gate.source_hashes(runner)
        runner.write_text("# changed synthetic runner\n")
        second = gate.source_hashes(runner)
        assert first != second


def test_freeze_roundtrip_and_runner_mutation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        cache, signals, runner = fixture(root)
        freeze = root / "freeze.json"
        built = gate.build_freeze(cache, signals, runner, freeze, "a" * 40)
        assert built["status"] == "frozen" and built["scores_2026"] is False
        assert gate.verify_freeze(cache, signals, runner, freeze) == built
        runner.write_text("# runner changed after freeze\n")
        try:
            gate.verify_freeze(cache, signals, runner, freeze)
        except ValueError as exc:
            assert "sources" in str(exc) or "runner hash" in str(exc)
        else:
            raise AssertionError("post-freeze runner mutation passed")


if __name__ == "__main__":
    tests = [
        test_hash_and_closed_outcome_gate,
        test_signal_inventory_boundary,
        test_source_hash_change,
        test_freeze_roundtrip_and_runner_mutation,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
