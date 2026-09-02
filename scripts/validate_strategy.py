"""
Run the validation pipeline and write trading approvals.

This is the gate. A strategy that does not pass here cannot trade, in paper or
live mode, because `config/approved_strategies.json` is the only source of
trading rights.

Usage:
    # Quick look at the majors, longs only
    python scripts/validate_strategy.py --symbols BTCUSDT ETHUSDT --side LONG

    # Full run across every configured candidate, both sides
    python scripts/validate_strategy.py --all

    # Baseline-only mode: no optimisation, just the legacy parameters per regime
    python scripts/validate_strategy.py --symbols BTCUSDT --baseline-only
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone

from config.logging_setup import setup_logging
from config.pipeline import APPROVED_RESEARCH_SYMBOLS
from config.settings import get_settings
from config.universe import get_universe
from core.data.funding import FundingRates
from core.strategy.base import SignalSide
from research.costs import DEFAULT_COSTS
from research.datasets import DatasetLoader, classify_periods, regime_summary
from research.engine import BacktestConfig
from research.validate import (
    DEFAULT_CRITERIA,
    SymbolVerdict,
    evaluate_baseline_by_regime,
    merge_search_space,
    strategy_kit,
    validate_symbol,
    write_approvals,
)

logger = logging.getLogger(__name__)

#: Timeframes the legacy parameters were configured for. Validating a 4h short
#: setup on 15m candles would test a strategy nobody has ever proposed.
#: Timeframes the legacy parameters were configured for. Validating a 4h short
#: setup on 15m candles would test a strategy nobody has ever proposed.
DEFAULT_TIMEFRAME_BY_SIDE = {SignalSide.LONG: "15m", SignalSide.SHORT: "4h"}
# Donchian is a slower CTA rule. The catalog asks for 1h/4h; using the RSI
# 15m clock over-trades and is not the test we meant to run next time.
STRATEGY_TIMEFRAME_BY_SIDE = {
    "rsi_trend": DEFAULT_TIMEFRAME_BY_SIDE,
    "donchian_breakout": {SignalSide.LONG: "1h", SignalSide.SHORT: "4h"},
    "ema_adx_trend": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "bollinger_mean_reversion": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    # 4h trend is resampled inside the sleeve; the walk-forward clock is 1h.
    "trend_pullback_htf": {SignalSide.LONG: "1h", SignalSide.SHORT: "1h"},
    "atr_channel_breakout": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "bb_squeeze_breakout": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "rsi_fade_chop": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "macd_trend_pullback": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "atr_fade_chop": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "volume_climax_fade": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "opening_range_breakout": {SignalSide.LONG: "1h", SignalSide.SHORT: "1h"},
    "utc_session_vwap_reversion": {SignalSide.LONG: "1h", SignalSide.SHORT: "1h"},
    "asian_range_breakout": {SignalSide.LONG: "1h", SignalSide.SHORT: "1h"},
    "inside_bar_breakout": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "swing_failure_reversal": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "consecutive_bar_exhaustion": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "wick_rejection_reversal": {SignalSide.LONG: "1h", SignalSide.SHORT: "1h"},
    "prior_day_pivot_breakout": {SignalSide.LONG: "1h", SignalSide.SHORT: "1h"},
    "weekend_gap_fill": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "engulfing_reversal": {SignalSide.LONG: "4h", SignalSide.SHORT: "4h"},
    "utc_midnight_gap_fill": {SignalSide.LONG: "1h", SignalSide.SHORT: "1h"},
}


def _timeframe_for(strategy: str, side: SignalSide) -> str:
    mapped = STRATEGY_TIMEFRAME_BY_SIDE.get(strategy)
    if mapped:
        return mapped[side]
    try:
        from firm.sleeve_factory import spec_for_family

        spec = spec_for_family(strategy)
        if spec is not None:
            parts = spec.clock.split("/")
            return parts[0] if side is SignalSide.LONG else parts[-1]
    except Exception:
        pass
    return DEFAULT_TIMEFRAME_BY_SIDE[side]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", nargs="*", help="Symbols to validate.")
    parser.add_argument("--all", action="store_true", help="Validate every configured candidate.")
    parser.add_argument(
        "--strategy",
        default="rsi_trend",
        help="Coded family to walk-forward (rsi_trend, donchian_breakout, ema_adx_trend, bollinger_mean_reversion, trend_pullback_htf, atr_channel_breakout, opening_range_breakout).",
    )
    parser.add_argument(
        "--job-id",
        type=int,
        default=0,
        help="Research job id to mark done when this process finishes.",
    )
    parser.add_argument(
        "--side",
        choices=["LONG", "SHORT", "BOTH"],
        default="BOTH",
        help="Which direction(s) to validate.",
    )
    parser.add_argument(
        "--timeframe",
        default=None,
        help="Candle timeframe. Defaults to the legacy per-side timeframe "
             "(LONG 15m, SHORT 4h), which is what the parameters were tuned on.",
    )
    parser.add_argument("--train-days", type=int, default=180)
    parser.add_argument("--test-days", type=int, default=60)
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="Skip walk-forward; only evaluate baseline parameters per regime.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write approvals (dry run).",
    )
    parser.add_argument("--limit", type=int, default=0, help="Cap symbols processed.")
    return parser.parse_args()


def resolve_symbols(args: argparse.Namespace, side: SignalSide) -> list[str]:
    """Decide which symbols to test for a given side."""
    universe = get_universe()
    if args.symbols:
        return args.symbols
    if args.all:
        return universe.research_candidates(side.value)
    # Default: the most liquid names, where cost assumptions are most reliable.
    return list(APPROVED_RESEARCH_SYMBOLS)


def main() -> int:
    args = parse_args()
    setup_logging("validation")
    try:
        return _run_validation(args)
    except Exception as exc:
        _finish_research_job(args, ok=False, summary=f"{args.strategy} failed: {exc}")
        raise


def _finish_research_job(
    args: argparse.Namespace,
    *,
    ok: bool,
    summary: str,
    pairs_approved: int | None = None,
) -> None:
    """Tell the desk this walk-forward finished, if we were spawned as a job."""
    job_id = int(getattr(args, "job_id", 0) or 0)
    if not job_id:
        return
    from firm.research_jobs import finish_job

    finish_job(job_id, summary, ok, pairs_approved=pairs_approved)


def _run_validation(args: argparse.Namespace) -> int:
    settings = get_settings()

    sides = (
        [SignalSide.LONG, SignalSide.SHORT]
        if args.side == "BOTH"
        else [SignalSide(args.side)]
    )

    logger.info("=" * 78)
    logger.info("STRATEGY VALIDATION")
    logger.info("=" * 78)

    logger.info("Classifying market regimes from BTC history...")
    periods = classify_periods()
    summary = regime_summary(periods)
    logger.info(
        "Regimes: %d quarters over %d days | bull=%d bear=%d chop=%d",
        summary["total_periods"],
        summary["span_days"],
        len(summary["by_regime"]["bull"]),
        len(summary["by_regime"]["bear"]),
        len(summary["by_regime"]["chop"]),
    )

    config = BacktestConfig(
        initial_capital=10_000.0,
        position_fraction=0.10,
        compound=True,
        pessimistic_intrabar=True,
        costs=DEFAULT_COSTS,
    )

    verdicts: list[SymbolVerdict] = []
    baselines: dict[str, dict] = {}

    with FundingRates() as funding_source:
        for side in sides:
            symbols = resolve_symbols(args, side)
            if args.limit:
                symbols = symbols[: args.limit]

            timeframe = args.timeframe or _timeframe_for(args.strategy, side)

            logger.info("")
            logger.info("-" * 78)
            logger.info("%s: %d symbols on %s candles", side.value, len(symbols), timeframe)
            logger.info("strategy=%s", args.strategy)
            logger.info("-" * 78)

            loader = DatasetLoader(timeframe=timeframe)
            try:
                _validate_side(
                    args, side, symbols, timeframe, loader, funding_source,
                    config, periods, verdicts, baselines,
                )
            finally:
                loader.close()

    _write_report(args, periods, summary, baselines, verdicts, settings)
    approved = [v for v in verdicts if v.approved]
    _finish_research_job(
        args,
        ok=True,
        summary=f"{args.strategy}: {len(approved)} of {len(verdicts)} pairs approved.",
        pairs_approved=len(approved),
    )
    return 0


def _job_param_change(args: argparse.Namespace) -> dict:
    """Frozen grid overlay from the research job that spawned this process."""
    job_id = int(getattr(args, "job_id", 0) or 0)
    if not job_id:
        return {}
    try:
        from firm.research_jobs import list_jobs

        job = next((j for j in list_jobs() if int(j.get("id") or 0) == job_id), None)
    except Exception:
        return {}
    if not job:
        return {}
    change = job.get("param_change")
    return dict(change) if isinstance(change, dict) else {}


def _job_search_space(args: argparse.Namespace, side: SignalSide) -> dict:
    """Family grid plus any catalog freeze recorded on the job."""
    _factory, _base, space = strategy_kit(args.strategy, side)
    change = _job_param_change(args)
    merged = merge_search_space(space, change)
    if change:
        logger.info("param_change overlay=%s merged_space=%s", change, merged)
    return merged


def _validate_side(
    args: argparse.Namespace,
    side: SignalSide,
    symbols: list[str],
    timeframe: str,
    loader: DatasetLoader,
    funding_source: FundingRates,
    config: BacktestConfig,
    periods: list,
    verdicts: list[SymbolVerdict],
    baselines: dict[str, dict],
) -> None:
    """Validate every symbol for one side, appending verdicts in place."""
    for symbol in symbols:
        try:
            candles = loader.load(symbol)
        except Exception as exc:
            logger.warning("%s: could not load candles: %s", symbol, exc)
            continue

        if candles.empty:
            logger.warning("%s: no candles available, skipping.", symbol)
            continue

        # Symbol-specific slippage: majors fill far better than memes.
        symbol_config = BacktestConfig(
            initial_capital=config.initial_capital,
            position_fraction=config.position_fraction,
            compound=config.compound,
            pessimistic_intrabar=config.pessimistic_intrabar,
            costs=DEFAULT_COSTS.for_symbol(symbol),
        )

        history = funding_source.get(
            symbol,
            candles.index[0].to_pydatetime(),
            candles.index[-1].to_pydatetime(),
        )

        logger.info(
            "%s %s %s: %d bars %s..%s (slippage %.2f bps)",
            symbol, side.value, timeframe, len(candles),
            candles.index[0].date(), candles.index[-1].date(),
            symbol_config.costs.slippage * 10_000,
        )

        if args.baseline_only:
            continue

        if args.strategy == "rsi_trend":
            baseline = evaluate_baseline_by_regime(
                symbol, side, candles, periods, symbol_config, history
            )
            baselines[f"{symbol}:{side.value}"] = baseline
            _log_baseline(symbol, side, baseline)

        verdict = validate_symbol(
            symbol=symbol,
            side=side,
            candles=candles,
            config=symbol_config,
            periods=periods,
            funding=history,
            criteria=DEFAULT_CRITERIA,
            search_space=_job_search_space(args, side),
            train_days=args.train_days,
            test_days=args.test_days,
            timeframe=timeframe,
            strategy_name=args.strategy,
        )
        verdicts.append(verdict)
        logger.info("  VERDICT: %s", verdict)


def _write_report(
    args: argparse.Namespace,
    periods: list,
    summary: dict,
    baselines: dict[str, dict],
    verdicts: list[SymbolVerdict],
    settings,  # noqa: ANN001
) -> None:
    """Persist the validation report and, unless dry-running, the approvals."""
    del periods  # summarised already

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": args.strategy,
        "timeframe": args.timeframe or DEFAULT_TIMEFRAME_BY_SIDE,
        "train_days": args.train_days,
        "test_days": args.test_days,
        "regimes": summary,
        "cost_assumptions": {
            "taker_fee": DEFAULT_COSTS.taker_fee,
            "base_slippage": DEFAULT_COSTS.slippage,
            "funding_included": DEFAULT_COSTS.include_funding,
            "round_trip_cost_pct": round(DEFAULT_COSTS.round_trip_cost_pct() * 100, 4),
        },
        "baseline_by_regime": baselines,
        "verdicts": [v.summary() for v in verdicts],
    }

    report_path = settings.artifacts_dir / "validation_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(report, indent=2, default=str)
    report_path.write_text(body, encoding="utf-8")
    # Keep a per-job copy so the next run cannot overwrite the evidence.
    if getattr(args, "job_id", 0):
        job_path = settings.artifacts_dir / f"job_{int(args.job_id)}_report.json"
        job_path.write_text(body, encoding="utf-8")

    logger.info("")
    logger.info("=" * 78)
    logger.info("SUMMARY")
    logger.info("=" * 78)
    approved = [v for v in verdicts if v.approved]
    for verdict in verdicts:
        logger.info("  %s", verdict)
    logger.info("")
    logger.info("Approved: %d of %d", len(approved), len(verdicts))
    logger.info("Report: %s", report_path)

    if verdicts and not args.no_write:
        write_approvals(verdicts)
        logger.info("Approvals written. Only approved pairs may trade.")
    elif args.no_write:
        logger.info("Dry run: approvals not written.")


def _log_baseline(symbol: str, side: SignalSide, baseline: dict) -> None:
    """Print the per-regime baseline table: the legacy project's missing test."""
    if not baseline:
        return

    logger.info("  Baseline (unoptimised legacy params) by quarter:")
    total_trades = 0
    weighted_expectancy = 0.0
    for name, stats in baseline.items():
        trades = stats["trades"]
        total_trades += trades
        weighted_expectancy += stats["expectancy_pct"] * trades
        if trades:
            pf = stats["profit_factor"]
            logger.info(
                "    %-8s %-5s %3d trades  WR %5.1f%%  PF %-6s  ret %+7.2f%%  exp %+.3f%%",
                name, stats["regime"], trades, stats["win_rate"],
                f"{pf:.2f}" if pf else "n/a", stats["return_pct"], stats["expectancy_pct"],
            )

    if total_trades:
        logger.info(
            "    TOTAL: %d trades, trade-weighted expectancy %+.4f%%",
            total_trades, weighted_expectancy / total_trades,
        )


if __name__ == "__main__":
    raise SystemExit(main())
