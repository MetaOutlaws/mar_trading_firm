"""Dollar-neutral weekly book.

This is the engine half of the cell. It builds tercile weights, marks each
name from the next open to the next Monday open or to a stop, and charges
the flat per-leg cost. It does not compute a profit factor, a confidence
interval, or a random book. Those live in ``scorer``.

Accounting, per week, with signed weights that sum to zero and each side
grossing 1::

    gross = sum(weight * underlying_return)
    cost  = sum(|weight| * cost_rate)
    net   = gross - cost

``underlying_return`` is ``exit / entry_open - 1``. A short weight is
negative, so a rise in the shorted coin reduces the spread. Costs always
reduce the spread. The weekly net spread is the long-leg equal-weight
mean minus the short-leg equal-weight mean, minus both legs' costs.

A stop exits at the next open, not at the stop price and not at an
intrabar print. A gap that opens through the stop fills at that open.
A name that was stopped is flat for the rest of the week and is a new
entry if it is selected again next week.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.xs_spread.cells import CellConfig, WINDOWS
from research.xs_spread.costs import LEG_COST_RATE, charge_leg
from research.xs_spread.signals import bars_closed_by, get_signal


def as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def rebalance_times(window: str) -> list[pd.Timestamp]:
    """Monday 00:00 UTC dates inside the frozen window, inclusive."""
    try:
        start_s, end_s = WINDOWS[window]
    except KeyError as exc:
        raise KeyError(f"unknown window {window!r}") from exc
    start = as_utc(start_s)
    end = as_utc(end_s)
    day = start
    while day.weekday() != 0:
        day += pd.Timedelta(days=1)
    times: list[pd.Timestamp] = []
    while day <= end:
        times.append(day)
        day += pd.Timedelta(days=7)
    return times


def is_listed(row: pd.Series, t: pd.Timestamp) -> bool:
    """Listed at t when launch <= t and the delist, if any, is still ahead.

    A missing launch falls back to ``first_bar``. At the exact delist
    timestamp the name is already out.
    """
    launch = row["launch_time"] if pd.notna(row["launch_time"]) else row["first_bar"]
    if pd.isna(launch) or launch > t:
        return False
    delist = row["delist_time"]
    if pd.notna(delist) and t >= delist:
        return False
    return True


def has_history(row: pd.Series, t: pd.Timestamp, min_days: int) -> bool:
    """``first_bar`` is at least ``min_days`` before t. That is the price start."""
    first = row["first_bar"]
    if pd.isna(first):
        return False
    return bool(first <= t - pd.Timedelta(days=min_days))


def eligible_symbols(membership: pd.DataFrame, t: pd.Timestamp, min_days: int) -> list[str]:
    """Point-in-time names. Not in the membership table means not listed."""
    names: list[str] = []
    for symbol, row in membership.iterrows():
        if is_listed(row, t) and has_history(row, t, min_days):
            names.append(str(symbol))
    return names


def tercile_weights(scores: pd.Series, *, long_side: str) -> pd.Series:
    """Equal-weight long/short terciles. Weights sum to 0; each side sums to ±1.

    ``k = n // 3``. The remainder stays in the middle and is not traded, so
    the two legs have the same count. Ties break by symbol so a sort cannot
    move. Fewer than 3 finite scores produces an empty book.
    """
    if long_side not in ("bottom", "top"):
        raise ValueError(f"long_side must be bottom or top, got {long_side!r}")
    clean = scores.replace([np.inf, -np.inf], np.nan).dropna()
    frame = clean.rename("score").rename_axis("symbol").reset_index()
    frame["symbol"] = frame["symbol"].astype(str)
    frame = frame.sort_values(["score", "symbol"], kind="mergesort")
    n = len(frame)
    k = n // 3
    if k < 1:
        return pd.Series(dtype="float64", name="weight")
    low = frame.iloc[:k]
    high = frame.iloc[-k:]
    if long_side == "bottom":
        long_symbols = low["symbol"]
        short_symbols = high["symbol"]
    else:
        long_symbols = high["symbol"]
        short_symbols = low["symbol"]
    weight = pd.Series(0.0, index=frame["symbol"].tolist(), dtype="float64")
    weight.loc[list(long_symbols)] = 1.0 / k
    weight.loc[list(short_symbols)] = -1.0 / k
    weight = weight[weight != 0.0]
    weight.index.name = "symbol"
    weight.name = "weight"
    return weight


def _normalize_bars(bars: pd.DataFrame) -> pd.DataFrame:
    frame = bars.loc[:, ["open", "high", "low", "close"]].copy()
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError("bars index must be the bar open time")
    if frame.index.tz is None:
        frame.index = frame.index.tz_localize("UTC")
    else:
        frame.index = frame.index.tz_convert("UTC")
    frame = frame.sort_index()
    if frame.index.has_duplicates:
        raise ValueError("duplicate bar opens")
    for col in ("open", "high", "low", "close"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def normalize_panel(panel: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    return {str(symbol): _normalize_bars(bars) for symbol, bars in panel.items()}


@dataclass(frozen=True)
class SidePath:
    reason: str  # hold, stop, delist
    exit_time: pd.Timestamp
    exit_price: float
    underlying_return: float

    @property
    def stopped(self) -> bool:
        return self.reason == "stop"


@dataclass(frozen=True)
class NamePath:
    symbol: str
    entry_time: pd.Timestamp
    entry_open: float
    long: SidePath
    short: SidePath


def _side_path(
    bars: pd.DataFrame,
    entry_pos: int,
    end_pos: int,
    t_next: pd.Timestamp,
    entry_open: float,
    side: str,
    stop_pct: float,
) -> SidePath:
    """Stop fill is an open, never the stop price and never an intrabar print.

    An intrabar breach (the open is still on the safe side of the stop, the
    low or high is not) fills at the next bar's open. A bar that opens
    already through the stop fills at that open. If the tape ends on the
    trigger bar, the fill is that bar's close: the last price.
    """
    index = bars.index
    stop_level = entry_open * (1.0 - stop_pct) if side == "long" else entry_open * (1.0 + stop_pct)
    last_scan = min(end_pos, len(index))
    for i in range(entry_pos, last_scan):
        row = bars.iloc[i]
        open_ = float(row["open"])
        high = float(row["high"])
        low = float(row["low"])
        close = float(row["close"])
        if side == "long":
            breached = np.isfinite(low) and low <= stop_level
            gap = np.isfinite(open_) and open_ <= stop_level
        else:
            breached = np.isfinite(high) and high >= stop_level
            gap = np.isfinite(open_) and open_ >= stop_level
        if not breached:
            continue
        # The entry bar's open is the entry price, so it cannot gap through.
        if gap and i != entry_pos:
            return _done("stop", index[i], open_, entry_open)
        if i + 1 < len(index):
            nxt = float(bars.iloc[i + 1]["open"])
            return _done("stop", index[i + 1], nxt, entry_open)
        return _done("stop", index[i], close, entry_open)
    if end_pos < len(index) and index[end_pos] == t_next:
        return _done("hold", t_next, float(bars.iloc[end_pos]["open"]), entry_open)
    last_i = last_scan - 1
    return _done("delist", index[last_i], float(bars.iloc[last_i]["close"]), entry_open)


def _done(reason: str, exit_time: pd.Timestamp, exit_price: float, entry_open: float) -> SidePath:
    if not np.isfinite(exit_price) or exit_price <= 0 or entry_open <= 0:
        underlying = float("nan")
    else:
        underlying = exit_price / entry_open - 1.0
    return SidePath(reason=reason, exit_time=as_utc(exit_time), exit_price=float(exit_price), underlying_return=underlying)


def path_for_symbol(
    bars: pd.DataFrame,
    t: pd.Timestamp,
    t_next: pd.Timestamp,
    stop_pct: float,
) -> NamePath | None:
    """Entry is the first open at or after t and before the next rebalance.

    Missing that open means the name cannot be traded this week. The hold
    exit, when the series reaches it, is the open of the bar at ``t_next``.
    A series that ends earlier exits at its last close.
    """
    index = bars.index
    entry_pos = int(index.searchsorted(t, side="left"))
    if entry_pos >= len(index) or index[entry_pos] >= t_next:
        return None
    entry_open = float(bars.iloc[entry_pos]["open"])
    if not np.isfinite(entry_open) or entry_open <= 0:
        return None
    end_pos = int(index.searchsorted(t_next, side="left"))
    return NamePath(
        symbol="",
        entry_time=as_utc(index[entry_pos]),
        entry_open=entry_open,
        long=_side_path(bars, entry_pos, end_pos, t_next, entry_open, "long", stop_pct),
        short=_side_path(bars, entry_pos, end_pos, t_next, entry_open, "short", stop_pct),
    )


def _side_of(weight: float) -> str:
    if weight > 0:
        return "long"
    if weight < 0:
        return "short"
    raise ValueError("weight must be non-zero")


def renormalize(weights: pd.Series, tradable: set[str]) -> pd.Series:
    """Drop names with no fill and restore equal weight and dollar neutrality."""
    kept = weights[weights.index.isin(tradable)]
    long = kept[kept > 0]
    short = kept[kept < 0]
    if long.empty or short.empty:
        return pd.Series(dtype="float64", name="weight")
    out = pd.Series(0.0, index=list(long.index) + list(short.index), dtype="float64")
    out.loc[list(long.index)] = 1.0 / len(long)
    out.loc[list(short.index)] = -1.0 / len(short)
    out.index.name = "symbol"
    out.name = "weight"
    return out


def scores_at(
    panel: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
    t: pd.Timestamp,
    config: CellConfig,
) -> pd.Series:
    """Scores for names that are listed and have enough history.

    The signal only receives bars that have already closed. Names the
    signal cannot score come back as NaN and are dropped by the tercile.
    """
    names = eligible_symbols(membership, t, config.min_history_days)
    sliced = {
        symbol: bars_closed_by(panel[symbol], t)
        for symbol in names
        if symbol in panel
    }
    # Beta needs BTC's daily returns. BTC is not a ranked name, and it still
    # has to be visible to the signal when the membership row is present.
    if config.signal_name == "btc_beta" and "BTCUSDT" in panel and "BTCUSDT" not in sliced:
        sliced["BTCUSDT"] = bars_closed_by(panel["BTCUSDT"], t)
    signal = get_signal(config.signal_name)
    if not sliced:
        return pd.Series(dtype="float64", name="score")
    return signal(sliced, t, config)


def build_paths(
    panel: dict[str, pd.DataFrame],
    symbols: list[str],
    t: pd.Timestamp,
    t_next: pd.Timestamp,
    stop_pct: float,
) -> dict[str, NamePath]:
    paths: dict[str, NamePath] = {}
    for symbol in symbols:
        bars = panel.get(symbol)
        if bars is None:
            continue
        path = path_for_symbol(bars, t, t_next, stop_pct)
        if path is None or not np.isfinite(path.long.underlying_return):
            continue
        if not np.isfinite(path.short.underlying_return):
            continue
        paths[symbol] = NamePath(
            symbol=symbol,
            entry_time=path.entry_time,
            entry_open=path.entry_open,
            long=path.long,
            short=path.short,
        )
    return paths


def _charges(reason: str, *, is_new: bool, continues: bool, terminal: bool) -> list[str]:
    """Actions that pay the per-leg rate. A continuation of a live hold pays nothing.

    A stop or a delist is the exit. It is not also charged as a rebalance exit.
    The last week of the window liquidates every name still open.
    """
    actions: list[str] = []
    if is_new:
        actions.append("entry")
    if reason == "stop":
        actions.append("stop")
    elif reason == "delist":
        actions.append("delist")
    elif terminal or not continues:
        actions.append("exit")
    return actions


def apply_schedule(
    weights: pd.DataFrame,
    paths: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Turn a target book and precomputed paths into weekly nets and leg-trades.

    ``weights`` columns: rebalance_time, symbol, side, weight, score.
    ``paths`` columns: rebalance_time, symbol, entry_time, entry_open,
    long_reason, long_exit_time, long_exit_price, long_return,
    short_reason, short_exit_time, short_exit_price, short_return.

    Both frames are what the harness writes. The scorer calls this again
    with a random book's weights and the same paths, so the cost and the
    stop cannot drift between the two.
    """
    if weights.empty:
        return _empty_weekly(), _empty_trades()
    w = weights.copy()
    p = paths.copy()
    w["rebalance_time"] = pd.to_datetime(w["rebalance_time"], utc=True)
    p["rebalance_time"] = pd.to_datetime(p["rebalance_time"], utc=True)
    times = list(dict.fromkeys(w["rebalance_time"].tolist()))
    path_groups = {t: g.set_index("symbol") for t, g in p.groupby("rebalance_time", sort=False)}
    weight_groups = {t: g.set_index("symbol") for t, g in w.groupby("rebalance_time", sort=False)}

    # Positions still open after last week: symbol -> side. A stop or a
    # delist clears the name, so next week's selection is a new entry.
    still_open: dict[str, str] = {}
    weekly_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []

    for i, t in enumerate(times):
        group = weight_groups[t]
        path_group = path_groups.get(t, pd.DataFrame())
        terminal = i == len(times) - 1
        next_group = None if terminal else weight_groups[times[i + 1]]
        gross = 0.0
        cost = 0.0
        n_entries = n_exits = n_stops = n_delist = 0
        n_long = int((group["weight"] > 0).sum())
        n_short = int((group["weight"] < 0).sum())
        next_open: dict[str, str] = {}

        for symbol, row in group.iterrows():
            if symbol not in path_group.index:
                raise ValueError(f"{symbol} is in the book at {t} but has no path")
            side = str(row["side"])
            weight = float(row["weight"])
            path_row = path_group.loc[symbol]
            if isinstance(path_row, pd.DataFrame):
                path_row = path_row.iloc[0]
            reason = str(path_row[f"{side}_reason"])
            underlying = float(path_row[f"{side}_return"])
            exit_time = path_row[f"{side}_exit_time"]
            exit_price = float(path_row[f"{side}_exit_price"])
            entry_time = path_row["entry_time"]
            entry_open = float(path_row["entry_open"])
            is_new = still_open.get(str(symbol)) != side
            continues = False
            if next_group is not None and symbol in next_group.index:
                continues = str(next_group.loc[symbol, "side"]) == side
            actions = _charges(reason, is_new=is_new, continues=continues, terminal=terminal)
            cost_rate = 0.0
            for action in actions:
                # fee_for on a unit notional is the rate. The week's cost
                # scales it by |weight| below, so each coin pays 0.31% of
                # its own notional and the spread sees the weighted sum.
                rate = charge_leg(1.0)
                cost_rate += rate
                fill_time = entry_time if action == "entry" else exit_time
                fill_price = entry_open if action == "entry" else exit_price
                trade_rows.append(
                    {
                        "rebalance_time": t,
                        "symbol": symbol,
                        "side": side,
                        "action": action,
                        "fill_time": fill_time,
                        "fill_price": fill_price,
                        "weight": weight,
                        "cost_rate": rate,
                    }
                )
                if action == "entry":
                    n_entries += 1
                elif action == "stop":
                    n_stops += 1
                elif action == "delist":
                    n_delist += 1
                else:
                    n_exits += 1
            gross += weight * underlying
            cost += abs(weight) * cost_rate
            if reason == "hold" and not terminal:
                next_open[str(symbol)] = side

        n_leg_trades = n_entries + n_exits + n_stops + n_delist
        n_positions = n_long + n_short
        iso = pd.Timestamp(t).isocalendar()
        weekly_rows.append(
            {
                "rebalance_time": t,
                "iso_year": int(iso.year),
                "iso_week": int(iso.week),
                "n_long": n_long,
                "n_short": n_short,
                "gross_spread": gross,
                "cost": cost,
                "net_spread": gross - cost,
                "n_entries": n_entries,
                "n_exits": n_exits,
                "n_stops": n_stops,
                "n_delist": n_delist,
                "n_leg_trades": n_leg_trades,
                "turnover": (n_leg_trades / n_positions) if n_positions else 0.0,
            }
        )
        still_open = next_open

    weekly = pd.DataFrame(weekly_rows)
    trades = pd.DataFrame(trade_rows) if trade_rows else _empty_trades()
    return weekly, trades


