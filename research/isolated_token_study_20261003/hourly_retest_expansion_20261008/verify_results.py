"""Independent post-run verifier for H-RETEST-EXPANSION-01.

This verifier is deliberately separate from the scorer.  It reopens only the
frozen 2022-2025 artifacts, rebuilds each arm's portfolio admissions from the
saved opportunity ledger, recomputes cash returns and both denominators, and
writes a hash-bound verification report.  It never produces or changes a trade.
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


EXPERIMENT_ID = "H-RETEST-EXPANSION-01"
PERIODS = ("historical", "evaluation")
ARMS = ("immediate", "retest")
POLLS = (0, 1)
STRESSES = (1, 2)
PAIR = ["partition", "symbol", "side", "signal_i", "stress", "poll_minutes"]
VIEW = ["entry_rule", "poll_minutes", "partition", "stress"]


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
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")
    temporary.replace(path)


def check_output_hashes(out: Path, verification: dict) -> int:
    hashes = verification.get("output_hashes")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("scorer verification has no output hashes")
    for name, expected in sorted(hashes.items()):
        path = out / name
        if not path.is_file() or sha256(path) != expected:
            raise AssertionError(f"result output hash mismatch: {name}")
    return len(hashes)


def check_costs(ledger: pd.DataFrame) -> int:
    """Recalculate runtime-stop-fill cash returns without scorer helpers."""
    if len(ledger) == 0:
        return 0
    required = {"entry_price", "entry_fill", "quote", "exit_price", "reason",
                "side", "slippage_per_side", "fees", "funding", "net_return",
                "stop_price", "target_price"}
    missing = sorted(required - set(ledger.columns))
    if missing:
        raise AssertionError(f"ledger cost columns missing: {missing}")
    side = ledger.side.to_numpy(dtype=float)
    entry = ledger.entry_price.to_numpy(dtype=float)
    slip = ledger.slippage_per_side.to_numpy(dtype=float)
    quote = ledger.quote.to_numpy(dtype=float)
    stop = ledger.reason.eq("stop").to_numpy()
    exit_price = np.where(stop, quote, quote * (1 - side * slip))
    fees = 0.00055 * (1 + exit_price / entry)
    net = ((exit_price / entry - 1) * side - fees
           - ledger.funding.to_numpy(dtype=float))
    checks = {
        "entry_fill": (ledger.entry_fill.to_numpy(dtype=float), entry),
        "exit_price": (ledger.exit_price.to_numpy(dtype=float), exit_price),
        "fees": (ledger.fees.to_numpy(dtype=float), fees),
        "net_return": (ledger.net_return.to_numpy(dtype=float), net),
        "stop_price": (ledger.stop_price.to_numpy(dtype=float), entry * (1 - side * .02)),
        "target_price": (ledger.target_price.to_numpy(dtype=float), entry * (1 + side * .025)),
    }
    for name, (observed, expected) in checks.items():
        if not np.allclose(observed, expected, rtol=0, atol=1e-11, equal_nan=True):
            raise AssertionError(f"independent cost mismatch: {name}")
    if not set(ledger.reason.unique()).issubset({"stop", "target", "boundary_mtm"}):
        raise AssertionError("unexpected holding-timeout or exit reason")
    return len(ledger)


def rebuild_books(retest, opportunities: pd.DataFrame, ledger: pd.DataFrame,
                  rejections: pd.DataFrame) -> int:
    """Recreate every independent admission replay and compare stable keys."""
    count = 0
    stable = PAIR + ["entry_rule", "entry", "entry_i", "exit_bar", "exit_i",
                     "reason", "entry_price", "exit_price", "net_return"]
    for arm in ARMS:
        for poll in POLLS:
            for partition in PERIODS:
                for stress in STRESSES:
                    source = opportunities[
                        (opportunities.entry_rule == arm)
                        & (opportunities.poll_minutes == poll)
                        & (opportunities.partition == partition)
                        & (opportunities.stress == stress)
                    ]
                    admitted, rejected = retest.admission(source)
                    observed = ledger[
                        (ledger.entry_rule == arm) & (ledger.poll_minutes == poll)
                        & (ledger.partition == partition) & (ledger.stress == stress)
                    ]
                    rebuilt = admitted.copy()
                    rebuilt["entry_rule"] = arm
                    left = rebuilt[stable].sort_values(PAIR).reset_index(drop=True)
                    right = observed[stable].sort_values(PAIR).reset_index(drop=True)
                    pd.testing.assert_frame_equal(left, right, check_exact=True)
                    saved_rejections = rejections[
                        (rejections.entry_rule == arm)
                        & (rejections.poll_minutes == poll)
                        & (rejections.partition == partition)
                        & (rejections.stress == stress)
                    ]
                    if len(rejected) != len(saved_rejections):
                        raise AssertionError("rejection count mismatch")
                    if len(admitted) + len(rejected) != len(source):
                        raise AssertionError("admission replay is not exhaustive")
                    count += 1
    return count


def independent_metrics(frame: pd.DataFrame, original_signals: int) -> dict:
    closed = frame[frame.reason.isin(["stop", "target"])] if len(frame) else frame
    values = frame.net_return.to_numpy(dtype=float) if len(frame) else np.array([], dtype=float)
    gains = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    return {
        "admitted": len(frame),
        "completed_trades": len(closed),
        "targets": int(frame.reason.eq("target").sum()) if len(frame) else 0,
        "stop_losses": int(frame.reason.eq("stop").sum()) if len(frame) else 0,
        "marks": int(frame.reason.eq("boundary_mtm").sum()) if len(frame) else 0,
        "net_positive": int((values > 0).sum()),
        "net_win_rate": float((values > 0).mean()) if len(values) else np.nan,
        "completed_net_win_rate": float((closed.net_return > 0).mean()) if len(closed) else np.nan,
        "marked_net_return_sum": float(frame.loc[frame.reason == "boundary_mtm", "net_return"].sum()) if len(frame) else 0.,
        "closed_net_per_original_signal": float(closed.net_return.sum() / original_signals) if original_signals else np.nan,
        "stop_rate_completed": float(frame.reason.eq("stop").sum() / len(closed))
        if len(closed) else np.nan,
        "mean_net_per_admitted_trade": float(values.mean()) if len(values) else np.nan,
        "mean_net_per_completed_trade": float(closed.net_return.mean()) if len(closed) else np.nan,
        "net_per_original_signal": float(values.sum() / original_signals)
        if original_signals else np.nan,
    }


def assert_numeric_row(observed: pd.Series, expected: dict, label: str) -> None:
    for name, wanted in expected.items():
        got = observed[name]
        if isinstance(wanted, (int, np.integer)):
            if int(got) != int(wanted):
                raise AssertionError(f"{label} mismatch: {name}")
        elif not np.isclose(float(got), float(wanted), rtol=0, atol=1e-12,
                            equal_nan=True):
            raise AssertionError(f"{label} mismatch: {name}")


def check_denominators(signals: pd.DataFrame, opportunities: pd.DataFrame,
                       ledger: pd.DataFrame, pooled: pd.DataFrame) -> int:
    rows = 0
    for arm in ARMS:
        for poll in POLLS:
            for partition in PERIODS:
                original = signals[signals.partition == partition]
                for stress in STRESSES:
                    view = ledger[(ledger.entry_rule == arm) & (ledger.poll_minutes == poll)
                                  & (ledger.partition == partition)
                                  & (ledger.stress == stress)]
                    qualified = opportunities[
                        (opportunities.entry_rule == arm)
                        & (opportunities.poll_minutes == poll)
                        & (opportunities.partition == partition)
                        & (opportunities.stress == stress)]
                    observed = pooled[(pooled.entry_rule == arm)
                                      & (pooled.poll_minutes == poll)
                                      & (pooled.partition == partition)
                                      & (pooled.stress == stress)]
                    if len(observed) != 1:
                        raise AssertionError("pooled result view missing or duplicated")
                    expected = {"original_signals": len(original),
                                "qualified_fills": len(qualified),
                                "unfilled": len(original) - len(qualified),
                                "rejected": len(qualified) - len(view)}
                    expected.update(independent_metrics(view, len(original)))
                    assert_numeric_row(observed.iloc[0], expected, "pooled denominator")
                    rows += 1
    return rows


def check_token_side_cells(signals: pd.DataFrame, ledger: pd.DataFrame,
                           cells: pd.DataFrame, universe=None) -> int:
    symbols = sorted(universe if universe is not None else signals.symbol.unique())
    checked = 0
    token_cells = cells[cells.symbol != "ALL"]
    for arm in ARMS:
        for poll in POLLS:
            for partition in PERIODS:
                for stress in STRESSES:
                    view = ledger[(ledger.entry_rule == arm) & (ledger.poll_minutes == poll)
                                  & (ledger.partition == partition)
                                  & (ledger.stress == stress)]
                    for symbol in symbols:
                        for side in (-1, 1):
                            original = signals[(signals.partition == partition)
                                               & (signals.symbol == symbol)
                                               & (signals.side == side)]
                            trades = view[(view.symbol == symbol) & (view.side == side)]
                            observed = token_cells[
                                (token_cells.entry_rule == arm)
                                & (token_cells.poll_minutes == poll)
                                & (token_cells.partition == partition)
                                & (token_cells.stress == stress)
                                & (token_cells.symbol == symbol)
                                & (token_cells.side == side)]
                            if len(observed) != 1:
                                raise AssertionError("token/side cell missing or duplicated")
                            expected = {"original_signals": len(original)}
                            expected.update(independent_metrics(trades, len(original)))
                            assert_numeric_row(observed.iloc[0], expected, "token/side cell")
                            checked += 1
    return checked


def check_entry_year_cells(signals: pd.DataFrame, ledger: pd.DataFrame,
                           cells: pd.DataFrame) -> int:
    checked = 0
    signal_year = pd.to_datetime(signals.signal_time, utc=True).dt.year
    trade_year = pd.to_datetime(ledger.signal_time, utc=True).dt.year
    years = sorted(signal_year.unique())
    annual = cells[cells.symbol == "ALL"]
    for arm in ARMS:
        for poll in POLLS:
            for partition in PERIODS:
                for stress in STRESSES:
                    view = ledger[(ledger.entry_rule == arm) & (ledger.poll_minutes == poll)
                                  & (ledger.partition == partition)
                                  & (ledger.stress == stress)]
                    view_year = trade_year.loc[view.index]
                    for year in years:
                        original = signals[(signals.partition == partition)
                                           & (signal_year == year)]
                        if not len(original):
                            continue
                        trades = view[view_year == year]
                        observed = annual[(annual.entry_rule == arm)
                                          & (annual.poll_minutes == poll)
                                          & (annual.partition == partition)
                                          & (annual.stress == stress)
                                          & (annual.signal_year == year)]
                        if len(observed) != 1:
                            raise AssertionError("entry-year cell missing or duplicated")
                        expected = {"original_signals": len(original)}
                        expected.update(independent_metrics(trades, len(original)))
                        assert_numeric_row(observed.iloc[0], expected, "entry-year cell")
                        checked += 1
    return checked


def check_signal_pairs(signals: pd.DataFrame, opportunities: pd.DataFrame,
                       ledger: pd.DataFrame, pairs: pd.DataFrame) -> int:
    expected = len(signals) * len(POLLS) * len(STRESSES)
    if len(pairs) != expected or pairs.duplicated(PAIR).any():
        raise AssertionError("signal-pair inventory mismatch")
    if len(opportunities[opportunities.entry_rule == "immediate"]) != expected:
        raise AssertionError("immediate arm does not cover every original signal")
    for arm in ARMS:
        admitted = pd.MultiIndex.from_frame(ledger[ledger.entry_rule == arm][PAIR])
        mask = pd.MultiIndex.from_frame(pairs[PAIR]).isin(admitted)
        if not np.array_equal(mask, pairs[f"{arm}_admitted"].astype(bool).to_numpy()):
            raise AssertionError(f"paired admission mismatch: {arm}")
        source = f"net_return_{arm}"
        expected_net = np.where(mask, pairs[source].fillna(0), 0.0)
        if not np.allclose(expected_net, pairs[f"{arm}_realized_net"],
                           rtol=0, atol=1e-12):
            raise AssertionError(f"paired realized-net mismatch: {arm}")
    delta = pairs.retest_realized_net - pairs.immediate_realized_net
    if not np.allclose(delta, pairs.delta_realized_net, rtol=0, atol=1e-12):
        raise AssertionError("paired difference mismatch")
    return len(pairs)


def check_closed_boundary(signals: pd.DataFrame, opportunities: pd.DataFrame,
                          ledger: pd.DataFrame) -> None:
    for frame, column in [(signals, "signal_time"), (opportunities, "signal_time"),
                          (ledger, "signal_time")]:
        times = pd.to_datetime(frame[column], utc=True)
        if len(times) and times.max() >= pd.Timestamp("2026-01-01", tz="UTC"):
            raise AssertionError("reserved 2026 outcome boundary was opened")


def check_actual_entry_years(ledger, annual):
    checked = 0
    for row in annual.itertuples(index=False):
        view = ledger[(ledger.entry_rule == row.entry_rule) & (ledger.partition == row.partition)
                      & (ledger.poll_minutes == row.poll_minutes) & (ledger.stress == row.stress)
                      & (pd.to_datetime(ledger.entry, utc=True).dt.year == row.entry_year)]
        assert_numeric_row(pd.Series(row._asdict()), independent_metrics(view, 0), "actual entry year")
        checked += 1
    if checked != 32:
        raise AssertionError("actual entry-year inventory incomplete")
    return checked


def check_weekly_intervals(signals, ledger, reported):
    """Rebuild week totals from source signals and admitted books, then use
    bootstrap multiplicity weights rather than the scorer's row-sum sampler."""
    checked = 0
    for partition, start, end in [("historical", "2022-01-01", "2025-01-01"),
                                   ("evaluation", "2025-01-01", "2026-01-01")]:
        weeks = pd.period_range(pd.Timestamp(start).to_period("W-SUN"),
                  (pd.Timestamp(end)-pd.Timedelta(minutes=1)).to_period("W-SUN"), freq="W-SUN")
        original = signals[signals.partition == partition].copy()
        original["week"] = pd.to_datetime(original.signal_time, utc=True).dt.tz_localize(None).dt.to_period("W-SUN")
        for stress in STRESSES:
            values = np.zeros((len(weeks), 5))
            values[:,4] = original.groupby("week").size().reindex(weeks,fill_value=0)
            for i,arm in enumerate(ARMS):
                q = ledger[(ledger.partition == partition) & (ledger.stress == stress)
                           & (ledger.poll_minutes == 1) & (ledger.entry_rule == arm)].copy()
                q["week"] = pd.to_datetime(q.signal_time,utc=True).dt.tz_localize(None).dt.to_period("W-SUN")
                values[:,i] = q.groupby("week").net_return.sum().reindex(weeks,fill_value=0)
                values[:,i+2] = q.groupby("week").size().reindex(weeks,fill_value=0)
            for seed in (20261007,20261010):
                for block in (1,4):
                    n=len(weeks);draws=10000
                    starts=np.random.default_rng(seed).integers(0,n,(draws,int(np.ceil(n/block))))
                    idx=((starts[:,:,None]+np.arange(block))%n).reshape(draws,-1)[:,:n]
                    weights=np.bincount((np.arange(draws)[:,None]*n+idx).ravel(),minlength=draws*n).reshape(draws,n)
                    sample=weights@values
                    def ratio(a,b):return np.divide(a,b,out=np.full(draws,np.nan),where=np.abs(b)>1e-15)
                    im=ratio(sample[:,0],sample[:,2]);rt=ratio(sample[:,1],sample[:,3])
                    distributions={"immediate_mean_net_per_trade":im,"retest_mean_net_per_trade":rt,
                       "difference_mean_net_per_trade":rt-im,
                       "immediate_net_per_original_signal":ratio(sample[:,0],sample[:,4]),
                       "retest_net_per_original_signal":ratio(sample[:,1],sample[:,4]),
                       "difference_net_per_original_signal":ratio(sample[:,1]-sample[:,0],sample[:,4]),
                       "fraction_baseline_net_missed":ratio(sample[:,0]-sample[:,1],sample[:,0])}
                    for metric,dist in distributions.items():
                        valid=dist[np.isfinite(dist)]
                        bounds=np.quantile(valid,[.025,.975]) if len(valid) else [np.nan,np.nan]
                        row=reported[(reported.partition==partition)&(reported.stress==stress)
                          &(reported.seed==seed)&(reported.block_weeks==block)&(reported.metric==metric)]
                        if len(row)!=1 or int(row.iloc[0].draws)!=len(valid) or not np.allclose(row.iloc[0][['low_95','high_95']].astype(float),bounds,rtol=1e-10,atol=1e-12,equal_nan=True):
                            raise AssertionError(f"independent weekly interval mismatch: {partition} {stress} {seed} {block} {metric}")
                        checked+=1
    return checked


