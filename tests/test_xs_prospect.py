"""Synthetic tests for xs_prospect_value_weekly.

No real tape is read. TK is checked against hand-computed cases. The
countersign hash, the ex-ante funding rule, both cost levels, the regime
gate and the report-only ret60 regression are checked on constructed bars.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.xs_spread.cells import (
    TK_COUNTERSIGN_SHA256,
    TK_LOCK_SHA256,
    TK_PREREG_SHA256,
    TK_PROXY_LEG_COST,
    XS_PROSPECT_VALUE_WEEKLY,
    XS_REALIZED_SKEW_WEEKLY,
)
from research.xs_spread.harness import HoldoutLockedError, countersign_path, run_window
from research.xs_spread.hashing import sha256_file, write_sha256sums
from research.xs_spread.scorer import (
    MAX_DRAWDOWN,
    MIN_PROFITABLE_FOLD_RATIO,
    N_PERMUTATIONS,
    PF_MIN,
    RANDOM_SEED,
    _regime_gate,
    fama_macbeth_tstats,
    momentum_explained_flag,
    partial_ret60_report,
    prospect_main_verdict,
    score_book,
)
from research.xs_spread.signals import (
    TK_ALPHA,
    TK_GAMMA_GAIN,
    TK_GAMMA_LOSS,
    TK_LAMBDA,
    decision_weight,
    prospect_at,
    tk_value,
)
from research.xs_spread.tk import (
    apply_tk_schedule,
    funding_accrual,
    funding_print_before_entry,
)

PACKAGE = Path("research/xs_spread")
CELL_DOCS = PACKAGE / "xs_prospect_value_weekly"


def _utc(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


def _membership(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows).set_index("symbol")
    for column in ("launch_time", "delist_time", "first_bar", "last_bar"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def _listed(symbol: str, *, first: str = "2023-10-01T00:00:00Z", last: str = "2024-01-15T00:00:00Z") -> dict:
    return {
        "symbol": symbol,
        "launch_time": first,
        "delist_time": pd.NaT,
        "first_bar": first,
        "last_bar": last,
    }


def _hourly(start: str, hours: int, log_ret: float, price0: float = 100.0) -> pd.DataFrame:
    """Hourly bars. High and low sit 10 bps off the close so a 12% stop stays quiet."""
    index = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    close = price0 * np.exp(log_ret * np.arange(hours))
    open_ = np.empty(hours)
    open_[0] = price0
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * 1.001
    low = np.minimum(open_, close) * 0.999
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def _funding(start: str, end: str, rate: float = 0.0001) -> pd.Series:
    index = pd.date_range(start, end, freq="8h", tz="UTC")
    return pd.Series(rate, index=index, dtype="float64")


def _hand_weight(probability: float, gamma: float) -> float:
    """The prestated weight, written out for the hand cases. Not tk_value."""
    if probability <= 0.0:
        return 0.0
    if probability >= 1.0:
        return 1.0
    p_term = probability ** gamma
    complement = (1.0 - probability) ** gamma
    return p_term / (p_term + complement) ** (1.0 / gamma)


def test_tk_matches_hand_computed_cases() -> None:
    """Small samples expanded by hand from the frozen TK definition."""
    # One gain: w+(1) = 1, so TK is just the value function.
    assert tk_value(np.array([0.01])) == pytest.approx(0.01 ** TK_ALPHA)
    # One loss: w-(1) = 1, lambda 2.25.
    assert tk_value(np.array([-0.02])) == pytest.approx(-TK_LAMBDA * (0.02 ** TK_ALPHA))
    # Two equal gains. The cumulative weights sum to 1, so TK equals v(x).
    assert tk_value(np.array([0.04, 0.04])) == pytest.approx(0.04 ** TK_ALPHA)
    # Two equal losses likewise.
    assert tk_value(np.array([-0.03, -0.03])) == pytest.approx(-TK_LAMBDA * (0.03 ** TK_ALPHA))

    # Mixed pair, n = 2. Worst loss gets w-(1/2). Best gain gets w+(1/2).
    # v(-0.02) = -2.25 * 0.02^0.88, v(0.01) = 0.01^0.88.
    loss_weight = _hand_weight(0.5, TK_GAMMA_LOSS)
    gain_weight = _hand_weight(0.5, TK_GAMMA_GAIN)
    hand_mixed = (-TK_LAMBDA * (0.02 ** TK_ALPHA)) * loss_weight + (0.01 ** TK_ALPHA) * gain_weight
    assert hand_mixed == pytest.approx(-0.02535890135049534)
    assert tk_value(np.array([0.01, -0.02])) == pytest.approx(hand_mixed)
    assert tk_value(np.array([0.01, -0.02])) == pytest.approx(-0.02535890135049534)

    # Three outcomes: -0.01, 0, +0.01. Zero is a gain with value 0, so it
    # only pushes the best gain's cumulative probability to 1/3.
    # π- = w-(1/3), π+(best) = w+(1/3).
    hand_three = (-TK_LAMBDA * (0.01 ** TK_ALPHA)) * _hand_weight(1.0 / 3.0, TK_GAMMA_LOSS)
    hand_three += (0.01 ** TK_ALPHA) * _hand_weight(1.0 / 3.0, TK_GAMMA_GAIN)
    assert hand_three == pytest.approx(-0.00782248895456416)
    assert tk_value(np.array([-0.01, 0.0, 0.01])) == pytest.approx(hand_three)
    # Lambda > 1, so a symmetric gain/loss pair is a loss in TK units.
    assert tk_value(np.array([-0.01, 0.01])) < 0.0
    assert math.isnan(tk_value(np.array([np.nan])))


def test_probability_weight_at_one_half_has_a_closed_form() -> None:
    """w(1/2) = 2^(-γ - 1/γ + 1). Checked for both frozen gammas."""
    for gamma in (TK_GAMMA_GAIN, TK_GAMMA_LOSS):
        closed = 2.0 ** (-gamma - (1.0 / gamma) + 1.0)
        assert decision_weight(0.5, gamma) == pytest.approx(closed)
    assert decision_weight(0.0, TK_GAMMA_GAIN) == 0.0
    assert decision_weight(1.0, TK_GAMMA_LOSS) == 1.0
    assert decision_weight(0.5, TK_GAMMA_GAIN) == pytest.approx(0.42063935433575617)


def test_last_daily_return_uses_the_sunday_23_bar_and_needs_50() -> None:
    as_of = _utc("2024-01-01T00:00:00Z")  # Monday
    # Two daily closes: Sunday 00:00 from Saturday 23:00, Monday 00:00 from Sunday 23:00.
    bars = _hourly("2023-12-30T23:00:00Z", 26, 0.0, price0=100.0)
    # Saturday 23:00 close = 100 (Sunday 00:00 sample). Sunday 23:00 close = 110.
    saturday = _utc("2023-12-30T23:00:00Z")
    sunday = _utc("2023-12-31T23:00:00Z")
    monday_open = _utc("2024-01-01T00:00:00Z")
    bars.loc[saturday, "close"] = 100.0
    bars.loc[sunday, "close"] = 110.0
    # The Monday 00:00 bar closes at 01:00. Its close must not be the last sample.
    bars.loc[monday_open, "close"] = 999.0
    tk_score, ret60 = prospect_at(bars, as_of, lookback_days=2, min_returns=1)
    assert ret60 == pytest.approx(math.log(110.0 / 100.0))
    assert tk_score == pytest.approx((math.log(1.1)) ** TK_ALPHA)

    # A full history scores. Punching out daily closes until fewer than 50
    # finite returns remain in the 60-day window is a NaN, even though as_of
    # itself is still on the tape.
    full = _hourly("2023-10-01T00:00:00Z", 24 * 120, -0.0002)
    scored, total = prospect_at(full, as_of, lookback_days=60, min_returns=50)
    assert math.isfinite(scored)
    assert math.isfinite(total)
    assert total < 0.0
    thin = full.copy()
    closes_23 = thin.index[(thin.index.hour == 23) & (thin.index < as_of - pd.Timedelta(hours=1))]
    thin.loc[closes_23[-20:], "close"] = np.nan
    missing, _missing_ret = prospect_at(thin, as_of, lookback_days=60, min_returns=50)
    assert math.isnan(missing)


def test_features_ignore_bars_that_have_not_closed() -> None:
    as_of = _utc("2024-01-01T00:00:00Z")
    bars = _hourly("2023-10-01T00:00:00Z", 24 * 120, 0.0001)
    base, base_ret = prospect_at(bars, as_of, lookback_days=60, min_returns=50)
    future = bars.copy()
    # A bar that opens at as_of closes an hour later. Changing it must not move TK.
    future.loc[as_of, ["open", "high", "low", "close"]] = [1.0, 1.0, 1.0, 1.0]
    later = as_of + pd.Timedelta(hours=5)
    future.loc[later, "close"] = 1.0
    moved, moved_ret = prospect_at(future, as_of, lookback_days=60, min_returns=50)
    assert moved == pytest.approx(base)
    assert moved_ret == pytest.approx(base_ret)
    # The Sunday 23:00 close is inside the feature. Changing it must move TK.
    sunday = as_of - pd.Timedelta(hours=1)
    touched = bars.copy()
    touched.loc[sunday, "close"] = float(touched.loc[sunday, "close"]) * 1.5
    changed, _changed_ret = prospect_at(touched, as_of, lookback_days=60, min_returns=50)
    assert changed != pytest.approx(base)


def test_funding_window_and_in_hold_gap() -> None:
    entry = _utc("2024-01-01T00:00:00Z")
    rates = _funding("2023-12-31T00:00:00Z", "2024-01-08T00:00:00Z", rate=0.0001)
    # Sunday 16:00 is inside [entry-8h, entry). Monday 00:00 is not.
    assert funding_print_before_entry(rates, entry)
    only_at_entry = pd.Series([0.0], index=pd.DatetimeIndex([entry]))
    assert funding_print_before_entry(only_at_entry, entry) is False
    too_early = pd.Series([0.0001], index=pd.DatetimeIndex([entry - pd.Timedelta(hours=9)]))
    assert funding_print_before_entry(too_early, entry) is False
    assert funding_print_before_entry(None, entry) is False
    # A zero rate exactly 8h earlier is a print, not a hole.
    zero = pd.Series([0.0], index=pd.DatetimeIndex([entry - pd.Timedelta(hours=8)]))
    assert funding_print_before_entry(zero, entry)

    exit_time = entry + pd.Timedelta(hours=8)
    total, gaps = funding_accrual(rates, entry, exit_time)
    assert total == pytest.approx(0.0001)
    assert gaps == 0
    gapped = rates.drop(exit_time)
    total_gap, n_gaps = funding_accrual(gapped, entry, exit_time)
    assert total_gap == 0.0
    assert n_gaps == 1


def _panel() -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, pd.Series]]:
    start = "2023-10-01T00:00:00Z"
    hours = 24 * 110
    drifts = {
        "BTCUSDT": -0.0004,
        "AAA": -0.0008,
        "BBB": -0.0002,
        "CCC": 0.0001,
        "DDD": 0.0004,
        "EEE": 0.0008,
        "NOFUND": -0.002,
    }
    panel = {symbol: _hourly(start, hours, drift) for symbol, drift in drifts.items()}
    # Crash every name on 2 Jan so a position opened Monday stops.
    crash = _utc("2024-01-02T00:00:00Z")
    for bars in panel.values():
        bars.loc[crash, "low"] = 1.0
        bars.loc[crash, "high"] = 10_000.0
    rows = [_listed(symbol) for symbol in drifts]
    rows.append(
        {
            "symbol": "DEAD",
            "launch_time": "2023-01-01T00:00:00Z",
            "delist_time": "2023-12-01T00:00:00Z",
            "first_bar": "2023-01-01T00:00:00Z",
            "last_bar": "2023-12-01T00:00:00Z",
        }
    )
    rows.append(_listed("YOUNG", first="2023-12-20T00:00:00Z"))
    membership = _membership(rows)
    funding = {
        symbol: _funding("2023-10-01T00:00:00Z", "2024-01-20T00:00:00Z", rate=0.0001)
        for symbol in drifts
        if symbol != "NOFUND"
    }
    # AAA keeps the position but misses the Monday 08:00 settlement.
    funding["AAA"] = funding["AAA"].drop(_utc("2024-01-01T08:00:00Z"))
    return panel, membership, funding


def test_book_is_dollar_neutral_and_obeys_the_funding_rule(tmp_path: Path) -> None:
    panel, membership, funding = _panel()
    output = tmp_path / "main"
    result = run_window(
        panel,
        membership,
        XS_PROSPECT_VALUE_WEEKLY,
        "main",
        output,
        funding=funding,
    )
    assert result["n_weeks"] > 0
    weights = pd.read_csv(output / "weights.csv")
    weekly = pd.read_csv(output / "weekly_returns.csv")
    scores = pd.read_csv(output / "scores.csv")
    trades = pd.read_csv(output / "leg_trades.csv")
    week = weights[weights["rebalance_time"] == "2024-01-01T00:00:00Z"]
    assert not week.empty
    assert set(week["symbol"]).isdisjoint({"NOFUND", "DEAD", "YOUNG"})
    assert "BTCUSDT" in set(scores["symbol"])
    assert week["weight"].sum() == pytest.approx(0.0)
    assert week.loc[week["weight"] > 0, "weight"].sum() == pytest.approx(1.0)
    assert week.loc[week["weight"] < 0, "weight"].sum() == pytest.approx(-1.0)
    # Long the low TK names. AAA's drift is the most negative of the funded names.
    assert set(week.loc[week["side"] == "long", "symbol"]) >= {"AAA"}
    assert int(weekly["n_stops"].sum()) > 0
    assert int(weekly["funding_gap_count"].sum()) > 0
    assert int(weekly["long_funding_gap_count"].sum()) > 0
    jan = weekly[weekly["rebalance_time"] == "2024-01-01T00:00:00Z"].iloc[0]
    # Proxy cost is smaller, so the proxy net is the official net plus the cost gap.
    assert jan["net_spread_proxy"] == pytest.approx(jan["net_spread"] + jan["cost"] - jan["cost_proxy"])
    assert jan["cost_proxy"] < jan["cost"]
    assert np.allclose(trades["cost_rate"].to_numpy(dtype="float64"), 0.0031)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["funding_included"] is True
    assert manifest["funding_zero_filled"] is False
    assert manifest["countersign_sha256"] == sha256_file(CELL_DOCS / "COUNTERSIGN.md")
    assert manifest["countersign_sha256"] == TK_COUNTERSIGN_SHA256
    assert manifest["documents"]["countersign_sha256"] == manifest["countersign_sha256"]
    assert manifest["countersign_sha256"] is not None
    assert manifest["cost"]["official_binds_gates"] is True
    assert manifest["cost"]["measured_rt_binds_gates"] is False
    assert manifest["cost"]["measured_rt_rate_per_leg_trade"] == pytest.approx(0.00158)
    assert manifest["cost"]["btc_sampler_rt"] == pytest.approx(0.00135)
    assert manifest["cost"]["sol_sampler_rt"] == pytest.approx(0.00181)
    assert manifest["live"] == "off"
    metrics = score_book(output, n_perm=4, n_bootstrap=50)
    assert metrics["score_profile"] == "prospect_value"
    assert metrics["n_permutations"] == 4
    assert metrics["random_seed"] == RANDOM_SEED
    assert metrics["measured_rt"]["binds_gates"] is False
    assert metrics["measured_rt"]["rescues_fail"] is False
    assert metrics["ret60_partial"]["binds_gates"] is False
    assert metrics["ret60_partial"]["rescues_or_vetoes"] is False
    assert "tk_alone" in metrics["ret60_partial"]
    assert "tk_partial_ret60" in metrics["ret60_partial"]
    assert "leg_trades_per_year" in metrics["gates"]
    assert "no_losing_regime" in metrics["gates"]
    assert metrics["momentum_explained_binds_gates"] is False
    assert metrics["mde"]["binds_gates"] is False
    assert metrics["mde"]["d"] == pytest.approx(0.262)


def test_missing_countersign_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "COUNTERSIGN.md"
    monkeypatch.setattr(
        "research.xs_spread.harness.countersign_path",
        lambda _config: missing,
    )
    panel, membership, funding = _panel()
    with pytest.raises(FileNotFoundError, match="COUNTERSIGN.md"):
        run_window(
            panel,
            membership,
            XS_PROSPECT_VALUE_WEEKLY,
            "main",
            tmp_path / "out",
            funding=funding,
        )


def test_countersign_sha_is_the_file_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The manifest hash follows the file. A constant is not written instead."""
    path = tmp_path / "COUNTERSIGN.md"
    path.write_bytes(b"different countersign bytes\n")
    monkeypatch.setattr(
        "research.xs_spread.harness.countersign_path",
        lambda _config: path,
    )
    panel, membership, funding = _panel()
    output = tmp_path / "book"
    run_window(panel, membership, XS_PROSPECT_VALUE_WEEKLY, "main", output, funding=funding)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    digest = sha256_file(path)
    assert manifest["countersign_sha256"] == digest
    assert manifest["documents"]["countersign_sha256"] == digest
    assert manifest["countersign_sha256"] != TK_COUNTERSIGN_SHA256
    assert manifest["countersign_sha256"] is not None


