"""Merge six owner-approved PAPER overrides without replacing the cloud book.

Run inside the actual paper container from /app. Default is read-only.
--apply is the already-authorized activation. --verify checks a later persisted
cycle; it neither invokes a trading cycle nor creates orders itself.
"""
import argparse
import errno
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
NAME = "hourly_compression_v1"


def desired_records():
    return {f"{NAME}:{symbol}:{side}:1h": {
        "strategy": NAME, "timeframe": "1h", "approved": False,
        "paper_override": True, "activation_mode": "unrestricted",
        "blocked_regimes": [], "regime_activation_filter": [],
        "params": {"stop_loss_pct": .02, "take_profit_pct": .025, "max_holding_bars": 0},
        "owner_approved_at": "2026-10-07", "owner_approval_scope": "BTC/ETH/SOL hourly paper pilot, both directions",
        "research_qualification": "exploratory; positive baseline retained; independent confirmation pending",
        "research_baseline": "family_followups_20261007/compression_hourly/SL2_TP2.5"
    } for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT") for side in ("LONG", "SHORT")}


def merged_book(current):
    if not isinstance(current, dict):
        raise ValueError("approval book must be an object")
    wanted = desired_records()
    for key, value in wanted.items():
        if key in current and current[key] != value:
            raise ValueError(f"Existing different record: {key}; refusing to overwrite")
    return {**current, **wanted}


def verify_plan():
    from config.universe import get_universe
    from core.execution.engine import build_plan
    get_universe.cache_clear()
    expected = {(s, side, "1h") for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT") for side in ("LONG", "SHORT")}
    plan = build_plan(require_approval=False)
    rows = [e for e in plan.entries if e.strategy.name == NAME]
    actual = {(e.symbol, e.side.value, e.timeframe) for e in rows}
    if actual != expected or len(rows) != 6:
        raise RuntimeError(f"Missing paper plan rows: {expected-actual}")
    live = build_plan(require_approval=True)
    if any(e.strategy.name == NAME for e in live.entries):
        raise RuntimeError("paper pilot leaked into approved-only plan")
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    from config.settings import TradingMode, get_settings
    from config.universe import APPROVALS_PATH
    from core.strategy.registry import get_strategy
    if get_settings().trading_mode is not TradingMode.PAPER:
        raise RuntimeError("Activation and verification require the PAPER container")
    get_strategy(NAME)()
    path = APPROVALS_PATH.resolve(strict=True)  # retain persistent-state symlinks
    before = path.read_bytes()
    current = json.loads(before)
    updated = merged_book(current)
    state = path.parent / "hourly_compression_v1_activation.json"
    if args.verify:
        from core.execution.engine import load_last_cycle
        if any(current.get(k) != v for k, v in desired_records().items()):
            raise RuntimeError("six approved paper records are not installed")
        verify_plan()
        activation = json.loads(state.read_text())
        cycle = load_last_cycle() or {}
        started = datetime.fromisoformat(str(cycle.get("started_at", "")))
        if started <= datetime.fromisoformat(activation["activated_at"]):
            raise RuntimeError("Await a completed cycle after activation")
        if (datetime.now(timezone.utc)-started).total_seconds() > 1800:
            raise RuntimeError("Latest cycle is older than 30 minutes")
        expected = set(desired_records())
        scanned = {f'{r.get("strategy")}:{r.get("symbol")}:{r.get("side")}:{r.get("timeframe")}' for r in cycle.get("plan", [])}
        if not expected.issubset(scanned) or cycle.get("entries_blocked") or cycle.get("halted") or cycle.get("errors"):
            raise RuntimeError("Cycle plan/health does not verify active scanning")
        if cycle.get("symbols_scanned", 0) < len(cycle.get("plan", [])):
            raise RuntimeError("Cycle did not visit every planned sleeve")
        print(json.dumps({"status": "scanning_verified", "cycle_started_at": started.isoformat(), "sleeves": sorted(expected), "errors": cycle.get("errors", [])}, indent=2))
        return
    if not args.apply:
        print(json.dumps({"status": "dry_run", "approval_path": str(path), "existing_records_preserved": len(current), "additions": sorted(set(updated)-set(current)), "records": desired_records()}, indent=2))
        return
    if before != path.read_bytes():
        raise RuntimeError("approval book changed during preflight; retry")
    now = datetime.now(timezone.utc)
    backup = path.with_name(path.name + ".before-hourly-" + now.strftime("%Y%m%dT%H%M%S%fZ"))
    backup.write_bytes(before)
    if updated != current:
        fd, temporary = tempfile.mkstemp(prefix=".hourly-", dir=path.parent)
        try:
            with os.fdopen(fd, "w") as handle:
                json.dump(updated, handle, indent=2)
                handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
            os.chmod(temporary, path.stat().st_mode & 0o777)
            if before != path.read_bytes():
                raise RuntimeError("approval book changed before write; retry")
            try:
                os.replace(temporary, path)
            except OSError as exc:
                if exc.errno == errno.EBUSY:
                    raise RuntimeError(
                        "Approval file is a Docker mount point. Approval bytes were not changed. "
                        "Use the host-side repair installer; do not truncate this mounted file."
                    ) from exc
                raise
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    if json.loads(path.read_bytes()) != updated:
        raise RuntimeError("Approval readback differs; inspect the backup and current book")
    # If this fails, retain the backup and report failure; never claim running.
    count = verify_plan()
    record = {"status": "installed_awaiting_cycle", "activated_at": now.isoformat(), "sleeves": count,
              "backup": str(backup), "approval_before_sha256": hashlib.sha256(before).hexdigest(),
              "approval_after_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    state.write_text(json.dumps(record, indent=2))
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