def _empty_weekly() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "rebalance_time",
            "iso_year",
            "iso_week",
            "n_long",
            "n_short",
            "gross_spread",
            "cost",
            "net_spread",
            "n_entries",
            "n_exits",
            "n_stops",
            "n_delist",
            "n_leg_trades",
            "turnover",
        ]
    )


def _empty_trades() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "rebalance_time",
            "symbol",
            "side",
            "action",
            "fill_time",
            "fill_price",
            "weight",
            "cost_rate",
        ]
    )


def ensure_membership(membership: pd.DataFrame) -> pd.DataFrame:
    """Accept the canonical frame or the raw membership_pit columns."""
    needed = {"launch_time", "delist_time", "first_bar", "last_bar"}
    if needed.issubset(membership.columns) and (
        membership.index.name == "symbol" or "symbol" not in membership.columns
    ):
        frame = membership.copy()
    else:
        from research.xs_spread.tape import normalize_membership

        frame = normalize_membership(membership)
    for column in ("launch_time", "delist_time", "first_bar", "last_bar"):
        frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame


def _path_row(t: pd.Timestamp, symbol: str, path: NamePath) -> dict[str, object]:
    return {
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


def run_book(
    panel: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
    config: CellConfig,
    window: str,
    funding: dict[str, pd.Series] | None = None,
) -> dict[str, pd.DataFrame]:
    """Full engine pass for one window. No profit factor and no random book.

    ``funding`` is required when the cell includes funding. A missing print
    drops that name for the week. It is not replaced with zero.
    """
    if not config.runnable:
        raise NotImplementedError(config.note)
    if abs(config.leg_cost_rate - LEG_COST_RATE) > 1e-15:
        raise ValueError(
            f"{config.name} leg cost {config.leg_cost_rate} != pinned rate {LEG_COST_RATE}"
        )
    if config.funding_included and funding is None:
        raise RuntimeError(
            f"{config.name} includes funding on both legs and will not zero-fill a missing tape"
        )
    beta_book = config.weighting == "beta_neutral"
    if beta_book and config.proxy_leg_cost_rate is None:
        raise ValueError(f"{config.name} is missing the report-only cost level")
    panel = normalize_panel(panel)
    membership = ensure_membership(membership)
    if beta_book and "BTCUSDT" not in panel:
        raise RuntimeError("BTCUSDT bars are required to estimate beta and are not a traded leg")
    times = rebalance_times(window)
    weight_rows: list[dict[str, object]] = []
    path_rows: list[dict[str, object]] = []
    score_rows: list[dict[str, object]] = []
    if beta_book:
        from research.xs_spread.bab import (
            apply_beta_schedule,
            beta_neutral_weights,
            funding_rate_sum,
            leg_sets_from_scores,
            regime_at,
        )
    for t in times:
        t_next = t + pd.Timedelta(days=config.hold_days)
        scores = scores_at(panel, membership, t, config)
        scores.index = scores.index.map(str)
        finite = scores.replace([np.inf, -np.inf], np.nan).dropna()
        if not beta_book:
            # Skew path. Same terciles, same paths, same equal-weight renormalize.
            raw = tercile_weights(finite, long_side=config.long_side)
            paths = build_paths(panel, list(finite.index.astype(str)), t, t_next, config.stop_pct)
            weights = renormalize(raw, set(paths))
            for symbol, path in paths.items():
                path_rows.append(_path_row(t, symbol, path))
            for symbol, weight in weights.items():
                weight_rows.append(
                    {
                        "rebalance_time": t,
                        "symbol": symbol,
                        "side": _side_of(float(weight)),
                        "weight": float(weight),
                        "score": float(finite.loc[symbol]),
                    }
                )
            continue
        paths = build_paths(panel, list(finite.index.astype(str)), t, t_next, config.stop_pct)
        funded: dict[str, tuple[NamePath, float, float]] = {}
        series = funding or {}
        for symbol, path in paths.items():
            rates = series.get(symbol)
            long_sum = funding_rate_sum(rates, path.entry_time, path.long.exit_time)
            short_sum = funding_rate_sum(rates, path.entry_time, path.short.exit_time)
            if not np.isfinite(long_sum) or not np.isfinite(short_sum):
                continue
            funded[symbol] = (path, long_sum, short_sum)
        scored = finite[finite.index.isin(funded)]
        long_symbols, short_symbols = leg_sets_from_scores(scored, long_side=config.long_side)
        weights = beta_neutral_weights(
            scored,
            long_symbols,
            short_symbols,
            leverage_cap=config.leverage_cap,
        )
        regime = regime_at(panel["BTCUSDT"], t)
        for symbol, (path, long_sum, short_sum) in funded.items():
            row = _path_row(t, symbol, path)
            row["long_funding_sum"] = long_sum
            row["short_funding_sum"] = short_sum
            path_rows.append(row)
            score_rows.append(
                {"rebalance_time": t, "symbol": symbol, "score": float(scored.loc[symbol])}
            )
        for symbol, weight in weights.items():
            weight_rows.append(
                {
                    "rebalance_time": t,
                    "symbol": symbol,
                    "side": _side_of(float(weight)),
                    "weight": float(weight),
                    "score": float(scored.loc[symbol]),
                    "regime": regime if regime is not None else "",
                }
            )
    weight_cols = ["rebalance_time", "symbol", "side", "weight", "score"]
    path_cols = [
        "rebalance_time",
        "symbol",
        "entry_time",
        "entry_open",
        "long_reason",
        "long_exit_time",
        "long_exit_price",
        "long_return",
        "short_reason",
        "short_exit_time",
        "short_exit_price",
        "short_return",
    ]
    if beta_book:
        weight_cols = [*weight_cols, "regime"]
        path_cols = [*path_cols, "long_funding_sum", "short_funding_sum"]
    weights_frame = pd.DataFrame(weight_rows, columns=weight_cols)
    paths_frame = pd.DataFrame(path_rows, columns=path_cols)
    if beta_book:
        weekly, trades = apply_beta_schedule(
            weights_frame,
            paths_frame,
            proxy_rate=float(config.proxy_leg_cost_rate),
        )
        tables = {
            "weights": weights_frame,
            "name_paths": paths_frame,
            "weekly_returns": weekly,
            "leg_trades": trades,
            "scores": pd.DataFrame(score_rows, columns=["rebalance_time", "symbol", "score"]),
        }
        return tables
    weekly, trades = apply_schedule(weights_frame, paths_frame)
    return {
        "weights": weights_frame,
        "name_paths": paths_frame,
        "weekly_returns": weekly,
        "leg_trades": trades,
    }