def test_holdout_and_2026_stay_shut_without_a_main_pass(tmp_path: Path) -> None:
    panel, membership, funding = _panel()
    with pytest.raises(HoldoutLockedError, match="main-output-hash"):
        run_window(
            panel,
            membership,
            XS_PROSPECT_VALUE_WEEKLY,
            "holdout",
            tmp_path / "holdout",
            funding=funding,
        )
    with pytest.raises(HoldoutLockedError, match="2026"):
        run_window(
            panel,
            membership,
            XS_PROSPECT_VALUE_WEEKLY,
            "veto",
            tmp_path / "veto",
            funding=funding,
        )
    # The skew veto window is unchanged: it is not behind this cell's lock.
    # A prospect cell still refuses 2026 when the supplied main verdict is not PASS.
    main_dir = tmp_path / "main"
    main_dir.mkdir()
    (main_dir / "manifest.json").write_text(
        json.dumps({"window": "main", "cell": "xs_prospect_value_weekly"}) + "\n",
        encoding="utf-8",
    )
    (main_dir / "metrics.json").write_text(json.dumps({"verdict": "FAIL"}) + "\n", encoding="utf-8")
    (main_dir / "note.txt").write_text("synthetic\n", encoding="utf-8")
    write_sha256sums(main_dir)
    digest = sha256_file(main_dir / "SHA256SUMS")
    with pytest.raises(HoldoutLockedError, match="not PASS"):
        run_window(
            panel,
            membership,
            XS_PROSPECT_VALUE_WEEKLY,
            "veto",
            tmp_path / "veto-fail",
            main_output_hash=digest,
            main_output_dir=main_dir,
            funding=funding,
        )


