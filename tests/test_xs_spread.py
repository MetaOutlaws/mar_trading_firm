"""Synthetic tests for the weekly cross-sectional harness.

No real tape is read. The holdout lock, the stop, the per-leg cost, the
point-in-time filter, dollar neutrality and the no-lookahead rule are
checked on constructed bars.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.costs import DEFAULT_COSTS
from research.validate import DEFAULT_CRITERIA
from research.xs_spread.book import (
    apply_schedule,
    is_listed,
    path_for_symbol,
    rebalance_times,
    run_book,
    tercile_weights,
)
from research.xs_spread.cells import (
    COUNTERSIGN_SHA256,
    LOCK_SHA256,
    MEMBERSHIP_PIT_PARQUET_SHA256,
    PERP_1H_SHA256,
    PREREG_SHA256,
    TAPE_C_SUMS_SHA256,
    SIZE_FACTOR_WEEKLY_CAP,
    XS_REALIZED_SKEW_WEEKLY,
)
from research.xs_spread.costs import LEG_COST_RATE, charge_leg, leg_cost_model
from research.xs_spread.harness import HoldoutLockedError, run_window
from research.xs_spread.hashing import sha256_file, source_hashes, write_sha256sums
from research.xs_spread.scorer import (
    BEATS_RANDOM_ALPHA,
    MAX_DRAWDOWN,
    MIN_LEG_TRADES,
    MIN_PROFITABLE_FOLD_RATIO,
    PF_MIN,
    draw_leg,
    permutation_p_value,
    score_book,
    turnover_matched_schedule,
)
from research.xs_spread.signals import market_cap_scores, realized_skew, realized_skew_at
from research.xs_spread.tape import TapeIntegrityError, load_tape, normalize_membership, verify_sums

PACKAGE = Path("research/xs_spread")
T0 = pd.Timestamp("2024-01-01T00:00:00Z")


def _utc(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


def _membership(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows).set_index("symbol")
    for column in ("launch_time", "delist_time", "first_bar", "last_bar"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def _constant_bars(start: str, hours: int, log_ret: float, price0: float = 100.0) -> pd.DataFrame:
    """Hourly bars whose close-to-close log return is constant.

    High/low sit 10 bps off the open/close so a 12% stop does not trip.
    """
    index = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    close = price0 * np.exp(log_ret * np.arange(hours))
    open_ = np.empty(hours)
    open_[0] = price0
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) * 1.001
    low = np.minimum(open_, close) * 0.999
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=index)


def _smash(bars: pd.DataFrame, when: str, scale: float) -> pd.DataFrame:
    """One down-bar inside the lookback, so realized skew is strictly below -1."""
    frame = bars.copy()
    stamp = _utc(when)
    loc = frame.index.get_loc(stamp)
    previous = float(frame["close"].iloc[loc - 1])
    smashed = previous * scale
    frame.iloc[loc, frame.columns.get_loc("close")] = smashed
    frame.iloc[loc, frame.columns.get_loc("low")] = smashed
    return frame


def _flat_from(bars: pd.DataFrame, until: str) -> pd.DataFrame:
    """Continue a series flat, so the hold after the signal does not stop."""
    last = bars.index[-1]
    end = _utc(until)
    if end <= last:
        return bars
    extra_index = pd.date_range(last + pd.Timedelta(hours=1), end, freq="h", tz="UTC")
    price = float(bars["close"].iloc[-1])
    extra = pd.DataFrame(
        {"open": price, "high": price * 1.001, "low": price * 0.999, "close": price},
        index=extra_index,
    )
    return pd.concat([bars, extra])


def _listed_row(symbol: str, first: str = "2023-12-01T00:00:00Z", last: str = "2024-03-01T00:00:00Z") -> dict:
    return {
        "symbol": symbol,
        "launch_time": first,
        "delist_time": pd.NaT,
        "first_bar": first,
        "last_bar": last,
    }


def test_documents_match_the_pinned_digests() -> None:
    """SPEC, the prereg and the countersign are the verbatim attachments."""
    assert sha256_file(PACKAGE / "SPEC.md") == LOCK_SHA256
    assert sha256_file(PACKAGE / "PREREG.md") == PREREG_SHA256
    assert sha256_file(PACKAGE / "COUNTERSIGN.md") == COUNTERSIGN_SHA256
    assert LOCK_SHA256.startswith("974a05ad")
    assert PREREG_SHA256.startswith("41a91e19")
    assert COUNTERSIGN_SHA256.startswith("112c5212")


def test_tape_c_pins_and_house_gates() -> None:
    assert TAPE_C_SUMS_SHA256.startswith("ab447221")
    assert PERP_1H_SHA256.startswith("e974ef5a")
    assert MEMBERSHIP_PIT_PARQUET_SHA256.startswith("3f856213")
    assert DEFAULT_CRITERIA.min_profit_factor == 1.15
    assert PF_MIN == DEFAULT_CRITERIA.min_profit_factor
    assert MIN_LEG_TRADES == DEFAULT_CRITERIA.min_oos_trades == 30
    assert MAX_DRAWDOWN == pytest.approx(DEFAULT_CRITERIA.max_drawdown_pct / 100.0)
    assert MIN_PROFITABLE_FOLD_RATIO == pytest.approx(
        DEFAULT_CRITERIA.min_profitable_fold_ratio / 100.0
    )
    assert BEATS_RANDOM_ALPHA == 0.05
    assert (PACKAGE / "HOLDOUT_LOCK").read_text(encoding="utf-8").startswith("LOCKED")


def test_window_counts() -> None:
    main = rebalance_times("main")
    holdout = rebalance_times("holdout")
    veto = rebalance_times("veto")
    assert len(main) == 90
    assert len(holdout) == 26
    assert len(veto) == 41
    assert main[0] == _utc("2023-10-16")
    assert main[-1] == _utc("2025-06-30")
    assert holdout[0] == _utc("2025-07-07")
    assert holdout[-1] == _utc("2025-12-29")
    assert all(stamp.weekday() == 0 and stamp.hour == 0 for stamp in main)


def test_realized_skew_matches_the_amaya_ratio() -> None:
    """Equal non-zero log returns are +1 or -1. Too few bars is NaN."""
    assert realized_skew(np.full(20, 0.01)) == pytest.approx(1.0)
    assert realized_skew(np.full(20, -0.02)) == pytest.approx(-1.0)
    assert np.isnan(realized_skew(np.zeros(20)))
    bars = _constant_bars("2024-01-01", 220, 0.001)
    as_of = bars.index[-1] + pd.Timedelta(hours=1)
    assert realized_skew_at(bars, as_of, lookback_bars=168, min_bars=150) == pytest.approx(1.0)
    short = bars.iloc[:100]
    assert np.isnan(
        realized_skew_at(short, short.index[-1] + pd.Timedelta(hours=1), lookback_bars=168, min_bars=150)
    )


def test_perturbation_after_t_does_not_change_the_weight_at_t() -> None:
    """A bar that has not closed by t cannot move the tercile weight at t."""
    # Identical log returns inside a sign so the skew ties are exact and the
    # symbol sort, not float noise, decides the tercile.
    names = ["A", "B", "C", "D", "E", "F"]
    returns = [-0.001, -0.001, -0.001, 0.001, 0.001, 0.001]
    panel = {
        name: _flat_from(_constant_bars("2023-12-01", 24 * 40, log_ret), "2024-03-01")
        for name, log_ret in zip(names, returns)
    }
    membership = _membership(
        [_listed_row(name, last="2024-03-01T00:00:00Z") for name in names]
    )
    before = run_book(panel, membership, XS_REALIZED_SKEW_WEEKLY, "main")
    jan1 = before["weights"]
    jan1 = jan1[jan1["rebalance_time"] == T0].sort_values("symbol")
    assert set(jan1.loc[jan1["side"] == "long", "symbol"]) == {"A", "B"}
    assert set(jan1.loc[jan1["side"] == "short", "symbol"]) == {"E", "F"}

    shifted = {}
    for name, bars in panel.items():
        copy = bars.copy()
        future = copy.index >= T0
        copy.loc[future, ["open", "high", "low", "close"]] *= 3.0
        shifted[name] = copy
    after = run_book(shifted, membership, XS_REALIZED_SKEW_WEEKLY, "main")
    after_jan1 = after["weights"]
    after_jan1 = after_jan1[after_jan1["rebalance_time"] == T0].sort_values("symbol")
    assert list(jan1["symbol"]) == list(after_jan1["symbol"])
    assert np.allclose(jan1["weight"], after_jan1["weight"])
    assert np.allclose(jan1["score"], after_jan1["score"])

    # The same bar, moved before t, does change the weight. Otherwise the
    # assertion above could pass on a signal that ignores the tape.
    touched = {name: bars.copy() for name, bars in panel.items()}
    last_closed = T0 - pd.Timedelta(hours=1)
    touched["A"].loc[last_closed, "close"] = touched["A"].loc[last_closed, "close"] * 5.0
    changed = run_book(touched, membership, XS_REALIZED_SKEW_WEEKLY, "main")
    changed_jan1 = changed["weights"]
    changed_jan1 = changed_jan1[changed_jan1["rebalance_time"] == T0]
    assert not np.allclose(
        sorted(jan1["score"]),
        sorted(changed_jan1["score"]),
    )


def test_dollar_neutrality() -> None:
    scores = pd.Series({f"S{i}": float(i) for i in range(9)})
    weights = tercile_weights(scores, long_side="bottom")
    assert weights.sum() == pytest.approx(0.0)
    assert weights[weights > 0].sum() == pytest.approx(1.0)
    assert weights[weights < 0].sum() == pytest.approx(-1.0)
    assert set(weights[weights > 0].index) == {"S0", "S1", "S2"}
    assert set(weights[weights < 0].index) == {"S6", "S7", "S8"}
    assert weights.max() == pytest.approx(weights[weights > 0].iloc[0])
    # Remainder of 9 / 3 is 0, so each leg has 3 equal names.
    assert len(weights) == 6

    names = ["A", "B", "C", "D", "E", "F"]
    panel = {
        name: _flat_from(_constant_bars("2023-12-01", 24 * 32, log_ret), "2024-02-01")
        for name, log_ret in zip(names, [-0.002, -0.001, -0.0004, 0.0004, 0.001, 0.002])
    }
    membership = _membership([_listed_row(name, last="2024-02-01T00:00:00Z") for name in names])
    tables = run_book(panel, membership, XS_REALIZED_SKEW_WEEKLY, "main")
    booked = tables["weights"]
    booked = booked[booked["rebalance_time"] == T0]
    assert booked["weight"].sum() == pytest.approx(0.0)
    assert booked.loc[booked["weight"] > 0, "weight"].sum() == pytest.approx(1.0)
    assert booked.loc[booked["weight"] < 0, "weight"].sum() == pytest.approx(-1.0)


def _paths_frame(panel: dict[str, pd.DataFrame], times: list[pd.Timestamp]) -> pd.DataFrame:
    rows = []
    for t in times:
        t_next = t + pd.Timedelta(days=7)
        for symbol, bars in panel.items():
            path = path_for_symbol(bars, t, t_next, 0.12)
            assert path is not None
            rows.append(
                {
                    "rebalance_time": t,
                    "symbol": symbol,
                    "entry_time": path.entry_time,
                    "entry_open": path.entry_open,
                    "long_reason": path.long.reason,
                    "long_exit_time": path.long.exit_time,
                    "long_exit_price": path.long.exit_price,
                    "long_return": path.long.underlying_return,
                    "short_reason": path.short.reason,
                    "short_exit_time": path.short.exit_time,
                    "short_exit_price": path.short.exit_price,
                    "short_return": path.short.underlying_return,
                }
            )
    return pd.DataFrame(rows)


def _weight_rows(schedule: list[tuple[pd.Timestamp, dict[str, float]]]) -> pd.DataFrame:
    rows = []
    for t, book in schedule:
        for symbol, weight in book.items():
            rows.append(
                {
                    "rebalance_time": t,
                    "symbol": symbol,
                    "side": "long" if weight > 0 else "short",
                    "weight": weight,
                    "score": 0.0,
                }
            )
    return pd.DataFrame(rows)


def test_cost_is_charged_on_every_entry_exit_and_not_on_a_continuation() -> None:
    """0.31% per entry and per exit. A name that stays open pays nothing that week."""
    assert charge_leg(1.0) == pytest.approx(LEG_COST_RATE)
    assert charge_leg(4.0) == pytest.approx(0.0124)
    # The pinned default is 0.31% per round trip, 0.155% per side, and it
    # collects the slip by moving the fill. The cell rate is not that number.
    assert DEFAULT_COSTS.round_trip_cost_pct() == pytest.approx(0.0031)
    assert DEFAULT_COSTS.taker_fee + DEFAULT_COSTS.slippage == pytest.approx(0.00155)
    assert leg_cost_model().entry_price(100.0, "LONG") == pytest.approx(100.0)
    assert "entry_price" not in Path("research/xs_spread/book.py").read_text(encoding="utf-8")

    times = [_utc("2024-01-01"), _utc("2024-01-08"), _utc("2024-01-15")]
    panel = {
        "A": _constant_bars("2023-12-01", 24 * 60, 0.0, price0=100.0),
        "B": _constant_bars("2023-12-01", 24 * 60, 0.0, price0=100.0),
    }
    # B's second Monday open is 10% higher, so week 1 has a known gross.
    b = panel["B"].copy()
    b.loc[b.index >= _utc("2024-01-08"), ["open", "high", "low", "close"]] = (
        b.loc[b.index >= _utc("2024-01-08"), ["open", "high", "low", "close"]] * 1.1
    )
    panel["B"] = b
    paths = _paths_frame(panel, times)
    # Week 1 holds both, week 2 holds both, week 3 (terminal) holds both.
    weights = _weight_rows([(t, {"A": 1.0, "B": -1.0}) for t in times])
    weekly, trades = apply_schedule(weights, paths)
    assert list(weekly["cost"]) == pytest.approx([0.0062, 0.0, 0.0062])
    week1 = trades[trades["rebalance_time"] == times[0]]
    week2 = trades[trades["rebalance_time"] == times[1]]
    week3 = trades[trades["rebalance_time"] == times[2]]
    assert sorted(week1["action"]) == ["entry", "entry"]
    assert week2.empty
    assert sorted(week3["action"]) == ["exit", "exit"]
    assert np.allclose(week1["cost_rate"], 0.0031)
    # B rose 10%. Short weight -1, so the gross spread is -10%, minus two entries.
    assert weekly.loc[0, "gross_spread"] == pytest.approx(-0.10)
    assert weekly.loc[0, "net_spread"] == pytest.approx(-0.10 - 0.0062)
    # Fills are the opens, not a slipped price.
    assert np.allclose(week1["fill_price"], 100.0)


def test_stop_fills_at_the_next_open_and_is_charged_once() -> None:
    """An intrabar breach fills at the next open, not at the 12% stop price."""
    index = pd.to_datetime(
        ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-08 00:00"],
        utc=True,
    )
    # Low prints 80 during the entry bar. Stop level is 88. Next open is 91.
    bars = pd.DataFrame(
        {
            "open": [100.0, 91.0, 100.0],
            "high": [101.0, 92.0, 101.0],
            "low": [80.0, 90.0, 99.0],
            "close": [95.0, 91.0, 100.0],
        },
        index=index,
    )
    path = path_for_symbol(bars, _utc("2024-01-01"), _utc("2024-01-08"), 0.12)
    assert path is not None
    assert path.long.reason == "stop"
    assert path.long.exit_price == pytest.approx(91.0)
    assert path.long.exit_time == _utc("2024-01-01T01:00:00")
    assert path.long.exit_price != pytest.approx(88.0)
    assert path.long.underlying_return == pytest.approx(-0.09)

    # Eleven percent does not stop. The name is held to the next Monday open.
    calm = bars.copy()
    calm.loc[index[0], "low"] = 89.0
    held = path_for_symbol(calm, _utc("2024-01-01"), _utc("2024-01-08"), 0.12)
    assert held is not None
    assert held.long.reason == "hold"
    assert held.long.exit_price == pytest.approx(100.0)

    # A later bar that opens through the stop fills at that open.
    gap_index = pd.to_datetime(
        ["2024-01-01 00:00", "2024-01-01 02:00", "2024-01-08 00:00"],
        utc=True,
    )
    gap = pd.DataFrame(
        {
            "open": [100.0, 80.0, 100.0],
            "high": [101.0, 81.0, 101.0],
            "low": [99.0, 79.0, 99.0],
            "close": [100.0, 80.0, 100.0],
        },
        index=gap_index,
    )
    gapped = path_for_symbol(gap, _utc("2024-01-01"), _utc("2024-01-08"), 0.12)
    assert gapped is not None
    assert gapped.long.reason == "stop"
    assert gapped.long.exit_price == pytest.approx(80.0)
    assert gapped.long.exit_time == _utc("2024-01-01T02:00:00")

    # Short stop is the mirror: a 20% intrabar rally fills at the next open,
    # not at entry * 1.12.
    short_bars = bars.copy()
    short_bars.loc[index[0], ["high", "low"]] = [120.0, 99.0]
    short_path = path_for_symbol(short_bars, _utc("2024-01-01"), _utc("2024-01-08"), 0.12)
    assert short_path is not None
    assert short_path.short.reason == "stop"
    assert short_path.short.exit_price == pytest.approx(91.0)
    assert short_path.short.exit_price != pytest.approx(112.0)

    paths = pd.DataFrame(
        [
            {
                "rebalance_time": _utc("2024-01-01"),
                "symbol": "A",
                "entry_time": path.entry_time,
                "entry_open": path.entry_open,
                "long_reason": path.long.reason,
                "long_exit_time": path.long.exit_time,
                "long_exit_price": path.long.exit_price,
                "long_return": path.long.underlying_return,
                "short_reason": path.short.reason,
                "short_exit_time": path.short.exit_time,
                "short_exit_price": path.short.exit_price,
                "short_return": path.short.underlying_return,
            },
            {
                "rebalance_time": _utc("2024-01-01"),
                "symbol": "B",
                "entry_time": path.entry_time,
                "entry_open": 50.0,
                "long_reason": "hold",
                "long_exit_time": _utc("2024-01-08"),
                "long_exit_price": 50.0,
                "long_return": 0.0,
                "short_reason": "hold",
                "short_exit_time": _utc("2024-01-08"),
                "short_exit_price": 50.0,
                "short_return": 0.0,
            },
        ]
    )
    weights = _weight_rows([(_utc("2024-01-01"), {"A": 1.0, "B": -1.0})])
    weekly, trades = apply_schedule(weights, paths)
    stopped = trades[(trades["symbol"] == "A")]
    assert sorted(stopped["action"]) == ["entry", "stop"]
    assert "exit" not in set(stopped["action"])
    assert stopped.loc[stopped["action"] == "stop", "fill_price"].iloc[0] == pytest.approx(91.0)
    assert weekly.loc[0, "cost"] == pytest.approx(0.0031 * 4)  # A entry+stop, B entry+exit
    assert weekly.loc[0, "n_stops"] == 1


def test_pit_membership_excludes_names_and_delist_exits_at_last_price() -> None:
    """Delisted, unborn, too-young and unknown names stay out. A mid-week delist exits at the last close."""
    t = T0
    listed = pd.Series(
        {
            "launch_time": _utc("2020-01-01"),
            "delist_time": _utc("2024-01-01"),
            "first_bar": _utc("2020-01-01"),
            "last_bar": _utc("2024-01-01"),
        }
    )
    assert is_listed(listed, _utc("2023-12-25"))
    assert not is_listed(listed, t)

    # Constant non-zero log returns all have realized skew of exactly ±1, so a
    # single much larger down-bar is what separates the names. AAA is eligible
    # and the most negative eligible score. The excluded names are even more
    # negative, so a leaked membership filter would put them in the long leg.
    mild = {
        "A": -0.001,
        "B": -0.0005,
        "C": 0.0002,
        "D": 0.0005,
        "E": 0.001,
        "F": 0.002,
        "AAA": -0.0008,
    }
    panel = {
        name: _flat_from(_constant_bars("2023-11-01", 24 * 70, log_ret), "2024-02-15")
        for name, log_ret in mild.items()
    }
    panel["AAA"] = _smash(panel["AAA"], "2023-12-20T12:00:00Z", 0.7)
    for leaked, scale in (("DEAD", 0.25), ("UNBORN", 0.25), ("GHOST", 0.25)):
        panel[leaked] = _smash(
            _flat_from(_constant_bars("2023-11-01", 24 * 70, -0.001), "2024-02-15"),
            "2023-12-20T12:00:00Z",
            scale,
        )
    # YOUNG only has 12 days of bars before t: enough for RSK, not for 31 days.
    panel["YOUNG"] = _smash(
        _flat_from(_constant_bars("2023-12-20", 24 * 40, -0.001), "2024-02-15"),
        "2023-12-28T12:00:00Z",
        0.25,
    )
    # AAA stops printing on Wednesday 11:00 and is delisted that afternoon.
    panel["AAA"] = panel["AAA"].loc[: _utc("2024-01-03T11:00:00")]

    rows = [_listed_row(name, first="2023-11-01T00:00:00Z", last="2024-02-15T00:00:00Z") for name in "ABCDEF"]
    rows.append(
        {
            "symbol": "AAA",
            "launch_time": "2023-11-01T00:00:00Z",
            "delist_time": "2024-01-03T12:00:00Z",
            "first_bar": "2023-11-01T00:00:00Z",
            "last_bar": "2024-01-03T11:00:00Z",
        }
    )
    rows.append(
        {
            "symbol": "DEAD",
            "launch_time": "2023-11-01T00:00:00Z",
            "delist_time": "2023-12-01T00:00:00Z",
            "first_bar": "2023-11-01T00:00:00Z",
            "last_bar": "2024-02-15T00:00:00Z",
        }
    )
    rows.append(
        {
            "symbol": "UNBORN",
            "launch_time": "2024-06-01T00:00:00Z",
            "delist_time": pd.NaT,
            "first_bar": "2023-11-01T00:00:00Z",
            "last_bar": "2024-02-15T00:00:00Z",
        }
    )
    rows.append(
        {
            "symbol": "YOUNG",
            "launch_time": "2023-12-20T00:00:00Z",
            "delist_time": pd.NaT,
            "first_bar": "2023-12-20T00:00:00Z",
            "last_bar": "2024-02-15T00:00:00Z",
        }
    )
    # GHOST is on the tape and not in the membership table.
    tables = run_book(panel, _membership(rows), XS_REALIZED_SKEW_WEEKLY, "main")
    jan1 = tables["weights"][tables["weights"]["rebalance_time"] == t]
    assert set(jan1["symbol"]).isdisjoint({"DEAD", "UNBORN", "YOUNG", "GHOST"})
    assert "AAA" in set(jan1["symbol"])
    exited_path = tables["name_paths"]
    exited_path = exited_path[(exited_path["rebalance_time"] == t) & (exited_path["symbol"] == "AAA")]
    assert exited_path["long_reason"].iloc[0] == "delist"
    last_close = float(panel["AAA"]["close"].iloc[-1])
    assert exited_path["long_exit_price"].iloc[0] == pytest.approx(last_close)
    nxt = tables["weights"][tables["weights"]["rebalance_time"] == _utc("2024-01-08")]
    assert "AAA" not in set(nxt["symbol"])
    delist_trades = tables["leg_trades"]
    delist_trades = delist_trades[(delist_trades["symbol"] == "AAA") & (delist_trades["action"] == "delist")]
    assert len(delist_trades) == 1
    assert delist_trades["cost_rate"].iloc[0] == pytest.approx(0.0031)
    assert delist_trades["fill_price"].iloc[0] == pytest.approx(last_close)


def test_holdout_lock(tmp_path: Path) -> None:
    output = tmp_path / "holdout"
    with pytest.raises(HoldoutLockedError, match="main-output-hash"):
        run_window({}, pd.DataFrame(), XS_REALIZED_SKEW_WEEKLY, "holdout", output)

    main_dir = tmp_path / "main"
    main_dir.mkdir()
    (main_dir / "manifest.json").write_text(
        json.dumps({"window": "main", "cell": "xs_realized_skew_weekly"}) + "\n",
        encoding="utf-8",
    )
    (main_dir / "metrics.json").write_text(json.dumps({"verdict": "FAIL"}) + "\n", encoding="utf-8")
    (main_dir / "note.txt").write_text("synthetic\n", encoding="utf-8")
    write_sha256sums(main_dir)
    digest = sha256_file(main_dir / "SHA256SUMS")

    with pytest.raises(HoldoutLockedError, match="mismatch"):
        run_window(
            {},
            pd.DataFrame(),
            XS_REALIZED_SKEW_WEEKLY,
            "holdout",
            output,
            main_output_hash="0" * 64,
            main_output_dir=main_dir,
        )
    with pytest.raises(HoldoutLockedError, match="not PASS"):
        run_window(
            {},
            pd.DataFrame(),
            XS_REALIZED_SKEW_WEEKLY,
            "holdout",
            output,
            main_output_hash=digest,
            main_output_dir=main_dir,
        )

    (main_dir / "metrics.json").write_text(json.dumps({"verdict": "PASS"}) + "\n", encoding="utf-8")
    (main_dir / "SHA256SUMS").unlink()
    write_sha256sums(main_dir)
    digest = sha256_file(main_dir / "SHA256SUMS")
    names = ["A", "B", "C", "D", "E", "F"]
    panel = {
        name: _flat_from(_constant_bars("2025-06-01", 24 * 30, log_ret), "2026-01-08")
        for name, log_ret in zip(names, [-0.002, -0.001, -0.0002, 0.0002, 0.001, 0.002])
    }
    membership = _membership(
        [_listed_row(name, first="2025-06-01T00:00:00Z", last="2026-01-08T00:00:00Z") for name in names]
    )
    result = run_window(
        panel,
        membership,
        XS_REALIZED_SKEW_WEEKLY,
        "holdout",
        output,
        main_output_hash=digest,
        main_output_dir=main_dir,
    )
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["holdout_unlocked_with_main_hash"] == digest
    assert manifest["metrics_computed"] is False
    assert result["n_weeks"] > 0

    # Scoring a holdout book that never recorded the unlock hash is refused.
    manifest["holdout_unlocked_with_main_hash"] = None
    (output / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    with pytest.raises(HoldoutLockedError, match="does not record"):
        score_book(output, n_perm=2, n_bootstrap=20)


def test_turnover_matched_random_book_keeps_the_realized_churn() -> None:
    names = [f"S{i}" for i in range(9)]
    times = [_utc("2024-01-01") + pd.Timedelta(days=7 * i) for i in range(4)]
    panel = {name: _constant_bars("2023-12-01", 24 * 70, 0.0) for name in names}
    paths = _paths_frame(panel, times)
    schedule = []
    for week, t in enumerate(times):
        long = names[week : week + 3]
        short = names[week + 3 : week + 6]
        book = {symbol: 1.0 / 3.0 for symbol in long}
        book.update({symbol: -1.0 / 3.0 for symbol in short})
        schedule.append((t, book))
    weights = _weight_rows(schedule)
    realized, _ = apply_schedule(weights, paths)
    children = np.random.SeedSequence(20261016).spawn(5)
    for child in children:
        rng = np.random.default_rng(child)
        random_weights = turnover_matched_schedule(weights, paths, rng)
        random_weekly, _ = apply_schedule(random_weights, paths)
        assert list(random_weekly["cost"]) == pytest.approx(list(realized["cost"]))
        prev_long: set[str] = set()
        prev_short: set[str] = set()
        for t in times:
            part = random_weights[random_weights["rebalance_time"] == t]
            long = set(part.loc[part["side"] == "long", "symbol"])
            short = set(part.loc[part["side"] == "short", "symbol"])
            assert long.isdisjoint(short)
            assert len(long) == 3 and len(short) == 3
            realized_part = weights[weights["rebalance_time"] == t]
            realized_long = set(realized_part.loc[realized_part["side"] == "long", "symbol"])
            realized_short = set(realized_part.loc[realized_part["side"] == "short", "symbol"])
            assert len(long - prev_long) == len(realized_long - prev_long_realized(weights, t))
            assert len(short - prev_short) == len(realized_short - prev_short_realized(weights, t))
            prev_long, prev_short = long, short
    # p = (1 + count of random means at least as large) / (n + 1)
    assert permutation_p_value(1.0, np.array([0.0, 0.1, -0.2])) == pytest.approx(1.0 / 4.0)
    # Two of the three random means are >= 0, so p = (1 + 2) / 4.
    assert permutation_p_value(0.0, np.array([0.0, 1.0, -1.0])) == pytest.approx(0.75)


def prev_long_realized(weights: pd.DataFrame, t: pd.Timestamp) -> set[str]:
    times = list(dict.fromkeys(weights["rebalance_time"]))
    pos = times.index(t)
    if pos == 0:
        return set()
    prev = weights[weights["rebalance_time"] == times[pos - 1]]
    return set(prev.loc[prev["side"] == "long", "symbol"])


def prev_short_realized(weights: pd.DataFrame, t: pd.Timestamp) -> set[str]:
    times = list(dict.fromkeys(weights["rebalance_time"]))
    pos = times.index(t)
    if pos == 0:
        return set()
    prev = weights[weights["rebalance_time"] == times[pos - 1]]
    return set(prev.loc[prev["side"] == "short", "symbol"])


def test_draw_leg_replaces_the_requested_count() -> None:
    rng = np.random.default_rng(7)
    eligible = [f"S{i}" for i in range(9)]
    prev = {"S0", "S1", "S2"}
    drawn = draw_leg(prev, eligible, k=3, n_new=1, banned=set(), rng=rng)
    assert len(drawn) == 3
    assert len(drawn - prev) == 1
    assert len(prev - drawn) == 1


def test_size_factor_stub_does_not_run() -> None:
    with pytest.raises(NotImplementedError, match="stub"):
        market_cap_scores({}, T0, SIZE_FACTOR_WEEKLY_CAP)
    with pytest.raises(NotImplementedError, match="(?i)stub"):
        run_book({}, pd.DataFrame(), SIZE_FACTOR_WEEKLY_CAP, "main")


def test_sums_verification(tmp_path: Path) -> None:
    tape = tmp_path / "tape"
    tape.mkdir()
    frame = pd.DataFrame({"symbol": ["BTCUSDT"], "start": [1_700_000_000_000], "open": [1.0], "high": [1.0], "low": [1.0], "close": [1.0]})
    frame.to_parquet(tape / "perp_1h.parquet")
    membership = pd.DataFrame([_listed_row("BTCUSDT")])
    membership.to_parquet(tape / "membership_pit.parquet")
    # SHA256SUMS is written by hashing the two tables. verify_sums(check_pins=False) must pass.
    write_sha256sums(tape)
    report = verify_sums(tape, check_pins=False)
    assert report["n_files"] == 2
    with pytest.raises(TapeIntegrityError, match="Tape C pin"):
        verify_sums(tape, check_pins=True)
    payload = (tape / "perp_1h.parquet").read_bytes()
    (tape / "perp_1h.parquet").write_bytes(payload + b"\x00")
    with pytest.raises(TapeIntegrityError, match="perp_1h.parquet"):
        verify_sums(tape, check_pins=False)


def test_harness_and_scorer_are_separate_hashable_files() -> None:
    tree = ast.parse((PACKAGE / "harness.py").read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert not any("scorer" in name for name in imported)
    hashes = source_hashes()
    assert hashes["harness_sha256"] != hashes["scorer_sha256"]
    assert len(str(hashes["harness_sha256"])) == 64
    assert len(str(hashes["scorer_sha256"])) == 64
    files = hashes["files"]
    assert isinstance(files, dict)
    assert set(files) >= {"harness.py", "scorer.py", "SPEC.md", "PREREG.md", "COUNTERSIGN.md"}


def test_score_synthetic_book_writes_metrics(tmp_path: Path) -> None:
    """The scorer runs on a synthetic book and leaves PF / CI / the random book on disk."""
    names = ["A", "B", "C", "D", "E", "F"]
    panel = {
        name: _flat_from(_constant_bars("2023-12-01", 24 * 40, log_ret), "2024-03-01")
        for name, log_ret in zip(names, [-0.002, -0.001, -0.0003, 0.0003, 0.001, 0.002])
    }
    membership = _membership([_listed_row(name, last="2024-03-01T00:00:00Z") for name in names])
    output = tmp_path / "book"
    run_window(panel, membership, XS_REALIZED_SKEW_WEEKLY, "main", output)
    metrics = score_book(output, n_perm=4, n_bootstrap=80)
    assert metrics["window"] == "main"
    assert metrics["verdict"] in {"PASS", "FAIL"}
    assert metrics["n_permutations"] == 4
    assert "profit_factor" in metrics["gates"]
    assert "week_cluster_ci" in metrics["gates"]
    assert "beats_random" in metrics["gates"]
    assert (output / "metrics.json").is_file()
    assert (output / "random_book.json").is_file()
    assert (output / "SHA256SUMS").is_file()
    # Veto language cannot come back as PASS.
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    manifest["window"] = "veto"
    (output / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    veto = score_book(output, n_perm=2, n_bootstrap=20)
    assert veto["verdict"] in {"VETO", "NO_VETO", "REPORT_ONLY"}
    assert veto["verdict"] != "PASS"
    assert veto["can_rescue_a_fail"] is False


# Tape C perp_1h.parquet, as reported by the box, and membership_pit.csv.
TAPE_C_PERP_COLUMNS = (
    "symbol",
    "bar_open_ts_ms",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "turnover",
)
TAPE_C_MEMBERSHIP_COLUMNS = (
    "symbol",
    "status_now",
    "in_79_tradable",
    "launchTime",
    "delistTime",
    "first_bar",
    "last_bar",
    "perp_bars",
    "perp_missing",
    "perp_gap_count",
    "first_funding",
    "last_funding",
    "funding_n",
    "spot_pair_listed_now",
    "spot_first",
    "spot_last",
    "spot_bars",
    "spot_missing",
    "spot_gap_count",
    "spot_mapped_symbol",
    "spot_mapped_first",
    "spot_mapped_last",
    "spot_mapped_bars",
    "flags",
)


def test_tape_c_column_names_and_funding_flag(tmp_path: Path) -> None:
    """Load a fixture that uses Tape C's column names, and record funding off.

    ``bar_open_ts_ms`` is milliseconds. A value of 1_704_067_200_000 is
    2024-01-01 00:00 UTC, not a nanosecond stamp. Membership uses the
    attached membership_pit.csv header, including an empty delistTime.
    """
    open_ms = 1_704_067_200_000
    hours = 3
    perp = pd.DataFrame(
        {
            "symbol": ["BTCUSDT"] * hours + ["GONEUSDT"] * hours,
            "bar_open_ts_ms": [open_ms + i * 3_600_000 for i in range(hours)] * 2,
            "open": [100.0, 101.0, 102.0, 50.0, 51.0, 49.0],
            "high": [101.0, 102.0, 103.0, 51.0, 52.0, 50.0],
            "low": [99.0, 100.0, 101.0, 49.0, 50.0, 48.0],
            "close": [101.0, 102.0, 103.0, 51.0, 49.0, 48.0],
            "volume": [1.0] * (hours * 2),
            "turnover": [100.0] * (hours * 2),
        }
    )
    assert tuple(perp.columns) == TAPE_C_PERP_COLUMNS
    listed = {
        "symbol": "BTCUSDT",
        "status_now": "Trading",
        "in_79_tradable": True,
        "launchTime": "2023-01-06T02:10Z",
        "delistTime": "",
        "first_bar": "2023-01-06T09:00Z",
        "last_bar": "2026-10-16T05:00Z",
        "perp_bars": 3,
        "perp_missing": 0,
        "perp_gap_count": 0,
        "first_funding": "2023-01-06T08:00Z",
        "last_funding": "2026-10-16T04:00Z",
        "funding_n": 1,
        "spot_pair_listed_now": False,
        "spot_first": "",
        "spot_last": "",
        "spot_bars": 0,
        "spot_missing": "",
        "spot_gap_count": 0,
        "spot_mapped_symbol": "",
        "spot_mapped_first": "",
        "spot_mapped_last": "",
        "spot_mapped_bars": "",
        "flags": "",
    }
    closed = {
        **listed,
        "symbol": "GONEUSDT",
        "status_now": "Closed",
        "in_79_tradable": False,
        "launchTime": "2023-02-24T08:56Z",
        "delistTime": "2024-06-01T00:00Z",
        "first_bar": "2023-02-24T11:00Z",
        "last_bar": "2024-06-01T00:00Z",
    }
    membership_raw = pd.DataFrame([listed, closed])
    assert tuple(membership_raw.columns) == TAPE_C_MEMBERSHIP_COLUMNS

    tape = tmp_path / "tape"
    tape.mkdir()
    perp.to_parquet(tape / "perp_1h.parquet", index=False)
    membership_raw.to_parquet(tape / "membership_pit.parquet", index=False)
    membership_raw.to_csv(tape / "membership_pit.csv", index=False)
    write_sha256sums(tape)

    panel, membership, report = load_tape(tape, check_pins=False)
    assert report["n_files"] == 3
    btc = panel["BTCUSDT"]
    assert list(btc.columns) == ["open", "high", "low", "close"]
    assert btc.index[0] == pd.Timestamp("2024-01-01T00:00:00Z")
    assert btc.index[1] == pd.Timestamp("2024-01-01T01:00:00Z")
    # The csv header, not only the parquet, has to normalize.
    from_csv = normalize_membership(pd.read_csv(tape / "membership_pit.csv"))
    assert from_csv.loc["BTCUSDT", "launch_time"] == pd.Timestamp("2023-01-06T02:10:00Z")
    assert pd.isna(from_csv.loc["BTCUSDT", "delist_time"])
    assert from_csv.loc["BTCUSDT", "first_bar"] == pd.Timestamp("2023-01-06T09:00:00Z")
    assert membership.loc["GONEUSDT", "delist_time"] == pd.Timestamp("2024-06-01T00:00:00Z")
    assert is_listed(membership.loc["BTCUSDT"], pd.Timestamp("2024-01-01T00:00:00Z"))
    assert not is_listed(membership.loc["GONEUSDT"], pd.Timestamp("2024-06-01T00:00:00Z"))

    output = tmp_path / "book"
    run_window(panel, membership, XS_REALIZED_SKEW_WEEKLY, "main", output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["funding_included"] is False
    assert manifest["cost"]["funding_included"] is False
