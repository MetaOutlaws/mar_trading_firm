"""Verify context and opt the existing paper worker into L01 after restart.

Default dry run. --apply atomically records the exact approved config hash.
Does not launch/restart a worker, change cash/risk, retire other sleeves, close
positions, or claim activation. Use the L01 runbook for the full deployment.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.data.bybit_linear_instruments import AVAILABLE, fetch_registry
from core.strategy.f111_config import L01_CONFIG_PATH, L01_ENABLE_PATH, assert_f111_paper_only, load_f111_config
from core.strategy.l01_context import ContextStore, decision


def preflight(config, store, registry, now) -> dict:
    by_symbol = {r.symbol: r for r in registry}
    failures, available, unavailable = [], [], []
    for symbol in config["universe"]:
        instrument = by_symbol.get(symbol)
        if instrument is None or str(instrument.reason).startswith("instruments-info unreachable"):
            failures.append({"symbol": symbol, "reason": "registry_not_verified"})
        elif instrument.availability != AVAILABLE:
            unavailable.append({"symbol": symbol, "reason": instrument.reason})
        else:
            try:
                _passed, reason, _info = decision("LONG", store.read(symbol), now)
            except Exception as exc:
                reason = str(exc)
            if reason not in {"", "l01_long_trend_gate"}:
                failures.append({"symbol": symbol, "reason": reason})
            else:
                available.append(symbol)
    if not available:
        failures.append({"reason": "no_available_context_ready_symbols"})
    return {"ready": not failures, "available_context_ready": len(available),
            "unavailable": unavailable, "failures": failures, "expected_sleeves": 192}


def write_marker(path: Path, digest: str, now) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"paper_only": True, "configuration_sha256": digest,
               "approved_case": "L01", "recorded_at": now.isoformat(), "activation_verified": False}
    if path.exists():
        old = json.loads(path.read_text())
        if old.get("configuration_sha256") != digest:
            raise RuntimeError("Different activation already exists; inspect before replacing")
        return
    fd, temporary = tempfile.mkstemp(prefix=".l01-enable-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=2); handle.write("\n")
            handle.flush(); os.fsync(handle.fileno())
        # No overwrite of a concurrently created marker.
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    assert_f111_paper_only()
    config, digest = load_f111_config(L01_CONFIG_PATH)
    now = datetime.now(timezone.utc)
    report = preflight(config, ContextStore(), fetch_registry(config["universe"]), now)
    report.update(configuration_sha256=digest, paper_only=True, worker_started=False,
                  activation_verified=False, status="dry_run")
    if not report["ready"]:
        print(json.dumps(report, indent=2)); return 2
    if args.apply:
        write_marker(L01_ENABLE_PATH, digest, now)
        report["status"] = "configured_restart_and_runtime_verification_required"
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
