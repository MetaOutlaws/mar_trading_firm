"""Create and verify the immutable pre-run freeze for H-RETEST-EXPANSION-01."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa


HERE = Path(__file__).resolve().parent
EXPERIMENT_ID = "H-RETEST-EXPANSION-01"
REQUIRED_SOURCE = [
    "PROTOCOL.md",
    "PRIOR_USE_AUDIT.md",
    "adapter.py",
    "data_gate.py",
    "run_state.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
    temporary.replace(path)


def _safe_cache_file(cache: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe audited-cache path: {name!r}")
    path = cache / relative
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or unsafe audited-cache file: {name}")
    return path


def audited_input_hashes(cache: Path) -> tuple[dict, dict[str, str]]:
    audit = read_json(cache / "audit.json")
    if audit.get("status") != "usable_provisional":
        raise ValueError("audited cache has not passed its execution coverage gate")
    if audit.get("scores_2026") is not False or audit.get("outcomes_scored") is not False:
        raise ValueError("audited cache does not preserve the closed outcome flags")
    output_hashes = audit.get("output_hashes")
    if not isinstance(output_hashes, dict) or not output_hashes:
        raise ValueError("audit.json has no frozen output hashes")
    verified = {}
    for name, expected in sorted(output_hashes.items()):
        path = _safe_cache_file(cache, name)
        actual = sha256(path)
        if actual != expected:
            raise ValueError(f"audited-cache hash mismatch: {name}")
        verified[name] = actual
    verified["audit.json"] = sha256(cache / "audit.json")
    return audit, verified


def signal_inventory_hashes(signal_dir: Path) -> tuple[dict, dict[str, str]]:
    verification = read_json(signal_dir / "VERIFICATION.json")
    if verification.get("status") != "pass":
        raise ValueError("outcome-blind signal inventory has not passed")
    if verification.get("scores_2026") is not False:
        raise ValueError("signal inventory opened the reserved 2026 boundary")
    if verification.get("trade_outcomes_scored") is not False:
        raise ValueError("signal inventory is not outcome blind")
    names = ["VERIFICATION.json", "signal_contexts.parquet", "frozen_signals.parquet"]
    hashes = {}
    for name in names:
        path = signal_dir / name
        if not path.is_file():
            raise ValueError(f"signal inventory file missing: {name}")
        hashes[name] = sha256(path)
    signals = pd.read_parquet(signal_dir / "frozen_signals.parquet", columns=["signal_time"])
    times = pd.to_datetime(signals.signal_time, utc=True)
    if len(times) and times.max() >= pd.Timestamp("2026-01-01", tz="UTC"):
        raise ValueError("reserved 2026 signal found in inventory")
    if verification.get("selected_signals") != len(signals):
        raise ValueError("signal count differs from VERIFICATION.json")
    return verification, hashes


def source_hashes(runner: Path) -> dict[str, str]:
    paths = [HERE / name for name in REQUIRED_SOURCE] + [runner.resolve()]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise ValueError(f"freeze source missing: {missing}")
    result = {}
    for path in paths:
        key = path.name if path.parent == HERE else f"runner/{path.name}"
        if key in result:
            raise ValueError(f"ambiguous freeze source name: {key}")
        result[key] = sha256(path)
    return result


def build_freeze(
    cache: Path,
    signal_dir: Path,
    runner: Path,
    output: Path,
    protocol_commit: str,
) -> dict:
    if len(protocol_commit) != 40:
        raise ValueError("a full public protocol/source commit SHA is required")
    preparation = read_json(HERE / "PREPARATION_VERIFICATION.json")
    parity_path = HERE / "reference_parity_v1" / "VERIFICATION.json"
    parity = read_json(parity_path)
    if preparation.get("status") != "pass" or not preparation.get("outcome_blind"):
        raise ValueError("preparation verification is not outcome blind and passing")
    if parity.get("status") != "pass" or parity.get("reference_signals") != 69:
        raise ValueError("reference parity is not passing")
    if parity.get("ledger_rows") != 420 or parity.get("new_token_outcomes_scored") is not False:
        raise ValueError("reference ledger parity or outcome flag is invalid")
    audit, input_hashes = audited_input_hashes(cache)
    signal_verification, signal_hashes = signal_inventory_hashes(signal_dir)
    if sorted(audit.get("new_token_symbols", [])) != sorted(signal_verification.get("symbols", [])):
        raise ValueError("audited universe differs from the outcome-blind signal inventory")
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(output)
    value = {
        "experiment_id": EXPERIMENT_ID,
        "status": "frozen",
        "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "protocol_commit": protocol_commit,
        "sources": source_hashes(runner),
        "audited_inputs": input_hashes,
        "signal_inventory": signal_hashes,
        "reference_parity_sha256": sha256(parity_path),
        "preparation_verification_sha256": sha256(HERE / "PREPARATION_VERIFICATION.json"),
        "dataset_manifest_sha256": sha256(cache / "audit.json"),
        "runner_sha256": sha256(runner),
        "new_token_symbols": sorted(audit["new_token_symbols"]),
        "selected_signals": signal_verification["selected_signals"],
        "periods": {
            "historical": ["2022-01-01", "2025-01-01"],
            "evaluation": ["2025-01-01", "2026-01-01"],
        },
        "arms": ["immediate", "retest"],
        "exit_models": ["intrabar", "poll_1m"],
        "slippage_per_side": [0.001, 0.002],
        "fee_per_side": 0.00055,
        "stop": 0.02,
        "target": 0.025,
        "retest_deadline_minutes": 60,
        "holding_timeout": None,
        "scores_2026": False,
        "prior_grok_outcome_exposure": "disclosed_possible_but_outputs_not_accessed_or_used",
        "production_changes": False,
        "packages": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
        },
    }
    write_json(output, value)
    verify_freeze(cache, signal_dir, runner, output)
    return value


def verify_freeze(cache: Path, signal_dir: Path, runner: Path, freeze_path: Path) -> dict:
    freeze = read_json(freeze_path)
    if freeze.get("experiment_id") != EXPERIMENT_ID or freeze.get("status") != "frozen":
        raise ValueError("freeze identity/status mismatch")
    if freeze.get("scores_2026") is not False or freeze.get("production_changes") is not False:
        raise ValueError("freeze safety flags changed")
    _, input_hashes = audited_input_hashes(cache)
    _, signal_hashes = signal_inventory_hashes(signal_dir)
    checks = {
        "sources": source_hashes(runner),
        "audited_inputs": input_hashes,
        "signal_inventory": signal_hashes,
    }
    for group, observed in checks.items():
        if freeze.get(group) != observed:
            raise ValueError(f"freeze hash group mismatch: {group}")
    parity = HERE / "reference_parity_v1" / "VERIFICATION.json"
    if freeze.get("reference_parity_sha256") != sha256(parity):
        raise ValueError("reference parity hash mismatch")
    if freeze.get("preparation_verification_sha256") != sha256(
        HERE / "PREPARATION_VERIFICATION.json"
    ):
        raise ValueError("preparation verification hash mismatch")
    if freeze.get("dataset_manifest_sha256") != sha256(cache / "audit.json"):
        raise ValueError("dataset manifest hash mismatch")
    if freeze.get("runner_sha256") != sha256(runner):
        raise ValueError("runner hash mismatch")
    return freeze


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "verify"])
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--signal-dir", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--protocol-commit")
    args = parser.parse_args()
    if args.command == "build":
        if not args.protocol_commit:
            parser.error("--protocol-commit is required for build")
        result = build_freeze(
            args.cache, args.signal_dir, args.runner, args.freeze, args.protocol_commit
        )
    else:
        result = verify_freeze(args.cache, args.signal_dir, args.runner, args.freeze)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
