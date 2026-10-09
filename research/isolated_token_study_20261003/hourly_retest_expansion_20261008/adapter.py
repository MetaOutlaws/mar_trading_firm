"""Frozen new-token adapter and reference-parity gate.

The adapter reuses the reviewed approved-signal and retest implementations from
the cumulative checkpoint.  It can generate 2022-2025 signal contexts from an
audited cache, but it deliberately contains no reporting, optimization or 2026
new-token path.  Reference parity must pass before a scoring runner is frozen.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


BEGIN = "2022-01-01"
EVALUATION = "2025-01-01"
END = "2026-01-01"
REFERENCE_END = "2026-10-02 16:00"
REFERENCE_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
KEYS = ["partition", "symbol", "side", "signal_i"]
PAIR = KEYS + ["stress", "poll_minutes"]
NUMERIC_CONTEXT = [
    "entry_boundary",
    "prior_atr",
    "filter_crsi",
    "btc24",
    "efficiency24_before_signal",
    "extension_atr",
]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str))


def load_stack(reference_root: Path):
    """Load the exact checkpoint modules without copying or modifying them."""
    root = reference_root.resolve()
    required = [
        root / "hourly_reserved_2026_20261008" / "run_replication_2026.py",
        root / "hourly_retest_entry_20261008" / "run_retest.py",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"reference checkpoint source missing: {missing}")
    for folder in [
        root / "hourly_reserved_2026_20261008",
        root / "hourly_retest_entry_20261008",
    ]:
        name = str(folder)
        if name not in sys.path:
            sys.path.insert(0, name)
    replication = importlib.import_module("run_replication_2026")
    retest = importlib.import_module("run_retest")
    return replication, retest


def partition_of(index: pd.DatetimeIndex, include_reference_2026: bool) -> np.ndarray:
    values = np.full(len(index), "", dtype=object)
    values[(index >= pd.Timestamp(BEGIN, tz="UTC")) & (index < pd.Timestamp(EVALUATION, tz="UTC"))] = "historical"
    values[(index >= pd.Timestamp(EVALUATION, tz="UTC")) & (index < pd.Timestamp(END, tz="UTC"))] = "evaluation"
    if include_reference_2026:
        values[(index >= pd.Timestamp(END, tz="UTC")) & (index < pd.Timestamp(REFERENCE_END, tz="UTC"))] = "reserved_replication"
    return values


def audited_membership(cache: Path) -> tuple[dict, pd.DataFrame, list[str]]:
    audit_path = cache / "audit.json"
    if not audit_path.is_file():
        raise ValueError("audited cache is missing audit.json")
    audit = json.loads(audit_path.read_text())
    if audit.get("status") != "usable_provisional":
        raise ValueError("audited cache has not passed the execution coverage gate")
    if audit.get("scores_2026") is not False or audit.get("outcomes_scored") is not False:
        raise ValueError("audited cache does not preserve outcome-blind status")
    rows = json.loads((cache / "membership.json").read_text())
    member = pd.DataFrame(rows)
    required = {"month", "symbol", "rank"}
    if not required.issubset(member.columns) or member.empty:
        raise ValueError("audited membership schema is incomplete")
    if "selected" not in member:
        member["selected"] = True
    else:
        member["selected"] = member["selected"].fillna(False).astype(bool)
    member["eligible"] = member["selected"]
    member = member[member.eligible].copy()
    symbols = sorted(member.symbol.unique())
    if set(symbols) & REFERENCE_SYMBOLS:
        raise ValueError("reference symbols may not enter primary new-token membership")
    if set(symbols) != set(audit.get("new_token_symbols", [])):
        raise ValueError("audited membership differs from audit.json")
    return audit, member, symbols


def signal_contexts(
    cache: Path,
    runtime: Path,
    reference_root: Path,
    out: Path,
) -> dict:
    """Build only causal 2022-2025 contexts; do not calculate trade outcomes."""
    replication, _ = load_stack(reference_root)
    audit, member, symbols = audited_membership(cache)
    btc_candles, _ = replication.load(cache, "BTCUSDT", END)
    btc = replication.br.hourly_context(btc_candles)
    btc_ohlcv = btc_candles.resample("h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    all_contexts = []
    verification = []
    for symbol in symbols:
        candles, funding = replication.load(cache, symbol, END)
        raw, checks = replication.contexts(
            candles,
            funding,
            btc,
            btc_ohlcv,
            symbol,
            member,
            BEGIN,
            END,
            runtime,
        )
        raw = raw.copy()
        raw["partition"] = partition_of(raw.index, False)
        raw["signal_i"] = raw.entry_i.astype(int)
        raw["signal_time"] = raw.entry
        if (raw.index >= pd.Timestamp(END, tz="UTC")).any():
            raise AssertionError("reserved 2026 context escaped the adapter boundary")
        all_contexts.append(raw)
        verification.append({"symbol": symbol, **checks})
    contexts = pd.concat(all_contexts).sort_values(["entry", "symbol", "side"])
    selected = contexts[contexts.passes_approved].copy()
    out.mkdir(parents=True, exist_ok=False)
    contexts.to_parquet(out / "signal_contexts.parquet", index=False)
    selected.to_parquet(out / "frozen_signals.parquet", index=False)
    result = {
        "status": "pass",
        "experiment_id": "H-RETEST-EXPANSION-01",
        "symbols": symbols,
        "context_rows": len(contexts),
        "selected_signals": len(selected),
        "runtime_parity": verification,
        "scores_2026": False,
        "trade_outcomes_scored": False,
        "audit_status": audit["status"],
    }
    write_json(out / "VERIFICATION.json", result)
    return result


def _generated_reference_signals(replication, retest, cache: Path, runtime: Path):
    member = replication.membership(cache, BEGIN, REFERENCE_END)
    btc_candles, _ = replication.load(cache, "BTCUSDT", REFERENCE_END)
    btc = replication.br.hourly_context(btc_candles)
    btc_ohlcv = btc_candles.resample("h").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    )
    generated = []
    runtime_checks = []
    for symbol in replication.SYMBOLS:
        candles, funding = replication.load(cache, symbol, REFERENCE_END)
        raw, checks = replication.contexts(
            candles,
            funding,
            btc,
            btc_ohlcv,
            symbol,
            member,
            BEGIN,
            REFERENCE_END,
            runtime,
        )
        raw = raw[raw.passes_approved].copy()
        raw["partition"] = partition_of(raw.index, True)
        raw["signal_i"] = raw.entry_i.astype(int)
        raw["signal_time"] = raw.entry
        generated.append(raw)
        runtime_checks.append({"symbol": symbol, **checks})
    observed = pd.concat(generated).sort_values(KEYS).reset_index(drop=True)
    _, reference_raw, _ = retest.verified_reference(cache, runtime)
    expected = retest.signals_of(reference_raw).sort_values(KEYS).reset_index(drop=True)
    assert len(observed) == len(expected) == 69
    pd.testing.assert_frame_equal(
        observed[KEYS + ["signal_time"]],
        expected[KEYS + ["signal_time"]],
        check_exact=True,
    )
    for column in NUMERIC_CONTEXT:
        if not np.allclose(observed[column], expected[column], rtol=1e-11, atol=1e-9):
            raise AssertionError(f"reference context mismatch: {column}")
    return expected, runtime_checks


def reference_parity(cache: Path, runtime: Path, reference_root: Path, out: Path) -> dict:
    """Rebuild the known 69 signals and both complete reference ledgers."""
    replication, retest = load_stack(reference_root)
    signals, runtime_checks = _generated_reference_signals(replication, retest, cache, runtime)
    _, baseline, reference_immediate = retest.verified_reference(cache, runtime)
    saved = pd.read_parquet(reference_root / "hourly_retest_entry_20261008" / "results_v1" / "pooled_ledger.parquet")
    saved_plans = pd.read_parquet(reference_root / "hourly_retest_entry_20261008" / "results_v1" / "entry_plans.parquet")

    baseline_rebuilt = []
    treatment = []
    plans = []
    baseline_paths = treatment_paths = selections = prefix_checks = 0
    for symbol in replication.SYMBOLS:
        for limit, parts in [
            (END, ["historical", "evaluation"]),
            (REFERENCE_END, ["reserved_replication"]),
        ]:
            candles, funding = retest.load(cache, symbol, limit)
            tape = retest.base.Tape(candles, funding)
            for _, row in baseline[(baseline.symbol == symbol) & baseline.partition.isin(parts)].iterrows():
                rebuilt = retest.replay_fill(candles, funding, tape, row, int(row.signal_i))
                pd.testing.assert_series_equal(row, rebuilt[row.index], check_names=False, check_exact=True)
                baseline_rebuilt.append(rebuilt)
                baseline_paths += 1
            for _, signal in signals[(signals.symbol == symbol) & signals.partition.isin(parts)].iterrows():
                signal_i = int(signal.signal_i)
                side = int(signal.side)
                endpoint = int(
                    candles.index.searchsorted(pd.Timestamp(retest.PERIODS[signal.partition][1], tz="UTC"))
                )
                plan = retest.select_entry(
                    tape.h,
                    tape.l,
                    tape.cl,
                    signal_i,
                    endpoint,
                    side,
                    signal.entry_boundary,
                )
                sequential = retest.sequential_entry(
                    tape.h,
                    tape.l,
                    tape.cl,
                    signal_i,
                    endpoint,
                    side,
                    signal.entry_boundary,
                )
                assert plan == sequential
                selections += 1
                truncation = min(endpoint, signal_i + 61)
                assert plan == retest.select_entry(
                    tape.h[:truncation],
                    tape.l[:truncation],
                    tape.cl[:truncation],
                    signal_i,
                    truncation,
                    side,
                    signal.entry_boundary,
                )
                prefix_checks += 1
                plans.append({**{key: signal[key] for key in KEYS}, **plan})
                if plan["entry_status"] != "filled":
                    continue
                rows = baseline[
                    (baseline.symbol == symbol)
                    & (baseline.partition == signal.partition)
                    & (baseline.side == side)
                    & (baseline.signal_i == signal_i)
                ]
                assert len(rows) == 4
                for _, row in rows.iterrows():
                    rebuilt = retest.replay_fill(
                        candles, funding, tape, row, int(plan["planned_entry_i"])
                    )
                    rebuilt["entry_rule"] = "retest"
                    rebuilt["arm"] = "retest"
                    rebuilt["delay_minutes"] = plan["delay_minutes"]
                    treatment.append(rebuilt)
                    treatment_paths += 1

    assert baseline_paths == 276 and treatment_paths == 168
    observed_plans = pd.DataFrame(plans).sort_values(KEYS).reset_index(drop=True)
    expected_plans = saved_plans.sort_values(KEYS).reset_index(drop=True)
    plan_columns = KEYS + [
        "planned_entry_i",
        "touch_i",
        "confirm_i",
        "entry_status",
        "delay_minutes",
    ]
    pd.testing.assert_frame_equal(
        observed_plans[plan_columns], expected_plans[plan_columns], check_exact=True
    )

    rebuilt_baseline = pd.DataFrame(baseline_rebuilt).assign(
        entry_rule="immediate", arm="immediate", delay_minutes=0
    )
    rebuilt_treatment = pd.DataFrame(treatment)
    opportunities = pd.concat([rebuilt_baseline, rebuilt_treatment], ignore_index=True)
    ledgers = []
    admissions = 0
    for rule in ["immediate", "retest"]:
        for poll in retest.POLLS:
            for partition in retest.PERIODS:
                for stress in [1, 2]:
                    group = opportunities[
                        (opportunities.entry_rule == rule)
                        & (opportunities.poll_minutes == poll)
                        & (opportunities.partition == partition)
                        & (opportunities.stress == stress)
                    ]
                    admitted, _ = retest.admission(group)
                    expected = saved[
                        (saved.entry_rule == rule)
                        & (saved.poll_minutes == poll)
                        & (saved.partition == partition)
                        & (saved.stress == stress)
                    ]
                    stable = [column for column in expected.columns if column in admitted.columns]
                    pd.testing.assert_frame_equal(
                        admitted[stable].sort_values(PAIR).reset_index(drop=True),
                        expected[stable].sort_values(PAIR).reset_index(drop=True),
                        check_exact=True,
                    )
                    if rule == "immediate":
                        old = reference_immediate[
                            (reference_immediate.poll_minutes == poll)
                            & (reference_immediate.partition == partition)
                            & (reference_immediate.stress == stress)
                        ]
                        original_columns = [c for c in old.columns if c != "arm"]
                        pd.testing.assert_frame_equal(
                            admitted[original_columns].sort_values(PAIR).reset_index(drop=True),
                            old[original_columns].sort_values(PAIR).reset_index(drop=True),
                            check_exact=True,
                        )
                    ledgers.append(admitted)
                    admissions += 1
    ledger = pd.concat(ledgers, ignore_index=True)
    assert len(ledger) == len(saved) == 420

    out.mkdir(parents=True, exist_ok=False)
    result = {
        "status": "pass",
        "experiment_id": "H-RETEST-EXPANSION-01",
        "reference_signals": len(signals),
        "runtime_signal_checks": runtime_checks,
        "baseline_paths_and_costs": baseline_paths,
        "treatment_entry_selections": selections,
        "treatment_prefix_checks": prefix_checks,
        "treatment_paths_and_costs": treatment_paths,
        "admission_replays": admissions,
        "ledger_rows": len(ledger),
        "immediate_ledger_rows": int((ledger.entry_rule == "immediate").sum()),
        "retest_ledger_rows": int((ledger.entry_rule == "retest").sum()),
        "new_token_outcomes_scored": False,
        "scores_2026": False,
        "production_changes": False,
    }
    write_json(out / "VERIFICATION.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["reference-parity", "signal-contexts"])
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--reference-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "reference-parity":
        result = reference_parity(args.cache, args.runtime, args.reference_root, args.out)
    else:
        result = signal_contexts(args.cache, args.runtime, args.reference_root, args.out)
    print(json.dumps(result, indent=2, default=str))