def test_proxy_sign_flip_vetoes_and_cannot_rescue() -> None:
    assert prospect_main_verdict(official_pass=False, sign_veto=False) == ("FAIL", False)
    assert prospect_main_verdict(official_pass=False, sign_veto=True) == ("FAIL", False)
    assert prospect_main_verdict(official_pass=True, sign_veto=True) == ("VETO", False)
    assert prospect_main_verdict(official_pass=True, sign_veto=False) == ("PASS", True)
    assert TK_PROXY_LEG_COST == pytest.approx(0.00158)
    assert TK_PROXY_LEG_COST == pytest.approx((0.00135 + 0.00181) / 2.0)


def test_two_cost_levels_on_a_one_week_book() -> None:
    """Gross sits between the proxy drag and the official drag, so the signs differ."""
    t = _utc("2024-01-01T00:00:00Z")
    weights = pd.DataFrame(
        [
            {"rebalance_time": t, "symbol": "AAA", "side": "long", "weight": 1.0, "score": -1.0, "regime": "BULL"},
            {"rebalance_time": t, "symbol": "EEE", "side": "short", "weight": -1.0, "score": 1.0, "regime": "BULL"},
        ]
    )
    # Entry and a same-week exit. Price P&L is +1% on the long and 0 on the short.
    paths = pd.DataFrame(
        [
            {
                "rebalance_time": t,
                "symbol": "AAA",
                "entry_time": t,
                "entry_open": 100.0,
                "long_reason": "hold",
                "long_exit_time": t + pd.Timedelta(days=7),
                "long_exit_price": 101.0,
                "long_return": 0.01,
                "short_reason": "hold",
                "short_exit_time": t + pd.Timedelta(days=7),
                "short_exit_price": 99.0,
                "short_return": -0.01,
                "long_funding_sum": 0.0,
                "short_funding_sum": 0.0,
                "long_funding_gaps": 1,
                "short_funding_gaps": 0,
            },
            {
                "rebalance_time": t,
                "symbol": "EEE",
                "entry_time": t,
                "entry_open": 100.0,
                "long_reason": "hold",
                "long_exit_time": t + pd.Timedelta(days=7),
                "long_exit_price": 100.0,
                "long_return": 0.0,
                "short_reason": "hold",
                "short_exit_time": t + pd.Timedelta(days=7),
                "short_exit_price": 100.0,
                "short_return": 0.0,
                "long_funding_sum": 0.0,
                "short_funding_sum": 0.0,
                "long_funding_gaps": 0,
                "short_funding_gaps": 2,
            },
        ]
    )
    weekly, trades = apply_tk_schedule(weights, paths, proxy_rate=TK_PROXY_LEG_COST)
    # One week, terminal: entry and exit on each of two names. Notional 1 each.
    assert int(weekly["n_leg_trades"].iloc[0]) == 4
    assert weekly["cost"].iloc[0] == pytest.approx(4 * 0.0031)
    assert weekly["cost_proxy"].iloc[0] == pytest.approx(4 * 0.00158)
    assert weekly["gross_spread"].iloc[0] == pytest.approx(0.01)
    assert weekly["net_spread"].iloc[0] < 0.0
    assert weekly["net_spread_proxy"].iloc[0] > 0.0
    assert weekly["net_exposure"].iloc[0] == pytest.approx(0.0)
    assert int(weekly["long_funding_gap_count"].iloc[0]) == 1
    assert int(weekly["short_funding_gap_count"].iloc[0]) == 2
    assert set(trades["action"]) == {"entry", "exit"}
    with pytest.raises(ValueError, match="zero-fill"):
        apply_tk_schedule(weights, paths.drop(columns=["long_funding_sum"]), proxy_rate=0.00158)


