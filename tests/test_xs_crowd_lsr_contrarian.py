"""Synthetic checks for xs_crowd_lsr_contrarian v2.

No market tape is read. The cases are the frozen rules: point-in-time
usability, the stable (L, symbol) tie-break, the five dropped Mondays,
a thin leg, frozen sizing, the 12% close-only stop, funding that books 0
when a name has no prints, 0.31% in and out, the regime gate, the random
book's seed, and a missing Monday open blocking the run.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.xs_crowd_lsr_contrarian import hashing, pins
from research.xs_crowd_lsr_contrarian.book import (
    RatioStore,
    Schedule,
    TradeWeek,
    build_schedule,
    run_strategy,
)
from research.xs_crowd_lsr_contrarian.calendar import (
    WindowError,
    as_utc,
    assert_dropped_monday_list,
    exit_cap,
    is_dropped_monday,
    rebalance_mondays,
    veto_only_mondays,
)
from research.xs_crowd_lsr_contrarian.harness import (
    BOOK_STAGE_FILES,
    HoldoutLockedError,
    assert_holdout_allowed,
    print_run_hashes,
    run_prepared,
    stage_digest,
    veto_only_frame,
)
from research.xs_crowd_lsr_contrarian.hashing import HashSeedError, assert_documents, sha256_file
from research.xs_crowd_lsr_contrarian.paths import (
    BlockedRun,
    funding_over_hold,
    path_for_side,
    require_paths,
)
from research.xs_crowd_lsr_contrarian.pins import (
    CELL,
    DROPPED_MONDAYS,
    GROSS,
    LEG,
    MAIN_COMMAND,
    MAX_DRAWDOWN,
    N_RANDOM_DRAWS,
    OFFICIAL_LEG_COST,
    RANDOM_SEED,
)
from research.xs_crowd_lsr_contrarian.random_book import random_book_means
from research.xs_crowd_lsr_contrarian.regime import (
    classify_ema_band,
    four_hour_closes,
    regime_gate,
    regimes_for,
)
from research.xs_crowd_lsr_contrarian.scorer import ScoreError, evaluate, max_drawdown
from research.xs_crowd_lsr_contrarian.signal import assign_terciles, leg_weights, mean_buy_ratio, usable_at
from research.xs_crowd_lsr_contrarian.tape import clip_loaded_inputs, load_ratio_frame

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _symbols(n: int) -> list[str]:
    return [f"S{i:02d}" for i in range(n)]


def _levels(symbols: list[str]) -> dict[str, float]:
    return {symbol: (index + 1) / 100.0 for index, symbol in enumerate(symbols)}


def _membership(symbols: list[str], first: str, last: str) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        rows.append(
            {
                "symbol": symbol,
                "launch_time": pd.Timestamp(first, tz="UTC"),
                "delist_time": pd.NaT,
                "first_bar": pd.Timestamp(first, tz="UTC"),
                "last_bar": pd.Timestamp(last, tz="UTC"),
            }
        )
    return pd.DataFrame(rows).set_index("symbol")


def _ratios(symbols: list[str], levels: dict[str, float], start: str, end: str) -> pd.DataFrame:
    days = pd.date_range(start, end, freq="1D", tz="UTC")
    rows = [
        (symbol, day, levels[symbol])
        for symbol in symbols
        for day in days
    ]
    return pd.DataFrame(rows, columns=["symbol", "ts", "buy_ratio"])


def _flat_bars(start: pd.Timestamp, end: pd.Timestamp, price: float = 100.0) -> pd.DataFrame:
    """Flat closes with wicks that would stop the book if wicks counted."""
    index = pd.date_range(start, end, freq="1h", tz="UTC")
    n = len(index)
    return pd.DataFrame(
        {
            "open": np.full(n, price),
            "high": np.full(n, price * 1.5),
            "low": np.full(n, price * 0.5),
            "close": np.full(n, price),
        },
        index=index,
    )


def _week(
    t: pd.Timestamp,
    symbols: list[str],
    levels: dict[str, float],
    bars: pd.DataFrame,
    *,
    rates: dict[str, pd.Series] | None = None,
    long: list[str] | None = None,
    short: list[str] | None = None,
) -> TradeWeek:
    t = as_utc(t)
    t_next = t + pd.Timedelta(days=7)
    scored = [(symbol, levels[symbol]) for symbol in symbols]
    if long is None or short is None:
        long, short, k = assign_terciles(scored)
    else:
        k = len(long)
    weights = leg_weights(long, short, LEG)
    paths = {}
    for symbol in symbols:
        series = None if rates is None else rates.get(symbol)
        paths[symbol] = require_paths(symbol, t, bars, t_next, series)
    ordered = sorted(scored, key=lambda row: row[0].encode("ascii"))
    ordered.sort(key=lambda row: (row[1], row[0].encode("ascii")))
    return TradeWeek(
        t=t,
        t_next=t_next,
        weights=weights,
        paths=paths,
        scores=dict(scored),
        eligible_order=[symbol for symbol, _level in ordered],
        regime=None,
        n_valid=len(scored),
        k=k,
        long=list(long),
        short=list(short),
        status={symbol: "Trading" for symbol in symbols},
    )


def _coverage() -> dict[str, object]:
    return {"leg_mean_fill": False, "missing_books_zero": True, "names_with_no_funding_data": []}


@pytest.fixture(scope="module")
def flat_main():
    """Full main calendar, 30 names, flat prices, no funding prints."""
    symbols = _symbols(30)
    levels = _levels(symbols)
    membership = _membership(symbols, "2023-08-01", "2025-07-07")
    ratios = RatioStore.from_frame(_ratios(symbols, levels, "2023-08-01", "2025-07-06"))
    bars = _flat_bars(pd.Timestamp("2023-08-01", tz="UTC"), pd.Timestamp("2025-07-07", tz="UTC"))
    panel = {symbol: bars for symbol in symbols}
    schedule = build_schedule(panel, membership, ratios, {}, {}, "main", None)
    sim = run_strategy(schedule)
    weekly = pd.DataFrame(sim.weekly)
    return {"schedule": schedule, "weekly": weekly, "name_pnl": pd.DataFrame(sim.name_pnl)}


# ---------------------------------------------------------------------------
# Point in time, raw tape, tie-break
# ---------------------------------------------------------------------------


def test_pit_usability_requires_both_halves():
    t = pd.Timestamp("2024-06-10", tz="UTC")
    assert usable_at(t - pd.Timedelta(days=1), t)
    assert usable_at(t - pd.Timedelta(days=7), t)
    # Stamped at t, the period has not closed.
    assert not usable_at(t, t)
    # ts < t is not enough when the daily period is still open.
    assert not usable_at(t - pd.Timedelta(hours=20), t)
    # Older than the 7-day window.
    assert mean_buy_ratio([(t - pd.Timedelta(days=8), 0.2)] * 1, t) is None
    stamps = [(t - pd.Timedelta(days=day), 0.10) for day in range(1, 6)]
    assert mean_buy_ratio(stamps, t) == pytest.approx(0.10)
    # Four closed days is not a feature.
    assert mean_buy_ratio(stamps[:4], t) is None


def test_raw_buy_ratio_is_not_rescaled(tmp_path: Path):
    """0.10 stays 0.10. The 0.35 + 0.30 restatement is not applied."""
    kept = int(pd.Timestamp("2024-06-01", tz="UTC").timestamp() * 1000)
    dropped = int(pd.Timestamp("2026-01-01", tz="UTC").timestamp() * 1000)
    frame = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA"],
            "ts_ms": [kept, dropped],
            "buyRatio": [0.10, 0.99],
        }
    )
    frame.to_parquet(tmp_path / "bybit_lsratio_20261020_ls1d_combined.parquet")
    out = load_ratio_frame(tmp_path)
    assert len(out) == 1
    assert float(out["buy_ratio"].iloc[0]) == pytest.approx(0.10)
    assert float(out["buy_ratio"].iloc[0]) != pytest.approx(0.35 + 0.30 * 0.10)
    t = pd.Timestamp("2024-06-08", tz="UTC")
    stamps = [(t - pd.Timedelta(days=day), 0.10) for day in range(1, 8)]
    assert mean_buy_ratio(stamps, t) == pytest.approx(0.10)


def test_tie_break_is_stable_on_L_then_symbol_ascii():
    """Tied L: alphabetically later symbol is the one that goes short.

    The sort is symbol ASCII first, then a stable sort on (L, symbol).
    Shuffling the input does not change either leg.
    """
    # Three names, k = 1. AAA and CCC share the high L. CCC is later, so
    # CCC is short and AAA stays in the middle. BBB is the low L, so long.
    scored = [("CCC", 0.9), ("AAA", 0.9), ("BBB", 0.2)]
    long, short, k = assign_terciles(scored)
    assert k == 1
    assert long == ["BBB"]
    assert short == ["CCC"]

    shuffled = [
        [("BBB", 0.2), ("CCC", 0.9), ("AAA", 0.9)],
        [("AAA", 0.9), ("BBB", 0.2), ("CCC", 0.9)],
        [("CCC", 0.9), ("BBB", 0.2), ("AAA", 0.9)],
    ]
    for rows in shuffled:
        assert assign_terciles(rows)[:2] == (["BBB"], ["CCC"])

    # Six names, k = 2. C, D, and E tie. E is the later name at that tie,
    # so E is inside the short leg and C is not.
    six = [("E", 0.5), ("A", 0.1), ("C", 0.5), ("F", 0.9), ("B", 0.2), ("D", 0.5)]
    long6, short6, k6 = assign_terciles(six)
    assert k6 == 2
    assert long6 == ["A", "B"]
    assert short6 == ["E", "F"]
    assert "C" not in short6 and "D" not in short6
    reversed_rows = list(reversed(six))
    assert assign_terciles(reversed_rows)[:2] == (long6, short6)


# ---------------------------------------------------------------------------
# Calendar: dropped Mondays, thin leg, fresh entry, 2026
# ---------------------------------------------------------------------------


def test_dropped_mondays_match_the_predicate_and_are_not_weeks(flat_main):
    assert assert_dropped_monday_list("main") == list(DROPPED_MONDAYS)
    assert assert_dropped_monday_list("holdout") == []
    found = [t.strftime("%Y-%m-%d") for t in rebalance_mondays("main") if is_dropped_monday(t)]
    assert found == list(DROPPED_MONDAYS)
    weekly = flat_main["weekly"]
    booked = set(pd.to_datetime(weekly["rebalance_time"], utc=True).dt.strftime("%Y-%m-%d"))
    for day in DROPPED_MONDAYS:
        assert day not in booked
    reasons = {skip.t.strftime("%Y-%m-%d"): skip.reason for skip in flat_main["schedule"].skips}
    for day in DROPPED_MONDAYS:
        assert reasons[day] == "v2_exclusion"
    # No zero-return placeholder. The dates are absent, not flat weeks.
    assert len(weekly) == len(rebalance_mondays("main")) - len(DROPPED_MONDAYS)


def test_week_after_the_gap_is_a_fresh_full_entry(flat_main):
    weekly = flat_main["weekly"].copy()
    weekly["day"] = pd.to_datetime(weekly["rebalance_time"], utc=True).dt.strftime("%Y-%m-%d")
    june = weekly.loc[weekly["day"] == "2025-06-09"].iloc[0]
    assert bool(june["fresh_entry"]) is True
    assert float(june["traded_notional"]) == pytest.approx(GROSS)
    assert float(june["w_long"]) == pytest.approx(LEG)
    assert float(june["w_short"]) == pytest.approx(LEG)
    # The kept Monday before the gap is 2025-04-28, which is not 7 days earlier.
    previous = weekly.loc[weekly["day"] < "2025-06-09"].iloc[-1]
    assert previous["day"] == "2025-04-28"
    assert bool(previous["flatten"]) is True


def test_thin_leg_is_not_a_week():
    symbols = _symbols(27)
    levels = _levels(symbols)
    membership = _membership(symbols, "2023-08-01", "2025-07-07")
    ratios = RatioStore.from_frame(_ratios(symbols, levels, "2023-08-01", "2025-07-06"))
    schedule = build_schedule({}, membership, ratios, {}, {}, "main", None)
    assert schedule.trades == []
    thin = [skip for skip in schedule.skips if skip.reason == "thin_leg"]
    assert thin
    assert {skip.k for skip in thin} == {9}
    assert {skip.n_valid for skip in thin} == {27}
    # Thirty names clear k = 10. Checked on the full flat book.
    assert 27 // 3 == 9
    assert 30 // 3 == 10


def test_thirty_names_trade(flat_main):
    week = flat_main["schedule"].trades[0]
    assert week.k == 10
    assert len(week.long) == 10 and len(week.short) == 10
    assert abs(sum(w for w in week.weights.values() if w > 0) - LEG) < 1e-12
    assert abs(-sum(w for w in week.weights.values() if w < 0) - LEG) < 1e-12


def test_2026_window_is_refused():
    with pytest.raises(WindowError):
        rebalance_mondays("2026")
    with pytest.raises(WindowError):
        rebalance_mondays("veto")
    assert exit_cap("main") == pd.Timestamp("2025-07-07", tz="UTC")
    assert rebalance_mondays("main")[-1] == pd.Timestamp("2025-06-30", tz="UTC")
    assert exit_cap("holdout") == pd.Timestamp("2025-12-29", tz="UTC")
    assert all(t <= pd.Timestamp("2025-12-22", tz="UTC") for t in rebalance_mondays("holdout"))


def test_holdout_evidence_is_the_25_mondays_through_dec_22():
    """Addendum d0cc64c8. 2025-12-29 is veto-only and is not a metric week."""
    mondays = rebalance_mondays("holdout")
    days = [stamp.strftime("%Y-%m-%d") for stamp in mondays]
    assert days[0] == "2025-07-07"
    assert days[-1] == "2025-12-22"
    assert len(days) == 25
    assert days == list(pd.date_range("2025-07-07", "2025-12-22", freq="W-MON").strftime("%Y-%m-%d"))
    assert "2025-12-29" not in days
    assert veto_only_mondays("holdout") == [pd.Timestamp("2025-12-29", tz="UTC")]
    assert veto_only_mondays("main") == []
    assert exit_cap("holdout") == pd.Timestamp("2025-12-29T00:00:00Z")
    assert exit_cap("main") == pd.Timestamp("2025-07-07T00:00:00Z")
    line = veto_only_frame("holdout")
    assert list(line["rebalance_time"]) == [pd.Timestamp("2025-12-29", tz="UTC")]
    assert set(line["label"]) == {"veto_only"}
    assert line["evidence"].eq(False).all()
    assert line["binds_gates"].eq(False).all()
    assert line["can_rescue_a_fail"].eq(False).all()
    assert line["in_metrics"].eq(False).all()
    assert "net_return" not in line.columns
    assert veto_only_frame("main").empty
    docs = assert_documents()
    assert docs["COUNTERSIGN_ADDENDUM.md"] == pins.COUNTERSIGN_ADDENDUM_SHA256


def test_holdout_loader_reads_nothing_after_the_dec_29_open():
    """The 2025-12-22 hold closes at the 2025-12-29 00:00 open. Nothing later."""
    cap = exit_cap("holdout")
    opened = pd.Timestamp("2025-12-22", tz="UTC")
    index = pd.date_range(opened, pd.Timestamp("2026-01-05", tz="UTC"), freq="1h")
    opens = np.full(len(index), 100.0)
    opens[index.get_loc(cap)] = 123.0
    bars = pd.DataFrame(
        {"open": opens, "high": 100.0, "low": 100.0, "close": 100.0},
        index=index,
    )
    funding = pd.Series(
        [0.001, 0.002, 0.009],
        index=pd.to_datetime(
            ["2025-12-22 08:00", "2025-12-29 00:00", "2025-12-29 08:00"],
            utc=True,
        ),
    )
    ratios = pd.DataFrame(
        {
            "symbol": ["AAA", "AAA", "AAA"],
            "ts": pd.to_datetime(["2025-12-21", "2025-12-29", "2026-01-01"], utc=True),
            "buy_ratio": [0.2, 0.8, 0.9],
        }
    )
    panel, kept_funding, kept_ratios = clip_loaded_inputs(
        {"AAA": bars},
        {"AAA": funding},
        ratios,
        cap,
        window="holdout",
    )
    loaded = panel["AAA"]
    assert loaded.index.max() == cap
    assert (loaded.index > cap).sum() == 0
    assert pd.Timestamp("2025-12-29 01:00", tz="UTC") not in loaded.index
    assert pd.Timestamp("2026-01-05", tz="UTC") not in loaded.index
    assert kept_funding["AAA"].index.max() == cap
    assert pd.Timestamp("2025-12-29 08:00", tz="UTC") not in kept_funding["AAA"].index
    assert (kept_ratios["ts"] >= cap).sum() == 0
    path = path_for_side(loaded, opened, cap, "long", kept_funding["AAA"])
    assert path is not None
    assert path.reason == "hold"
    assert path.exit_time == cap
    assert path.exit_price == pytest.approx(123.0)
    assert path.funding_sum == pytest.approx(0.003)


def test_dec_29_cannot_enter_holdout_metrics_or_rescue_a_fail():
    # -0.02 then +0.50 would pass on the mean if 2025-12-29 were evidence.
    rescued = _weekly([-0.02, 0.50], start="2025-12-22")
    with pytest.raises(ScoreError):
        evaluate(rescued, window="holdout", random_means=None, funding_coverage=_coverage())
    evidence = _weekly([0.02], start="2025-12-22")
    metrics = evaluate(evidence, window="holdout", random_means=None, funding_coverage=_coverage())
    assert metrics["n_weeks"] == 1
    assert metrics["verdict"] == "PASS"
    assert pd.Timestamp("2025-12-29", tz="UTC") not in set(
        pd.to_datetime(evidence["rebalance_time"], utc=True)
    )


# ---------------------------------------------------------------------------
# Sizing, cost, stop, funding
# ---------------------------------------------------------------------------


def test_two_flat_weeks_turnover_and_cost_both_ways():
    """Week 1 trades 1.18. Week 2, still in the chain, trades the cost drift.

    A third week keeps week 2 from flattening, so week 2's notional is only
    the Monday resize. G and the leg are the constants, not arguments.
    """
    symbols = _symbols(20)
    levels = _levels(symbols)
    long, short = symbols[:10], symbols[10:]
    start = pd.Timestamp("2024-01-01", tz="UTC")
    bars = _flat_bars(start, start + pd.Timedelta(days=21))
    weeks = [
        _week(start + pd.Timedelta(days=7 * i), symbols, levels, bars, long=long, short=short)
        for i in range(3)
    ]
    sim = run_strategy(Schedule(trades=weeks))
    weekly = pd.DataFrame(sim.weekly)
    cash = OFFICIAL_LEG_COST * GROSS
    assert float(weekly.loc[0, "traded_notional"]) == pytest.approx(GROSS)
    assert float(weekly.loc[0, "cost"]) == pytest.approx(cash)
    assert float(weekly.loc[0, "gross_price"]) == pytest.approx(0.0)
    assert float(weekly.loc[0, "funding"]) == pytest.approx(0.0)
    assert float(weekly.loc[0, "net_return"]) == pytest.approx(-cash)
    assert bool(weekly.loc[0, "fresh_entry"]) is True
    assert bool(weekly.loc[1, "fresh_entry"]) is False
    assert bool(weekly.loc[1, "flatten"]) is False
    expected = GROSS * cash / (1.0 - cash)
    assert float(weekly.loc[1, "traded_notional"]) == pytest.approx(expected)
    # Entry and, on the last week, the exit. Both charged at 0.31%.
    assert bool(weekly.loc[2, "flatten"]) is True
    assert float(weekly.loc[2, "rate"]) == pytest.approx(OFFICIAL_LEG_COST)
    # Wicks of 50% did not stop anyone.
    assert int(weekly["n_stops"].sum()) == 0
    pnl = pd.DataFrame(sim.name_pnl)
    for stamp, part in pnl.groupby("rebalance_time"):
        net = float(weekly.loc[weekly["rebalance_time"] == stamp, "net_return"].iloc[0])
        assert float(part["pnl"].sum()) == pytest.approx(net)


def test_stop_is_on_the_close_exits_at_the_next_open_and_does_not_resize():
    t = pd.Timestamp("2024-01-01", tz="UTC")
    t_next = t + pd.Timedelta(days=7)
    index = pd.date_range(t, t_next, freq="1h", tz="UTC")
    n = len(index)

    def bars(close_at: dict[int, float] | None = None, next_open: dict[int, float] | None = None):
        close = np.full(n, 100.0)
        open_ = np.full(n, 100.0)
        if close_at:
            for i, price in close_at.items():
                close[i] = price
        if next_open:
            for i, price in next_open.items():
                open_[i] = price
        return pd.DataFrame(
            {
                "open": open_,
                "high": np.full(n, 150.0),
                "low": np.full(n, 50.0),
                "close": close,
            },
            index=index,
        )

    # Inclusive 12% breach on the close. The wick on bar 0 is ignored.
    stopped_bars = bars({5: 88.0}, {6: 91.0})
    held_bars = bars()
    stopped = path_for_side(stopped_bars, t, t_next, "long", None)
    assert stopped is not None
    assert stopped.reason == "stop"
    assert stopped.exit_price == pytest.approx(91.0)
    assert stopped.exit_time == index[6]
    assert stopped.exit_price != pytest.approx(88.0)
    # Same bars, short side: 88 is not a short stop, and the 150 wick is not either.
    short = path_for_side(stopped_bars, t, t_next, "short", None)
    assert short is not None and short.reason == "hold"
    held = path_for_side(held_bars, t, t_next, "long", None)
    assert held is not None and held.reason == "hold"

    names = ["AAA", "BBB", "CCC", "DDD"]
    weight = LEG / 2.0
    weights = {"AAA": weight, "BBB": weight, "CCC": -weight, "DDD": -weight}
    paths = {
        "AAA": require_paths("AAA", t, stopped_bars, t_next, None),
        "BBB": require_paths("BBB", t, held_bars, t_next, None),
        "CCC": require_paths("CCC", t, held_bars, t_next, None),
        "DDD": require_paths("DDD", t, held_bars, t_next, None),
    }
    week = TradeWeek(
        t=t,
        t_next=t_next,
        weights=weights,
        paths=paths,
        scores={name: 0.5 for name in names},
        eligible_order=names,
        regime=None,
        n_valid=4,
        k=2,
        long=["AAA", "BBB"],
        short=["CCC", "DDD"],
        status={name: "Trading" for name in names},
    )
    sim = run_strategy(Schedule(trades=[week]))
    booked = {row["symbol"]: row["weight"] for row in sim.weights}
    # Cash from AAA is not given to BBB. Both keep the entry weight.
    assert booked["AAA"] == pytest.approx(weight)
    assert booked["BBB"] == pytest.approx(weight)
    assert booked["CCC"] == pytest.approx(-weight)
    row = sim.weekly[0]
    # Entries of 1.18, AAA's stop at its entry weight, and the other three
    # marked exits. AAA is not charged a second time at the flatten.
    assert float(row["traded_notional"]) == pytest.approx(GROSS + weight + 3.0 * weight)
    assert float(row["cost"]) == pytest.approx(OFFICIAL_LEG_COST * float(row["traded_notional"]))
    assert float(sum(item["pnl"] for item in sim.name_pnl)) == pytest.approx(float(row["net_return"]))


def test_funding_books_zero_when_missing_and_sums_the_open_interval():
    t = pd.Timestamp("2024-01-01", tz="UTC")
    t_next = t + pd.Timedelta(days=7)
    bars = _flat_bars(t, t_next)
    observed = pd.Series(
        {
            t: 0.01,  # print at the entry is the previous interval
            t + pd.Timedelta(hours=4): 0.002,  # off the 8h grid, still summed
            t + pd.Timedelta(hours=8): 0.001,
            t_next: 0.003,
            t_next + pd.Timedelta(hours=8): 0.05,
        }
    )
    total, gaps, missing, off_grid = funding_over_hold(observed, t, t_next)
    assert total == pytest.approx(0.006)
    assert gaps == 19
    assert missing is False
    assert off_grid == 1
    nothing = funding_over_hold(None, t, t_next)
    assert nothing[0] == 0.0 and nothing[2] is True

    long, short = ["AAA"], ["BBB"]
    levels = {"AAA": 0.1, "BBB": 0.9}
    week = _week(t, ["AAA", "BBB"], levels, bars, rates={"AAA": observed}, long=long, short=short)
    sim = run_strategy(Schedule(trades=[week]))
    row = sim.weekly[0]
    assert float(row["funding"]) == pytest.approx(-0.59 * 0.006)
    by_name = {item["symbol"]: item for item in sim.name_pnl}
    assert by_name["BBB"]["funding"] == pytest.approx(0.0)
    assert by_name["AAA"]["funding"] == pytest.approx(-0.59 * 0.006)
    from research.xs_crowd_lsr_contrarian.book import funding_coverage

    coverage = funding_coverage(pd.DataFrame(sim.name_pnl), Schedule(trades=[week]))
    assert coverage["leg_mean_fill"] is False
    assert coverage["missing_books_zero"] is True
    assert coverage["names_with_no_funding_data"] == ["BBB"]
    assert float(sum(item["pnl"] for item in sim.name_pnl)) == pytest.approx(float(row["net_return"]))


def test_missing_monday_open_blocks_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    t = pd.Timestamp("2024-01-01", tz="UTC")
    later = pd.date_range(t + pd.Timedelta(hours=1), periods=4, freq="1h", tz="UTC")
    bars = _flat_bars(t, t + pd.Timedelta(days=7)).drop(index=t)
    assert t not in bars.index
    assert path_for_side(bars, t, t + pd.Timedelta(days=7), "long", None) is None
    with pytest.raises(BlockedRun) as caught:
        require_paths("AAA", t, bars, t + pd.Timedelta(days=7), None)
    assert caught.value.symbol == "AAA"
    assert len(later) == 4

    symbols = _symbols(30)
    levels = _levels(symbols)
    membership = _membership(symbols, "2023-08-01", "2025-07-07")
    ratios = RatioStore.from_frame(_ratios(symbols, levels, "2023-08-01", "2025-07-06"))
    with pytest.raises(BlockedRun) as blocked:
        build_schedule({}, membership, ratios, {}, {}, "main", None)
    assert blocked.value.symbol == "S00"
    assert not (tmp_path / "SHA256SUMS").exists()

    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    out = tmp_path / "run"
    with pytest.raises(HashSeedError):
        run_prepared(Schedule(), window="main", output_dir=out)
    assert not out.exists()


def test_delist_exits_at_the_last_close():
    t = pd.Timestamp("2024-01-01", tz="UTC")
    index = pd.date_range(t, periods=6, freq="1h", tz="UTC")
    bars = pd.DataFrame(
        {"open": 100.0, "high": 100.0, "low": 100.0, "close": [100, 101, 102, 103, 104, 105]},
        index=index,
    )
    path = path_for_side(bars, t, t + pd.Timedelta(days=7), "long", None)
    assert path is not None
    assert path.reason == "delist"
    assert path.exit_price == pytest.approx(105.0)


# ---------------------------------------------------------------------------
# Regime and the drawdown gate
# ---------------------------------------------------------------------------


def _btc_from(origin: float, n_blocks: int, slope: float) -> pd.DataFrame:
    start = pd.Timestamp("2023-01-02", tz="UTC")
    index: list[pd.Timestamp] = []
    close: list[float] = []
    for i in range(n_blocks):
        open_time = start + pd.Timedelta(hours=4 * i)
        price = origin + slope * i
        index.extend([open_time, open_time + pd.Timedelta(hours=3)])
        close.extend([price, price])
    frame = pd.DataFrame(
        {"open": close, "high": close, "low": close, "close": close},
        index=pd.DatetimeIndex(index),
    )
    return frame


def test_regime_band_and_loss_rule():
    assert classify_ema_band(102.0, 100.0) == "BULL"
    assert classify_ema_band(98.0, 100.0) == "BEAR"
    assert classify_ema_band(100.5, 100.0) == "CHOP"

    rising = _btc_from(100.0, 210, 1.0)
    # Stay positive. A close of 0 is not a bar, so the slope cannot cross zero.
    falling = _btc_from(400.0, 210, -1.0)
    flat = _btc_from(100.0, 210, 0.0)
    closes = four_hour_closes(rising)
    assert len(closes) == 210
    labelled = regimes_for(rising, [closes.index[199]])
    assert labelled[as_utc(closes.index[199])] == "BULL"
    earlier = closes.index[199] - pd.Timedelta(nanoseconds=1)
    assert regimes_for(rising, [earlier])[as_utc(earlier)] is None
    last = closes.index[-1]
    assert regimes_for(falling, [last])[as_utc(last)] == "BEAR"
    flat_closes = four_hour_closes(flat)
    assert regimes_for(flat, [flat_closes.index[-1]])[as_utc(flat_closes.index[-1])] == "CHOP"

    # A missing last hour drops that block. It is not filled.
    dropped = rising.drop(index=rising.index[1])
    assert len(four_hour_closes(dropped)) == 209

    losing = pd.DataFrame({"regime": ["BULL"] * 5, "net_return": [-0.01] * 5})
    report = regime_gate(losing)
    assert report["pass"] is False
    assert report["failing"] == ["BULL"]
    short = pd.DataFrame({"regime": ["BEAR"] * 4, "net_return": [-0.02] * 4})
    small = regime_gate(short)
    assert small["pass"] is True
    assert small["regimes"]["BEAR"]["status"] == "report_only"


def _weekly(nets: list[float], *, proxy: list[float] | None = None, regimes: list[str] | None = None,
            n_entries: int = 1, start: str = "2024-01-01") -> pd.DataFrame:
    times = pd.date_range(start, periods=len(nets), freq="7D", tz="UTC")
    return pd.DataFrame(
        {
            "rebalance_time": times,
            "net_return": nets,
            "net_return_proxy": list(proxy) if proxy is not None else list(nets),
            "n_leg_trades": [40] * len(nets),
            "n_entries": [n_entries] * len(nets),
            "regime": regimes if regimes is not None else [""] * len(nets),
        }
    )


def test_drawdown_gate_is_strict_and_has_no_sizing_knob():
    assert pins.GROSS == 1.18 and pins.LEG == 0.59
    assert pins.MAX_DRAWDOWN == 0.25
    exact = max_drawdown(np.array([-0.25]))
    assert exact == pytest.approx(0.25)
    assert not (exact < MAX_DRAWDOWN)
    under = evaluate(
        _weekly([-0.20]),
        window="main",
        random_means=np.zeros(5),
        funding_coverage=_coverage(),
    )
    gate = under["gates"]["max_drawdown"]
    assert gate["pass"] is True
    assert gate["comparison"] == "<"
    assert gate["gross"] == 1.18 and gate["leg"] == 0.59
    assert gate["sizing_knob"] is False
    exact_book = evaluate(
        _weekly([-0.25]),
        window="main",
        random_means=np.zeros(5),
        funding_coverage=_coverage(),
    )
    assert exact_book["gates"]["max_drawdown"]["pass"] is False
    assert exact_book["verdict"] == "FAIL"


def _passing_weeks(*, proxy_sign: float) -> pd.DataFrame:
    anchors = [
        "2023-10-16",
        "2024-01-01",
        "2024-04-01",
        "2024-07-01",
        "2024-10-07",
        "2025-01-06",
        "2025-04-07",
    ]
    times: list[pd.Timestamp] = []
    for anchor in anchors:
        start = pd.Timestamp(anchor, tz="UTC")
        times.extend(start + pd.Timedelta(days=7 * i) for i in range(5))
    n = len(times)
    nets = [0.01] * n
    return pd.DataFrame(
        {
            "rebalance_time": times,
            "net_return": nets,
            "net_return_proxy": [proxy_sign * 0.01] * n,
            "n_leg_trades": [4] * n,
            "n_entries": [20] * n,
            "regime": [""] * n,
        }
    )


def test_sign_veto_cannot_rescue_a_fail_and_blocks_a_pass():
    means = np.full(20, -1.0)
    veto = evaluate(
        _passing_weeks(proxy_sign=-1.0),
        window="main",
        random_means=means,
        funding_coverage=_coverage(),
    )
    assert veto["verdict"] == "VETO"
    assert veto["passed"] is False
    assert veto["can_rescue_a_fail"] is False
    passed = evaluate(
        _passing_weeks(proxy_sign=1.0),
        window="main",
        random_means=means,
        funding_coverage=_coverage(),
    )
    assert passed["verdict"] == "PASS"
    failed = evaluate(
        _weekly([-0.01] * 5, proxy=[0.02] * 5),
        window="main",
        random_means=means,
        funding_coverage=_coverage(),
    )
    assert failed["verdict"] == "FAIL"
    assert failed["gates"]["sign_flip_veto"]["veto"] is True


def test_holdout_score_is_mean_and_profit_factor_only():
    good = evaluate(
        _weekly([0.02, 0.01]),
        window="holdout",
        random_means=None,
        funding_coverage=_coverage(),
    )
    assert good["verdict"] == "PASS"
    assert good["gates_applied"] == ["positive_mean", "profit_factor"]
    bad = evaluate(
        _weekly([-0.02, -0.01]),
        window="holdout",
        random_means=None,
        funding_coverage=_coverage(),
    )
    assert bad["verdict"] == "FAIL"


# ---------------------------------------------------------------------------
# Random book, hash seed, blind stdout, holdout lock
# ---------------------------------------------------------------------------


def test_random_book_seed_is_deterministic(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    signature = inspect.signature(random_book_means)
    assert signature.parameters["n_perm"].default == N_RANDOM_DRAWS == 1000
    assert signature.parameters["seed"].default == RANDOM_SEED == 20261016
    symbols = _symbols(30)
    levels = _levels(symbols)
    start = pd.Timestamp("2024-01-01", tz="UTC")
    bars = _flat_bars(start, start + pd.Timedelta(days=14))
    weeks = [_week(start + pd.Timedelta(days=7 * i), symbols, levels, bars) for i in range(2)]
    schedule = Schedule(trades=weeks)
    first = random_book_means(schedule, n_perm=4, seed=RANDOM_SEED)
    second = random_book_means(schedule, n_perm=4, seed=RANDOM_SEED)
    assert first.shape == (4,)
    assert np.array_equal(first, second)
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    with pytest.raises(HashSeedError):
        random_book_means(schedule, n_perm=1, seed=RANDOM_SEED)


def test_pythonhashseed_must_already_be_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    from research.xs_crowd_lsr_contrarian.__main__ import main

    with pytest.raises(HashSeedError):
        main(["run", "--window", "main", "--output", "unused-output"])
    monkeypatch.setenv("PYTHONHASHSEED", "1")
    with pytest.raises(HashSeedError):
        main(["run", "--window", "main", "--output", "unused-output"])
    # The hash command identifies the code. It does not run the book.
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    assert main(["hash"]) == 0
    printed = capsys.readouterr().out
    assert "harness_sha256" in printed and "scorer_sha256" in printed
    assert MAIN_COMMAND.startswith("PYTHONHASHSEED=0 python -m research.xs_crowd_lsr_contrarian run ")
    for module in (
        hashing,
        __import__("research.xs_crowd_lsr_contrarian.harness", fromlist=["harness"]),
        __import__("research.xs_crowd_lsr_contrarian.__main__", fromlist=["main"]),
        __import__("research.xs_crowd_lsr_contrarian.random_book", fromlist=["random_book"]),
    ):
        text = Path(module.__file__).read_text(encoding="utf-8")
        assert "os.environ[" not in text


def _seal_dir(directory: Path, verdict: str) -> str:
    directory.mkdir()
    (directory / "manifest.json").write_text(
        json.dumps({"cell": CELL, "window": "main", "metrics_computed": False}) + "\n",
        encoding="utf-8",
    )
    (directory / "metrics.json").write_text(
        json.dumps({"verdict": verdict}) + "\n",
        encoding="utf-8",
    )
    (directory / "SHA256SUMS").write_text("abc  weekly_returns.csv\n", encoding="utf-8")
    return sha256_file(directory / "SHA256SUMS")


def test_holdout_refuses_without_flag_seal_and_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PYTHONHASHSEED", "0")
    from research.xs_crowd_lsr_contrarian.__main__ import main
    from research.xs_crowd_lsr_contrarian.tape import TapeIntegrityError

    out = tmp_path / "holdout"
    with pytest.raises(HoldoutLockedError):
        main(["run", "--window", "holdout", "--output", str(out)])
    with pytest.raises(HoldoutLockedError):
        main(["run", "--window", "holdout", "--holdout", "--output", str(out)])
    failed = tmp_path / "failed"
    seal = _seal_dir(failed, "FAIL")
    with pytest.raises(HoldoutLockedError):
        assert_holdout_allowed(
            "holdout",
            holdout_flag=True,
            seal_hash=seal,
            main_output_dir=failed,
        )
    passed = tmp_path / "passed"
    good = _seal_dir(passed, "PASS")
    with pytest.raises(HoldoutLockedError):
        assert_holdout_allowed(
            "holdout",
            holdout_flag=True,
            seal_hash="0" * 64,
            main_output_dir=passed,
        )
    assert assert_holdout_allowed(
        "holdout",
        holdout_flag=True,
        seal_hash=good,
        main_output_dir=passed,
    ) == good
    # The lock is open, so the run proceeds to the tape and then refuses
    # because this fixture has no SUMS. It still writes nothing.
    with pytest.raises(TapeIntegrityError):
        main(
            [
                "run",
                "--window",
                "holdout",
                "--holdout",
                "--seal-hash",
                good,
                "--main-output-dir",
                str(passed),
                "--root",
                str(tmp_path / "empty"),
                "--output",
                str(out),
            ]
        )
    assert not out.exists()
    with pytest.raises(SystemExit):
        main(["run", "--window", "2026", "--output", str(out)])
    with pytest.raises(SystemExit):
        main(["run", "--window", "main", "--output", str(out), "--seed", "1"])


def test_blind_run_seals_hashseed_and_score_does_not_move_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
):
    monkeypatch.setenv("PYTHONHASHSEED", "0")

    def fake_means(schedule, n_perm=N_RANDOM_DRAWS, seed=RANDOM_SEED, progress=None):
        assert n_perm == 1000 and seed == RANDOM_SEED
        if progress is not None:
            progress(n_perm, n_perm)
        return np.zeros(n_perm)

    monkeypatch.setattr(
        "research.xs_crowd_lsr_contrarian.harness.random_book_means",
        fake_means,
    )
    symbols = _symbols(20)
    levels = _levels(symbols)
    start = pd.Timestamp("2024-01-01", tz="UTC")
    bars = _flat_bars(start, start + pd.Timedelta(days=7))
    week = _week(start, symbols, levels, bars, long=symbols[:10], short=symbols[10:])
    out = tmp_path / "main"
    print_run_hashes()
    result = run_prepared(Schedule(trades=[week]), window="main", output_dir=out)
    captured = capsys.readouterr().out
    sys_out = captured
    assert "harness_sha256" in sys_out and "scorer_sha256" in sys_out
    assert "random_book 1000/1000" in sys_out
    for banned in ("verdict", "profit_factor", "max_drawdown", "mean_net", "PASS", "FAIL"):
        assert banned not in sys_out

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["pythonhashseed"] == "0"
    assert manifest["metrics_computed"] is False
    assert manifest["sizing_knob"] is False
    assert manifest["gross"] == 1.18 and manifest["leg"] == 0.59
    assert manifest["random_book_draws"] == 1000
    assert manifest["random_book_seed"] == RANDOM_SEED
    assert manifest["documents"]["COUNTERSIGN.md"] == pins.COUNTERSIGN_SHA256
    assert manifest["documents"]["COUNTERSIGN_ADDENDUM.md"] == pins.COUNTERSIGN_ADDENDUM_SHA256
    assert manifest["veto_only"]["rebalances"] == []
    assert manifest["veto_only"]["in_metrics"] is False
    assert manifest["veto_only"]["can_rescue_a_fail"] is False
    assert manifest["documents"]["proposal_status_fix_sha256"] == pins.PROPOSAL_STATUS_FIX_SHA256
    assert manifest["documents"]["proposal_status_fix_bytes_in_checkout"] is False
    assert manifest["book_stage_sha256"] == stage_digest(out, BOOK_STAGE_FILES)
    book = json.loads((out / "random_book.json").read_text(encoding="utf-8"))
    assert "p_value" not in book and book["n_draws"] == 1000 and book["seed"] == RANDOM_SEED
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8")
    assert "FINAL_HASH" not in sums and "metrics.json" not in sums
    assert (out / "FINAL_HASH").read_text(encoding="utf-8").strip() == result["final_sha256"]
    assert sha256_file(out / "SHA256SUMS") == result["final_sha256"]
    seal_before = sha256_file(out / "SHA256SUMS")

    from research.xs_crowd_lsr_contrarian.__main__ import main

    assert main(["score", "--book", str(out)]) == 0
    scored = capsys.readouterr().out.strip().splitlines()
    assert scored[0].startswith("verdict ")
    assert scored[1].startswith("metrics_sha256 ")
    assert "profit_factor" not in "\n".join(scored)
    assert sha256_file(out / "SHA256SUMS") == seal_before
    assert (out / "metrics.json").is_file()
    # A second write is refused.
    with pytest.raises(FileExistsError):
        run_prepared(Schedule(trades=[week]), window="main", output_dir=out)


def test_name_pnl_sums_to_the_week_on_the_flat_calendar(flat_main):
    weekly = flat_main["weekly"]
    pnl = flat_main["name_pnl"]
    assert int(weekly["n_stops"].sum()) == 0
    for stamp, part in pnl.groupby("rebalance_time"):
        net = float(weekly.loc[weekly["rebalance_time"] == stamp, "net_return"].iloc[0])
        assert float(part["pnl"].sum()) == pytest.approx(net, rel=1e-12, abs=1e-12)
