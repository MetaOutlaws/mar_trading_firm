"""Prepare/refresh L01 minute-derived EMA context. No orders or trading worker.

Run before enabling L01, then at least every four hours. Existing minute caches
are reused; only missing context is fetched. This is indicator preparation for
forward paper operation, not a 2026 strategy backtest or performance study.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.data.bybit_linear_instruments import AVAILABLE, fetch_registry
from core.data.ohlcv import BybitOHLCV
from core.strategy.f111_config import L01_CONFIG_PATH, assert_f111_paper_only, load_f111_config
from core.strategy.l01_context import ContextStore, decision


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", action="append", help="Subset for data preparation only.")
    args = parser.parse_args(argv)
    assert_f111_paper_only()
    config, _ = load_f111_config(L01_CONFIG_PATH)
    symbols = args.symbol or config["universe"]
    if not set(symbols).issubset(config["universe"]):
        parser.error("symbols must belong to the approved universe")
    registry = fetch_registry(symbols)
    now = datetime.now(timezone.utc)
    store, data = ContextStore(), BybitOHLCV()
    failed = 0
    for instrument in registry:
        if instrument.availability != AVAILABLE:
            print(json.dumps({"symbol": instrument.symbol, "status": "unavailable", "reason": instrument.reason}), flush=True)
            if str(instrument.reason).startswith("instruments-info unreachable"):
                failed += 1
            continue
        try:
            state = store.refresh(instrument.symbol, now, data, max_catchup_hours=None)
            _passed, reason, info = decision("LONG", state, now)
            ready = reason in {"", "l01_long_trend_gate"}
            failed += int(not ready)
            print(json.dumps({"symbol": instrument.symbol, "ready": ready, "reason": reason, **info}), flush=True)
        except Exception as exc:
            failed += 1
            print(json.dumps({"symbol": instrument.symbol, "ready": False, "error": str(exc)}), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
