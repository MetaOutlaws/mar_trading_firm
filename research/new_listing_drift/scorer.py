"""Metrics, both cost levels, and the same-name random-date book.

Nothing in the harness imports this module. The hashes are provisional
until Garwe countersigns. Tests call this on synthetic books only.

Hard gates on main use the official 0.31% per leg only. They are the
house gates from ``research.validate.DEFAULT_CRITERIA`` plus this cell's
own floors:

* PF >= 1.15 on spread-trade net R
* week-cluster bootstrap 95% CI of the mean of cluster means excludes
  zero on the positive side (10,000 resamples, seed 42, the house bootstrap)
* beats-random p < 0.05
* at least 30 spread trades and 30 week-clusters
* at least 100 spread trades a year
* at least half of entry-quarters profitable
* max drawdown under 25% on the 10%-per-leg book

The measured proxy (BTC 0.135% + listing 0.181%) is reported beside the
official column. If the two means disagree in sign, the verdict is a veto.
A positive measured mean never turns a FAIL into a PASS.

Beats-random redraws each name's entry at a uniform 1h open inside the
same window, excluding that name's first 15 days. Count, side, hold,
stop, official cost and funding stay as they are. A name with no such
bar keeps its real trade and is not replaced. 2,000 permutations, seed
20261016. p = (1 + #{random mean >= observed}) / 2001.

Holdout passes only on a positive week-cluster mean and PF >= 1.15.
2026 is veto-only: with at least 10 clusters, a mean <= 0 or PF < 1.0
vetoes. Below 10 clusters it is report-only. Neither window can rescue
a main FAIL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from research.new_listing_drift.catalog import iso_week_id, window_bounds, window_years
from research.new_listing_drift.cells import (
    BOOTSTRAP_SEED,
    LEG_NOTIONAL_FRACTION,
    MDE_CLUSTERS,
    MDE_D,
    MDE_Z_ALPHA,
    MDE_Z_POWER,
    MIN_TRADES_PER_YEAR,
    N_BOOTSTRAP,
    N_PERMUTATIONS,
    RANDOM_SEED,
    VETO_MIN_CLUSTERS,
    VETO_PF,
)
from research.new_listing_drift.costs import (
    MEASURED_BTC_LEG_RATE,
    MEASURED_LABEL,
    MEASURED_LISTING_LEG_RATE,
    OFFICIAL_LEG_RATE,
)
from research.new_listing_drift.engine import eligible_random_opens, simulate_spread
from research.new_listing_drift.harness import HoldoutLockedError, load_book, manifest_of
from research.new_listing_drift.hashing import source_hashes, write_sha256sums
from research.significance import bootstrap_expectancy
from research.validate import DEFAULT_CRITERIA

# House thresholds, read from the house criteria so a second copy cannot drift.
PF_MIN = DEFAULT_CRITERIA.min_profit_factor
MIN_SPREAD_TRADES = DEFAULT_CRITERIA.min_oos_trades
MIN_WEEK_CLUSTERS = DEFAULT_CRITERIA.min_oos_trades
MAX_DRAWDOWN = DEFAULT_CRITERIA.max_drawdown_pct / 100.0
MIN_PROFITABLE_FOLD_RATIO = DEFAULT_CRITERIA.min_profitable_fold_ratio / 100.0
BEATS_RANDOM_ALPHA = 0.05


def permutation_p_value(observed: float, random_means: np.ndarray) -> float:
    """Prereg p-value. The +1 in the numerator and the denominator is required."""
    means = np.asarray(random_means, dtype="float64")
    if means.size == 0:
        raise ValueError("random book produced no means")
    count = int(np.sum(means >= observed))
    return (1.0 + count) / (means.size + 1.0)


def profit_factor(net: np.ndarray) -> float:
    """Profit factor of spread-trade net R. Inf when nothing was lost."""
    values = np.asarray(net, dtype="float64")
    won = float(np.sum(values[values > 0.0])) if np.any(values > 0.0) else 0.0
    lost = float(-np.sum(values[values < 0.0])) if np.any(values < 0.0) else 0.0
    if lost == 0.0:
        return float("inf") if won > 0.0 else 0.0
    return won / lost


def signs_disagree(official_mean: float, measured_mean: float) -> bool:
    """True when the two cost levels do not have the same sign.

    Zero disagrees with a positive mean and with a negative mean. The
    measured column is a veto in that case, and it still cannot rescue
    an official FAIL.
    """
    def _sign(value: float) -> int:
        if value > 0.0:
            return 1
        if value < 0.0:
            return -1
        return 0

    return _sign(official_mean) != _sign(measured_mean)


def week_cluster_means(net: pd.Series, entry_time: pd.Series) -> pd.Series:
    """Mean net R inside each ISO week of entry. One week, one cluster."""
    frame = pd.DataFrame({"net": net.to_numpy(dtype="float64"), "entry_time": entry_time})
    frame["week"] = iso_week_id(frame["entry_time"])
    return frame.groupby("week", sort=True)["net"].mean()


def book_max_drawdown(trades: pd.DataFrame, column: str = "net_official") -> float:
    """Max drawdown of the prereg book.

    Each trade is opened at 10% of current equity per leg notional. R is
    already the P&L per one-leg notional, so dollar P&L is R times that
    notional. Equity is marked at each exit. An exit that lands on another
    trade's entry is marked first. Equity at or below zero is a full loss.
    """
    if trades.empty:
        return 0.0
    rows = trades.sort_values(["entry_time", "symbol"]).to_dict("records")
    equity = 1.0
    peak = 1.0
    worst = 0.0
    open_book: list[tuple[pd.Timestamp, str, float]] = []

    def settle(until: pd.Timestamp) -> bool:
        nonlocal equity, peak, worst
        open_book.sort(key=lambda item: (item[0], item[1]))
        remain: list[tuple[pd.Timestamp, str, float]] = []
        ruined = False
        for exit_time, symbol, pnl in open_book:
            if exit_time > until:
                remain.append((exit_time, symbol, pnl))
                continue
            equity += pnl
            if equity <= 0.0:
                ruined = True
                break
            peak = max(peak, equity)
            worst = max(worst, (peak - equity) / peak)
        open_book[:] = remain
        return ruined

    for row in rows:
        if settle(pd.Timestamp(row["entry_time"])):
            return 1.0
        size = LEG_NOTIONAL_FRACTION * equity
        open_book.append(
            (pd.Timestamp(row["exit_time"]), str(row["symbol"]), float(row[column]) * size)
        )
    horizon = pd.Timestamp("2100-01-01", tz="UTC")
    if settle(horizon):
        return 1.0
    return worst


def profitable_quarter_ratio(trades: pd.DataFrame, column: str = "net_official") -> float:
    """Share of entry-quarters whose net R sums to a gain."""
    if trades.empty:
        return 0.0
    stamps = pd.to_datetime(trades["entry_time"], utc=True)
    quarter = stamps.dt.year.astype(str) + "Q" + (((stamps.dt.month - 1) // 3) + 1).astype(str)
    sums = trades.assign(quarter=quarter.to_numpy()).groupby("quarter", sort=True)[column].sum()
    if len(sums) == 0:
        return 0.0
    return float((sums > 0.0).mean())


def _gap_count(frame: pd.DataFrame) -> int:
    """Sum of in-hold funding gaps. Absent column means the book did not count."""
    if frame.empty or "funding_gaps" not in frame.columns:
        return 0
    return int(pd.to_numeric(frame["funding_gaps"], errors="coerce").fillna(0).sum())


def _finite_trades(trades: pd.DataFrame) -> pd.DataFrame:
    """Trades with a real official net. An ex-ante skip is not a zero."""
    if trades.empty:
        return trades
    taken = trades.loc[trades["exit_reason"] != "no_trade"].copy()
    nets = pd.to_numeric(taken["net_official"], errors="coerce")
    return taken.loc[nets.notna()].copy()


def random_book_means(
    trades: pd.DataFrame,
    panels: dict[str, dict[str, Any]],
    window: str,
    *,
    n_perm: int = N_PERMUTATIONS,
    seed: int = RANDOM_SEED,
) -> tuple[np.ndarray, int]:
    """Mean official net R of each same-name random-date book.

    The second return is the number of names that had no eligible bar and
    kept their real entry. That count is a property of the names, not of
    a particular draw, so it is the same in every permutation.
    """
    book = _finite_trades(trades)
    if book.empty:
        return np.empty(0, dtype="float64"), 0
    start, stop = window_bounds(window)
    prepared: list[tuple[float, pd.DatetimeIndex, dict[str, Any]]] = []
    kept = 0
    for row in book.sort_values("symbol").to_dict("records"):
        symbol = str(row["symbol"])
        panel = panels[symbol]
        opens = eligible_random_opens(
            panel["listing"],
            panel["btc"],
            launch=panel["launch"],
            window_start=start,
            window_stop=stop,
            deadline=panel.get("deadline"),
        )
        if len(opens) == 0:
            kept += 1
        prepared.append((float(row["net_official"]), opens, panel | {"symbol": symbol}))

    children = np.random.SeedSequence(seed).spawn(n_perm)
    means = np.empty(n_perm, dtype="float64")
    for i, child in enumerate(children):
        rng = np.random.default_rng(child)
        draw: list[float] = []
        for real_net, opens, panel in prepared:
            if len(opens) == 0:
                draw.append(real_net)
                continue
            pick = opens[int(rng.integers(0, len(opens)))]
            sim = simulate_spread(
                panel["listing"],
                panel["btc"],
                symbol=panel["symbol"],
                launch=panel["launch"],
                listing_funding=panel.get("listing_funding"),
                btc_funding=panel.get("btc_funding"),
                listing_interval=panel.get("listing_interval", pd.Timedelta(hours=8)),
                btc_interval=panel.get("btc_interval", pd.Timedelta(hours=8)),
                deadline=panel.get("deadline"),
                deadline_kind=panel.get("deadline_kind"),
                entry_time=pick,
            )
            net = sim["net_official"]
            # An ex-ante skip has no net. It is not scored as zero, and
            # that draw keeps the real trade. An in-hold gap has a finite
            # net (observed prints only) and is used.
            if net is None or (isinstance(net, float) and not np.isfinite(net)):
                draw.append(real_net)
            else:
                draw.append(float(net))
        means[i] = float(np.mean(draw))
    return means, kept


def _json_float(value: float) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def _level_block(net: np.ndarray, cluster_means: pd.Series) -> dict[str, object]:
    mean_events = float(net.mean()) if net.size else float("nan")
    mean_clusters = float(cluster_means.mean()) if len(cluster_means) else float("nan")
    pf = profit_factor(net) if net.size else 0.0
    return {
        "mean_net_r": _json_float(mean_events),
        "mean_week_cluster_r": _json_float(mean_clusters),
        "profit_factor": _json_float(pf),
        "profit_factor_infinite": bool(np.isinf(pf)),
    }


def score_trades(
    trades: pd.DataFrame,
    *,
    window: str,
    random_means: np.ndarray,
    names_kept_real: int = 0,
    n_bootstrap: int = N_BOOTSTRAP,
) -> dict[str, object]:
    """Apply the frozen gates. Official cost binds. Measured cost vetoes on sign."""
    book = _finite_trades(trades)
    missing_funding = 0
    n_truncated = 0
    n_funding_gaps = 0
    if len(trades):
        taken = trades.loc[trades["exit_reason"] != "no_trade"]
        missing_funding = int(taken["funding_missing"].fillna(False).astype(bool).sum()) if len(taken) else 0
        n_truncated = int(taken["truncated"].fillna(False).astype(bool).sum()) if len(taken) else 0
        n_funding_gaps = _gap_count(taken)
    # An in-hold gap stays in the book and does not blank the verdict.
    # funding_missing is the old refusal flag. The engine no longer sets
    # it for a counted gap. A row that still carries it cannot pass.
    incomplete = missing_funding > 0

    official = book["net_official"].to_numpy(dtype="float64") if len(book) else np.empty(0)
    measured = book["net_measured"].to_numpy(dtype="float64") if len(book) else np.empty(0)
    clusters = (
        week_cluster_means(book["net_official"], book["entry_time"]) if len(book) else pd.Series(dtype="float64")
    )
    measured_clusters = (
        week_cluster_means(book["net_measured"], book["entry_time"]) if len(book) else pd.Series(dtype="float64")
    )
    n_trades = int(official.size)
    n_weeks = int(clusters.size)
    official_block = _level_block(official, clusters)
    measured_block = _level_block(measured, measured_clusters)
    official_mean = float(official_block["mean_net_r"]) if official_block["mean_net_r"] is not None else float("nan")
    measured_mean = float(measured_block["mean_net_r"]) if measured_block["mean_net_r"] is not None else float("nan")
    cluster_mean = (
        float(official_block["mean_week_cluster_r"])
        if official_block["mean_week_cluster_r"] is not None
        else float("nan")
    )
    pf = profit_factor(official) if n_trades else 0.0
    drawdown = book_max_drawdown(book) if n_trades else 0.0
    quarter_ratio = profitable_quarter_ratio(book) if n_trades else 0.0
    years = window_years(window)
    per_year = n_trades / years if years else float("nan")

    observed = official_mean
    p_value = permutation_p_value(observed, random_means) if n_trades and random_means.size else 1.0
    bootstrap = bootstrap_expectancy(
        clusters.to_numpy(dtype="float64"),
        iterations=n_bootstrap,
        confidence=0.95,
        seed=BOOTSTRAP_SEED,
    )
    ci_ok = bool(bootstrap.is_significant) and not incomplete
    pf_ok = bool((np.isfinite(pf) and pf >= PF_MIN) or (np.isinf(pf) and pf > 0.0))
    beats = bool(p_value < BEATS_RANDOM_ALPHA) and not incomplete
    trades_ok = n_trades >= MIN_SPREAD_TRADES and not incomplete
    weeks_ok = n_weeks >= MIN_WEEK_CLUSTERS and not incomplete
    rate_ok = bool(np.isfinite(per_year) and per_year >= MIN_TRADES_PER_YEAR) and not incomplete
    folds_ok = quarter_ratio + 1e-15 >= MIN_PROFITABLE_FOLD_RATIO and not incomplete
    # The prereg says max DD under 25%. Equal to 25% does not pass.
    dd_ok = drawdown < MAX_DRAWDOWN and not incomplete
    sign_veto = bool(
        n_trades
        and np.isfinite(official_mean)
        and np.isfinite(measured_mean)
        and signs_disagree(official_mean, measured_mean)
    )

    gates = {
        "profit_factor": {"threshold": PF_MIN, "value": _json_float(pf), "pass": pf_ok, "cost": "official"},
        "week_cluster_ci": {
            "threshold": "95% CI of the mean of week-cluster means excludes zero on the positive side",
            "ci95_low": float(bootstrap.ci_low),
            "ci95_high": float(bootstrap.ci_high),
            "pass": ci_ok,
            "iterations": n_bootstrap,
            "seed": BOOTSTRAP_SEED,
            "cost": "official",
        },
        "beats_random": {
            "threshold": BEATS_RANDOM_ALPHA,
            "p_value": p_value if n_trades else None,
            "pass": beats,
            "permutations": int(random_means.size),
            "seed": RANDOM_SEED,
            "names_kept_real": names_kept_real,
            "exclusion": "first 15 days after launch",
            "cost": "official",
        },
        "spread_trades": {"threshold": MIN_SPREAD_TRADES, "value": n_trades, "pass": trades_ok},
        "week_clusters": {"threshold": MIN_WEEK_CLUSTERS, "value": n_weeks, "pass": weeks_ok},
        "trades_per_year": {
            "threshold": MIN_TRADES_PER_YEAR,
            "value": _json_float(per_year),
            "years": years,
            "pass": rate_ok,
        },
        "profitable_quarters": {
            "threshold": MIN_PROFITABLE_FOLD_RATIO,
            "value": quarter_ratio,
            "pass": folds_ok,
        },
        "max_drawdown": {
            "threshold": MAX_DRAWDOWN,
            "comparison": "<",
            "value": drawdown,
            "leg_notional_fraction": LEG_NOTIONAL_FRACTION,
            "pass": dd_ok,
        },
        "measured_sign_veto": {
            "pass": not sign_veto,
            "sign_disagrees": sign_veto,
            "can_rescue_a_fail": False,
        },
    }

    official_pass = bool(
        n_trades
        and pf_ok
        and ci_ok
        and beats
        and trades_ok
        and weeks_ok
        and rate_ok
        and folds_ok
        and dd_ok
        and not incomplete
    )
    # Measured never rescues. A sign disagreement vetoes only an otherwise
    # official pass; an official fail stays a fail.
    if window == "holdout":
        passed = bool(n_trades and cluster_mean > 0.0 and pf_ok and not incomplete and not sign_veto)
        if incomplete:
            verdict = "INCOMPLETE"
        elif sign_veto and cluster_mean > 0.0 and pf_ok:
            verdict = "VETO"
        else:
            verdict = "PASS" if passed else "FAIL"
        applied = ["positive_week_cluster_mean", "profit_factor", "measured_sign_veto"]
    elif window == "veto":
        # Veto-only. Fewer than 10 week-clusters is report-only. Never a PASS.
        pf_veto = bool(np.isfinite(pf) and pf < VETO_PF) or (n_trades == 0)
        mean_veto = bool(not np.isfinite(cluster_mean) or cluster_mean <= 0.0)
        if incomplete:
            verdict = "INCOMPLETE"
        elif n_weeks < VETO_MIN_CLUSTERS:
            verdict = "REPORT_ONLY"
        elif mean_veto or pf_veto or sign_veto:
            verdict = "VETO"
        else:
            verdict = "NO_VETO"
        passed = False
        applied = ["veto_only"]
    else:
        if incomplete:
            verdict = "INCOMPLETE"
            passed = False
        elif official_pass and sign_veto:
            verdict = "VETO"
            passed = False
        elif official_pass:
            verdict = "PASS"
            passed = True
        else:
            verdict = "FAIL"
            passed = False
        applied = list(gates)

    hashes = source_hashes()
    return {
        "window": window,
        "live": "off",
        "paper_only": True,
        "hash_status": hashes["hash_status"],
        "garwe_ack": hashes["garwe_ack"],
        "can_rescue_a_fail": False,
        "unit": (
            "spread R per one-leg notional: short listing return + long BTC "
            "return + funding (listing received minus BTC paid) - cost"
        ),
        "n_spread_trades": n_trades,
        "n_week_clusters": n_weeks,
        "n_funding_missing": missing_funding,
        "n_funding_gaps": n_funding_gaps,
        "n_truncated": n_truncated,
        "funding_zero_filled": False,
        "funding_gap_rule": (
            "In-hold gaps are counted and accrued from observed prints. "
            "They do not drop the event. A skip is only the 8h before entry."
        ),
        "incomplete_funding": incomplete,
        "trades_per_year": _json_float(per_year),
        "max_drawdown": drawdown,
        "profitable_quarter_ratio": quarter_ratio,
        "beats_random_p": p_value if n_trades else None,
        "random_mean_of_means": _json_float(float(np.mean(random_means))) if random_means.size else None,
        "names_kept_real": names_kept_real,
        "official": {
            "binds_gates": True,
            "per_leg_round_trip": OFFICIAL_LEG_RATE,
            "per_spread": OFFICIAL_LEG_RATE * 2.0,
            **official_block,
        },
        "measured_proxy": {
            "binds_gates": False,
            "report_only": True,
            "label": MEASURED_LABEL,
            "btc_leg_round_trip": MEASURED_BTC_LEG_RATE,
            "listing_leg_round_trip": MEASURED_LISTING_LEG_RATE,
            "per_spread": MEASURED_BTC_LEG_RATE + MEASURED_LISTING_LEG_RATE,
            "sign_veto": sign_veto,
            "can_rescue_a_fail": False,
            **measured_block,
        },
        "mde": {
            "d": MDE_D,
            "clusters": MDE_CLUSTERS,
            "alpha_one_sided": 0.05,
            "power": 0.80,
            "formula": "(z_alpha + z_power) / sqrt(n)",
            "z_alpha": MDE_Z_ALPHA,
            "z_power": MDE_Z_POWER,
            "is_a_gate": False,
            "note": "Preregistered MDE on 87 main week-clusters. Not estimated from this book.",
        },
        "gates": gates,
        "gates_applied": applied,
        "verdict": verdict,
        "passed": passed,
        "house_criteria": {
            "min_profit_factor": PF_MIN,
            "min_oos_trades": MIN_SPREAD_TRADES,
            "max_drawdown_pct": DEFAULT_CRITERIA.max_drawdown_pct,
            "min_profitable_fold_ratio": DEFAULT_CRITERIA.min_profitable_fold_ratio,
        },
    }


def score_book(
    output_dir: Path,
    panels: dict[str, dict[str, Any]],
    *,
    n_perm: int = N_PERMUTATIONS,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = RANDOM_SEED,
) -> dict[str, object]:
    """Score a harness directory. Refuses a closed window the lock did not open.

    Writes ``metrics.json`` and ``random_book.json``, then refreshes
    SHA256SUMS. The new SHA256SUMS digest is the output hash.
    """
    output_dir = Path(output_dir)
    manifest = manifest_of(output_dir)
    window = str(manifest.get("window"))
    if window in {"holdout", "veto"} and not manifest.get("closed_window_unlocked_with_main_hash"):
        raise HoldoutLockedError(
            "Refusing to score a holdout or 2026 book that does not record a main-output hash."
        )
    trades = load_book(output_dir)
    if _finite_trades(trades).empty:
        means = np.array([], dtype="float64")
        kept = 0
    else:
        means, kept = random_book_means(trades, panels, window, n_perm=n_perm, seed=seed)
    if means.size == 0:
        metrics = score_trades(
            trades,
            window=window,
            random_means=np.array([0.0]),
            names_kept_real=kept,
            n_bootstrap=n_bootstrap,
        )
        metrics["verdict"] = "FAIL" if window != "veto" else "REPORT_ONLY"
        metrics["passed"] = False
        metrics["beats_random_p"] = None
        metrics["empty_book"] = True
    else:
        metrics = score_trades(
            trades,
            window=window,
            random_means=means,
            names_kept_real=kept,
            n_bootstrap=n_bootstrap,
        )
    metrics["cell"] = manifest.get("cell")
    metrics["n_permutations"] = int(means.size) if means.size else 0
    metrics["random_seed"] = seed
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    random_payload = {
        "seed": seed,
        "n_permutations": int(means.size),
        "names_kept_real": kept,
        "means": [float(v) for v in means],
        "note": (
            "Each mean is a same-name random-date book. Entries are uniform "
            "1h opens in the window, excluding the first 15 days. Hold, stop, "
            "official cost and funding match the real trade. A name with no "
            "eligible bar keeps its real net."
        ),
    }
    (output_dir / "random_book.json").write_text(
        json.dumps(random_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sums_path = output_dir / "SHA256SUMS"
    if sums_path.is_file():
        sums_path.unlink()
    output_hash = write_sha256sums(output_dir)
    metrics["output_sha256"] = output_hash
    return metrics
