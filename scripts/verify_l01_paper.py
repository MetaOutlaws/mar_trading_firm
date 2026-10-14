"""Verify L01 evidence inside the existing paper container. Never starts a worker.

Requires a current worker restart, a live paper process, its complete registry
census and a subsequent hourly gate decision. A separate fresh scan cannot
satisfy these checks. Full fill-path parity and profitability are not implied.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.settings import PROJECT_ROOT
from core.execution.f111_paper import row_recorded_time
from core.strategy.f111_config import TELEMETRY_PATH, assert_f111_paper_only, load_f111_config, scan_enabled
from core.strategy.l01_context import ContextStore
from core.data.bybit_linear_instruments import fetch_registry
from scripts.enable_l01_paper import preflight
from scripts.verify_f111_paper_scan import _read_jsonl


def worker_evidence(rows, config, digest, code_hash, now, process_check) -> dict:
    failures = []
    starts = [(i, row) for i, row in enumerate(rows) if row.get("deploy_marker") == "restart"]
    if not starts:
        return {"verified": False, "failures": ["no_worker_restart"]}
    index, start = starts[-1]
    run_id = start.get("run_id")
    if (not run_id or start.get("configuration_sha256") != digest
            or start.get("strategy_version") != config["strategy_version"]
            or start.get("runtime_code_sha256") != code_hash):
        failures.append("worker_restart_does_not_match_current_code_and_config")
    if not process_check(start):
        failures.append("paper_process_not_verified")
    current = [r for r in rows[index:] if r.get("run_id") == run_id
               and r.get("configuration_sha256") == digest
               and r.get("strategy_version") == config["strategy_version"]]
    recent = [r for r in current if (stamp := row_recorded_time(r)) is not None
              and 0 <= (now-stamp).total_seconds() <= 4500]
    census = {(r.get("symbol"), r.get("side")): r for r in recent if r.get("record_kind") == "registry"}
    expected = {(s, side) for s in config["universe"] for side in config["sides"]}
    if set(census) != expected:
        failures.append("current_worker_192_sleeve_census_missing_or_stale")
    if any(str(r.get("rejection_reason", "")).startswith("instruments-info unreachable") for r in census.values()):
        failures.append("worker_registry_transport_failure")
    gates = [r for r in recent if r.get("source_signal_id") and r.get("record_kind") != "registry"]
    if not gates:
        failures.append("no_current_worker_hourly_decision")
    return {"verified": not failures, "failures": failures, "worker_run_id": run_id,
            "worker_sleeves": len(census), "worker_gate_rows": len(gates),
            "zero_fills_is_valid": True}


def paper_process_matches(start):
    try:
        pid = int(start["process_id"])
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        return stat == start.get("process_start_ticks") and any(
            item.endswith(b"/run_paper_trading.py") for item in command)
    except (KeyError, ValueError, OSError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    assert_f111_paper_only()
    config, digest = load_f111_config()
    if config.get("research_case") != "L01" or not scan_enabled(config):
        print(json.dumps({"activation_verified": False, "reason": "L01_entries_not_enabled"}))
        return 2
    now = datetime.now(timezone.utc)
    code_hash = hashlib.sha256((PROJECT_ROOT / "core/execution/f111_paper.py").read_bytes()).hexdigest()
    evidence = worker_evidence(_read_jsonl(TELEMETRY_PATH), config, digest, code_hash, now, paper_process_matches)
    context = preflight(config, ContextStore(), fetch_registry(config["universe"]), now)
    from api.desk_status import deployed_git_sha
    deployed = deployed_git_sha()
    commit_matches = deployed.get("sha") == args.expected_commit and len(args.expected_commit) == 40
    report = {"paper_only": True, "activation_verified": evidence["verified"] and context["ready"] and commit_matches,
              "configuration_sha256": digest, "deployed_commit": deployed, "commit_matches": commit_matches,
              "worker": evidence, "context": context, "saved_path_parity": "UNVERIFIED"}
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
    return 0 if report["activation_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
