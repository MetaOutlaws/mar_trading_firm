"""Gates for a sealed book. The blind run does not import this module.

Desk gates are read from ``research.validate.DEFAULT_CRITERIA`` and checked
against the prereg's numbers before a score is written. A house edit that
moves PF, the 30-count, the 25% drawdown, or the 50% fold ratio refuses
the score instead of loosening this cell.

Drawdown is strict: MDD < 25%. A drawdown of exactly 25% fails.

The week-cluster interval resamples kept weeks. One row is one ISO week.
The bootstrap seed is 20261016, the seed this prereg names.

The 100 leg-trades/yr floor uses realized entry count, including a
re-entry after a stop, divided by the calendar span of the window. The
five dropped Mondays stay in that span. One-way actions (entries, exits,
stops, delists, resizes) are the desk's >= 30 OOS leg-trades count.

A2 re-tests both floors on the realized book. Thin skips are not weeks.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.significance import bootstrap_expectancy
from research.validate import DEFAULT_CRITERIA
from research.xs_crowd_lsr_contrarian.calendar import (
    as_utc,
    calendar_years,
    rebalance_mondays,
    veto_only_mondays,
)
from research.xs_crowd_lsr_contrarian.hashing import sha256_file
from research.xs_crowd_lsr_contrarian.pins import (
    BEATS_RANDOM_ALPHA,
    BOOTSTRAP_SEED,
    CELL,
    MAX_DRAWDOWN,
    MIN_LEG_TRADES,
    MIN_LEG_TRADES_PER_YEAR,
    MIN_PROFITABLE_FOLDS,
    MIN_WEEK_CLUSTERS,
    N_BOOTSTRAP,
    N_FOLDS,
    N_RANDOM_DRAWS,
    PF_MIN,
    RANDOM_SEED,
)
from research.xs_crowd_lsr_contrarian.regime import regime_gate

MAIN_FOLDS = (
    "2023Q4",
    "2024Q1",
    "2024Q2",
    "2024Q3",
    "2024Q4",
    "2025Q1",
    "2025Q2",
)


class ScoreError(RuntimeError):
    """The sealed book cannot be scored as this cell."""


def assert_house_gates() -> None:
    """Refuse if the desk criteria are not the gates this prereg froze."""
    criteria = DEFAULT_CRITERIA
    checks = (
        (criteria.min_profit_factor, PF_MIN, "min_profit_factor"),
        (criteria.min_oos_trades, MIN_LEG_TRADES, "min_oos_trades"),
        (criteria.max_drawdown_pct, MAX_DRAWDOWN * 100.0, "max_drawdown_pct"),
        (criteria.min_profitable_fold_ratio, 50.0, "min_profitable_fold_ratio"),
    )
    for got, expected, name in checks:
        if float(got) != float(expected):
            raise ScoreError(
                f"house gate {name} is {got}, prereg requires {expected}. "
                "This cell does not follow a loosened gate."
            )
    if len(MAIN_FOLDS) != N_FOLDS or MIN_PROFITABLE_FOLDS != 4:
        raise ScoreError("fold grid is not the prereg's 7 quarters / 4 profitable")


def permutation_p_value(observed: float, random_means: np.ndarray) -> float:
    """(1 + #{mean >= observed}) / (n + 1). One-sided. Passes when p < 0.05."""
    means = np.asarray(random_means, dtype="float64")
    if means.size == 0 or not np.isfinite(means).all():
        raise ScoreError("random book has no finite means")
    count = int(np.sum(means >= observed))
    return (1.0 + count) / (float(means.size) + 1.0)


def profit_factor(net: np.ndarray) -> float:
    """Sum of positive weekly nets over the absolute sum of negative ones."""
    values = np.asarray(net, dtype="float64")
    won = float(values[values > 0.0].sum()) if np.any(values > 0.0) else 0.0
    lost = float(-values[values < 0.0].sum()) if np.any(values < 0.0) else 0.0
    if lost == 0.0:
        return float("inf") if won > 0.0 else 0.0
    return won / lost


def max_drawdown(net: np.ndarray) -> float:
    """Max drawdown of equity compounded from the weekly net return."""
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in np.asarray(net, dtype="float64"):
        equity *= 1.0 + float(value)
        if equity <= 0.0:
            return 1.0
        peak = max(peak, equity)
        worst = max(worst, (peak - equity) / peak)
    return float(worst)


def quarter_label(stamp: object) -> str:
    ts = as_utc(stamp)
    quarter = (int(ts.month) - 1) // 3 + 1
    return f"{int(ts.year)}Q{quarter}"


def fold_report(weekly: pd.DataFrame) -> dict[str, object]:
    """Seven named quarters. An empty quarter is not profitable."""
    labels = weekly["rebalance_time"].map(quarter_label) if len(weekly) else []
    detail: dict[str, dict[str, object]] = {}
    profitable = 0
    for fold in MAIN_FOLDS:
        if len(weekly):
            part = weekly.loc[np.asarray(labels) == fold, "net_return"]
            total = float(part.sum()) if len(part) else 0.0
            n = int(len(part))
        else:
            total = 0.0
            n = 0
        ok = bool(total > 0.0)
        if ok:
            profitable += 1
        detail[fold] = {"n_weeks": n, "sum_net_return": total, "profitable": ok}
    return {
        "n_folds": N_FOLDS,
        "n_profitable": profitable,
        "pass": profitable >= MIN_PROFITABLE_FOLDS,
        "folds": detail,
    }


def _json_float(value: float) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def evaluate(
    weekly: pd.DataFrame,
    *,
    window: str,
    random_means: np.ndarray | None,
    funding_coverage: dict[str, object],
) -> dict[str, object]:
    """Apply the frozen gates. Does not read a tape and does not print."""
    assert_house_gates()
    if window == "holdout":
        _refuse_veto_only_evidence(weekly)
    if funding_coverage.get("leg_mean_fill") is not False:
        raise ScoreError("funding coverage does not record leg_mean_fill = false")
    if funding_coverage.get("missing_books_zero") is not True:
        raise ScoreError("funding coverage does not record missing names booking 0")
    net = weekly["net_return"].to_numpy(dtype="float64") if len(weekly) else np.empty(0)
    n_weeks = int(net.size)
    n_leg_trades = int(weekly["n_leg_trades"].sum()) if n_weeks else 0
    n_entries = int(weekly["n_entries"].sum()) if n_weeks else 0
    mean = float(net.mean()) if n_weeks else float("nan")
    pf = profit_factor(net) if n_weeks else 0.0
    drawdown = max_drawdown(net) if n_weeks else 0.0
    folds = fold_report(weekly)
    years = calendar_years(window)
    entries_per_year = float(n_entries) / years if years > 0 else 0.0
    one_way_per_year = float(n_leg_trades) / years if years > 0 else 0.0
    pf_ok = bool((np.isfinite(pf) and pf >= PF_MIN) or (np.isinf(pf) and pf > 0.0))
    # Strict. Exactly 25% fails.
    dd_ok = bool(drawdown < MAX_DRAWDOWN)
    trades_ok = n_leg_trades >= MIN_LEG_TRADES
    weeks_ok = n_weeks >= MIN_WEEK_CLUSTERS
    per_year_ok = entries_per_year >= MIN_LEG_TRADES_PER_YEAR
    proxy = (
        weekly["net_return_proxy"].to_numpy(dtype="float64")
        if n_weeks and "net_return_proxy" in weekly.columns
        else np.empty(0)
    )
    proxy_mean = float(proxy.mean()) if proxy.size else float("nan")
    sign_veto = bool(
        np.isfinite(mean) and np.isfinite(proxy_mean) and mean * proxy_mean < 0.0
    )
    regime = regime_gate(weekly)

    if window == "main":
        if random_means is None:
            raise ScoreError("main score requires the sealed random-book means")
        p_value = permutation_p_value(mean, random_means) if n_weeks else 1.0
        bootstrap = bootstrap_expectancy(
            net,
            iterations=N_BOOTSTRAP,
            confidence=0.95,
            seed=BOOTSTRAP_SEED,
        )
        ci_ok = bool(n_weeks > 0 and bootstrap.is_significant)
        beats = bool(p_value < BEATS_RANDOM_ALPHA)
        gates = {
            "profit_factor": {"threshold": PF_MIN, "value": _json_float(pf), "pass": pf_ok},
            "week_cluster_ci": {
                "threshold": "95% CI of the mean excludes zero on the positive side",
                "ci95_low": float(bootstrap.ci_low) if n_weeks else None,
                "ci95_high": float(bootstrap.ci_high) if n_weeks else None,
                "pass": ci_ok,
                "iterations": N_BOOTSTRAP,
                "seed": BOOTSTRAP_SEED,
            },
            "beats_random": {
                "threshold": BEATS_RANDOM_ALPHA,
                "p_value": p_value,
                "pass": beats,
                "draws": int(np.asarray(random_means).size),
                "seed": RANDOM_SEED,
            },
            "leg_trades": {"threshold": MIN_LEG_TRADES, "value": n_leg_trades, "pass": trades_ok},
            "week_clusters": {"threshold": MIN_WEEK_CLUSTERS, "value": n_weeks, "pass": weeks_ok},
            "leg_trades_per_year": {
                "threshold": MIN_LEG_TRADES_PER_YEAR,
                "value": entries_per_year,
                "numerator": "realized entries, including stop re-entries",
                "calendar_years": years,
                "pass": per_year_ok,
                "one_way_per_year_report_only": one_way_per_year,
            },
            "profitable_folds": {
                "threshold": MIN_PROFITABLE_FOLDS,
                "n_folds": N_FOLDS,
                "n_profitable": folds["n_profitable"],
                "pass": bool(folds["pass"]),
                "folds": folds["folds"],
            },
            "max_drawdown": {
                "threshold": MAX_DRAWDOWN,
                "comparison": "<",
                "value": drawdown,
                "pass": dd_ok,
                "gross": 1.18,
                "leg": 0.59,
                "sizing_knob": False,
            },
            "no_losing_regime": {
                "threshold": "regime with >= 5 weeks has mean net >= 0",
                "pass": bool(regime["pass"]),
                "regimes": regime["regimes"],
                "failing": regime["failing"],
            },
            "sign_flip_veto": {
                "pass": not sign_veto,
                "veto": sign_veto,
                "official_mean": _json_float(mean),
                "proxy_mean": _json_float(proxy_mean),
                "proxy_binds_gates": False,
                "proxy_can_rescue_a_fail": False,
            },
        }
        official_pass = bool(
            n_weeks > 0
            and pf_ok
            and ci_ok
            and beats
            and trades_ok
            and weeks_ok
            and per_year_ok
            and folds["pass"]
            and dd_ok
            and regime["pass"]
        )
        if official_pass and sign_veto:
            verdict, passed = "VETO", False
        elif official_pass:
            verdict, passed = "PASS", True
        else:
            verdict, passed = "FAIL", False
        applied = list(gates)
    elif window == "holdout":
        # Binding holdout rule: week-mean > 0 and PF >= 1.15. No 30-week floor.
        # 2025-12-29 was refused above, before this mean was computed.
        passed = bool(n_weeks > 0 and mean > 0.0 and pf_ok)
        verdict = "PASS" if passed else "FAIL"
        p_value = None
        gates = {
            "positive_mean": {"threshold": "> 0", "value": _json_float(mean), "pass": bool(mean > 0.0)},
            "profit_factor": {"threshold": PF_MIN, "value": _json_float(pf), "pass": pf_ok},
        }
        applied = list(gates)
    else:
        raise ScoreError(f"refusing to score window {window!r}")

    return {
        "cell": CELL,
        "window": window,
        "live": "off",
        "paper_only": True,
        "verdict": verdict,
        "passed": passed,
        "can_rescue_a_fail": False,
        "unit": "weekly net return on equity at 0.31% per one-way leg-trade, funding included",
        "n_weeks": n_weeks,
        "n_leg_trades": n_leg_trades,
        "n_entries": n_entries,
        "mean_net_return": _json_float(mean),
        "profit_factor": _json_float(pf),
        "profit_factor_infinite": bool(np.isinf(pf)),
        "max_drawdown": drawdown,
        "entries_per_year": entries_per_year,
        "gates": gates,
        "gates_applied": applied,
        "beats_random_p": p_value if window == "main" else None,
        "funding_coverage": {
            "n_names_with_no_funding_data": funding_coverage.get("n_names_with_no_funding_data"),
            "names_with_no_funding_data": funding_coverage.get("names_with_no_funding_data"),
            "leg_mean_fill": False,
        },
        "measured_cost": {
            "rate_per_leg_trade": 0.00158,
            "label": "proxy, likely optimistic for alts",
            "mean_net_return": _json_float(proxy_mean),
            "binds_gates": False,
            "sign_veto": sign_veto if window == "main" else False,
        },
    }


def _refuse_veto_only_evidence(weekly: pd.DataFrame) -> None:
    """A veto-only rebalance cannot enter the holdout mean or the verdict."""
    if weekly.empty or "rebalance_time" not in weekly.columns:
        return
    last = rebalance_mondays("holdout")[-1]
    banned = {as_utc(stamp) for stamp in veto_only_mondays("holdout")}
    times = pd.to_datetime(weekly["rebalance_time"], utc=True)
    for stamp in times:
        as_of = as_utc(stamp)
        if as_of in banned or as_of > last:
            raise ScoreError(
                f"{as_of.strftime('%Y-%m-%d')} is not holdout evidence. "
                "The veto-only line cannot enter metrics or turn a FAIL into a PASS."
            )


def assert_random_book(payload: dict[str, object]) -> np.ndarray:
    """The sealed null is 1,000 draws at seed 20261016. Anything else refuses."""
    if int(payload.get("n_draws", -1)) != N_RANDOM_DRAWS:
        raise ScoreError(f"random book n_draws is not {N_RANDOM_DRAWS}")
    if int(payload.get("seed", -1)) != RANDOM_SEED:
        raise ScoreError(f"random book seed is not {RANDOM_SEED}")
    means = np.asarray(payload.get("means", []), dtype="float64")
    if means.size != N_RANDOM_DRAWS:
        raise ScoreError("random book mean count does not match n_draws")
    return means


def score_directory(output_dir: Path) -> dict[str, object]:
    """Write metrics.json beside a sealed book. Does not rewrite SHA256SUMS."""
    output_dir = Path(output_dir)
    sums = output_dir / "SHA256SUMS"
    if not sums.is_file():
        raise ScoreError("refusing to score a directory that has no SHA256SUMS seal")
    seal = sha256_file(sums)
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("cell") != CELL:
        raise ScoreError("manifest cell is not xs_crowd_lsr_contrarian")
    if manifest.get("metrics_computed") is not False:
        raise ScoreError("blind manifest must record metrics_computed false")
    window = str(manifest.get("window"))
    weekly = pd.read_csv(output_dir / "weekly_returns.csv")
    if len(weekly):
        weekly["rebalance_time"] = pd.to_datetime(weekly["rebalance_time"], utc=True)
    coverage = json.loads((output_dir / "funding_coverage.json").read_text(encoding="utf-8"))
    means = None
    if window == "main":
        payload = json.loads((output_dir / "random_book.json").read_text(encoding="utf-8"))
        means = assert_random_book(payload)
    metrics = evaluate(weekly, window=window, random_means=means, funding_coverage=coverage)
    metrics["seal_sha256"] = seal
    text = json.dumps(metrics, indent=2, sort_keys=True) + "\n"
    target = output_dir / "metrics.json"
    target.write_text(text, encoding="utf-8")
    metrics["metrics_sha256"] = sha256_file(target)
    # The seal file is unchanged. metrics.json is not part of it.
    if sha256_file(sums) != seal:
        raise ScoreError("scoring rewrote SHA256SUMS; the seal must stay put")
    return metrics