def verify(cache: Path, signal_dir: Path, reference_root: Path, runner: Path,
           freeze: Path, record: Path, out: Path, report: Path) -> dict:
    frozen = freeze_gate.verify_freeze(cache, signal_dir, runner, freeze)
    run_record = run_state.read_record(record)
    if not run_record or run_record.get("status") != "complete":
        raise ValueError("independent run record is not complete")
    if run_record.get("dataset_manifest_sha256") != frozen["dataset_manifest_sha256"]:
        raise AssertionError("run record dataset differs from freeze")
    if run_record.get("runner_sha256") != frozen["runner_sha256"]:
        raise AssertionError("run record runner differs from freeze")
    status = read_json(out / "STATUS.json")
    scorer = read_json(out / "VERIFICATION.json")
    if status.get("status") != "complete" or scorer.get("status") != "pass":
        raise ValueError("scorer result is not complete and passing")
    if status.get("scores_2026") is not False or status.get("production_changes") is not False:
        raise AssertionError("result safety flags changed")
    if status.get("verification_sha256") != sha256(out / "VERIFICATION.json"):
        raise AssertionError("status does not bind scorer verification")
    if run_record.get("result_verification_sha256") != sha256(out / "VERIFICATION.json"):
        raise AssertionError("run record does not bind scorer verification")
    hash_checks = check_output_hashes(out, scorer)
    signals = pd.read_csv(out / "frozen_signals.csv")
    opportunities = pd.read_parquet(out / "all_opportunities.parquet")
    ledger = pd.read_parquet(out / "pooled_ledger.parquet")
    rejections = pd.read_csv(out / "rejections.csv")
    pooled = pd.read_csv(out / "pooled_results.csv")
    cells = pd.read_csv(out / "token_side_cells.csv")
    pairs = pd.read_csv(out / "signal_pairs.csv")
    universe = json.loads((cache / "audit.json").read_text())["new_token_symbols"]
    check_closed_boundary(signals, opportunities, ledger)
    if opportunities.duplicated(PAIR + ["entry_rule"]).any():
        raise AssertionError("duplicate opportunity key")
    if ledger.duplicated(PAIR + ["entry_rule"]).any():
        raise AssertionError("duplicate admitted-trade key")
    _, retest = adapter.load_stack(reference_root)
    result = {
        "status": "pass",
        "experiment_id": EXPERIMENT_ID,
        "freeze_sha256": sha256(freeze),
        "run_record_sha256": sha256(record),
        "scorer_verification_sha256": sha256(out / "VERIFICATION.json"),
        "hashed_outputs_checked": hash_checks,
        "cash_paths_recalculated": check_costs(ledger),
        "independent_admission_replays": rebuild_books(
            retest, opportunities, ledger, rejections),
        "pooled_denominator_rows_recalculated": check_denominators(
            signals, opportunities, ledger, pooled),
        "token_side_cells_recalculated": check_token_side_cells(signals, ledger, cells, universe),
        "entry_year_cells_recalculated": check_entry_year_cells(signals, ledger, cells),
        "actual_entry_year_rows_recalculated": check_actual_entry_years(ledger, pd.read_csv(out / "actual_entry_year_results.csv")),
        "weekly_intervals_recalculated": check_weekly_intervals(signals, ledger, pd.read_csv(out / "bootstrap_intervals.csv")),
        "signal_pairs_recalculated": check_signal_pairs(
            signals, opportunities, ledger, pairs),
        "signals": len(signals),
        "opportunity_rows": len(opportunities),
        "ledger_rows": len(ledger),
        "additional_token_2026_outcomes_scored": False,
        "production_changes": False,
        "automatic_deployment": False,
    }
    write_json(report, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--signal-dir", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--runner", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.cache, args.signal_dir, args.reference_root,
                            args.runner, args.freeze, args.record, args.out,
                            args.report), indent=2, sort_keys=True))