def test_regime_gate_needs_five_weeks_and_the_trade_floor_stays() -> None:
    bear = pd.DataFrame(
        {
            "regime": ["BEAR"] * 5,
            "net_spread": [-0.01, -0.02, 0.001, -0.01, -0.01],
        }
    )
    failed = _regime_gate(bear)
    assert failed["pass"] is False
    assert failed["regimes"]["BEAR"]["status"] == "fail"
    short = bear.iloc[:4]
    assert _regime_gate(short)["pass"] is True
    assert _regime_gate(short)["regimes"]["BEAR"]["status"] == "report_only"
    bull = pd.DataFrame({"regime": ["BULL"] * 5, "net_spread": [0.01] * 5})
    assert _regime_gate(bull)["pass"] is True
    assert _regime_gate(pd.DataFrame({"regime": [""], "net_spread": [-1.0]}))["pass"] is True
    # House gates are not loosened. The extra floors sit on top of them.
    assert PF_MIN >= 1.15
    assert MAX_DRAWDOWN <= 0.25
    assert MIN_PROFITABLE_FOLD_RATIO >= 0.5
    assert N_PERMUTATIONS == 2000
    assert RANDOM_SEED == 20261016
    assert XS_PROSPECT_VALUE_WEEKLY.leg_cost_rate == pytest.approx(0.0031)
    assert XS_PROSPECT_VALUE_WEEKLY.stop_pct == pytest.approx(0.12)
    assert XS_PROSPECT_VALUE_WEEKLY.long_side == "bottom"


