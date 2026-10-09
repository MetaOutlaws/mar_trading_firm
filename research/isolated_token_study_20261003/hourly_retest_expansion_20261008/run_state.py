"""Atomic run ownership for the independent H-RETEST-EXPANSION-01 execution."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


EXPERIMENT_ID = "H-RETEST-EXPANSION-01"
OWNER = "codex_independent"
TERMINAL = {"complete", "failed", "blocked"}
ACTIVE = {"claimed", "preflight", "frozen", "running", "verifying"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_record(path: Path) -> dict | None:
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("run record must be an object")
    return value


def claim(path: Path, dataset_manifest_sha256: str, runner_sha256: str) -> dict:
    if len(dataset_manifest_sha256) != 64 or len(runner_sha256) != 64:
        raise ValueError("full SHA256 digests are required")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "status": "claimed",
        "claimed_at": now(),
        "dataset_manifest_sha256": dataset_manifest_sha256,
        "runner_sha256": runner_sha256,
        "scores_2026": False,
        "production_changes": False,
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        existing = read_record(path)
        status = existing.get("status") if existing else "unknown"
        raise RuntimeError(f"independent run already recorded with status={status}") from exc
    with os.fdopen(descriptor, "w") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    return record


def transition(path: Path, expected: str, status: str, **evidence: object) -> dict:
    if status not in ACTIVE | TERMINAL:
        raise ValueError(f"unsupported run status: {status}")
    record = read_record(path)
    if record is None:
        raise FileNotFoundError(path)
    if record.get("experiment_id") != EXPERIMENT_ID or record.get("owner") != OWNER:
        raise ValueError("run record identity mismatch")
    if record.get("status") != expected:
        raise RuntimeError(f"expected status={expected}, found {record.get('status')}")
    record.update(evidence)
    record["status"] = status
    record["updated_at"] = now()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True))
    temporary.replace(path)
    return record
