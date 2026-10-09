"""Synthetic checks for the independent expansion-result verifier."""
import numpy as np
import pandas as pd

import verify_results as verifier


def ledger_fixture() -> pd.DataFrame:
    return pd.DataFrame([
        dict(entry_price=100., entry_fill=100., quote=102.5, exit_price=102.3975,
             reason="target", side=1, slippage_per_side=.001, fees=.00111318625,
             funding=.0001, net_return=.02276181375, stop_price=98., target_price=102.5,
             holding_minutes=10),
        dict(entry_price=100., entry_fill=100., quote=98., exit_price=98.,
             reason="stop", side=1, slippage_per_side=.002, fees=.001089,
             funding=-.0002, net_return=-.020889, stop_price=98., target_price=102.5,
             holding_minutes=5),
    ])


def test_independent_cash_recalculation() -> None:
    assert verifier.check_costs(ledger_fixture()) == 2
    changed = ledger_fixture()
    changed.loc[0, "net_return"] += .001
    try:
        verifier.check_costs(changed)
    except AssertionError as exc:
        assert "net_return" in str(exc)
    else:
        raise AssertionError("changed return passed independent cost check")


def test_completed_and_original_signal_denominators() -> None:
    ledger = ledger_fixture()
    metrics = verifier.independent_metrics(ledger, 4)
    assert metrics["completed_trades"] == 2
    assert metrics["stop_losses"] == 1
    assert np.isclose(metrics["mean_net_per_completed_trade"],
                      ledger.net_return.mean())
    assert np.isclose(metrics["net_per_original_signal"],
                      ledger.net_return.sum() / 4)


def test_reserved_2026_boundary() -> None:
    historical = pd.DataFrame({"signal_time": ["2025-12-31T23:59:00Z"]})
    verifier.check_closed_boundary(historical, historical, historical)
    opened = pd.DataFrame({"signal_time": ["2026-01-01T00:00:00Z"]})
    try:
        verifier.check_closed_boundary(opened, historical, historical)
    except AssertionError as exc:
        assert "2026" in str(exc)
    else:
        raise AssertionError("reserved 2026 boundary passed")


def test_signal_pair_zero_fill_accounting() -> None:
    pairs = pd.DataFrame([
        dict(partition="historical", symbol="AAAUSDT", side=1, signal_i=1,
             stress=stress, poll_minutes=poll,
             immediate_admitted=(stress == 2 and poll == 1),
             retest_admitted=False, net_return_immediate=.02,
             net_return_retest=np.nan,
             immediate_realized_net=.02 if stress == 2 and poll == 1 else 0.,
             retest_realized_net=0.,
             delta_realized_net=-.02 if stress == 2 and poll == 1 else 0.)
        for stress in verifier.STRESSES for poll in verifier.POLLS
    ])
    ledger = pd.DataFrame([
        dict(partition="historical", symbol="AAAUSDT", side=1, signal_i=1,
             stress=2, poll_minutes=1, entry_rule="immediate")
    ])
    signals = pd.DataFrame([{"signal_time": "2024-01-01T00:00:00Z"}])
    opportunities = pairs[verifier.PAIR].copy()
    opportunities["entry_rule"] = "immediate"
    assert verifier.check_signal_pairs(signals, opportunities, ledger, pairs) == 4


if __name__ == "__main__":
    for test in [test_independent_cash_recalculation,
                 test_completed_and_original_signal_denominators,
                 test_reserved_2026_boundary,
                 test_signal_pair_zero_fill_accounting]:
        test()
        print("PASS", test.__name__)
