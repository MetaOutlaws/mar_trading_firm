"""
Continuous paper trading: the 60-day forward-test clock.

Runs the trading engine on a fixed cycle, recording every fill so measured
slippage can be compared against the modelled 10 bps -- one of the plan's
go-live gates.

Important: paper mode deliberately trades *candidate* strategies that have not
passed validation. That is not a safety hole, it is the point. Forward-testing
an unproven idea in simulation is how evidence gets gathered; requiring
validation first would be circular. Live mode is the opposite: it trades only
research-approved pairs, and refuses to start with none.

Usage:
    python scripts/run_paper_trading.py                    # continuous
    python scripts/run_paper_trading.py --cycles 3         # a few cycles then stop
    python scripts/run_paper_trading.py --interval 60      # faster cycles for testing
    python scripts/run_paper_trading.py --status           # report progress and exit
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime, timezone

from config.logging_setup import setup_logging
from config.settings import TradingMode, get_settings
from core.db import init_db, session_scope
from core.execution.engine import build_engine
from core.ledger.store import Ledger

logger = logging.getLogger(__name__)

#: 15 minutes, matching the strategy timeframe. Scanning more often than the
#: candle interval cannot produce new information.
DEFAULT_INTERVAL_SECONDS = 900

_shutdown_requested = False


def _handle_shutdown(signum, _frame) -> None:  # noqa: ANN001
    """Finish the current cycle, then exit cleanly."""
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning("Signal %s received; finishing the current cycle then stopping.", signum)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycles", type=int, default=0, help="Stop after N cycles (0 = forever).")
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL_SECONDS, help="Seconds between cycles."
    )
    parser.add_argument("--equity", type=float, default=10_000.0, help="Starting paper equity.")
    parser.add_argument("--symbols", nargs="*", help="Override the candidate symbols.")
    parser.add_argument("--status", action="store_true", help="Print progress and exit.")
    return parser.parse_args()


def print_status(ledger: Ledger) -> None:
    """Report forward-test progress against the go-live gates."""
    performance = ledger.performance()

    print("\n" + "=" * 70)
    print(f"PAPER TRADING STATUS ({ledger.mode})")
    print("=" * 70)

    if not performance["trades"]:
        print("No completed trades yet.")
    else:
        for key, value in performance.items():
            print(f"  {key:<24}: {value}")

    from core.ledger.models import EquitySnapshot
    from sqlalchemy import func, select

    with session_scope() as session:
        first = session.scalar(
            select(func.min(EquitySnapshot.recorded_at)).where(
                EquitySnapshot.mode == ledger.mode
            )
        )
        latest = session.scalar(
            select(func.max(EquitySnapshot.equity)).where(EquitySnapshot.mode == ledger.mode)
        )

    if first:
        days = (datetime.now(timezone.utc) - first).days
        print(f"\n  Forward test running for {days} of the 60 days required.")
        print(f"  {'GATE MET' if days >= 60 else f'{60 - days} days remaining'}")
    else:
        print("\n  Forward test has not started (no equity snapshots recorded).")

    if latest:
        print(f"  Peak equity: {latest:.2f}")

    measured = performance.get("measured_slippage_bps")
    if measured is not None:
        print(f"\n  Measured slippage: {measured} bps versus 10 bps modelled")
        print(f"  {'within tolerance' if abs(measured) <= 20 else 'EXCEEDS the model'}")
    print("=" * 70 + "\n")


def main() -> int:
    args = parse_args()
    setup_logging("paper_trading")
    settings = get_settings()

    init_db()

    if args.status:
        print_status(Ledger(mode=settings.trading_mode.value, starting_equity=args.equity))
        return 0

    if settings.trading_mode is TradingMode.LIVE:
        logger.critical(
            "TRADING_MODE=live. This script is for paper trading. "
            "Use scripts/run_live_trading.py deliberately instead."
        )
        return 1

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    logger.info("=" * 70)
    logger.info("PAPER TRADING - mode=%s, interval=%ds", settings.trading_mode.value, args.interval)
    logger.info("=" * 70)

    engine = build_engine(starting_equity=args.equity, candidates=args.symbols)

    if not engine.plan.entries:
        logger.error("Nothing to trade: the plan is empty. Check config/asset_params.json.")
        return 1

    logger.info("Trading plan (%d pairs):", len(engine.plan.entries))
    for entry in engine.plan.entries:
        logger.info(
            "  %-14s %-6s %-5s %s",
            entry.symbol, entry.side.value, entry.timeframe, entry.strategy.name,
        )

    cycle = 0
    try:
        while not _shutdown_requested:
            cycle += 1
            logger.info("")
            logger.info("--- cycle %d at %s ---", cycle, datetime.now(timezone.utc).isoformat())

            try:
                report = engine.run_cycle()
                logger.info("%s", report)
                if report.halted:
                    logger.critical(
                        "Trading halted: %s. Investigate, then reset the kill switch "
                        "with scripts/reset_killswitch.py.",
                        report.halt_reason,
                    )
                    break
            except Exception:
                logger.exception("Cycle %d failed; continuing to the next cycle.", cycle)

            if args.cycles and cycle >= args.cycles:
                logger.info("Reached the requested %d cycles; stopping.", args.cycles)
                break

            # Sleep in short slices so a shutdown signal is honoured promptly
            # rather than after a full 15-minute interval.
            slept = 0
            while slept < args.interval and not _shutdown_requested:
                time.sleep(min(5, args.interval - slept))
                slept += 5

    finally:
        engine.close()
        print_status(engine.ledger)
        logger.info("Paper trading stopped after %d cycles.", cycle)

    return 0


if __name__ == "__main__":
    sys.exit(main())
