"""Turn one simulator result into the report rows and the frozen gates."""
from __future__ import annotations

import numpy as np

from protocol_constants import (
    BOOTSTRAP_DRAWS,
    BOOTSTRAP_SEED,
    CONCENTRATION_TOKEN,
    CONCENTRATION_YEAR,
    MAX_DRAWDOWN,
    MIN_CLOSED_TRADES,
    MIN_EXPECTANCY,
    MIN_PROFIT_FACTOR,
    MIN_PROFITABLE_YEAR_RATIO,
    NULL_SHIFT_MAX_DAYS,
    NULL_SHIFT_MIN_DAYS,
    NULL_SHIFTS,
    RISK_CEILING,
    STARTING_EQUITY_USDT,
)


def _pf(pnls: np.ndarray) -> float | None:
    wins = pnls[pnls > 0].sum()
    losses = -pnls[pnls < 0].sum()
    if losses == 0:
        return None if wins == 0 else float("inf")
    return float(wins / losses)


def summarise(result: dict, timestamps: np.ndarray, label: str) -> dict:
    trades = result["trades"]
    pnls = np.array([t["pnl"] for t in trades], dtype=float)
    wins = pnls[pnls > 0] if len(pnls) else pnls
    losses = pnls[pnls < 0] if len(pnls) else pnls
    rs = []
    for trade in trades:
        denom = RISK_CEILING * trade["equity_at_entry"]
        rs.append(trade["pnl"] / denom if denom else float("nan"))
    r_arr = np.array(rs, dtype=float)
    start = STARTING_EQUITY_USDT
    ending = float(result["ending_equity"])
    reasons = {}
    for trade in trades:
        reasons[trade["reason"]] = reasons.get(trade["reason"], 0) + 1
    by_token = {}
    for trade in trades:
        by_token[trade["symbol"]] = by_token.get(trade["symbol"], 0.0) + trade["pnl"]
    years = {}
    previous = start
    for year in (2022, 2023, 2024, 2025):
        end_equity = float(result["equity_at_year_end"].get(year, previous))
        closed = [
            t
            for t in trades
            if int(timestamps[t["exit_i"]] // 1000) >= _year_start(year)
            and int(timestamps[t["exit_i"]] // 1000) < _year_start(year + 1)
        ]
        cp = np.array([t["pnl"] for t in closed], dtype=float)
        years[str(year)] = {
            "start_equity": previous,
            "end_equity": end_equity,
            "net_return": end_equity / previous - 1.0 if previous else None,
            "max_drawdown": result["year_max_drawdown"].get(year, 0.0),
            "trades": int(len(closed)),
            "win_rate": float((cp > 0).mean()) if len(cp) else None,
            "profit_factor": _pf(cp) if len(cp) else None,
            "expectancy": float(cp.mean()) if len(cp) else None,
            "pnl": float(cp.sum()) if len(cp) else 0.0,
        }
        previous = end_equity
    components = {
        "spot_price": sum(t["spot_price"] for t in trades),
        "perp_price": sum(t["perp_price"] for t in trades),
        "funding": sum(t["funding"] for t in trades),
        "fees": sum(t["fees"] for t in trades),
        "slippage": sum(t["slippage"] for t in trades),
        "penalty": sum(t["penalty"] for t in trades),
    }
    return {
        "label": label,
        "ending_equity": ending,
        "net_return": ending / start - 1.0,
        "max_drawdown": result["max_drawdown"],
        "trades": len(trades),
        "win_rate": float((pnls > 0).mean()) if len(pnls) else None,
        "profit_factor": _pf(pnls) if len(pnls) else None,
        "expectancy": float(pnls.mean()) if len(pnls) else None,
        "average_win": float(wins.mean()) if len(wins) else None,
        "average_loss": float(losses.mean()) if len(losses) else None,
        "mean_R": float(np.nanmean(r_arr)) if len(r_arr) else None,
        "sum_R": float(np.nansum(r_arr)) if len(r_arr) else None,
        "utilisation_minutes": result["minutes_in_market"] / result["minutes"] if result["minutes"] else 0.0,
        "mean_gross_exposure": result["mean_gross_exposure"],
        "blocked": result["blocked"],
        "exit_reasons": reasons,
        "by_token_pnl": by_token,
        "years": years,
        "components": components,
        "open_positions": result["open_positions"],
    }


def _year_start(year: int) -> int:
    from datetime import datetime, timezone

    return int(datetime(year, 1, 1, tzinfo=timezone.utc).timestamp())


def gates(summary: dict, null_pnls: list[float] | None) -> dict:
    """Combined-account pass checks. A missing null distribution fails closed."""
    trades = summary["trades"]
    pf = summary["profit_factor"]
    expectancy = summary["expectancy"]
    dd = summary["max_drawdown"]
    year_changes = []
    previous = STARTING_EQUITY_USDT
    for year in ("2022", "2023", "2024", "2025"):
        end_equity = summary["years"][year]["end_equity"]
        year_changes.append(end_equity - previous)
        previous = end_equity
    profitable_years = sum(1 for change in year_changes if change > 0)
    year_ratio = profitable_years / 4.0
    pnls = None
    # Bootstrap is recomputed by the caller and passed in via summary if present.
    ci_low = summary.get("bootstrap_low")
    ci_high = summary.get("bootstrap_high")
    ci_ok = ci_low is not None and ci_low > 0
    if null_pnls is None:
        beats = False
        beats_count = None
    else:
        study = summary["ending_equity"] - STARTING_EQUITY_USDT
        beats_count = sum(1 for value in null_pnls if study > value)
        beats = beats_count >= 190
    total = summary["ending_equity"] - STARTING_EQUITY_USDT
    token_ok = True
    year_ok = True
    if total > 0:
        for value in summary["by_token_pnl"].values():
            if value / total > CONCENTRATION_TOKEN:
                token_ok = False
        for change in year_changes:
            if change / total > CONCENTRATION_YEAR:
                year_ok = False
    checks = {
        "min_trades": trades >= MIN_CLOSED_TRADES,
        "profit_factor": pf is not None and pf >= MIN_PROFIT_FACTOR,
        "expectancy": expectancy is not None and expectancy > MIN_EXPECTANCY,
        "drawdown": dd <= MAX_DRAWDOWN,
        "profitable_years": year_ratio >= MIN_PROFITABLE_YEAR_RATIO,
        "bootstrap_ci": ci_ok,
        "beats_shifted_funding": beats,
        "token_concentration": token_ok,
        "year_concentration": year_ok,
        "flat_at_end": summary["open_positions"] == [],
    }
    return {
        "checks": checks,
        "pass": all(checks.values()),
        "profitable_year_ratio": year_ratio,
        "beats_null_count": beats_count,
        "null_shifts": NULL_SHIFTS if null_pnls is not None else 0,
        "null_shift_days": [NULL_SHIFT_MIN_DAYS, NULL_SHIFT_MAX_DAYS],
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "bootstrap_seed": BOOTSTRAP_SEED,
    }


def bootstrap_interval(pnls: list[float]) -> tuple[float | None, float | None]:
    if len(pnls) < 2:
        return None, None
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sample = np.asarray(pnls, dtype=float)
    draws = rng.integers(0, len(sample), size=(BOOTSTRAP_DRAWS, len(sample)))
    means = sample[draws].mean(axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)