def test_ret60_partial_tstat_is_report_only() -> None:
    """Hand series [1, 2, 3]: FM t = 2*sqrt(3), NW lag-1 t = 3*sqrt(2)."""
    stats = fama_macbeth_tstats(np.array([1.0, 2.0, 3.0]))
    assert stats["mean"] == pytest.approx(2.0)
    assert stats["fama_macbeth_t"] == pytest.approx(2.0 * math.sqrt(3.0))
    assert stats["newey_west_lag1_t"] == pytest.approx(3.0 * math.sqrt(2.0))
    assert stats["n_weeks"] == 3

    weeks = []
    for week, shift in enumerate((0.0, 0.01, 0.02)):
        stamp = _utc("2024-01-01T00:00:00Z") + pd.Timedelta(days=7 * week)
        for i, symbol in enumerate(["A", "B", "C", "D", "E", "F"]):
            tk = float(i) + shift
            # Related to TK, and not an affine copy, so the partial regression
            # is not dropped for a singular design.
            ret60 = float(i) * 0.3 + (0.4 if i % 2 else -0.2)
            forward = 0.01 - 0.002 * float(i)
            weeks.append(
                {
                    "rebalance_time": stamp,
                    "symbol": symbol,
                    "score": tk,
                    "ret60": ret60,
                    "forward_return": forward,
                }
            )
    report = partial_ret60_report(pd.DataFrame(weeks))
    assert report["binds_gates"] is False
    assert report["rescues_or_vetoes"] is False
    assert report["tk_alone"]["n_weeks"] == 3
    assert report["tk_partial_ret60"]["n_weeks"] == 3
    # Higher TK lines up with a lower forward return, so the slope is negative.
    assert report["tk_alone"]["mean"] < 0.0
    assert momentum_explained_flag(passed=True, t_stat=0.4) is True
    assert momentum_explained_flag(passed=True, t_stat=1.2) is False
    assert momentum_explained_flag(passed=False, t_stat=0.4) is False
    assert momentum_explained_flag(passed=True, t_stat=None) is False
    verdict_before = "PASS"
    flagged = momentum_explained_flag(passed=True, t_stat=0.2)
    assert flagged is True
    assert verdict_before == "PASS"


def test_frozen_documents_match_their_pins() -> None:
    assert sha256_file(CELL_DOCS / "COUNTERSIGN.md") == TK_COUNTERSIGN_SHA256
    assert TK_COUNTERSIGN_SHA256.startswith("dfc6180d")
    assert sha256_file(CELL_DOCS / "PREREG.md") == TK_PREREG_SHA256
    assert TK_PREREG_SHA256.startswith("2afe8b36")
    assert sha256_file(CELL_DOCS / "SPEC.md") == TK_LOCK_SHA256
    assert TK_LOCK_SHA256.startswith("a712319a")
    assert countersign_path(XS_PROSPECT_VALUE_WEEKLY) == (CELL_DOCS / "COUNTERSIGN.md").resolve()
    # The skew cell is still the original one. This cell does not replace it.
    assert XS_REALIZED_SKEW_WEEKLY.funding_included is False
    assert XS_REALIZED_SKEW_WEEKLY.countersign_relative == ""


def test_running_without_a_funding_tape_refuses(tmp_path: Path) -> None:
    panel, membership, _funding = _panel()
    with pytest.raises(RuntimeError, match="zero-fill"):
        run_window(panel, membership, XS_PROSPECT_VALUE_WEEKLY, "main", tmp_path / "book")
