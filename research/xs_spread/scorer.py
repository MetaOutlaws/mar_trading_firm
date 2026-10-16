"""Metrics and the turnover-matched random book.

Nothing in the harness imports this module. Garwe ACKs ``scorer_sha256``
before a real-tape metric is read. Tests call it on synthetic books only.

Gates are the house gates, read from ``research.validate.DEFAULT_CRITERIA``
(PF >= 1.15, bootstrap CI excludes zero on the positive side, beats-random
at 5%, at least 30 leg-trades and 30 week-clusters, at least half of
quarterly folds profitable, max drawdown under 25%). This cell does not
carry a second set of numbers.

Beats-random is the prereg's book, not a reshuffle of the strategy's
trades. At each rebalance the null draws long and short sets of the same
size from the same point-in-time names, carrying the previous random book
and replacing exactly the realized number of names on each leg. The same
12% stop, next-open fill and 0.31% per leg-trade are applied through
``book.apply_schedule``. Stop costs stay path-dependent; the matched
quantity is the rebalance turnover.

p = (1 + #{random mean net weekly spread >= observed}) / (n_perm + 1)
with 2,000 permutations and seed 20261016. One-sided. The cell passes
when p < 0.05.

The week-cluster interval is the house bootstrap
(``research.significance.bootstrap_expectancy``, 10,000 resamples, seed 42)
on the weekly net spread. One ISO week is one cluster. Profit factor is
the sum of positive weekly nets over the absolute sum of negative weekly
nets.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.significance import bootstrap_expectancy
from research.validate import DEFAULT_CRITERIA
from research.xs_spread.book import apply_schedule
from research.xs_spread.cells import WINDOWS, XS_PROSPECT_VALUE_WEEKLY
from research.xs_spread.harness import HoldoutLockedError, load_book, manifest_of
from research.xs_spread.hashing import write_sha256sums
from research.xs_spread.tk import apply_tk_schedule

RANDOM_SEED = 20261016
N_PERMUTATIONS = 2000
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 42

# House thresholds. The prereg names the same PF, CI, beats-random, 30-count,
# 50% fold and 25% drawdown gates. They are read from the house criteria so
# a second copy cannot drift.
PF_MIN = DEFAULT_CRITERIA.min_profit_factor
MIN_LEG_TRADES = DEFAULT_CRITERIA.min_oos_trades
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
    """Profit factor of weekly net spread returns. Inf when nothing lost."""
    values = np.asarray(net, dtype="float64")
    won = float(np.sum(values[values > 0.0])) if np.any(values > 0.0) else 0.0
    lost = float(-np.sum(values[values < 0.0])) if np.any(values < 0.0) else 0.0
    if lost == 0.0:
        return float("inf") if won > 0.0 else 0.0
    return won / lost


def max_drawdown(net: np.ndarray) -> float:
    """Max drawdown of equity compounded from the weekly net spread."""
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in np.asarray(net, dtype="float64"):
        equity *= 1.0 + float(value)
        if equity <= 0.0:
            return 1.0
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak)
    return worst


def profitable_quarter_ratio(weekly: pd.DataFrame) -> float:
    """Share of calendar quarters whose net spread sums to a gain."""
    if weekly.empty:
        return 0.0
    frame = weekly.copy()
    frame["rebalance_time"] = pd.to_datetime(frame["rebalance_time"], utc=True)
    stamps = frame["rebalance_time"].dt.tz_convert("UTC")
    frame["quarter"] = (
        stamps.dt.year.astype(str) + "Q" + (((stamps.dt.month - 1) // 3) + 1).astype(str)
    )
    sums = frame.groupby("quarter", sort=True)["net_spread"].sum()
    if len(sums) == 0:
        return 0.0
    return float((sums > 0.0).mean())


def draw_leg(
    prev: set[str],
    eligible: list[str],
    k: int,
    n_new: int,
    banned: set[str],
    rng: np.random.Generator,
) -> set[str]:
    """Carry ``prev`` and replace ``n_new`` names.

    Names that left the eligible set cannot be carried, so a delisting can
    force extra turnover. On a stable eligible set with constant ``k`` the
    random leg has exactly ``n_new`` names that were not in ``prev``.
    """
    pool = [symbol for symbol in eligible if symbol not in banned]
    pool_set = set(pool)
    carried = [symbol for symbol in sorted(prev) if symbol in pool_set]
    target_keep = min(len(carried), max(0, k - int(n_new)))
    if len(carried) > target_keep:
        n_drop = len(carried) - target_keep
        drop_idx = rng.choice(len(carried), size=n_drop, replace=False)
        dropped = {carried[int(i)] for i in np.atleast_1d(drop_idx)}
        keep = [symbol for symbol in carried if symbol not in dropped]
    else:
        keep = list(carried)
    need = k - len(keep)
    keep_set = set(keep)
    # A dropped name has to stay dropped. Drawing it straight back would
    # make the realized turnover a ceiling instead of a match.
    fresh = [symbol for symbol in pool if symbol not in keep_set and symbol not in prev]
    if need > len(fresh):
        raise RuntimeError(
            f"eligible set cannot fill the leg: need {need} new names, have {len(fresh)}"
        )
    if need:
        pick = rng.choice(len(fresh), size=need, replace=False)
        chosen = [fresh[int(i)] for i in np.atleast_1d(pick)]
    else:
        chosen = []
    return set(keep) | set(chosen)


def _week_sets(weights: pd.DataFrame) -> list[tuple[pd.Timestamp, set[str], set[str]]]:
    """Realized long set and short set, in rebalance order."""
    weeks = []
    order = list(dict.fromkeys(pd.to_datetime(weights["rebalance_time"], utc=True)))
    grouped = weights.copy()
    grouped["rebalance_time"] = pd.to_datetime(grouped["rebalance_time"], utc=True)
    for t in order:
        part = grouped[grouped["rebalance_time"] == t]
        long = set(part.loc[part["side"] == "long", "symbol"].astype(str))
        short = set(part.loc[part["side"] == "short", "symbol"].astype(str))
        weeks.append((t, long, short))
    return weeks


def turnover_matched_schedule(
    weights: pd.DataFrame,
    paths: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """One random book with the realized leg size and the realized name-churn."""
    path_times = pd.to_datetime(paths["rebalance_time"], utc=True)
    weeks = _week_sets(weights)
    # n_new is measured on the realized book. The carried book is the random
    # one. Mixing the two would make the null's turnover depend on its own
    # previous draw instead of the strategy's realized churn.
    prev_realized_long: set[str] = set()
    prev_realized_short: set[str] = set()
    prev_random_long: set[str] = set()
    prev_random_short: set[str] = set()
    drawn: list[tuple[pd.Timestamp, set[str], set[str]]] = []
    for t, long, short in weeks:
        pool = sorted(set(paths.loc[path_times == t, "symbol"].astype(str)))
        n_new_long = len(long - prev_realized_long)
        n_new_short = len(short - prev_realized_short)
        random_long = draw_leg(prev_random_long, pool, len(long), n_new_long, set(), rng)
        random_short = draw_leg(
            prev_random_short, pool, len(short), n_new_short, random_long, rng
        )
        drawn.append((t, random_long, random_short))
        prev_realized_long, prev_realized_short = long, short
        prev_random_long, prev_random_short = random_long, random_short
    rows: list[dict[str, object]] = []
    for t, long, short in drawn:
        for symbol in sorted(long):
            rows.append(
                {
                    "rebalance_time": t,
                    "symbol": symbol,
                    "side": "long",
                    "weight": 1.0 / len(long),
                    "score": np.nan,
                }
            )
        for symbol in sorted(short):
            rows.append(
                {
                    "rebalance_time": t,
                    "symbol": symbol,
                    "side": "short",
                    "weight": -1.0 / len(short),
                    "score": np.nan,
                }
            )
    return pd.DataFrame(rows)


def random_book_means(
    weights: pd.DataFrame,
    paths: pd.DataFrame,
    *,
    n_perm: int = N_PERMUTATIONS,
    seed: int = RANDOM_SEED,
) -> np.ndarray:
    """Mean net weekly spread of each turnover-matched random book."""
    children = np.random.SeedSequence(seed).spawn(n_perm)
    means = np.empty(n_perm, dtype="float64")
    for i, child in enumerate(children):
        rng = np.random.default_rng(child)
        random_weights = turnover_matched_schedule(weights, paths, rng)
        weekly, _trades = apply_schedule(random_weights, paths)
        means[i] = float(weekly["net_spread"].mean()) if len(weekly) else float("nan")
    return means


def _json_float(value: float) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def score_weekly(
    weekly: pd.DataFrame,
    *,
    window: str,
    random_means: np.ndarray,
    n_bootstrap: int = N_BOOTSTRAP,
) -> dict[str, object]:
    """Apply the frozen gates. Holdout and the 2026 veto use their own rules."""
    net = weekly["net_spread"].to_numpy(dtype="float64") if len(weekly) else np.empty(0)
    n_weeks = int(net.size)
    n_leg_trades = int(weekly["n_leg_trades"].sum()) if n_weeks else 0
    mean = float(net.mean()) if n_weeks else float("nan")
    pf = profit_factor(net) if n_weeks else 0.0
    drawdown = max_drawdown(net) if n_weeks else 0.0
    quarter_ratio = profitable_quarter_ratio(weekly)
    observed = mean
    p_value = permutation_p_value(observed, random_means) if n_weeks else 1.0
    bootstrap = bootstrap_expectancy(
        net,
        iterations=n_bootstrap,
        confidence=0.95,
        seed=BOOTSTRAP_SEED,
    )
    ci_ok = bool(bootstrap.is_significant)
    pf_ok = bool((np.isfinite(pf) and pf >= PF_MIN) or (np.isinf(pf) and pf > 0.0))
    beats = bool(p_value < BEATS_RANDOM_ALPHA)
    trades_ok = n_leg_trades >= MIN_LEG_TRADES
    weeks_ok = n_weeks >= MIN_WEEK_CLUSTERS
    folds_ok = quarter_ratio + 1e-15 >= MIN_PROFITABLE_FOLD_RATIO
    dd_ok = drawdown <= MAX_DRAWDOWN + 1e-15

    gates = {
        "profit_factor": {"threshold": PF_MIN, "value": _json_float(pf), "pass": pf_ok},
        "week_cluster_ci": {
            "threshold": "95% CI of the mean excludes zero on the positive side",
            "ci95_low": float(bootstrap.ci_low),
            "ci95_high": float(bootstrap.ci_high),
            "pass": ci_ok,
            "iterations": n_bootstrap,
            "seed": BOOTSTRAP_SEED,
        },
        "beats_random": {
            "threshold": BEATS_RANDOM_ALPHA,
            "p_value": p_value,
            "pass": beats,
            "permutations": int(random_means.size),
            "seed": RANDOM_SEED,
        },
        "leg_trades": {"threshold": MIN_LEG_TRADES, "value": n_leg_trades, "pass": trades_ok},
        "week_clusters": {"threshold": MIN_WEEK_CLUSTERS, "value": n_weeks, "pass": weeks_ok},
        "profitable_quarters": {
            "threshold": MIN_PROFITABLE_FOLD_RATIO,
            "value": quarter_ratio,
            "pass": folds_ok,
        },
        "max_drawdown": {"threshold": MAX_DRAWDOWN, "value": drawdown, "pass": dd_ok},
    }

    if window == "holdout":
        # No 30-week floor. Positive week-cluster mean and PF >= 1.15.
        passed = bool(mean > 0.0 and pf_ok)
        verdict = "PASS" if passed else "FAIL"
        applied = ("positive_mean", "profit_factor")
    elif window == "veto":
        # Veto-only. Fewer than 10 weeks is report-only. Never a PASS.
        if n_weeks < 10:
            verdict = "REPORT_ONLY"
        elif mean <= 0.0:
            verdict = "VETO"
        else:
            verdict = "NO_VETO"
        passed = False
        applied = ("veto_only",)
    else:
        applied_gates = (
            pf_ok,
            ci_ok,
            beats,
            trades_ok,
            weeks_ok,
            folds_ok,
            dd_ok,
        )
        passed = bool(n_weeks > 0 and all(applied_gates))
        verdict = "PASS" if passed else "FAIL"
        applied = tuple(gates)

    return {
        "window": window,
        "live": "off",
        "paper_only": True,
        "can_rescue_a_fail": False,
        "unit": "weekly net spread (long EW mean minus short EW mean, net of 0.31% per leg-trade)",
        "n_weeks": n_weeks,
        "n_leg_trades": n_leg_trades,
        "mean_net_spread": _json_float(mean),
        "profit_factor": _json_float(pf),
        "profit_factor_infinite": bool(np.isinf(pf)),
        "max_drawdown": drawdown,
        "profitable_quarter_ratio": quarter_ratio,
        "total_cost": float(weekly["cost"].sum()) if n_weeks else 0.0,
        "mean_turnover": float(weekly["turnover"].mean()) if n_weeks else 0.0,
        "beats_random_p": p_value,
        "random_mean_of_means": _json_float(float(np.mean(random_means))),
        "gates": gates,
        "gates_applied": list(applied),
        "verdict": verdict,
        "passed": passed if window != "veto" else False,
        "house_criteria": {
            "min_profit_factor": PF_MIN,
            "min_oos_trades": MIN_LEG_TRADES,
            "max_drawdown_pct": DEFAULT_CRITERIA.max_drawdown_pct,
            "min_profitable_fold_ratio": DEFAULT_CRITERIA.min_profitable_fold_ratio,
        },
    }


def score_book(
    output_dir: Path,
    *,
    n_perm: int = N_PERMUTATIONS,
    n_bootstrap: int = N_BOOTSTRAP,
    seed: int = RANDOM_SEED,
) -> dict[str, object]:
    """Score a harness directory. Refuses a holdout book the lock did not open.

    Writes ``metrics.json`` and ``random_book.json``, then refreshes
    SHA256SUMS. The new SHA256SUMS digest is the output hash.
    """
    output_dir = Path(output_dir)
    manifest = manifest_of(output_dir)
    if manifest.get("score_profile") == "prospect_value":
        return _score_prospect_book(
            output_dir,
            manifest,
            n_perm=n_perm,
            n_bootstrap=n_bootstrap,
            seed=seed,
        )
    window = str(manifest.get("window"))
    if window == "holdout" and not manifest.get("holdout_unlocked_with_main_hash"):
        raise HoldoutLockedError(
            "Refusing to score a holdout book that does not record a main-output hash."
        )
    tables = load_book(output_dir)
    weights = tables["weights"]
    paths = tables["name_paths"]
    weekly = tables["weekly_returns"]
    if len(weights) == 0 or len(weekly) == 0:
        # An empty book has no mean to compare. It is not a pass.
        means = np.array([], dtype="float64")
    else:
        # Recompute the observed book through the same function as the null,
        # and refuse to score if it does not match the harness file.
        recomputed, _trades = apply_schedule(weights, paths)
        if len(recomputed) != len(weekly):
            raise RuntimeError("recomputed week count does not match weekly_returns.csv")
        if not np.allclose(
            recomputed["net_spread"].to_numpy(dtype="float64"),
            weekly["net_spread"].to_numpy(dtype="float64"),
            rtol=0.0,
            atol=1e-12,
        ):
            raise RuntimeError("recomputed net spread does not match weekly_returns.csv")
        means = random_book_means(weights, paths, n_perm=n_perm, seed=seed)
    if means.size == 0:
        metrics = score_weekly(weekly, window=window, random_means=np.array([0.0]), n_bootstrap=n_bootstrap)
        metrics["verdict"] = "FAIL" if window != "veto" else "REPORT_ONLY"
        metrics["passed"] = False
        metrics["beats_random_p"] = None
        metrics["empty_book"] = True
    else:
        metrics = score_weekly(weekly, window=window, random_means=means, n_bootstrap=n_bootstrap)
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
        "means": [float(v) for v in means],
        "note": (
            "Each mean is a turnover-matched random tercile book. Rebalance "
            "churn matches the realized number of new names on each leg. "
            "Stop costs follow that book's own paths and are not forced equal."
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


def fama_macbeth_tstats(coefficients: np.ndarray) -> dict[str, float | None]:
    """Mean coefficient, Fama-MacBeth t, and Newey-West lag-1 t.

    One week is one cluster. The Fama-MacBeth standard error is the sample
    standard deviation of the weekly coefficients divided by sqrt(T).

    Newey-West lag 1 uses the Bartlett weight ``1 - 1/2``. With
    ``γ_j = (1/T) Σ e_t e_{t-j}`` the variance of the mean is
    ``(γ_0 + γ_1) / T``. A non-positive variance has no t-stat.
    """
    values = np.asarray(coefficients, dtype="float64")
    values = values[np.isfinite(values)]
    count = int(values.size)
    if count == 0:
        return {"mean": None, "fama_macbeth_t": None, "newey_west_lag1_t": None, "n_weeks": 0}
    mean = float(values.mean())
    if count < 2:
        return {"mean": mean, "fama_macbeth_t": None, "newey_west_lag1_t": None, "n_weeks": count}
    deviations = values - mean
    sample_sd = float(np.sqrt(np.sum(deviations ** 2) / (count - 1)))
    fm_t = mean / (sample_sd / np.sqrt(count)) if sample_sd > 0.0 else None
    gamma0 = float(np.sum(deviations ** 2) / count)
    gamma1 = float(np.sum(deviations[1:] * deviations[:-1]) / count)
    nw_var = (gamma0 + gamma1) / count
    nw_t = float(mean / np.sqrt(nw_var)) if nw_var > 0.0 else None
    return {
        "mean": mean,
        "fama_macbeth_t": None if fm_t is None or not np.isfinite(fm_t) else float(fm_t),
        "newey_west_lag1_t": None if nw_t is None or not np.isfinite(nw_t) else float(nw_t),
        "n_weeks": count,
    }


def _zscore(values: np.ndarray) -> np.ndarray | None:
    """Cross-sectional z-score. A zero sample standard deviation is undefined."""
    sample = np.asarray(values, dtype="float64")
    if sample.size < 2:
        return None
    center = float(np.mean(sample))
    scale = float(np.sqrt(np.sum((sample - center) ** 2) / (sample.size - 1)))
    if not np.isfinite(scale) or scale == 0.0:
        return None
    return (sample - center) / scale


def _ols_slope(outcome: np.ndarray, design: np.ndarray) -> float | None:
    """Slope on column 1. A rank-deficient week is skipped, not pinned at zero."""
    rank = int(np.linalg.matrix_rank(design, tol=1e-10))
    if rank < design.shape[1]:
        return None
    beta, *_rest = np.linalg.lstsq(design, outcome, rcond=None)
    slope = float(beta[1])
    if not np.isfinite(slope):
        return None
    return slope


def partial_ret60_report(scores: pd.DataFrame) -> dict[str, object]:
    """Fama-MacBeth TK slope, alone and with ret60 partialled out.

    Each week is a cross-sectional OLS of the gross 7-day next-open return
    on the z-scored TK value and, in the second regression, the z-scored
    sum of the same daily log returns. Report only. It does not bind a gate.
    """
    empty = {
        "binds_gates": False,
        "rescues_or_vetoes": False,
        "tk_alone": fama_macbeth_tstats(np.array([])),
        "tk_partial_ret60": fama_macbeth_tstats(np.array([])),
    }
    if scores is None or len(scores) == 0:
        return empty
    frame = scores.copy()
    frame["rebalance_time"] = pd.to_datetime(frame["rebalance_time"], utc=True)
    needed = {"score", "ret60", "forward_return"}
    if not needed.issubset(frame.columns):
        raise ValueError("scores.csv is missing TK, ret60 or the forward return")
    alone: list[float] = []
    partial: list[float] = []
    for _stamp, part in frame.groupby("rebalance_time", sort=True):
        usable = part.replace([np.inf, -np.inf], np.nan).dropna(subset=["score", "ret60", "forward_return"])
        n = len(usable)
        if n < 3:
            continue
        outcome = usable["forward_return"].to_numpy(dtype="float64")
        z_tk = _zscore(usable["score"].to_numpy(dtype="float64"))
        if z_tk is None:
            continue
        alone_slope = _ols_slope(outcome, np.column_stack([np.ones(n), z_tk]))
        if alone_slope is not None:
            alone.append(alone_slope)
        if n < 4:
            continue
        z_ret = _zscore(usable["ret60"].to_numpy(dtype="float64"))
        if z_ret is None:
            continue
        partial_slope = _ols_slope(outcome, np.column_stack([np.ones(n), z_tk, z_ret]))
        if partial_slope is not None:
            partial.append(partial_slope)
    return {
        "binds_gates": False,
        "rescues_or_vetoes": False,
        "tk_alone": fama_macbeth_tstats(np.asarray(alone, dtype="float64")),
        "tk_partial_ret60": fama_macbeth_tstats(np.asarray(partial, dtype="float64")),
    }


def momentum_explained_flag(*, passed: bool, t_stat: float | None) -> bool:
    """Tag a main PASS whose partialled TK t-stat is below 1.

    The tag does not change the verdict. A fail stays a fail. A t-stat that
    was not estimated is not tagged.
    """
    if not passed or t_stat is None:
        return False
    if not np.isfinite(t_stat):
        return False
    return bool(t_stat < 1.0)


def _regime_gate(weekly: pd.DataFrame) -> dict[str, object]:
    """A regime with at least 5 weeks and a negative mean fails.

    Fewer than 5 weeks is report-only. Unlabelled weeks are not a regime.
    """
    if "regime" not in weekly.columns or weekly.empty:
        return {"pass": True, "regimes": {}, "failing": []}
    report: dict[str, object] = {}
    failing: list[str] = []
    labelled = weekly[weekly["regime"].isin(["BULL", "BEAR", "CHOP"])]
    for regime, part in labelled.groupby("regime", sort=True):
        mean = float(part["net_spread"].mean())
        n = len(part)
        if n < 5:
            status = "report_only"
        elif mean < 0.0:
            status = "fail"
            failing.append(str(regime))
        else:
            status = "pass"
        report[str(regime)] = {"n_weeks": n, "mean_net_spread": mean, "status": status}
    return {"pass": len(failing) == 0, "regimes": report, "failing": failing}


def prospect_main_verdict(*, official_pass: bool, sign_veto: bool) -> tuple[str, bool]:
    """The proxy column can veto a pass. It cannot turn a fail into a pass."""
    if not official_pass:
        return "FAIL", False
    if sign_veto:
        return "VETO", False
    return "PASS", True


def _leg_trades_per_year(n_leg_trades: int, window: str) -> float:
    start, end = WINDOWS[window]
    years = (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25
    if years <= 0:
        return 0.0
    return float(n_leg_trades) / years


def _score_prospect_book(
    output_dir: Path,
    manifest: dict[str, object],
    *,
    n_perm: int,
    n_bootstrap: int,
    seed: int,
) -> dict[str, object]:
    """Score TK at 0.31%. The 0.158% proxy is reported and can only veto."""
    window = str(manifest.get("window"))
    if window == "holdout" and not manifest.get("holdout_unlocked_with_main_hash"):
        raise HoldoutLockedError(
            "Refusing to score a holdout book that does not record a main-output hash."
        )
    if window == "veto" and not manifest.get("holdout_unlocked_with_main_hash"):
        raise HoldoutLockedError(
            "Refusing to score a 2026 veto book that does not record a main-output hash."
        )
    tables = load_book(output_dir)
    weights = tables["weights"]
    paths = tables["name_paths"]
    weekly = tables["weekly_returns"]
    scores = tables.get("scores")
    if scores is None:
        raise RuntimeError("prospect book is missing scores.csv; the ret60 report cannot be skipped")
    proxy_rate = float(XS_PROSPECT_VALUE_WEEKLY.proxy_leg_cost_rate or 0.0)
    if len(weights) == 0 or len(weekly) == 0:
        means = np.array([], dtype="float64")
    else:
        recomputed, _trades = apply_tk_schedule(weights, paths, proxy_rate=proxy_rate)
        if len(recomputed) != len(weekly) or not np.allclose(
            recomputed["net_spread"].to_numpy(dtype="float64"),
            weekly["net_spread"].to_numpy(dtype="float64"),
            rtol=0.0,
            atol=1e-12,
        ):
            raise RuntimeError("recomputed TK net spread does not match weekly_returns.csv")
        if not np.allclose(
            recomputed["net_spread_proxy"].to_numpy(dtype="float64"),
            weekly["net_spread_proxy"].to_numpy(dtype="float64"),
            rtol=0.0,
            atol=1e-12,
        ):
            raise RuntimeError("recomputed TK proxy net does not match weekly_returns.csv")
        gap_mismatch = "funding_gap_count" in weekly.columns and not np.array_equal(
            recomputed["funding_gap_count"].to_numpy(dtype="int64"),
            weekly["funding_gap_count"].to_numpy(dtype="int64"),
        )
        if gap_mismatch:
            raise RuntimeError("recomputed funding gap count does not match weekly_returns.csv")
        children = np.random.SeedSequence(seed).spawn(n_perm)
        means = np.empty(n_perm, dtype="float64")
        for i, child in enumerate(children):
            rng = np.random.default_rng(child)
            random_weights = turnover_matched_schedule(weights, paths, rng)
            random_weekly, _random_trades = apply_tk_schedule(
                random_weights, paths, proxy_rate=proxy_rate
            )
            means[i] = float(random_weekly["net_spread"].mean()) if len(random_weekly) else float("nan")
    if means.size == 0:
        metrics = score_weekly(weekly, window=window, random_means=np.array([0.0]), n_bootstrap=n_bootstrap)
        metrics["verdict"] = "FAIL" if window != "veto" else "REPORT_ONLY"
        metrics["passed"] = False
        metrics["beats_random_p"] = None
        metrics["empty_book"] = True
    else:
        metrics = score_weekly(weekly, window=window, random_means=means, n_bootstrap=n_bootstrap)
    metrics["cell"] = manifest.get("cell")
    if "funding_gap_count" in weekly.columns and len(weekly):
        metrics["funding_gap_count"] = int(weekly["funding_gap_count"].sum())
        metrics["long_funding_gap_count"] = int(weekly["long_funding_gap_count"].sum())
        metrics["short_funding_gap_count"] = int(weekly["short_funding_gap_count"].sum())
    else:
        metrics["funding_gap_count"] = 0
        metrics["long_funding_gap_count"] = 0
        metrics["short_funding_gap_count"] = 0
    metrics["n_permutations"] = int(means.size) if means.size else 0
    metrics["random_seed"] = seed
    metrics["score_profile"] = "prospect_value"
    metrics["mde"] = {
        "d": XS_PROSPECT_VALUE_WEEKLY.mde_d,
        "n_weeks": XS_PROSPECT_VALUE_WEEKLY.mde_weeks,
        "alpha": 0.05,
        "power": 0.80,
        "binds_gates": False,
    }
    official_mean = float(weekly["net_spread"].mean()) if len(weekly) else float("nan")
    proxy_mean = float(weekly["net_spread_proxy"].mean()) if len(weekly) and "net_spread_proxy" in weekly.columns else float("nan")
    sign_veto = bool(
        np.isfinite(official_mean) and np.isfinite(proxy_mean) and official_mean * proxy_mean < 0.0
    )
    metrics["measured_rt"] = {
        "rate_per_leg_trade": proxy_rate,
        "label": XS_PROSPECT_VALUE_WEEKLY.proxy_cost_label,
        "btc_sampler_rt": XS_PROSPECT_VALUE_WEEKLY.btc_sampler_rt,
        "sol_sampler_rt": XS_PROSPECT_VALUE_WEEKLY.sol_sampler_rt,
        "mean_net_spread": _json_float(proxy_mean),
        "binds_gates": False,
        "sign_veto": sign_veto,
        "rescues_fail": False,
    }
    report = partial_ret60_report(scores)
    partial_t = report["tk_partial_ret60"]["fama_macbeth_t"]
    if window == "main":
        per_year = _leg_trades_per_year(int(metrics["n_leg_trades"]), window)
        per_year_ok = per_year >= 100.0
        regime = _regime_gate(weekly)
        metrics["gates"]["leg_trades_per_year"] = {
            "threshold": 100.0,
            "value": per_year,
            "pass": per_year_ok,
        }
        metrics["gates"]["no_losing_regime"] = {
            "threshold": "regime with >= 5 weeks has mean net >= 0",
            "pass": bool(regime["pass"]),
            "regimes": regime["regimes"],
        }
        official_pass = bool(metrics["passed"]) and per_year_ok and bool(regime["pass"])
        verdict, passed = prospect_main_verdict(official_pass=official_pass, sign_veto=sign_veto)
        metrics["verdict"] = verdict
        metrics["passed"] = passed
        metrics["gates_applied"] = list(metrics["gates"])
    metrics["ret60_partial"] = report
    metrics["momentum_explained"] = momentum_explained_flag(
        passed=bool(metrics["passed"]) and window == "main",
        t_stat=partial_t if isinstance(partial_t, float) else None,
    )
    # The tag is not a gate. A pass stays a pass and a fail stays a fail.
    metrics["momentum_explained_binds_gates"] = False
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    random_payload = {
        "seed": seed,
        "n_permutations": int(means.size),
        "means": [float(v) for v in means],
        "note": (
            "Turnover-matched random rank-split. Same k per leg, equal-weight, "
            "dollar-neutral. The previous random book is carried and exactly the "
            "realized number of names on each leg is redrawn. Funding and the 12% "
            "stop follow each name's path. Cost is 0.31% of traded notional. "
            "The 0.158% proxy is not the null. 2,000 permutations, seed 20261016, "
            "when the caller does not override the count."
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
