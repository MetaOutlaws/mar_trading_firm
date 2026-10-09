"""Frozen one-shot scorer for H-RETEST-EXPANSION-01.

The runner is intentionally inert until an audited 2022-2025 cache, an
outcome-blind signal inventory and an immutable freeze all verify.  It claims
the independent run atomically, replays the two arms in separate books and
never loads candles at or beyond 2026-01-01.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import adapter
import freeze_gate
import run_state


PERIODS = {
    "historical": ("2022-01-01", "2025-01-01"),
    "evaluation": ("2025-01-01", "2026-01-01"),
}
ARMS = ("immediate", "retest")
POLLS = (0, 1)
STRESSES = (1, 2)
SLIPPAGE = {1: 0.001, 2: 0.002}
KEYS = ["partition", "symbol", "side", "signal_i"]
PAIR = KEYS + ["stress", "poll_minutes"]
STOP = 0.02
TARGET = 0.025


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
    temporary.replace(path)


def outcome_row(retest, candles, funding, tape, signal: pd.Series, fill_i: int,
                poll: int, stress: int, arm: str) -> pd.Series:
    """Build and independently reconcile one actual-fill SL/TP path."""
    original = signal.copy()
    original["poll_minutes"] = poll
    original["stress"] = stress
    original["slippage_per_side"] = SLIPPAGE[stress]
    original["cost_model"] = "runtime_stop_fill"
    original["arm"] = arm
    result = retest.replay_fill(candles, funding, tape, original, fill_i)
    result["entry_rule"] = arm
    result["arm"] = arm
    result["stress"] = stress
    result["poll_minutes"] = poll
    return result


def build_paths(cache: Path, signals: pd.DataFrame, reference_root: Path):
    """Generate all paths and entry plans without any portfolio competition."""
    _, retest = adapter.load_stack(reference_root)
    plans: list[dict] = []
    rows: list[pd.Series] = []
    counters = {"signals": 0, "entry_selections": 0, "causal_prefix_checks": 0,
                "paths_and_cost_checks": 0}
    for symbol in sorted(signals.symbol.unique()):
        candles, funding = retest.load(cache, symbol, "2026-01-01")
        if len(candles) and candles.index.max() >= pd.Timestamp("2026-01-01", tz="UTC"):
            raise AssertionError("reserved 2026 candle entered the scorer")
        tape = retest.base.Tape(candles, funding)
        for _, signal in signals[signals.symbol == symbol].sort_values("signal_time").iterrows():
            counters["signals"] += 1
            i = int(signal.signal_i)
            side = int(signal.side)
            part = str(signal.partition)
            end = int(candles.index.searchsorted(pd.Timestamp(PERIODS[part][1], tz="UTC")))
            if candles.index[i] != pd.Timestamp(signal.signal_time):
                raise AssertionError("signal index/time mismatch")
            prior = candles.iloc[i - 21 * 60:i - 60]
            boundary = prior.high.max() if side == 1 else prior.low.min()
            if len(prior) != 1200 or not np.isclose(boundary, signal.entry_boundary,
                                                    rtol=0, atol=1e-10):
                raise AssertionError("frozen breakout boundary mismatch")
            plan = retest.select_entry(tape.h, tape.l, tape.cl, i, end, side, boundary)
            sequential = retest.sequential_entry(tape.h, tape.l, tape.cl, i, end,
                                                  side, boundary)
            if plan != sequential:
                raise AssertionError("vector/sequential retest selection mismatch")
            trunc = min(end, i + 61)
            prefix = retest.select_entry(tape.h[:trunc], tape.l[:trunc],
                                         tape.cl[:trunc], i, trunc, side, boundary)
            if plan != prefix:
                raise AssertionError("retest decision is not prefix causal")
            counters["entry_selections"] += 1
            counters["causal_prefix_checks"] += 1
            entry_plan = {key: signal[key] for key in KEYS + ["signal_time", "entry_boundary"]}
            entry_plan.update(plan)
            entry_plan["touch_time"] = candles.index[plan["touch_i"]] if plan["touch_i"] >= 0 else pd.NaT
            entry_plan["confirmation_time"] = (candles.index[plan["confirm_i"]] + pd.Timedelta(minutes=1)
                                               if plan["confirm_i"] >= 0 else pd.NaT)
            entry_plan["planned_entry_time"] = (candles.index[plan["planned_entry_i"]]
                                                if plan["planned_entry_i"] >= 0 else pd.NaT)
            plans.append(entry_plan)
            for poll in POLLS:
                for stress in STRESSES:
                    rows.append(outcome_row(retest, candles, funding, tape, signal, i,
                                            poll, stress, "immediate"))
                    counters["paths_and_cost_checks"] += 1
                    if plan["entry_status"] == "filled":
                        if not 1 <= int(plan["delay_minutes"]) <= 60:
                            raise AssertionError("retest fill outside frozen deadline")
                        q = outcome_row(retest, candles, funding, tape, signal,
                                        int(plan["planned_entry_i"]), poll, stress, "retest")
                        q["delay_minutes"] = int(plan["delay_minutes"])
                        rows.append(q)
                        counters["paths_and_cost_checks"] += 1
    opportunities = pd.DataFrame(rows)
    plans_frame = pd.DataFrame(plans)
    if opportunities.duplicated(PAIR + ["entry_rule"]).any():
        raise AssertionError("duplicate opportunity key")
    return opportunities, plans_frame, counters


def replay_books(retest, opportunities: pd.DataFrame):
    """Replay each arm independently for every exit/cost/partition view."""
    ledgers, rejections = [], []
    replay_count = 0
    for arm in ARMS:
        for poll in POLLS:
            for partition in PERIODS:
                for stress in STRESSES:
                    group = opportunities[
                        (opportunities.entry_rule == arm)
                        & (opportunities.poll_minutes == poll)
                        & (opportunities.partition == partition)
                        & (opportunities.stress == stress)
                    ]
                    admitted, rejected = retest.admission(group)
                    replay_count += 1
                    admitted = admitted.copy()
                    admitted["entry_rule"] = arm
                    ledgers.append(admitted)
                    if len(rejected):
                        rejected = rejected.copy()
                        rejected["entry_rule"] = arm
                        rejected["poll_minutes"] = poll
                        rejected["partition"] = partition
                        rejected["stress"] = stress
                        rejections.append(rejected)
    ledger = pd.concat(ledgers, ignore_index=True) if ledgers else pd.DataFrame()
    rejected = (pd.concat(rejections, ignore_index=True) if rejections else
                pd.DataFrame(columns=PAIR + ["entry_rule", "reason"]))
    return ledger, rejected, replay_count


def metric_values(frame: pd.DataFrame, original_signals: int) -> dict:
    closed = frame[frame.reason.isin(["stop", "target"])] if len(frame) else frame
    values = frame.net_return.to_numpy(dtype=float) if len(frame) else np.array([], dtype=float)
    positives = int((values > 0).sum())
    gains = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    return {
        "admitted": int(len(frame)),
        "completed_trades": int(len(closed)),
        "targets": int((frame.reason == "target").sum()) if len(frame) else 0,
        "stop_losses": int((frame.reason == "stop").sum()) if len(frame) else 0,
        "marks": int((frame.reason == "boundary_mtm").sum()) if len(frame) else 0,
        "net_positive": positives,
        "net_win_rate": positives / len(frame) if len(frame) else np.nan,
        "completed_net_win_rate": float((closed.net_return > 0).mean()) if len(closed) else np.nan,
        "marked_net_return_sum": float(frame.loc[frame.reason == "boundary_mtm", "net_return"].sum()) if len(frame) else 0.,
        "closed_net_per_original_signal": float(closed.net_return.sum() / original_signals) if original_signals else np.nan,
        "stop_rate_completed": ((frame.reason == "stop").sum() / len(closed)
                                if len(closed) else np.nan),
        "mean_net_per_admitted_trade": float(values.mean()) if len(values) else np.nan,
        "mean_net_per_completed_trade": float(closed.net_return.mean()) if len(closed) else np.nan,
        "net_per_original_signal": float(values.sum() / original_signals)
        if original_signals else np.nan,
        "median_net": float(np.median(values)) if len(values) else np.nan,
        "profit_factor": gains / losses if losses else (np.inf if gains else np.nan),
        "mean_holding_minutes": float(frame.holding_minutes.mean()) if len(frame) else np.nan,
    }


def summary_tables(signals: pd.DataFrame, opportunities: pd.DataFrame,
                   ledger: pd.DataFrame, universe=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    pooled, cells = [], []
    symbols = sorted(universe if universe is not None else signals.symbol.unique())
    for arm in ARMS:
        for poll in POLLS:
            for partition in PERIODS:
                base_signals = signals[signals.partition == partition]
                for stress in STRESSES:
                    view = ledger[(ledger.entry_rule == arm) & (ledger.poll_minutes == poll)
                                  & (ledger.partition == partition) & (ledger.stress == stress)]
                    qualified = opportunities[(opportunities.entry_rule == arm)
                                              & (opportunities.poll_minutes == poll)
                                              & (opportunities.partition == partition)
                                              & (opportunities.stress == stress)]
                    meta = {"entry_rule": arm, "poll_minutes": poll,
                            "partition": partition, "stress": stress}
                    pooled.append(meta | {"original_signals": len(base_signals),
                                          "qualified_fills": len(qualified),
                                          "unfilled": len(base_signals) - len(qualified),
                                          "rejected": len(qualified) - len(view)}
                                  | metric_values(view, len(base_signals)))
                    for symbol in symbols:
                        for side in (-1, 1):
                            original = base_signals[(base_signals.symbol == symbol)
                                                    & (base_signals.side == side)]
                            cell = view[(view.symbol == symbol) & (view.side == side)]
                            cells.append(meta | {"symbol": symbol, "side": side,
                                                 "original_signals": len(original)}
                                         | metric_values(cell, len(original)))
                    yearly = base_signals.assign(signal_year=pd.to_datetime(
                        base_signals.signal_time, utc=True).dt.year)
                    for year in range(int(PERIODS[partition][0][:4]), int(PERIODS[partition][1][:4])):
                        original = yearly[yearly.signal_year == year]
                        cell = view[pd.to_datetime(view.signal_time, utc=True).dt.year == year]
                        cells.append(meta | {"symbol": "ALL", "side": 0,
                                             "signal_year": int(year),
                                             "original_signals": len(original)}
                                     | metric_values(cell, len(original)))
    return pd.DataFrame(pooled), pd.DataFrame(cells)


def pair_signals(opportunities: pd.DataFrame, ledger: pd.DataFrame,
                 plans: pd.DataFrame) -> pd.DataFrame:
    fields = PAIR + ["signal_time", "entry", "entry_i", "exit_bar", "exit_i",
                     "reason", "entry_price", "exit_price", "net_return",
                     "holding_minutes"]
    immediate = opportunities[opportunities.entry_rule == "immediate"][fields]
    retest = opportunities[opportunities.entry_rule == "retest"][fields]
    pairs = immediate.merge(retest, on=PAIR, how="left", suffixes=("_immediate", "_retest"),
                            validate="one_to_one").merge(plans, on=KEYS, how="left",
                                                         validate="many_to_one")
    for arm in ARMS:
        index = pd.MultiIndex.from_frame(ledger[ledger.entry_rule == arm][PAIR])
        pairs[f"{arm}_admitted"] = pd.MultiIndex.from_frame(pairs[PAIR]).isin(index)
    pairs["immediate_realized_net"] = np.where(pairs.immediate_admitted,
                                                pairs.net_return_immediate, 0.0)
    pairs["retest_realized_net"] = np.where(pairs.retest_admitted,
                                             pairs.net_return_retest.fillna(0), 0.0)
    pairs["delta_realized_net"] = pairs.retest_realized_net - pairs.immediate_realized_net
    pairs["entry_delay_minutes"] = pairs.entry_i_retest - pairs.entry_i_immediate
    pairs["fill_price_improvement"] = (pairs.side *
        (pairs.entry_price_immediate - pairs.entry_price_retest) / pairs.entry_price_immediate)
    pairs["admission_change"] = np.select(
        [pairs.immediate_admitted & pairs.retest_admitted,
         ~pairs.immediate_admitted & pairs.retest_admitted,
         pairs.immediate_admitted & ~pairs.retest_admitted],
        ["shared", "newly_admitted", "removed"], default="neither")
    pairs["no_trade_reason"] = np.where(
        pairs.retest_admitted, "admitted",
        np.where(pairs.entry_status == "filled", "occupancy_rejected", pairs.entry_status))
    return pairs


def comparison_tables(pairs: pd.DataFrame) -> dict[str, pd.DataFrame]:
    contrasts, missed, delays, decomposition = [], [], [], []
    for (poll, partition, stress), group in pairs.groupby(
            ["poll_minutes", "partition", "stress"], dropna=False):
        meta = {"poll_minutes": int(poll), "partition": partition, "stress": int(stress)}
        ni = int(group.immediate_admitted.sum())
        nr = int(group.retest_admitted.sum())
        si = float(group.immediate_realized_net.sum())
        sr = float(group.retest_realized_net.sum())
        contrasts.append(meta | {
            "original_signals": len(group), "immediate_admitted": ni,
            "retest_admitted": nr,
            "immediate_mean_net_per_trade": si / ni if ni else np.nan,
            "retest_mean_net_per_trade": sr / nr if nr else np.nan,
            "difference_mean_net_per_trade": (sr / nr - si / ni) if ni and nr else np.nan,
            "immediate_net_per_original_signal": si / len(group) if len(group) else np.nan,
            "retest_net_per_original_signal": sr / len(group) if len(group) else np.nan,
            "difference_net_per_original_signal": (sr - si) / len(group) if len(group) else np.nan,
        })
        for reason in ["no_retest", "retest_no_reclaim", "endpoint_censored",
                       "occupancy_rejected"]:
            subset = group[group.immediate_admitted & (group.no_trade_reason == reason)]
            missed.append(meta | {"no_trade_reason": reason, "n": len(subset),
                                  "missed_baseline_target_winners": int(
                                      (subset.reason_immediate == "target").sum()),
                                  "baseline_stops_avoided": int(
                                      (subset.reason_immediate == "stop").sum()),
                                  "baseline_net_missed": float(subset.net_return_immediate.sum())})
        for scope, subset in [("qualified", group[group.entry_status == "filled"]),
                              ("admitted", group[group.retest_admitted])]:
            delays.append(meta | {"scope": scope, "n": len(subset),
                                  "mean_delay_minutes": subset.entry_delay_minutes.mean(),
                                  "median_delay_minutes": subset.entry_delay_minutes.median(),
                                  "mean_fill_price_improvement": subset.fill_price_improvement.mean()})
        shared = group[group.admission_change == "shared"]
        new = group[group.admission_change == "newly_admitted"]
        removed = group[group.admission_change == "removed"]
        common = float((shared.net_return_retest - shared.net_return_immediate).sum())
        actual = sr - si
        check = common + float(new.net_return_retest.sum()) - float(removed.net_return_immediate.sum())
        if not np.isclose(actual, check, rtol=0, atol=1e-12):
            raise AssertionError("admission decomposition is not additive")
        decomposition.append(meta | {"shared": len(shared), "newly_admitted": len(new),
                                     "removed": len(removed), "shared_delta_net": common,
                                     "new_net": float(new.net_return_retest.sum()),
                                     "removed_immediate_net": float(removed.net_return_immediate.sum()),
                                     "actual_net_difference": actual})
    return {"contrasts": pd.DataFrame(contrasts), "missed_winners": pd.DataFrame(missed),
            "entry_delays": pd.DataFrame(delays),
            "admission_decomposition": pd.DataFrame(decomposition)}


def bootstrap_intervals(pairs: pd.DataFrame, draws: int = 10_000) -> pd.DataFrame:
    rows = []
    for (partition, stress), group in pairs[pairs.poll_minutes == 1].groupby(
            ["partition", "stress"]):
        begin, end = PERIODS[partition]
        weeks = pd.period_range(pd.Timestamp(begin).to_period("W-SUN"),
            (pd.Timestamp(end) - pd.Timedelta(minutes=1)).to_period("W-SUN"), freq="W-SUN")
        frame = group.copy()
        frame["week"] = pd.to_datetime(frame.signal_time_immediate, utc=True).dt.tz_localize(None).dt.to_period("W-SUN")
        agg = frame.groupby("week").agg(
            immediate_sum=("immediate_realized_net", "sum"),
            retest_sum=("retest_realized_net", "sum"),
            immediate_n=("immediate_admitted", "sum"),
            retest_n=("retest_admitted", "sum"),
            signals=("delta_realized_net", "size"),
        ).reindex(weeks, fill_value=0)
        values = agg.to_numpy(dtype=float)
        for seed in (20261007, 20261010):
            for block in (1, 4):
                n = len(values)
                starts = np.random.default_rng(seed).integers(
                    0, n, (draws, int(np.ceil(n / block))))
                indices = ((starts[:, :, None] + np.arange(block)) % n).reshape(draws, -1)[:, :n]
                sample = values[indices].sum(axis=1)
                im = np.divide(sample[:, 0], sample[:, 2],
                               out=np.full(draws, np.nan), where=sample[:, 2] > 0)
                rt = np.divide(sample[:, 1], sample[:, 3],
                               out=np.full(draws, np.nan), where=sample[:, 3] > 0)
                per_signal = np.divide(sample[:, 1] - sample[:, 0], sample[:, 4],
                                       out=np.full(draws, np.nan), where=sample[:, 4] > 0)
                fraction_missed = np.divide(sample[:, 0] - sample[:, 1], sample[:, 0],
                                            out=np.full(draws, np.nan),
                                            where=np.abs(sample[:, 0]) > 1e-15)
                for metric, distribution in {
                    "immediate_mean_net_per_trade": im,
                    "retest_mean_net_per_trade": rt,
                    "difference_mean_net_per_trade": rt - im,
                    "difference_net_per_original_signal": per_signal,
                    "immediate_net_per_original_signal": np.divide(sample[:, 0], sample[:, 4], out=np.full(draws, np.nan), where=sample[:, 4] > 0),
                    "retest_net_per_original_signal": np.divide(sample[:, 1], sample[:, 4], out=np.full(draws, np.nan), where=sample[:, 4] > 0),
                    "fraction_baseline_net_missed": fraction_missed,
                }.items():
                    valid = distribution[np.isfinite(distribution)]
                    low, high = np.quantile(valid, [0.025, 0.975]) if len(valid) else (np.nan, np.nan)
                    rows.append({"partition": partition, "stress": int(stress),
                                 "seed": seed, "block_weeks": block, "metric": metric,
                                 "draws": len(valid), "low_95": low, "high_95": high})
    return pd.DataFrame(rows)


def sensitivities(ledger: pd.DataFrame, signals: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, largest = [], []
    primary = ledger[(ledger.poll_minutes == 1) & (ledger.stress == 2)]
    for arm in ARMS:
        for partition in PERIODS:
            view = primary[(primary.entry_rule == arm) & (primary.partition == partition)]
            for symbol in sorted(signals.symbol.unique()):
                subset = view[view.symbol != symbol]
                rows.append({"entry_rule": arm, "partition": partition,
                             "removed_symbol": symbol, "admitted": len(subset),
                             "mean_net": subset.net_return.mean() if len(subset) else np.nan})
            if len(view):
                index = view.net_return.idxmax()
                subset = view.drop(index)
                largest.append({"entry_rule": arm, "partition": partition,
                                "removed_symbol": view.loc[index, "symbol"],
                                "removed_net_return": view.loc[index, "net_return"],
                                "admitted_after_removal": len(subset),
                                "mean_net_after_removal": subset.net_return.mean()
                                if len(subset) else np.nan})
    return pd.DataFrame(rows), pd.DataFrame(largest)


def classify(pooled: pd.DataFrame, contrasts: pd.DataFrame, intervals: pd.DataFrame,
             ledger: pd.DataFrame, audit: dict, leave_one_out: pd.DataFrame) -> dict:
    point = {}
    for partition in PERIODS:
        arm = pooled[(pooled.entry_rule == "retest") & (pooled.poll_minutes == 1)
                     & (pooled.stress == 2) & (pooled.partition == partition)].iloc[0]
        diff = contrasts[(contrasts.poll_minutes == 1) & (contrasts.stress == 2)
                         & (contrasts.partition == partition)].iloc[0]
        point[partition] = bool(arm.mean_net_per_admitted_trade > 0
                                and diff.difference_mean_net_per_trade > 0)
    evaluation = ledger[(ledger.entry_rule == "retest") & (ledger.poll_minutes == 1)
                        & (ledger.stress == 2) & (ledger.partition == "evaluation")]
    ci = intervals[(intervals.partition == "evaluation")]
    positive_difference_bounds = bool(len(ci[ci.metric == "difference_mean_net_per_trade"])
        and (ci[ci.metric == "difference_mean_net_per_trade"].low_95 > 0).all())
    positive_mean_bounds = bool(len(ci[ci.metric == "retest_mean_net_per_trade"])
        and (ci[ci.metric == "retest_mean_net_per_trade"].low_95 > 0).all())
    loto = leave_one_out[(leave_one_out.entry_rule == "retest")
                         & (leave_one_out.partition == "evaluation")]
    provenance = all(audit.get(key) is True for key in [
        "historical_universe_complete", "historical_funding_schedule_verified",
        "classification_history_verified"])
    requirements = {
        "evaluation_closed_trades_at_least_100": int(evaluation.reason.isin(["stop", "target"]).sum()) >= 100,
        "evaluation_entry_dates_at_least_50": evaluation.entry.dt.floor("D").nunique() >= 50 if len(evaluation) else False,
        "evaluation_entry_weeks_at_least_26": evaluation.entry.dt.tz_localize(None).dt.to_period("W-SUN").nunique() >= 26 if len(evaluation) else False,
        "evaluation_tokens_at_least_8": evaluation.symbol.nunique() >= 8,
        "positive_difference_lower_bounds_both_costs_blocks_seeds": positive_difference_bounds,
        "positive_challenger_mean_lower_bounds_both_costs_blocks_seeds": positive_mean_bounds,
        "positive_stressed_leave_one_token_out_means": bool(len(loto) and (loto.mean_net > 0).all()),
        "independently_verified_provenance": provenance,
    }
    strong = all(point.values()) and all(requirements.values())
    if strong:
        label = "strong_statistical_support"
    elif all(point.values()):
        label = "encouraging_not_strong_support"
    elif any(point.values()):
        label = "inconclusive"
    else:
        label = "unfavorable"
    return {"experiment_id": run_state.EXPERIMENT_ID, "classification": label,
            "positive_point_evidence": all(point.values()), "period_checks": point,
            "strong_support": strong, "strong_support_requirements": requirements,
            "additional_token_2026_outcomes_scored": False,
            "automatic_deployment": False, "production_changes": False,
            "return_sums_are_account_pnl": False}


def verify_outputs(out: Path, expected_signals: int, symbols: list[str]) -> dict:
    signals = pd.read_csv(out / "frozen_signals.csv")
    opportunities = pd.read_parquet(out / "all_opportunities.parquet")
    ledger = pd.read_parquet(out / "pooled_ledger.parquet")
    csv_ledger = pd.read_csv(out / "individual_trades.csv")
    cells = pd.read_csv(out / "token_side_cells.csv")
    if len(signals) != expected_signals or len(csv_ledger) != len(ledger):
        raise AssertionError("output row-count verification failed")
    if opportunities.duplicated(PAIR + ["entry_rule"]).any() or ledger.duplicated(
            PAIR + ["entry_rule"]).any():
        raise AssertionError("duplicate output keys")
    expected_cells = len(symbols) * 2 * len(ARMS) * len(POLLS) * len(PERIODS) * len(STRESSES)
    token_cells = cells[cells.symbol != "ALL"]
    if len(token_cells) != expected_cells:
        raise AssertionError("not every token/side cell was reported")
    decision = json.loads((out / "decision.json").read_text())
    if decision.get("additional_token_2026_outcomes_scored") is not False:
        raise AssertionError("2026 outcome flag changed")
    hashes = {path.name: sha256(path) for path in sorted(out.iterdir())
              if path.is_file() and path.name not in {"STATUS.json", "VERIFICATION.json"}}
    return {"status": "pass", "experiment_id": run_state.EXPERIMENT_ID,
            "signals": expected_signals, "opportunity_rows": len(opportunities),
            "ledger_rows": len(ledger), "all_token_side_cells": len(token_cells),
            "output_hashes": hashes, "scores_2026": False,
            "production_changes": False}


def run(cache: Path, signal_dir: Path, reference_root: Path, freeze: Path,
        record: Path, out: Path) -> None:
    runner = Path(__file__).resolve()
    frozen = freeze_gate.verify_freeze(cache, signal_dir, runner, freeze)
    if not frozen.get("reference_sources") or not frozen.get("runtime_sources"):
        raise ValueError("production comparison requires frozen reference and runtime sources")
    if Path(frozen["reference_root"]).resolve() != reference_root.resolve():
        raise ValueError("requested reference root differs from frozen source root")
    run_state.claim(record, frozen["dataset_manifest_sha256"], frozen["runner_sha256"])
    try:
        run_state.transition(record, "claimed", "preflight",
                             freeze_sha256=sha256(freeze))
        signals = pd.read_parquet(signal_dir / "frozen_signals.parquet")
        if len(signals) != frozen["selected_signals"]:
            raise AssertionError("frozen signal count mismatch")
        if len(signals) and pd.to_datetime(signals.signal_time, utc=True).max() >= pd.Timestamp(
                "2026-01-01", tz="UTC"):
            raise AssertionError("reserved 2026 signal entered scorer")
        audit = json.loads((cache / "audit.json").read_text())
        universe = sorted(audit["new_token_symbols"])
        out.mkdir(parents=True, exist_ok=False)
        run_state.transition(record, "preflight", "frozen",
                             symbols=sorted(signals.symbol.unique()), signals=len(signals))
        run_state.transition(record, "frozen", "running")
        opportunities, plans, counters = build_paths(cache, signals, reference_root)
        _, retest = adapter.load_stack(reference_root)
        ledger, rejections, replay_count = replay_books(retest, opportunities)
        pooled, cells = summary_tables(signals, opportunities, ledger, universe)
        pairs = pair_signals(opportunities, ledger, plans)
        comparisons = comparison_tables(pairs)
        intervals = bootstrap_intervals(pairs)
        leave_one_out, largest = sensitivities(ledger, signals)
        decision = classify(pooled, comparisons["contrasts"], intervals, ledger,
                            audit, leave_one_out)
        signals.to_csv(out / "frozen_signals.csv", index=False)
        plans.to_csv(out / "entry_plans.csv", index=False)
        opportunities.to_parquet(out / "all_opportunities.parquet", index=False)
        opportunities.to_csv(out / "all_opportunities.csv", index=False)
        ledger.to_parquet(out / "pooled_ledger.parquet", index=False)
        ledger.to_csv(out / "individual_trades.csv", index=False)
        annual = []
        for arm in ARMS:
            arm_ledger = ledger[ledger.entry_rule == arm]
            arm_ledger.to_csv(out / f"portfolio_{arm}.csv", index=False)
            for partition, (begin, end) in PERIODS.items():
                for poll in POLLS:
                    for stress in STRESSES:
                        view = arm_ledger[(arm_ledger.partition == partition) & (arm_ledger.poll_minutes == poll) & (arm_ledger.stress == stress)]
                        for year in range(int(begin[:4]), int(end[:4])):
                            q = view[pd.to_datetime(view.entry, utc=True).dt.year == year]
                            annual.append(dict(entry_rule=arm, partition=partition, poll_minutes=poll, stress=stress, entry_year=year, **metric_values(q, 0)))
        pd.DataFrame(annual).to_csv(out / "actual_entry_year_results.csv", index=False)
        concentration = ledger.groupby(["entry_rule", "partition", "poll_minutes", "stress", "symbol"]).agg(admitted=("net_return", "size"), net_return_sum=("net_return", "sum"), positive_return_sum=("net_return", lambda x: x[x > 0].sum())).reset_index()
        concentration.to_csv(out / "token_contributions.csv", index=False)
        rejections.to_csv(out / "rejections.csv", index=False)
        pooled.to_csv(out / "pooled_results.csv", index=False)
        cells.to_csv(out / "token_side_cells.csv", index=False)
        pairs.to_csv(out / "signal_pairs.csv", index=False)
        for name, frame in comparisons.items():
            frame.to_csv(out / f"{name}.csv", index=False)
        intervals.to_csv(out / "bootstrap_intervals.csv", index=False)
        leave_one_out.to_csv(out / "leave_one_token_out.csv", index=False)
        largest.to_csv(out / "largest_winner_sensitivity.csv", index=False)
        write_json(out / "decision.json", decision)
        run_state.transition(record, "running", "verifying",
                             path_and_cost_checks=counters["paths_and_cost_checks"],
                             independent_admission_replays=replay_count)
        verification = verify_outputs(out, len(signals), universe)
        verification.update(counters)
        verification["independent_admission_replays"] = replay_count
        write_json(out / "VERIFICATION.json", verification)
        write_json(out / "STATUS.json", {"status": "complete",
                   "experiment_id": run_state.EXPERIMENT_ID,
                   "verification_sha256": sha256(out / "VERIFICATION.json"),
                   "scores_2026": False, "production_changes": False})
        run_state.transition(record, "verifying", "complete",
                             result_verification_sha256=sha256(out / "VERIFICATION.json"),
                             classification=decision["classification"])
    except Exception as exc:
        current = run_state.read_record(record)
        if current and current.get("status") in run_state.ACTIVE:
            run_state.transition(record, current["status"], "failed", error=repr(exc))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--signal-dir", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.cache, args.signal_dir, args.reference_root, args.freeze, args.record, args.out)
