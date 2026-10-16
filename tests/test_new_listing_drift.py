"""Synthetic tests for the new-listing drift harness.

No real tape is read. Entry timing, the stop, delivery and delist
truncation, funding on both legs, both cost levels, and the holdout
and 2026 locks are checked on constructed bars.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.costs import DEFAULT_COSTS
from research.new_listing_drift import PACKAGE_DIR
from research.new_listing_drift.catalog import (
    coverage_disclosure,
    events_for_window,
    load_events,
    window_years,
)
from research.new_listing_drift.cells import (
    EVENTS_V2_SHA256,
    EXCLUSIONS,
    LOCK_SHA256,
    MDE_CLUSTERS,
    MDE_D,
    MDE_Z_ALPHA,
    MDE_Z_POWER,
    N_PERMUTATIONS,
    PREREG_SHA256,
    RANDOM_SEED,
    TAPE_SUMS_SHA256,
)
from research.new_listing_drift.costs import (
    MEASURED_BTC_LEG_RATE,
    MEASURED_LISTING_LEG_RATE,
    OFFICIAL_LEG_RATE,
    measured_spread_cost,
    official_leg_model,
    official_spread_cost,
)
from research.new_listing_drift.engine import (
    eligible_random_opens,
    find_entry,
    simulate_spread,
    spread_return,
)
from research.new_listing_drift.harness import (
    HoldoutLockedError,
    assert_closed_window_allowed,
    run_window,
    write_outputs,
)
from research.new_listing_drift.hashing import sha256_file, source_hashes
from research.new_listing_drift.scorer import (
    MIN_TRADES_PER_YEAR,
    PF_MIN,
    book_max_drawdown,
    permutation_p_value,
    random_book_means,
    score_trades,
    signs_disagree,
)
from research.new_listing_drift.tape import (
    CountersignRequired,
    TapeIntegrityError,
    assert_real_tapes_closed,
    listing_deadline,
    load_membership,
    load_symbol_bars,
    verify_sums,
)
from research.validate import DEFAULT_CRITERIA

LAUNCH = pd.Timestamp("2024-01-01T00:30:00Z")
BAR_START = "2024-01-01T00:00:00Z"


def _hourly(start: str, hours: int, price: float = 100.0, volume: float = 1.0) -> pd.DataFrame:
    index = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    px = np.full(hours, price, dtype="float64")
    return pd.DataFrame(
        {
            "open": px.copy(),
            "high": px.copy(),
            "low": px.copy(),
            "close": px.copy(),
            "volume": np.full(hours, volume, dtype="float64"),
        },
        index=index,
    )


def _flat_pair(hours: int = 500) -> tuple[pd.DataFrame, pd.DataFrame]:
    return _hourly(BAR_START, hours, 100.0), _hourly(BAR_START, hours, 200.0)


def _funding(stamps: list[str], rate: float) -> pd.Series:
    index = pd.DatetimeIndex([pd.Timestamp(s) for s in stamps])
    return pd.Series(np.full(len(index), rate), index=index, name="funding_rate")


def _expected_entry() -> pd.Timestamp:
    """First bar at or after launch whose close is at or after launch+24h, then the next open."""
    signal, entry = find_entry(_hourly(BAR_START, 80), LAUNCH)
    assert signal == pd.Timestamp("2024-01-02T00:00:00Z")
    assert entry == pd.Timestamp("2024-01-02T01:00:00Z")
    return entry


def test_entry_is_next_open_after_launch_plus_24h():
    entry = _expected_entry()
    listing, btc = _flat_pair()
    trade = simulate_spread(listing, btc, symbol="NEWUSDT", launch=LAUNCH)
    assert trade["exit_reason"] != "no_trade"
    assert trade["entry_time"] == entry
    assert trade["signal_open"] == pd.Timestamp("2024-01-02T00:00:00Z")
    # The signal close is the entry open on a continuous hourly grid.
    assert trade["signal_open"] + pd.Timedelta(hours=1) == trade["entry_time"]
    assert trade["listing_entry"] == 100.0
    assert trade["btc_entry"] == 200.0
    assert trade["exit_time"] == entry + pd.Timedelta(hours=336)
    assert trade["exit_reason"] == "hold_14d"


def test_entry_ignores_bars_that_open_before_launch():
    listing = _hourly(BAR_START, 80)
    # The 00:00 bar opens before launch 00:30. Even if its close is late,
    # it is not the signal bar. find_entry must start at 01:00.
    signal, _entry = find_entry(listing, LAUNCH)
    assert signal is not None and signal >= LAUNCH


def test_no_lookahead_entry_does_not_use_future_prices():
    listing, btc = _flat_pair()
    base = simulate_spread(listing, btc, symbol="NEWUSDT", launch=LAUNCH)
    entry = base["entry_time"]
    scrambled = listing.copy()
    # Every close, and every open after the fill, is noise. The fill open stays.
    rng = np.random.default_rng(0)
    scrambled["close"] = rng.uniform(10.0, 500.0, len(scrambled))
    scrambled["high"] = scrambled["close"] + 1.0
    scrambled["low"] = scrambled["close"] - 1.0
    after = scrambled.index > entry
    scrambled.loc[after, "open"] = rng.uniform(10.0, 500.0, int(after.sum()))
    # The entry bar's own close is after the decision. It must not move the fill.
    scrambled.at[entry, "close"] = 999.0
    again = simulate_spread(scrambled, btc, symbol="NEWUSDT", launch=LAUNCH)
    assert again["entry_time"] == base["entry_time"]
    assert again["listing_entry"] == base["listing_entry"]
    assert again["signal_open"] == base["signal_open"]


def test_stop_fills_next_open_and_ignores_the_wick():
    listing, btc = _flat_pair()
    entry = _expected_entry()
    wick = entry + pd.Timedelta(hours=2)
    trigger = entry + pd.Timedelta(hours=4)
    fill = entry + pd.Timedelta(hours=5)
    # A wick through the stop, with the close back at the entry price, is not a stop.
    listing.at[wick, "low"] = 1.0
    listing.at[wick, "close"] = 100.0
    # Close at 113 is (100-113)/100 = -13% on the short, BTC unchanged.
    listing.at[trigger, "close"] = 113.0
    listing.at[fill, "open"] = 130.0
    trade = simulate_spread(listing, btc, symbol="NEWUSDT", launch=LAUNCH)
    assert trade["exit_reason"] == "stop"
    assert trade["exit_time"] == fill
    assert trade["stop_trigger_open"] == trigger
    assert trade["listing_exit"] == 130.0
    assert trade["listing_exit"] != 113.0
    expected = spread_return(130.0, 200.0, 100.0, 200.0)
    assert trade["gross_r"] == pytest.approx(expected)
    assert trade["gross_r"] == pytest.approx(-0.30)


def test_delivery_skips_the_zero_volume_bar():
    listing, btc = _flat_pair()
    entry = _expected_entry()
    deadline = pd.Timestamp("2024-01-04T02:30:00Z")
    settlement = pd.Timestamp("2024-01-04T02:00:00Z")
    listing.at[settlement, "volume"] = 0.0
    listing.at[settlement, "open"] = 50.0
    trade = simulate_spread(
        listing,
        btc,
        symbol="NEWUSDT",
        launch=LAUNCH,
        deadline=deadline,
        deadline_kind="delivery",
    )
    assert trade["exit_reason"] == "delivery"
    assert trade["exit_time"] == pd.Timestamp("2024-01-04T01:00:00Z")
    assert trade["listing_exit"] == 100.0
    assert trade["exit_time"] != entry + pd.Timedelta(hours=336)


def test_delist_uses_the_last_tradable_bar():
    listing, btc = _flat_pair()
    deadline = pd.Timestamp("2024-01-05T00:30:00Z")
    trade = simulate_spread(
        listing,
        btc,
        symbol="OLDUSDT",
        launch=LAUNCH,
        deadline=deadline,
        deadline_kind="delist",
    )
    assert trade["exit_reason"] == "delist"
    assert trade["exit_time"] == pd.Timestamp("2024-01-05T00:00:00Z")
    assert trade["truncated"] is False


def test_tape_that_ends_early_is_truncated_not_a_stop():
    listing, btc = _flat_pair(hours=40)
    entry = _expected_entry()
    # Last bar close would be a stop if we were allowed to fill it. There
    # is no next open, so the exit stays the last open and is a truncation.
    listing.iloc[-1, listing.columns.get_loc("close")] = 180.0
    trade = simulate_spread(listing, btc, symbol="NEWUSDT", launch=LAUNCH)
    assert trade["exit_reason"] == "truncated"
    assert trade["truncated"] is True
    assert trade["exit_time"] == listing.index[-1]
    assert trade["exit_time"] > entry
    assert trade["listing_exit"] == float(listing.iloc[-1]["open"])


def test_funding_both_legs_and_no_zero_fill():
    listing, btc = _flat_pair()
    entry = _expected_entry()
    exit_time = entry + pd.Timedelta(hours=336)
    # A complete 8h grid. A hole in it would be a missing settlement, not a zero.
    grid = pd.date_range(entry + pd.Timedelta(hours=8), exit_time, freq="8h", tz="UTC")
    grid = grid[grid <= exit_time]
    listing_funding = pd.Series(0.001, index=grid)
    btc_funding = pd.Series(0.004, index=grid)
    trade = simulate_spread(
        listing,
        btc,
        symbol="NEWUSDT",
        launch=LAUNCH,
        listing_funding=listing_funding,
        btc_funding=btc_funding,
    )
    assert trade["funding_missing"] is False
    assert trade["funding_zero_filled"] is False
    assert trade["funding_listing"] == pytest.approx(0.001 * len(grid))
    assert trade["funding_btc"] == pytest.approx(0.004 * len(grid))
    # Short receives the listing rate. Long pays the BTC rate.
    assert trade["funding_r"] == pytest.approx(trade["funding_listing"] - trade["funding_btc"])
    assert trade["funding_r"] < 0.0
    assert trade["net_official"] == pytest.approx(
        trade["gross_r"] + trade["funding_r"] - official_spread_cost()
    )
    assert trade["net_measured"] == pytest.approx(
        trade["gross_r"] + trade["funding_r"] - measured_spread_cost()
    )

    missing = simulate_spread(
        listing,
        btc,
        symbol="NEWUSDT",
        launch=LAUNCH,
        listing_funding=pd.Series(dtype="float64"),
        btc_funding=btc_funding,
    )
    assert missing["funding_missing"] is True
    assert missing["funding_zero_filled"] is False
    assert np.isnan(missing["funding_listing"])
    assert np.isnan(missing["net_official"])
    assert np.isnan(missing["net_measured"])
    # The zero-fill number would be gross minus cost. That number is not stored.
    zero_fill = missing["gross_r"] - official_spread_cost()
    assert np.isnan(missing["net_official"])
    assert zero_fill == pytest.approx(-official_spread_cost())
    assert not np.isnan(zero_fill)
    flagged = pd.DataFrame([missing])
    scored = score_trades(flagged, window="main", random_means=np.array([0.0]), n_bootstrap=20)
    assert scored["verdict"] == "INCOMPLETE"
    assert scored["passed"] is False
    assert scored["funding_zero_filled"] is False
    assert scored["n_spread_trades"] == 0


def test_cost_per_leg_at_both_levels_does_not_move_the_fill():
    assert official_spread_cost() == pytest.approx(2 * OFFICIAL_LEG_RATE)
    assert official_spread_cost() == pytest.approx(0.0062)
    assert measured_spread_cost() == pytest.approx(MEASURED_BTC_LEG_RATE + MEASURED_LISTING_LEG_RATE)
    assert measured_spread_cost() == pytest.approx(0.00316)
    model = official_leg_model()
    assert model.include_funding is False
    assert model.slippage == 0.0
    assert model.fee_for(1.0) == pytest.approx(OFFICIAL_LEG_RATE)
    # The pinned default schedule would move a short fill. The engine does not.
    assert DEFAULT_COSTS.entry_price(100.0, "SHORT") != 100.0
    listing, btc = _flat_pair()
    trade = simulate_spread(listing, btc, symbol="NEWUSDT", launch=LAUNCH)
    assert trade["listing_entry"] == 100.0
    assert trade["listing_exit"] == 100.0
    assert trade["cost_official"] == pytest.approx(0.0062)
    assert trade["cost_measured"] == pytest.approx(0.00316)


def test_measured_sign_flip_vetoes_and_does_not_rescue():
    listing, btc = _flat_pair(hours=80)
    entry = _expected_entry()
    # Gross +0.5% sits between the 0.316% proxy and the 0.62% official cost.
    listing.at[pd.Timestamp("2024-01-02T05:00:00Z"), "open"] = 99.5
    trade = simulate_spread(
        listing,
        btc,
        symbol="NEWUSDT",
        launch=LAUNCH,
        deadline=pd.Timestamp("2024-01-02T05:30:00Z"),
        deadline_kind="delivery",
    )
    assert trade["entry_time"] == entry
    assert trade["gross_r"] == pytest.approx(0.005)
    assert trade["funding_missing"] is False
    assert trade["net_official"] < 0.0
    assert trade["net_measured"] > 0.0
    frame = pd.DataFrame([trade])
    metrics = score_trades(
        frame,
        window="main",
        random_means=np.array([0.0]),
        n_bootstrap=100,
    )
    assert metrics["measured_proxy"]["sign_veto"] is True
    assert metrics["measured_proxy"]["can_rescue_a_fail"] is False
    assert metrics["official"]["binds_gates"] is True
    assert metrics["measured_proxy"]["binds_gates"] is False
    assert metrics["verdict"] != "PASS"
    assert metrics["passed"] is False
    assert signs_disagree(trade["net_official"], trade["net_measured"]) is True


def test_holdout_passes_on_mean_and_pf_only_and_main_keeps_the_floors():
    rows = []
    for week, symbol in enumerate(("AAAUSDT", "BBBUSDT")):
        entry = pd.Timestamp("2024-01-01T00:00:00Z") + pd.Timedelta(days=7 * week)
        rows.append(
            {
                "symbol": symbol,
                "entry_time": entry,
                "exit_time": entry + pd.Timedelta(days=14),
                "exit_reason": "hold_14d",
                "net_official": 0.05,
                "net_measured": 0.05 + (0.0062 - 0.00316),
                "funding_missing": False,
                "truncated": False,
            }
        )
    frame = pd.DataFrame(rows)
    holdout = score_trades(frame, window="holdout", random_means=np.array([-1.0]), n_bootstrap=50)
    assert holdout["verdict"] == "PASS"
    assert holdout["passed"] is True
    main = score_trades(frame, window="main", random_means=np.array([-1.0]), n_bootstrap=50)
    assert main["verdict"] == "FAIL"
    assert main["gates"]["spread_trades"]["pass"] is False
    assert main["gates"]["trades_per_year"]["pass"] is False
    assert main["gates"]["trades_per_year"]["threshold"] == MIN_TRADES_PER_YEAR
    assert PF_MIN == DEFAULT_CRITERIA.min_profit_factor


def test_veto_2026_is_veto_only():
    rows = []
    for week in range(10):
        entry = pd.Timestamp("2026-01-05T00:00:00Z") + pd.Timedelta(days=7 * week)
        rows.append(
            {
                "symbol": f"N{week}USDT",
                "entry_time": entry,
                "exit_time": entry + pd.Timedelta(days=2),
                "exit_reason": "hold_14d",
                "net_official": -0.02,
                "net_measured": -0.01,
                "funding_missing": False,
                "truncated": week == 0,
            }
        )
    frame = pd.DataFrame(rows)
    veto = score_trades(frame, window="veto", random_means=np.array([0.0]), n_bootstrap=20)
    assert veto["verdict"] == "VETO"
    assert veto["passed"] is False
    assert veto["n_truncated"] == 1
    short = frame.iloc[:9].copy()
    report = score_trades(short, window="veto", random_means=np.array([0.0]), n_bootstrap=20)
    assert report["verdict"] == "REPORT_ONLY"
    assert report["passed"] is False


def _locked_main(tmp_path: Path, verdict: str) -> tuple[Path, str]:
    main_dir = tmp_path / "main"
    main_dir.mkdir(parents=True)
    trades = pd.DataFrame({"symbol": ["XUSDT"], "net_official": [0.01]})
    manifest = {"cell": "new_listing_drift_short", "window": "main", "live": "off"}
    write_outputs(main_dir, trades, manifest)
    metrics = {"verdict": verdict, "passed": verdict == "PASS"}
    (main_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    # The lock hashes SHA256SUMS as it stands after metrics.json is added.
    sums = main_dir / "SHA256SUMS"
    lines = []
    for path in sorted(p for p in main_dir.iterdir() if p.is_file() and p.name != "SHA256SUMS"):
        lines.append(f"{sha256_file(path)}  {path.name}")
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return main_dir, sha256_file(sums)


def test_holdout_and_2026_locks(tmp_path: Path):
    main_dir, digest = _locked_main(tmp_path, "PASS")
    kwargs = {
        "cell_name": "new_listing_drift_short",
        "main_output_hash": digest,
        "main_output_dir": main_dir,
    }
    assert assert_closed_window_allowed("main", **kwargs) is None
    assert assert_closed_window_allowed("holdout", **kwargs) == digest
    assert assert_closed_window_allowed("veto", **kwargs) == digest

    with pytest.raises(HoldoutLockedError):
        assert_closed_window_allowed(
            "holdout",
            cell_name="new_listing_drift_short",
            main_output_hash=None,
            main_output_dir=None,
        )
    with pytest.raises(HoldoutLockedError):
        assert_closed_window_allowed(
            "veto",
            cell_name="new_listing_drift_short",
            main_output_hash="0" * 64,
            main_output_dir=main_dir,
        )

    failed, failed_digest = _locked_main(tmp_path / "fail", "FAIL")
    with pytest.raises(HoldoutLockedError):
        assert_closed_window_allowed(
            "holdout",
            cell_name="new_listing_drift_short",
            main_output_hash=failed_digest,
            main_output_dir=failed,
        )
    with pytest.raises(HoldoutLockedError):
        assert_closed_window_allowed(
            "veto",
            cell_name="new_listing_drift_short",
            main_output_hash=failed_digest,
            main_output_dir=failed,
        )
    marker = (PACKAGE_DIR / "HOLDOUT_LOCK").read_text(encoding="utf-8")
    assert marker.startswith("LOCKED")


def test_random_baseline_excludes_the_first_15_days_and_keeps_a_short_tape():
    listing, btc = _flat_pair(hours=24 * 40)
    launch = listing.index[0]
    start = launch
    stop = listing.index[-1] + pd.Timedelta(hours=1)
    opens = eligible_random_opens(
        listing, btc, launch=launch, window_start=start, window_stop=stop
    )
    assert len(opens) > 0
    assert opens.min() >= launch + pd.Timedelta(days=15)

    # Two bars only: the single eligible open, and the stop fill after it.
    only_start = launch + pd.Timedelta(days=15)
    stopped = listing.loc[[only_start, only_start + pd.Timedelta(hours=1)]].copy()
    stopped.at[only_start, "close"] = 130.0
    stopped.at[only_start + pd.Timedelta(hours=1), "open"] = 140.0
    direct = simulate_spread(
        stopped,
        btc,
        symbol="NEWUSDT",
        launch=only_start - pd.Timedelta(days=15),
        entry_time=only_start,
        listing_interval=pd.Timedelta(hours=48),
        btc_interval=pd.Timedelta(hours=48),
    )
    assert direct["exit_reason"] == "stop"
    panel = {
        "NEWUSDT": {
            "listing": stopped,
            "btc": btc,
            "listing_funding": pd.Series(dtype="float64"),
            "btc_funding": pd.Series(dtype="float64"),
            "launch": only_start - pd.Timedelta(days=15),
            "deadline": None,
            "deadline_kind": None,
            "listing_interval": pd.Timedelta(hours=48),
            "btc_interval": pd.Timedelta(hours=48),
        }
    }
    book = pd.DataFrame(
        [
            {
                "symbol": "NEWUSDT",
                "entry_time": only_start,
                "exit_time": only_start + pd.Timedelta(hours=1),
                "exit_reason": "stop",
                "net_official": 0.2,
                "net_measured": 0.2,
                "funding_missing": False,
                "truncated": False,
            }
        ]
    )
    means, kept = random_book_means(book, panel, "main", n_perm=3, seed=RANDOM_SEED)
    assert kept == 0
    assert means[0] == pytest.approx(direct["net_official"])

    short_listing = _hourly(BAR_START, 24 * 10)
    short_panel = {
        "SHORTUSDT": {
            "listing": short_listing,
            "btc": _hourly(BAR_START, 24 * 10, 200.0),
            "listing_funding": pd.Series(dtype="float64"),
            "btc_funding": pd.Series(dtype="float64"),
            "launch": short_listing.index[0],
            "deadline": None,
            "deadline_kind": None,
            "listing_interval": pd.Timedelta(hours=8),
            "btc_interval": pd.Timedelta(hours=8),
        }
    }
    short_book = pd.DataFrame(
        [
            {
                "symbol": "SHORTUSDT",
                "entry_time": short_listing.index[30],
                "exit_time": short_listing.index[40],
                "exit_reason": "truncated",
                "net_official": 0.123,
                "net_measured": 0.123,
                "funding_missing": False,
                "truncated": True,
            }
        ]
    )
    kept_means, n_kept = random_book_means(short_book, short_panel, "main", n_perm=2, seed=RANDOM_SEED)
    assert n_kept == 1
    assert kept_means[0] == pytest.approx(0.123)
    assert N_PERMUTATIONS == 2000
    assert RANDOM_SEED == 20261016


def test_permutation_p_value_uses_the_prereg_formula():
    assert permutation_p_value(1.0, np.zeros(2000)) == pytest.approx(1.0 / 2001.0)
    assert permutation_p_value(0.0, np.zeros(2000)) == pytest.approx(1.0)
    mixed = np.array([-1.0, 0.0, 2.0])
    assert permutation_p_value(0.0, mixed) == pytest.approx((1.0 + 2.0) / 4.0)


def test_mde_is_the_prereg_value_on_87_clusters():
    d = (MDE_Z_ALPHA + MDE_Z_POWER) / np.sqrt(MDE_CLUSTERS)
    assert round(d, 3) == 0.267
    assert MDE_D == 0.267
    assert MDE_CLUSTERS == 87


def test_drawdown_book_uses_ten_percent_of_equity_per_leg():
    entry = pd.Timestamp("2024-01-01T00:00:00Z")
    later = entry + pd.Timedelta(days=1)
    frame = pd.DataFrame(
        [
            {
                "symbol": "AAAUSDT",
                "entry_time": entry,
                "exit_time": later,
                "net_official": -0.5,
            }
        ]
    )
    # Size is 0.10. Dollar P&L is -0.05. Drawdown is 5%.
    assert book_max_drawdown(frame) == pytest.approx(0.05)

    second_entry = entry + pd.Timedelta(hours=1)
    both = pd.DataFrame(
        [
            {
                "symbol": "AAAUSDT",
                "entry_time": entry,
                "exit_time": later,
                "net_official": 0.10,
            },
            {
                "symbol": "BBBUSDT",
                "entry_time": second_entry,
                "exit_time": second_entry + pd.Timedelta(hours=2),
                "net_official": -0.50,
            },
        ]
    )
    # Both open against equity 1. B exits first: equity 0.95. A then adds 0.01.
    assert book_max_drawdown(both) == pytest.approx(0.05)


def test_catalog_windows_disclosure_and_no_imputation():
    events = load_events(check_pin=True)
    assert sha256_file(PACKAGE_DIR / "data" / "events_v2.csv") == EVENTS_V2_SHA256
    main = events_for_window(events, "main")
    holdout = events_for_window(events, "holdout")
    veto = events_for_window(events, "veto")
    assert len(main) == 364
    assert main["iso_week"].nunique() == 87
    assert len(holdout) == 128
    assert holdout["iso_week"].nunique() == 27
    assert len(veto) == 338
    assert veto["iso_week"].nunique() == 39
    assert "HMSTRUSDT" not in set(events["symbol"])
    for name in EXCLUSIONS:
        assert name not in set(events["symbol"])
    disclosure = coverage_disclosure()
    assert disclosure["snapshot"]["main"]["with_event"] == 191
    assert disclosure["snapshot"]["main"]["snapshot_usdt"] == 192
    assert disclosure["snapshot"]["main"]["missing"] == ["HMSTRUSDT"]
    assert disclosure["snapshot"]["main"]["imputed"] is False
    assert disclosure["snapshot"]["holdout"] == {
        "snapshot_usdt": 106,
        "with_event": 106,
        "missing": [],
        "imputed": False,
    }
    tradfi = {"stock", "ETF", "commodity", "forex"}
    assert not set(main["typ"]) & tradfi
    assert not set(holdout["typ"]) & tradfi
    assert set(veto["typ"]) & tradfi
    # D is in the catalog. The cell cannot be scored from survivors alone.
    assert (main["src"] == "D").any()
    assert window_years("main") == pytest.approx(624 / 365.25)
    assert 364 / window_years("main") == pytest.approx(213.0625)


def test_imputed_name_is_rejected(tmp_path: Path):
    source = (PACKAGE_DIR / "data" / "events_v2.csv").read_text(encoding="utf-8").splitlines()
    fields = source[1].split(",")
    fields[0] = "HMSTRUSDT"
    target = tmp_path / "events.csv"
    target.write_text("\n".join([source[0], ",".join(fields), *source[2:]]) + "\n", encoding="utf-8")
    with pytest.raises(Exception, match="HMSTRUSDT"):
        load_events(target, check_pin=False)


def test_documents_match_the_pinned_digests():
    assert sha256_file(PACKAGE_DIR / "SPEC.md") == LOCK_SHA256
    assert sha256_file(PACKAGE_DIR / "PREREG.md") == PREREG_SHA256
    hashes = source_hashes()
    assert hashes["hash_status"] == "provisional"
    assert hashes["garwe_ack"] is False
    assert hashes["countersign_sha256"] is None
    assert len(hashes["harness_sha256"]) == 64
    assert len(hashes["scorer_sha256"]) == 64


def test_package_does_not_touch_approvals():
    text = "\n".join(path.read_text(encoding="utf-8") for path in PACKAGE_DIR.glob("*.py"))
    assert "approved_strategies" not in text
    assert "APPROVALS_PATH" not in text


def test_sums_verification_and_real_tape_refusal(tmp_path: Path):
    tape = tmp_path / "fixture"
    tape.mkdir()
    payload = tape / "perp_1h.csv"
    payload.write_text("symbol,bar_open_ts_ms,open,high,low,close,volume\n", encoding="utf-8")
    digest = sha256_file(payload)
    (tape / "SHA256SUMS").write_text(f"{digest}  perp_1h.csv\n", encoding="utf-8")
    report = verify_sums(tape, "C")
    assert report["pins_matched"] is False
    assert report["n_files"] == 1
    (tape / "SHA256SUMS").write_text(f"{'ab' * 32}  perp_1h.csv\n", encoding="utf-8")
    with pytest.raises(TapeIntegrityError):
        verify_sums(tape, "C")
    assert TAPE_SUMS_SHA256["D"].startswith("5d81bda3")
    assert TAPE_SUMS_SHA256["C"].startswith("ab447221")
    assert TAPE_SUMS_SHA256["N"].startswith("9c9916e2")
    with pytest.raises(CountersignRequired):
        assert_real_tapes_closed(
            {
                "C": Path("/workspace/research/universe96_full_history_20261016"),
                "D": tmp_path / "D",
                "N": tmp_path / "N",
            },
            pins_matched=False,
        )


def _write_tape(root: Path, symbol: str, price: float, launch_ms: int, delist: str | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    index = pd.date_range("2024-01-01", periods=30, freq="h", tz="UTC")
    open_ms = (index.asi8 // 1_000_000).astype("int64")
    bars = pd.DataFrame(
        {
            "symbol": symbol,
            "bar_open_ts_ms": open_ms,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": 1.0,
        }
    )
    bars.to_csv(root / "perp_1h.csv", index=False)
    funding_time = index[8]
    pd.DataFrame(
        {
            "symbol": symbol,
            "funding_ts_ms": [int(funding_time.value // 1_000_000)],
            "funding_rate": [0.0],
        }
    ).to_csv(root / "funding.csv", index=False)
    row = {
        "symbol": symbol,
        "launchTime": launch_ms,
        "delistTime": "" if delist is None else delist,
        "fundingInterval_min": 480,
    }
    pd.DataFrame([row]).to_csv(root / "membership_pit.csv", index=False)
    lines = []
    for name in ("perp_1h.csv", "funding.csv", "membership_pit.csv"):
        lines.append(f"{sha256_file(root / name)}  {name}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_delisted_tape_d_is_the_source_for_a_d_event(tmp_path: Path):
    launch_ms = int(pd.Timestamp("2023-12-01T00:00:00Z").value // 1_000_000)
    _write_tape(tmp_path / "C", "BTCUSDT", 50.0, launch_ms)
    _write_tape(tmp_path / "D", "GONEUSDT", 80.0, launch_ms, delist="2024-01-01T20:00:00Z")
    _write_tape(tmp_path / "N", "OTHERUSDT", 70.0, launch_ms)
    # C does not list GONEUSDT. The fill has to come from D's price.
    with pytest.raises(TapeIntegrityError):
        load_symbol_bars(tmp_path / "C", "GONEUSDT")
    bars = load_symbol_bars(tmp_path / "D", "GONEUSDT")
    assert float(bars["open"].iloc[0]) == 80.0
    membership = load_membership(tmp_path / "D")
    deadline, kind = listing_deadline(membership, "GONEUSDT")
    assert kind == "delist"
    assert deadline == pd.Timestamp("2024-01-01T20:00:00Z")
    events = pd.DataFrame(
        [
            {
                "symbol": "GONEUSDT",
                "src": "D",
                "typ": "",
                "launch": pd.Timestamp("2023-12-01T00:00:00Z"),
                "entry": pd.Timestamp("2024-06-01T00:00:00Z"),
                "exit": pd.Timestamp("2024-06-15T00:00:00Z"),
                "lag_h": 1.0,
                "iso_week": "2024-W22",
            }
        ]
    )
    # The catalog entry is inside main, so the event is simulated. The tape
    # itself ends in January, which is a truncation, and the price is D's.
    result = run_window(
        events,
        {"C": tmp_path / "C", "D": tmp_path / "D", "N": tmp_path / "N"},
        __import__("research.new_listing_drift.cells", fromlist=["NEW_LISTING_DRIFT_SHORT"]).NEW_LISTING_DRIFT_SHORT,
        "main",
        tmp_path / "out",
    )
    trade = result["trades"].iloc[0]
    assert trade["src"] == "D"
    assert trade["listing_entry"] == 80.0 or np.isnan(trade["listing_entry"])
    # Launch is December, bars start 1 January. The first qualifying bar is
    # the first bar (already past launch+24h) and the entry is the next open.
    if trade["exit_reason"] != "no_trade":
        assert trade["listing_entry"] == 80.0
        assert trade["btc_entry"] == 50.0
