"""Synthetic tests for xs_bab_btc_weekly. No real tape is read."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.xs_spread.bab import (
    apply_beta_schedule,
    beta_neutral_weights,
    classify_ema_band,
    funding_rate_sum,
    regime_at,
    settlement_times,
)
from research.xs_spread.cells import (
    BAB_LOCK_SHA256,
    BAB_PREREG_SHA256,
    XS_BAB_BTC_WEEKLY,
    XS_REALIZED_SKEW_WEEKLY,
    cost_rates,
)
from research.xs_spread.costs import LEG_COST_RATE, charge_leg, charge_leg_at
from research.xs_spread.harness import HoldoutLockedError, run_window
from research.xs_spread.hashing import sha256_file
from research.xs_spread.scorer import _regime_gate, bab_main_verdict, score_book
from research.xs_spread.signals import btc_beta_at, ols_slope

PACKAGE = Path("research/xs_spread/xs_bab_btc_weekly")


def _utc(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


def _membership(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows).set_index("symbol")
    for column in ("launch_time", "delist_time", "first_bar", "last_bar"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def _listed(symbol: str, first: str, last: str, delist: str | None = None) -> dict:
    return {
        "symbol": symbol,
        "launch_time": first,
        "delist_time": pd.NaT if delist is None else delist,
        "first_bar": first,
        "last_bar": last,
    }


def _bars_from_midnight(midnight: pd.Series) -> pd.DataFrame:
    """Hourly bars whose 23:00 close is the next 00:00 sample price."""
    start = midnight.index[0] - pd.Timedelta(hours=1)
    index = pd.date_range(start, midnight.index[-1], freq="h", tz="UTC")
    close = pd.Series(np.nan, index=index, dtype="float64")
    for stamp, price in midnight.items():
        close.loc[stamp - pd.Timedelta(hours=1)] = float(price)
    close = close.ffill().bfill()
    open_ = close.shift(1)
    open_.iloc[0] = float(close.iloc[0])
    return pd.DataFrame(
        {
            "open": open_.to_numpy(),
            "high": np.maximum(open_, close) * 1.001,
            "low": np.minimum(open_, close) * 0.999,
            "close": close.to_numpy(),
        },
        index=index,
    )


def _midnight_prices(start: str, days: int, daily_log: np.ndarray, price0: float = 100.0) -> pd.Series:
    index = pd.date_range(start, periods=days, freq="D", tz="UTC")
    log_price = np.log(price0) + np.cumsum(daily_log)
    return pd.Series(np.exp(log_price), index=index)


def _funding(symbols: list[str], start: str, end: str, rate: float = 0.0001) -> dict[str, pd.Series]:
    index = pd.date_range(start, end, freq="8h", tz="UTC")
    return {symbol: pd.Series(rate, index=index, dtype="float64") for symbol in symbols}


def _path_row(symbol: str, t: str, long_return: float, short_return: float, funding: float = 0.0) -> dict:
    entry = _utc(t)
    exit_time = entry + pd.Timedelta(days=7)
    return {
        "rebalance_time": entry,
        "symbol": symbol,
        "entry_time": entry,
        "entry_open": 100.0,
        "long_reason": "hold",
        "long_exit_time": exit_time,
        "long_exit_price": 100.0 * (1.0 + long_return),
        "long_return": long_return,
        "short_reason": "hold",
        "short_exit_time": exit_time,
        "short_exit_price": 100.0 * (1.0 + short_return),
        "short_return": short_return,
        "long_funding_sum": funding,
        "short_funding_sum": funding,
    }


def test_prereg_and_lock_bytes() -> None:
    assert sha256_file(PACKAGE / "PREREG.md") == BAB_PREREG_SHA256
    assert sha256_file(PACKAGE / "SPEC.md") == BAB_LOCK_SHA256
    assert BAB_PREREG_SHA256.startswith("bf736a50")
    assert BAB_LOCK_SHA256.startswith("76da2e9e")
    assert XS_BAB_BTC_WEEKLY.mde_d == pytest.approx(0.262)
    assert XS_BAB_BTC_WEEKLY.mde_weeks == 90
    assert XS_BAB_BTC_WEEKLY.leg_cost_rate == pytest.approx(0.0031)
    assert XS_BAB_BTC_WEEKLY.proxy_leg_cost_rate == pytest.approx(0.00181)
    assert XS_BAB_BTC_WEEKLY.btc_sampler_rt == pytest.approx(0.00135)
    assert XS_BAB_BTC_WEEKLY.proxy_cost_label == "proxy, alts unmeasured"
    assert cost_rates(XS_BAB_BTC_WEEKLY) == pytest.approx((0.0031, 0.00181))
    assert cost_rates(XS_REALIZED_SKEW_WEEKLY) == pytest.approx((0.0031,))
    assert XS_BAB_BTC_WEEKLY.funding_included is True
    assert XS_BAB_BTC_WEEKLY.leverage_cap == pytest.approx(3.0)


def test_ols_slope_and_no_lookahead() -> None:
    x = np.array([0.01, -0.02, 0.015, 0.005, -0.01])
    assert ols_slope(2.0 * x, x) == pytest.approx(2.0)
    rng = np.random.default_rng(1)
    btc_r = rng.normal(0.0, 0.02, size=120)
    btc_px = _midnight_prices("2023-08-01", 120, btc_r)
    alt_r = 0.4 * btc_r
    alt_px = _midnight_prices("2023-08-01", 120, alt_r, price0=50.0)
    btc = _bars_from_midnight(btc_px)
    alt = _bars_from_midnight(alt_px)
    as_of = _utc("2023-11-06")
    beta = btc_beta_at(alt, btc, as_of, lookback_days=90, min_pairs=60)
    assert beta == pytest.approx(0.4)

    # A bar that closes after the rebalance cannot move the beta.
    future = alt.copy()
    monday_open = as_of
    future.loc[monday_open, "close"] = future.loc[monday_open, "close"] * 3.0
    assert btc_beta_at(future, btc, as_of, lookback_days=90, min_pairs=60) == pytest.approx(beta)

    # Sunday 23:00 is the Monday 00:00 sample. Moving it changes the beta.
    sunday = as_of - pd.Timedelta(hours=1)
    touched = alt.copy()
    touched.loc[sunday, "close"] = touched.loc[sunday, "close"] * 1.5
    assert btc_beta_at(touched, btc, as_of, lookback_days=90, min_pairs=60) != pytest.approx(beta)

    # Fifty-nine pairs are not enough.
    assert np.isnan(btc_beta_at(alt, btc, _utc("2023-09-15"), lookback_days=90, min_pairs=60))


def test_beta_neutral_scaling_and_the_three_times_cap() -> None:
    scores = pd.Series({"L1": 0.5, "L2": 0.5, "H1": 1.0, "H2": 1.0})
    weights = beta_neutral_weights(scores, ["L1", "L2"], ["H1", "H2"], leverage_cap=3.0)
    w_long = float(weights[weights > 0].sum())
    w_short = float(-weights[weights < 0].sum())
    assert (w_long + w_short) / 2.0 == pytest.approx(1.0)
    assert w_long == pytest.approx(4.0 / 3.0)
    assert w_short == pytest.approx(2.0 / 3.0)
    # Not dollar-neutral. Ex-ante beta is zero when the cap does not bind.
    assert weights.sum() == pytest.approx(w_long - w_short)
    assert weights.sum() != pytest.approx(0.0)
    exposure = float((weights * scores.loc[weights.index]).sum())
    assert exposure == pytest.approx(0.0)

    # mean long beta 0.2 would lever 5x. The cap cuts that to 3 before scaling.
    capped_scores = pd.Series({"L": 0.2, "H": 1.0})
    capped = beta_neutral_weights(capped_scores, ["L"], ["H"], leverage_cap=3.0)
    assert float(capped["L"]) == pytest.approx(1.5)
    assert float(-capped["H"]) == pytest.approx(0.5)
    assert (abs(capped["L"]) + abs(capped["H"])) / 2.0 == pytest.approx(1.0)
    assert float((capped * capped_scores).sum()) != pytest.approx(0.0)


def test_net_exposure_funding_and_both_cost_levels() -> None:
    """Equal underlying returns leave the net dollar exposure in the P&L."""
    t = "2024-01-01"
    weights = pd.DataFrame(
        [
            {"rebalance_time": _utc(t), "symbol": "L", "side": "long", "weight": 4.0 / 3.0, "score": 0.5},
            {"rebalance_time": _utc(t), "symbol": "H", "side": "short", "weight": -2.0 / 3.0, "score": 1.0},
        ]
    )
    # Both legs up 10%. Net long $2/3 earns 10% of that.
    paths = pd.DataFrame(
        [
            _path_row("L", t, 0.10, 0.10, funding=0.0003),
            _path_row("H", t, 0.10, 0.10, funding=0.0003),
        ]
    )
    weekly, trades = apply_beta_schedule(weights, paths, proxy_rate=0.00181)
    assert weekly.loc[0, "gross_spread"] == pytest.approx((4.0 / 3.0 - 2.0 / 3.0) * 0.10)
    # Long pays funding, short receives it. Net funding = -(w_L - w_H) * rate_sum.
    assert weekly.loc[0, "funding"] == pytest.approx(-(4.0 / 3.0 - 2.0 / 3.0) * 0.0003)
    # A one-week window is the last week, so the book enters and liquidates.
    traded = 4.0 / 3.0 + 2.0 / 3.0
    assert weekly.loc[0, "cost"] == pytest.approx(2.0 * charge_leg(traded))
    assert weekly.loc[0, "cost"] == pytest.approx(2.0 * traded * LEG_COST_RATE)
    assert weekly.loc[0, "cost_proxy"] == pytest.approx(2.0 * charge_leg_at(traded, 0.00181))
    assert weekly.loc[0, "net_spread"] == pytest.approx(
        weekly.loc[0, "gross_spread"] + weekly.loc[0, "funding"] - weekly.loc[0, "cost"]
    )
    assert weekly.loc[0, "net_spread_proxy"] == pytest.approx(
        weekly.loc[0, "gross_spread"] + weekly.loc[0, "funding"] - weekly.loc[0, "cost_proxy"]
    )
    assert sorted(trades["action"]) == ["entry", "entry", "exit", "exit"]

    # A continuation whose weight changes pays the rate on the traded delta only.
    second = weights.copy()
    second["rebalance_time"] = _utc("2024-01-08")
    second.loc[second["symbol"] == "L", "weight"] = 1.0
    second.loc[second["symbol"] == "H", "weight"] = -1.0
    third = second.copy()
    third["rebalance_time"] = _utc("2024-01-15")
    paths2 = pd.concat(
        [
            paths,
            pd.DataFrame(
                [
                    _path_row("L", "2024-01-08", 0.0, 0.0),
                    _path_row("H", "2024-01-08", 0.0, 0.0),
                    _path_row("L", "2024-01-15", 0.0, 0.0),
                    _path_row("H", "2024-01-15", 0.0, 0.0),
                ]
            ),
        ],
        ignore_index=True,
    )
    both = pd.concat([weights, second, third], ignore_index=True)
    weekly2, trades2 = apply_beta_schedule(both, paths2, proxy_rate=0.00181)
    week2 = trades2[trades2["rebalance_time"] == _utc("2024-01-08")]
    assert sorted(week2["action"]) == ["rebalance", "rebalance"]
    assert float(week2["traded_notional"].sum()) == pytest.approx(abs(1.0 - 4.0 / 3.0) + abs(1.0 - 2.0 / 3.0))
    assert weekly2.loc[1, "cost"] == pytest.approx(float(week2["traded_notional"].sum()) * LEG_COST_RATE)


def test_missing_funding_is_not_zero_filled() -> None:
    entry = _utc("2024-01-01")
    exit_time = _utc("2024-01-08")
    expected = settlement_times(entry, exit_time)
    assert len(expected) == 21
    rates = pd.Series(0.0001, index=expected)
    assert funding_rate_sum(rates, entry, exit_time) == pytest.approx(0.0021)
    # An observed zero is a print.
    rates.iloc[0] = 0.0
    assert funding_rate_sum(rates, entry, exit_time) == pytest.approx(0.0020)
    # A hole is not a zero.
    gapped = rates.drop(expected[3])
    assert np.isnan(funding_rate_sum(gapped, entry, exit_time))


def test_regime_band_and_gate() -> None:
    assert classify_ema_band(102.0, 100.0) == "BULL"
    assert classify_ema_band(98.0, 100.0) == "BEAR"
    assert classify_ema_band(100.5, 100.0) == "CHOP"
    # Last closed 4h block at Monday 00:00 opened Sunday 20:00.
    index = pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC")
    # Not enough history to label, and a bar after Monday 00:00 is ignored.
    short = pd.DataFrame({"close": [1, 1, 1, 9]}, index=index)
    assert regime_at(short, _utc("2024-01-01")) is None
    weekly = pd.DataFrame(
        {
            "regime": ["BULL"] * 5 + ["BEAR"] * 2 + ["CHOP"] * 5,
            "net_spread": [0.01] * 5 + [-0.02, -0.03] + [-0.01] * 5,
        }
    )
    gate = _regime_gate(weekly)
    assert gate["regimes"]["BULL"]["status"] == "pass"
    assert gate["regimes"]["BEAR"]["status"] == "report_only"
    assert gate["regimes"]["CHOP"]["status"] == "fail"
    assert gate["pass"] is False
    assert bab_main_verdict(official_pass=True, sign_veto=True) == ("VETO", False)
    assert bab_main_verdict(official_pass=False, sign_veto=True) == ("FAIL", False)
    assert bab_main_verdict(official_pass=True, sign_veto=False) == ("PASS", True)


def test_holdout_and_2026_stay_locked() -> None:
    with pytest.raises(HoldoutLockedError, match="Holdout is locked"):
        run_window({}, pd.DataFrame(), XS_BAB_BTC_WEEKLY, "holdout", Path("/tmp/unused-bab-holdout"))
    with pytest.raises(HoldoutLockedError, match="2026 veto is locked"):
        run_window({}, pd.DataFrame(), XS_BAB_BTC_WEEKLY, "veto", Path("/tmp/unused-bab-veto"))


def test_pit_membership_excludes_btc_and_scores_both_costs(tmp_path: Path) -> None:
    rng = np.random.default_rng(2)
    btc_r = rng.normal(0.0, 0.02, size=160)
    start = "2023-08-01"
    last = "2024-01-08"
    betas = {"LOW": 0.4, "MID": 1.0, "HIGH": 1.8, "LEAK": 4.0, "YOUNG": 0.1}
    panel = {"BTCUSDT": _bars_from_midnight(_midnight_prices(start, 160, btc_r, price0=200.0))}
    for name, beta in betas.items():
        panel[name] = _bars_from_midnight(_midnight_prices(start, 160, beta * btc_r, price0=20.0))
    rows = [
        _listed("BTCUSDT", start + "T00:00:00Z", last + "T00:00:00Z"),
        _listed("LOW", start + "T00:00:00Z", last + "T00:00:00Z"),
        _listed("MID", start + "T00:00:00Z", last + "T00:00:00Z"),
        _listed("HIGH", start + "T00:00:00Z", last + "T00:00:00Z"),
        # Delisted before the first main Monday. A leak would short it: beta 4.
        _listed("LEAK", start + "T00:00:00Z", "2023-10-01T00:00:00Z", delist="2023-10-01T00:00:00Z"),
        # Listed, but not enough history.
        _listed("YOUNG", "2023-12-20T00:00:00Z", last + "T00:00:00Z"),
    ]
    membership = _membership(rows)
    symbols = list(panel)
    funding = _funding(symbols, "2023-07-01", "2024-02-01", rate=0.0001)
    # Drop one LEAK print anyway; it must stay out because of PIT, not funding.
    output = tmp_path / "bab"
    result = run_window(
        panel,
        membership,
        XS_BAB_BTC_WEEKLY,
        "main",
        output,
        funding=funding,
    )
    assert result["n_weeks"] > 0
    weights = result["tables"]["weights"]
    assert "BTCUSDT" not in set(weights["symbol"])
    assert "LEAK" not in set(weights["symbol"])
    assert "YOUNG" not in set(weights["symbol"])
    week = weights[weights["rebalance_time"] == weights["rebalance_time"].min()]
    assert set(week.loc[week["side"] == "long", "symbol"]) == {"LOW"}
    assert set(week.loc[week["side"] == "short", "symbol"]) == {"HIGH"}
    w_long = float(week.loc[week["side"] == "long", "weight"].sum())
    w_short = float(-week.loc[week["side"] == "short", "weight"].sum())
    assert (w_long + w_short) / 2.0 == pytest.approx(1.0)
    assert w_long != pytest.approx(w_short)
    weekly = result["tables"]["weekly_returns"]
    assert "net_spread_proxy" in weekly.columns
    assert "funding" in weekly.columns
    assert (weekly["cost"] + 1e-15 >= weekly["cost_proxy"]).all()
    assert (weekly["cost"] > weekly["cost_proxy"]).any()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["funding_included"] is True
    assert manifest["funding_zero_filled"] is False
    assert manifest["hashes_provisional"] is True
    assert manifest["mde_d"] == pytest.approx(0.262)
    assert manifest["cost"]["official_binds_gates"] is True
    assert manifest["cost"]["measured_rt_binds_gates"] is False
    assert manifest["cost"]["measured_rt_label"] == "proxy, alts unmeasured"
    assert manifest["documents"]["prereg_sha256"] == BAB_PREREG_SHA256
    # Remove one funding print on LOW over a week it is held and it leaves the book.
    held = weekly["rebalance_time"].iloc[0]
    hole = funding["LOW"].index[funding["LOW"].index > held][0]
    funding["LOW"] = funding["LOW"].drop(hole)
    again = tmp_path / "bab-hole"
    rerun = run_window(panel, membership, XS_BAB_BTC_WEEKLY, "main", again, funding=funding)
    punched = rerun["tables"]["weights"]
    punched = punched[punched["rebalance_time"] == held]
    assert "LOW" not in set(punched["symbol"])


def test_sign_veto_does_not_rescue_and_random_book_matches_churn(tmp_path: Path) -> None:
    from research.xs_spread.scorer import turnover_matched_beta_schedule

    t0 = _utc("2024-01-01")
    t1 = _utc("2024-01-08")
    scores = pd.DataFrame(
        [
            {"rebalance_time": t, "symbol": symbol, "score": beta}
            for t in (t0, t1)
            for symbol, beta in {
                "A": 0.4,
                "B": 0.5,
                "C": 0.8,
                "D": 1.1,
                "E": 1.4,
                "F": 1.8,
            }.items()
        ]
    )
    # Realized book changes one name per leg.
    realized = [
        ("A", "long", 0.4),
        ("B", "long", 0.5),
        ("E", "short", 1.4),
        ("F", "short", 1.8),
    ]
    realized_2 = [
        ("A", "long", 0.4),
        ("C", "long", 0.8),
        ("D", "short", 1.1),
        ("F", "short", 1.8),
    ]
    rows = []
    for t, book in ((t0, realized), (t1, realized_2)):
        scaled = beta_neutral_weights(
            pd.Series({symbol: beta for symbol, _side, beta in book}),
            [symbol for symbol, side, _beta in book if side == "long"],
            [symbol for symbol, side, _beta in book if side == "short"],
            leverage_cap=3.0,
        )
        for symbol, side, beta in book:
            rows.append(
                {
                    "rebalance_time": t,
                    "symbol": symbol,
                    "side": side,
                    "weight": float(scaled.loc[symbol]),
                    "score": beta,
                }
            )
    weights = pd.DataFrame(rows)
    path_rows = []
    for t in (t0, t1):
        for symbol in ["A", "B", "C", "D", "E", "F"]:
            path_rows.append(_path_row(symbol, str(t)[:10], 0.01, 0.02, funding=0.0001))
    paths = pd.DataFrame(path_rows)
    rng = np.random.default_rng(np.random.SeedSequence(20261016).spawn(1)[0])
    random_weights = turnover_matched_beta_schedule(
        weights, paths, scores, rng, leverage_cap=3.0
    )
    for t, book in ((t0, realized), (t1, realized_2)):
        part = random_weights[random_weights["rebalance_time"] == t]
        assert (part["side"] == "long").sum() == 2
        assert (part["side"] == "short").sum() == 2
        w_long = float(part.loc[part["side"] == "long", "weight"].sum())
        w_short = float(-part.loc[part["side"] == "short", "weight"].sum())
        assert (w_long + w_short) / 2.0 == pytest.approx(1.0)
        betas = scores[scores["rebalance_time"] == t].set_index("symbol")["score"]
        assert float((part.set_index("symbol")["weight"] * betas.loc[part["symbol"]].to_numpy()).sum()) == pytest.approx(0.0)
    # Churn: week 2 replaces one long and one short.
    long0 = set(random_weights[(random_weights["rebalance_time"] == t0) & (random_weights["side"] == "long")]["symbol"])
    long1 = set(random_weights[(random_weights["rebalance_time"] == t1) & (random_weights["side"] == "long")]["symbol"])
    short0 = set(random_weights[(random_weights["rebalance_time"] == t0) & (random_weights["side"] == "short")]["symbol"])
    short1 = set(random_weights[(random_weights["rebalance_time"] == t1) & (random_weights["side"] == "short")]["symbol"])
    assert len(long1 - long0) == 1
    assert len(short1 - short0) == 1

    # A one-week book whose proxy mean flips sign cannot pass.
    weights_one = weights[weights["rebalance_time"] == t0].copy()
    weights_one = weights_one[weights_one["symbol"].isin(["A", "F"])]
    # Force $1 per side. The week is terminal, so each name is entered and exited.
    weights_one.loc[weights_one["side"] == "long", "weight"] = 1.0
    weights_one.loc[weights_one["side"] == "short", "weight"] = -1.0
    paths_one = paths[paths["rebalance_time"] == t0].copy()
    paths_one = paths_one[paths_one["symbol"].isin(["A", "F"])]
    price = 0.01
    paths_one.loc[paths_one["symbol"] == "A", "long_return"] = price
    paths_one.loc[paths_one["symbol"] == "F", "short_return"] = 0.0
    paths_one["long_funding_sum"] = 0.0
    paths_one["short_funding_sum"] = 0.0
    weekly, _trades = apply_beta_schedule(weights_one, paths_one, proxy_rate=0.00181)
    assert weekly.loc[0, "net_spread"] < 0.0
    assert weekly.loc[0, "net_spread_proxy"] > 0.0
    book = tmp_path / "flip"
    # Use the engine writer via a hand-built tables dict and score_book.
    from research.xs_spread.harness import write_outputs

    weekly = weekly.copy()
    weekly["regime"] = ""
    scores_one = scores[scores["rebalance_time"] == t0]
    manifest = {
        "cell": "xs_bab_btc_weekly",
        "window": "main",
        "score_profile": "bab",
        "funding_included": True,
    }
    write_outputs(
        book,
        {
            "weights": weights_one,
            "name_paths": paths_one,
            "weekly_returns": weekly,
            "leg_trades": _trades,
            "scores": scores_one,
        },
        manifest,
    )
    metrics = score_book(book, n_perm=4, n_bootstrap=20)
    assert metrics["measured_rt"]["sign_veto"] is True
    assert metrics["measured_rt"]["rescues_fail"] is False
    assert metrics["verdict"] != "PASS"
    assert metrics["mde"]["d"] == pytest.approx(0.262)
    assert metrics["n_permutations"] == 4
