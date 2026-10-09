"""Synthetic outcome tests for the frozen expansion scorer's accounting."""
import pandas as pd
import numpy as np

import run_expansion as runner


def fixture():
    plans = pd.DataFrame([
        dict(partition="historical", symbol="AAAUSDT", side=1, signal_i=1,
             signal_time="2024-01-01T00:00:00Z", entry_boundary=10,
             entry_status="filled", delay_minutes=3),
        dict(partition="historical", symbol="AAAUSDT", side=-1, signal_i=2,
             signal_time="2024-01-08T00:00:00Z", entry_boundary=9,
             entry_status="no_retest", delay_minutes=-1),
    ])
    rows = []
    for signal_i, side, net, reason in [(1, 1, .02, "target"), (2, -1, -.02, "stop")]:
        base = dict(partition="historical", symbol="AAAUSDT", side=side,
                    signal_i=signal_i, stress=2, poll_minutes=1,
                    signal_time=pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=7*(signal_i-1)),
                    entry=pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=7*(signal_i-1)),
                    entry_i=signal_i, exit_bar=pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=7*(signal_i-1), minutes=5),
                    exit_i=signal_i+5, reason=reason, entry_price=10., exit_price=10.,
                    net_return=net, holding_minutes=5, entry_rule="immediate")
        rows.append(base)
    treatment = rows[0].copy()
    treatment.update(entry_rule="retest", entry_i=4,
                     entry=pd.Timestamp("2024-01-01 00:03", tz="UTC"), net_return=.03)
    opportunities = pd.DataFrame(rows + [treatment])
    ledger = opportunities.copy()
    return plans, opportunities, ledger


def test_pairing_zero_denominator_and_missed_winner() -> None:
    plans, opportunities, ledger = fixture()
    pairs = runner.pair_signals(opportunities, ledger, plans)
    assert pairs.retest_realized_net.tolist() == [.03, 0]
    assert np.allclose(pairs.delta_realized_net, [.01, .02], rtol=0, atol=1e-15)
    reports = runner.comparison_tables(pairs)
    contrast = reports["contrasts"].iloc[0]
    assert np.isclose(contrast.immediate_net_per_original_signal, 0)
    assert np.isclose(contrast.retest_net_per_original_signal, .015)
    missed = reports["missed_winners"]
    assert missed.missed_baseline_target_winners.sum() == 0
    assert missed.baseline_stops_avoided.sum() == 1


def test_every_token_side_cell_including_empty() -> None:
    plans, opportunities, ledger = fixture()
    signals = plans.copy()
    pooled, cells = runner.summary_tables(signals, opportunities, ledger)
    # One symbol, two sides, two arms, two polls, two periods, two costs.
    assert len(cells[cells.symbol != "ALL"]) == 32
    empty = cells[(cells.partition == "evaluation") & (cells.symbol == "AAAUSDT")]
    assert (empty.original_signals == 0).all() and (empty.admitted == 0).all()
    assert len(pooled) == 16


def test_bootstrap_is_deterministic_and_has_empty_weeks() -> None:
    plans, opportunities, ledger = fixture()
    pairs = runner.pair_signals(opportunities, ledger, plans)
    first = runner.bootstrap_intervals(pairs, draws=100)
    second = runner.bootstrap_intervals(pairs, draws=100)
    pd.testing.assert_frame_equal(first, second, check_exact=True)
    assert set(first.block_weeks) == {1, 4}
    assert set(first.seed) == {20261007, 20261010}
    assert "difference_net_per_original_signal" in set(first.metric)


def test_classification_requires_provenance() -> None:
    pooled = pd.DataFrame([
        dict(entry_rule="retest", poll_minutes=1, stress=2, partition=p,
             mean_net_per_admitted_trade=.01) for p in runner.PERIODS])
    contrasts = pd.DataFrame([
        dict(poll_minutes=1, stress=2, partition=p,
             difference_mean_net_per_trade=.005) for p in runner.PERIODS])
    intervals = pd.DataFrame([
        dict(partition="evaluation", stress=s, seed=seed, block_weeks=block,
             metric=metric, low_95=.001, high_95=.01)
        for s in runner.STRESSES for seed in (20261007, 20261010)
        for block in (1, 4) for metric in
        ("difference_mean_net_per_trade", "retest_mean_net_per_trade")])
    entries = pd.date_range("2025-01-01", periods=110, freq="3D", tz="UTC")
    ledger = pd.DataFrame(dict(entry_rule="retest", poll_minutes=1, stress=2,
        partition="evaluation", reason="target", entry=entries,
        symbol=[f"T{i%8}USDT" for i in range(110)]))
    loto = pd.DataFrame(dict(entry_rule=["retest"] * 8,
        partition=["evaluation"] * 8, mean_net=[.01] * 8))
    decision = runner.classify(pooled, contrasts, intervals, ledger,
        {"historical_universe_complete": False,
         "historical_funding_schedule_verified": False,
         "classification_history_verified": False}, loto)
    assert decision["positive_point_evidence"] is True
    assert decision["strong_support"] is False
    assert decision["automatic_deployment"] is False
    assert decision["additional_token_2026_outcomes_scored"] is False


if __name__ == "__main__":
    for test in [test_pairing_zero_denominator_and_missed_winner,
                 test_every_token_side_cell_including_empty,
                 test_bootstrap_is_deterministic_and_has_empty_weeks,
                 test_classification_requires_provenance]:
        test()
        print("PASS", test.__name__)
