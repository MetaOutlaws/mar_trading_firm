"""Weekly book for xs_crowd_lsr_contrarian v2.

Accounting, on equity, at each kept rebalance. G = 1.18 and 0.59 per leg
are constants. There is no sizing argument.

    price    = sum(weight * underlying return over the path actually held)
    funding  = sum(-weight * realized funding over that same path)
    cost     = 0.31% * traded notional
    net      = price + funding - cost
    equity   = equity * (1 + net)

``weight`` is the fraction of equity at the rebalance the position was
sized on. A stopped or delisted name contributes only up to its exit, and
its end-of-week exposure is zero. The other names keep the weights they
were given. Nothing is redistributed.

Traded notional at the Monday open is sum(|target - drifted|). Drifted is
the marked exposure carried from the previous kept week, expressed as a
fraction of this week's starting equity. After a dropped Monday, a thin
skip, or the first week, drifted is zero and the entry is fresh.

A stop or a delist trades the entry weight |w| back to cash inside the
week. A week whose next kept rebalance is not exactly seven days later
flattens at the 7-day exit: each name still open trades its marked
exposure |w * exit/entry| to cash, and the next kept Monday pays a full
entry. The last week of the window flattens the same way.

The 0.158% column uses the same notionals. It does not enter ``net``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from research.xs_crowd_lsr_contrarian.calendar import (
    as_utc,
    assert_dropped_monday_list,
    continuous,
    is_dropped_monday,
    rebalance_mondays,
)
from research.xs_crowd_lsr_contrarian.costs import charge_leg
from research.xs_crowd_lsr_contrarian.paths import BlockedRun, SidePath, require_paths
from research.xs_crowd_lsr_contrarian.pins import (
    GROSS,
    LEG,
    LISTING_CUTOFF,
    MIN_HISTORY_DAYS,
    MIN_NAMES_PER_LEG,
    OFFICIAL_LEG_COST,
    PROXY_LEG_COST,
)
from research.xs_crowd_lsr_contrarian.regime import regimes_for
from research.xs_crowd_lsr_contrarian.signal import assign_terciles, leg_weights, mean_buy_ratio

_CUTOFF = pd.Timestamp(LISTING_CUTOFF)


@dataclass
class RatioStore:
    """Daily buyRatio indexed by symbol. The values are not rescaled."""

    stamps: dict[str, np.ndarray]
    values: dict[str, np.ndarray]

    @classmethod
    def from_frame(cls, frame: pd.DataFrame | None) -> RatioStore:
        stamps: dict[str, np.ndarray] = {}
        values: dict[str, np.ndarray] = {}
        if frame is None or frame.empty:
            return cls(stamps, values)
        required = {"symbol", "ts", "buy_ratio"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"ratio frame is missing {sorted(missing)}")
        for symbol, part in frame.groupby("symbol", sort=False):
            # Integer nanoseconds, UTC. searchsorted then does not care
            # whether a caller still holds a timezone-aware Timestamp.
            ts = pd.to_datetime(part["ts"], utc=True)
            ns = ts.to_numpy(dtype="datetime64[ns]").astype("int64")
            order = np.argsort(ns, kind="mergesort")
            ordered = ns[order]
            if ordered.size > 1 and np.any(ordered[1:] == ordered[:-1]):
                raise ValueError(f"{symbol} has duplicate buyRatio timestamps")
            vals = pd.to_numeric(part["buy_ratio"], errors="coerce").to_numpy(dtype="float64")[order]
            stamps[str(symbol)] = ordered
            values[str(symbol)] = vals
        return cls(stamps, values)

    def level(self, symbol: str, t: pd.Timestamp) -> float | None:
        stamps = self.stamps.get(symbol)
        if stamps is None:
            return None
        start, end = (
            as_utc(t) - pd.Timedelta(days=7),
            as_utc(t) - pd.Timedelta(days=1),
        )
        left = int(np.searchsorted(stamps, int(start.value), side="left"))
        right = int(np.searchsorted(stamps, int(end.value), side="right"))
        if right <= left:
            return None
        rows = [
            (pd.Timestamp(int(stamps[i]), unit="ns", tz="UTC"), float(self.values[symbol][i]))
            for i in range(left, right)
        ]
        return mean_buy_ratio(rows, t)


def listing_status(symbol: str, metas: dict[str, str], row: pd.Series) -> str:
    """LSR meta status, else the prereg's last-bar fallback.

    ``last_bar`` strictly before 2026-10-16 10:00 UTC is Closed. A later
    last bar is Trading. Held names are on the LSR tape and have meta; the
    fallback is for a symbol the meta files do not name.
    """
    status = metas.get(symbol)
    if status in {"Trading", "Closed"}:
        return status
    last = row["last_bar"] if "last_bar" in row.index else pd.NaT
    if pd.isna(last) or as_utc(last) < _CUTOFF:
        return "Closed"
    return "Trading"


def _eligible_row(row: pd.Series, t: pd.Timestamp) -> bool:
    """Listed at t, with at least 31 days of history, and a bar at or after t."""
    launch = row["launch_time"] if pd.notna(row["launch_time"]) else row["first_bar"]
    if pd.isna(launch) or as_utc(launch) > t:
        return False
    delist = row["delist_time"]
    if pd.notna(delist) and t >= as_utc(delist):
        return False
    first = row["first_bar"]
    if pd.isna(first) or as_utc(first) > t - pd.Timedelta(days=MIN_HISTORY_DAYS):
        return False
    last = row["last_bar"]
    if pd.isna(last) or as_utc(last) < t:
        return False
    return True


def eligible_symbols(membership: pd.DataFrame, t: pd.Timestamp) -> list[str]:
    """Point-in-time names, in ASCII symbol order. Not listed means absent."""
    names: list[str] = []
    for symbol, row in membership.iterrows():
        if _eligible_row(row, t):
            names.append(str(symbol))
    names.sort(key=lambda name: name.encode("ascii"))
    return names


@dataclass
class SkipWeek:
    t: pd.Timestamp
    reason: str
    n_valid: int
    k: int


@dataclass
class TradeWeek:
    t: pd.Timestamp
    t_next: pd.Timestamp
    weights: dict[str, float]
    paths: dict[str, tuple[SidePath, SidePath]]
    scores: dict[str, float]
    eligible_order: list[str]
    regime: str | None
    n_valid: int
    k: int
    long: list[str]
    short: list[str]
    status: dict[str, str]


@dataclass
class Schedule:
    trades: list[TradeWeek] = field(default_factory=list)
    skips: list[SkipWeek] = field(default_factory=list)


def prepare_membership(membership: pd.DataFrame) -> pd.DataFrame:
    """Canonical columns, indexed by symbol."""
    frame = membership.copy()
    if frame.index.name != "symbol":
        if "symbol" not in frame.columns:
            raise ValueError("membership needs a symbol column or index")
        frame = frame.set_index("symbol", drop=True)
    frame.index = frame.index.map(str)
    if frame.index.has_duplicates:
        raise ValueError("membership has duplicate symbols")
    for column in ("launch_time", "delist_time", "first_bar", "last_bar"):
        if column not in frame.columns:
            frame[column] = pd.NaT
        frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce")
    return frame


def build_schedule(
    panel: dict[str, pd.DataFrame],
    membership: pd.DataFrame,
    ratios: RatioStore,
    funding: dict[str, pd.Series],
    metas: dict[str, str],
    window: str,
    btc_bars: pd.DataFrame | None,
) -> Schedule:
    """Selections, paths, and skips. Raises BlockedRun before any metric.

    Every PIT-eligible name with a valid L on a traded week must have both
    side paths. The null draws from that set, so a hole there is the same
    failure as a hole in the tercile: the name would be held and cannot be
    dropped.
    """
    assert_dropped_monday_list(window)
    membership = prepare_membership(membership)
    mondays = rebalance_mondays(window)
    regime_labels = regimes_for(btc_bars, mondays)
    schedule = Schedule()
    for t in mondays:
        t_next = t + pd.Timedelta(days=7)
        if is_dropped_monday(t):
            schedule.skips.append(SkipWeek(t=t, reason="v2_exclusion", n_valid=0, k=0))
            continue
        names = eligible_symbols(membership, t)
        scored: list[tuple[str, float]] = []
        for symbol in names:
            level = ratios.level(symbol, t)
            if level is None:
                continue
            scored.append((symbol, level))
        long, short, k = assign_terciles(scored)
        n_valid = len(scored)
        if k < MIN_NAMES_PER_LEG:
            schedule.skips.append(SkipWeek(t=t, reason="thin_leg", n_valid=n_valid, k=k))
            continue
        paths: dict[str, tuple[SidePath, SidePath]] = {}
        status: dict[str, str] = {}
        scores = {symbol: level for symbol, level in scored}
        # Pinned order is the tercile sort, which is (L, symbol).
        # Same stable sort as assign_terciles, so the null draws from that
        # order and the tercile ends are the head and tail of the pool.
        ordered = sorted(scored, key=lambda row: row[0].encode("ascii"))
        ordered.sort(key=lambda row: (row[1], row[0].encode("ascii")))
        eligible_order = [symbol for symbol, _level in ordered]
        if eligible_order[:k] != long or eligible_order[-k:] != short:
            raise RuntimeError(f"{t} tercile order does not match the pinned sort")
        for symbol in eligible_order:
            bars = panel.get(symbol)
            rates = funding.get(symbol)
            paths[symbol] = require_paths(symbol, t, bars, t_next, rates)
            status[symbol] = listing_status(symbol, metas, membership.loc[symbol])
        schedule.trades.append(
            TradeWeek(
                t=t,
                t_next=t_next,
                weights=leg_weights(long, short, LEG),
                paths=paths,
                scores=scores,
                eligible_order=eligible_order,
                regime=regime_labels.get(t),
                n_valid=n_valid,
                k=k,
                long=list(long),
                short=list(short),
                status=status,
            )
        )
    _assert_gross(schedule)
    return schedule


def _assert_gross(schedule: Schedule) -> None:
    """G and the leg are frozen. A traded week that is not 0.59/0.59 stops."""
    if abs(2.0 * LEG - GROSS) > 1e-15:
        raise RuntimeError(f"frozen gross {GROSS} != 2 * {LEG}")
    for week in schedule.trades:
        long_gross = sum(weight for weight in week.weights.values() if weight > 0)
        short_gross = -sum(weight for weight in week.weights.values() if weight < 0)
        if abs(long_gross - LEG) > 1e-12 or abs(short_gross - LEG) > 1e-12:
            raise RuntimeError(
                f"{week.t} legs are {long_gross} / {short_gross}, not {LEG}"
            )
        if len(week.long) != week.k or len(week.short) != week.k:
            raise RuntimeError(f"{week.t} leg count is not k={week.k}")


def open_actions(drifted: float, target: float) -> list[tuple[str, float, float]]:
    """Monday trades as (action, notional, signed weight being opened or closed).

    A same-sign resize is one rebalance. A sign change is an exit plus an
    entry, and the two notionals add up to |target - drifted|.
    """
    if drifted == 0.0 and target == 0.0:
        return []
    if drifted == 0.0:
        return [("entry", abs(target), target)]
    if target == 0.0:
        return [("exit", abs(drifted), drifted)]
    if (drifted > 0.0) != (target > 0.0):
        return [("exit", abs(drifted), drifted), ("entry", abs(target), target)]
    delta = abs(target - drifted)
    if delta == 0.0:
        return []
    return [("rebalance", delta, target)]


def _side_of(weight: float) -> str:
    if weight > 0.0:
        return "long"
    if weight < 0.0:
        return "short"
    raise ValueError("weight is zero")


@dataclass
class Simulation:
    weekly: list[dict[str, object]]
    trades: list[dict[str, object]]
    name_pnl: list[dict[str, object]]
    paths: list[dict[str, object]]
    weights: list[dict[str, object]]
    eligible: list[dict[str, object]]


def simulate_weeks(
    trades: list[TradeWeek],
    weight_fn,
    *,
    rate: float,
    collect: bool,
) -> Simulation:
    """Compound ``trades`` in order.

    ``weight_fn(week, fresh)`` returns the target weight map for that week.
    The strategy passes its tercile weights. A random draw passes its own.
    ``fresh`` is true when the previous kept rebalance was not 7 days ago,
    including the first week. The caller does not carry a book across that gap.
    """
    weekly: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []
    name_rows: list[dict[str, object]] = []
    path_rows: list[dict[str, object]] = []
    weight_rows: list[dict[str, object]] = []
    eligible_rows: list[dict[str, object]] = []
    carried: dict[str, float] = {}
    prev_t: pd.Timestamp | None = None
    equity = 1.0
    # Status is a symbol property from the pinned meta. An exit can belong
    # to a name that is no longer eligible this week, so the last status
    # seen for that symbol is kept.
    known_status: dict[str, str] = {}

    for i, week in enumerate(trades):
        known_status.update(week.status)
        fresh = not continuous(prev_t, week.t)
        if fresh:
            carried = {}
        nxt = trades[i + 1] if i + 1 < len(trades) else None
        flatten = nxt is None or not continuous(week.t, nxt.t)
        targets = weight_fn(week, fresh)
        if fresh:
            drifted_map = {}
        else:
            drifted_map = dict(carried)
        names = set(targets) | set(drifted_map)
        open_notional: dict[str, float] = {}
        for symbol in names:
            drifted = float(drifted_map.get(symbol, 0.0))
            target = float(targets.get(symbol, 0.0))
            open_notional[symbol] = abs(target - drifted)
            if collect and (drifted != 0.0 or target != 0.0):
                for action, notional, signed in open_actions(drifted, target):
                    trade_rows.append(
                        _trade_row(week.t, symbol, action, notional, signed, rate)
                    )

        price = 0.0
        funding = 0.0
        stop_notional = 0.0
        gap_count = 0
        missing_names = 0
        off_grid = 0
        end_exposure: dict[str, float] = {}
        for symbol, weight in targets.items():
            long_path, short_path = week.paths[symbol]
            path = long_path if weight > 0.0 else short_path
            price += weight * path.underlying_return
            # No leg-mean fill: a missing name contributes its own sum, which is 0.
            funding += -weight * path.funding_sum
            gap_count += path.funding_gaps
            off_grid += path.off_grid_prints
            if path.funding_missing_name:
                missing_names += 1
            if path.stopped:
                stop_notional += abs(weight)
                end_exp = 0.0
                if collect:
                    action = "stop" if path.reason == "stop" else "delist"
                    trade_rows.append(
                        _trade_row(week.t, symbol, action, abs(weight), weight, rate)
                    )
            else:
                end_exp = weight * path.price_ratio
            end_exposure[symbol] = end_exp
            if collect:
                path_rows.append(_path_row(week, symbol, weight, path))
                weight_rows.append(
                    {
                        "rebalance_time": week.t,
                        "symbol": symbol,
                        "side": _side_of(weight),
                        "weight": weight,
                        "L": week.scores[symbol],
                        "regime": week.regime or "",
                        "status": week.status.get(symbol, ""),
                    }
                )

        flatten_notional: dict[str, float] = {}
        if flatten:
            for symbol, exposure in end_exposure.items():
                if exposure != 0.0:
                    flatten_notional[symbol] = abs(exposure)
                    if collect:
                        trade_rows.append(
                            _trade_row(week.t, symbol, "exit", abs(exposure), exposure, rate)
                        )
            end_exposure = {symbol: 0.0 for symbol in end_exposure}

        traded = (
            float(sum(open_notional.values()))
            + stop_notional
            + float(sum(flatten_notional.values()))
        )
        cost = charge_leg(traded, rate)
        net = price + funding - cost
        if not np.isfinite(net):
            raise BlockedRun(next(iter(targets), "?"), week.t, "non-finite weekly return")
        equity_next = equity * (1.0 + net)

        if collect:
            for symbol in sorted(names):
                weight = float(targets.get(symbol, 0.0))
                symbol_cost = rate * (
                    open_notional.get(symbol, 0.0)
                    + (abs(weight) if weight != 0.0 and week.paths[symbol][0 if weight > 0 else 1].stopped else 0.0)
                    + flatten_notional.get(symbol, 0.0)
                )
                # The expression above indexes the tuple wrong when weight is 0.
                # Recompute the stop piece explicitly.
                name_rows.append(
                    {
                        "rebalance_time": week.t,
                        "symbol": symbol,
                        "weight": weight,
                        "status": known_status.get(symbol, ""),
                        "open_notional": open_notional.get(symbol, 0.0),
                        "flatten_notional": flatten_notional.get(symbol, 0.0),
                        "_symbol_cost_partial": symbol_cost,
                    }
                )
            for symbol in week.eligible_order:
                eligible_rows.append(
                    {
                        "rebalance_time": week.t,
                        "symbol": symbol,
                        "L": week.scores[symbol],
                        "status": week.status.get(symbol, ""),
                    }
                )

        n_long = sum(1 for weight in targets.values() if weight > 0.0)
        n_short = sum(1 for weight in targets.values() if weight < 0.0)
        actions = [row for row in trade_rows if row["rebalance_time"] == week.t] if collect else []
        # When not collecting, count actions from the same rules.
        counts = _count_actions(targets, drifted_map, week, flatten, flatten_notional)
        iso = week.t.isocalendar()
        weekly.append(
            {
                "rebalance_time": week.t,
                "iso_year": int(iso.year),
                "iso_week": int(iso.week),
                "n_long": n_long,
                "n_short": n_short,
                "n_valid": week.n_valid,
                "k": week.k,
                "regime": week.regime or "",
                "fresh_entry": fresh,
                "flatten": flatten,
                "gross_price": price,
                "funding": funding,
                "traded_notional": traded,
                "cost": cost,
                "net_return": net,
                "funding_gap_count": gap_count,
                "funding_missing_names": missing_names,
                "off_grid_prints": off_grid,
                "n_entries": counts["entry"],
                "n_exits": counts["exit"],
                "n_stops": counts["stop"],
                "n_delist": counts["delist"],
                "n_rebalance": counts["rebalance"],
                "n_leg_trades": sum(counts.values()),
                "w_long": sum(weight for weight in targets.values() if weight > 0.0),
                "w_short": -sum(weight for weight in targets.values() if weight < 0.0),
                "equity_start": equity,
                "equity_end": equity_next,
                "rate": rate,
            }
        )
        if equity_next <= 0.0 or not np.isfinite(equity_next):
            carried = {}
            equity = equity_next if np.isfinite(equity_next) else 0.0
        elif flatten:
            carried = {}
            equity = equity_next
        else:
            carried = {}
            scale = 1.0 + net
            for symbol, exposure in end_exposure.items():
                if exposure != 0.0:
                    carried[symbol] = exposure / scale
            equity = equity_next
        prev_t = week.t
        # ``actions`` is only used to keep the collector honest in tests.
        del actions

    if collect:
        name_rows = _finish_name_pnl(trades, name_rows, rate)
    return Simulation(weekly, trade_rows, name_rows, path_rows, weight_rows, eligible_rows)


def _finish_name_pnl(
    trades: list[TradeWeek],
    partial: list[dict[str, object]],
    rate: float,
) -> list[dict[str, object]]:
    """Replace the partial cost with the full per-name contribution.

    The partial loop above double-counts nothing but indexes a stop with a
    brittle expression. This pass is the one the survivor split reads.
    """
    by_week = {week.t: week for week in trades}
    # Rebuild from the recorded open/flatten notionals plus the path.
    finished: list[dict[str, object]] = []
    for row in partial:
        week = by_week[row["rebalance_time"]]
        symbol = str(row["symbol"])
        weight = float(row["weight"])
        stop_notional = 0.0
        price = 0.0
        funding = 0.0
        if weight != 0.0:
            path = week.paths[symbol][0 if weight > 0.0 else 1]
            price = weight * path.underlying_return
            funding = -weight * path.funding_sum
            if path.stopped:
                stop_notional = abs(weight)
        cost = rate * (
            float(row["open_notional"]) + stop_notional + float(row["flatten_notional"])
        )
        finished.append(
            {
                "rebalance_time": week.t,
                "symbol": symbol,
                "weight": weight,
                "status": row["status"],
                "price": price,
                "funding": funding,
                "cost": cost,
                "pnl": price + funding - cost,
            }
        )
    return finished


def _count_actions(
    targets: dict[str, float],
    drifted_map: dict[str, float],
    week: TradeWeek,
    flatten: bool,
    flatten_notional: dict[str, float],
) -> dict[str, int]:
    counts = {"entry": 0, "exit": 0, "stop": 0, "delist": 0, "rebalance": 0}
    names = set(targets) | set(drifted_map)
    for symbol in names:
        for action, _notional, _signed in open_actions(
            float(drifted_map.get(symbol, 0.0)),
            float(targets.get(symbol, 0.0)),
        ):
            counts[action] += 1
    for symbol, weight in targets.items():
        if weight == 0.0:
            continue
        path = week.paths[symbol][0 if weight > 0.0 else 1]
        if path.reason == "stop":
            counts["stop"] += 1
        elif path.reason == "delist":
            counts["delist"] += 1
    if flatten:
        counts["exit"] += sum(1 for value in flatten_notional.values() if value != 0.0)
    return counts


def _trade_row(
    t: pd.Timestamp,
    symbol: str,
    action: str,
    notional: float,
    signed: float,
    rate: float,
) -> dict[str, object]:
    side = _side_of(signed)
    return {
        "rebalance_time": t,
        "symbol": symbol,
        "side": side,
        "action": action,
        "notional": notional,
        "weight": signed,
        "cost_rate": rate,
        "cost": charge_leg(notional, rate),
    }


def _path_row(week: TradeWeek, symbol: str, weight: float, path: SidePath) -> dict[str, object]:
    return {
        "rebalance_time": week.t,
        "symbol": symbol,
        "side": _side_of(weight),
        "L": week.scores[symbol],
        "entry_time": week.t,
        "entry_open": path.exit_price / path.price_ratio,
        "exit_time": path.exit_time,
        "exit_price": path.exit_price,
        "reason": path.reason,
        "underlying_return": path.underlying_return,
        "price_ratio": path.price_ratio,
        "funding_sum": path.funding_sum,
        "funding_gaps": path.funding_gaps,
        "funding_missing_name": path.funding_missing_name,
        "weight": weight,
        "status": week.status.get(symbol, ""),
    }


def strategy_weights(week: TradeWeek, _fresh: bool) -> dict[str, float]:
    return week.weights


def run_strategy(schedule: Schedule, *, rate: float = OFFICIAL_LEG_COST) -> Simulation:
    """Official book at ``rate``. The binding call uses 0.31%."""
    return simulate_weeks(schedule.trades, strategy_weights, rate=rate, collect=True)


def proxy_weekly(schedule: Schedule) -> pd.DataFrame:
    """Same paths and trades at the report-only rate. Not a gate input."""
    sim = simulate_weeks(schedule.trades, strategy_weights, rate=PROXY_LEG_COST, collect=False)
    frame = pd.DataFrame(sim.weekly)
    if frame.empty:
        return frame
    return frame.loc[:, ["rebalance_time", "net_return", "cost", "traded_notional"]].rename(
        columns={
            "net_return": "net_return_proxy",
            "cost": "cost_proxy",
            "traded_notional": "traded_notional_proxy",
        }
    )


def attach_proxy(weekly: pd.DataFrame, proxy: pd.DataFrame) -> pd.DataFrame:
    if weekly.empty:
        out = weekly.copy()
        out["net_return_proxy"] = []
        out["cost_proxy"] = []
        return out
    merged = weekly.merge(proxy, on="rebalance_time", how="left")
    return merged


def funding_coverage(name_pnl: pd.DataFrame, schedule: Schedule) -> dict[str, object]:
    """Disclosure required before any metric. Missing names book 0.

    Coverage is over names that were actually held. A name with no funding
    rows is listed once. Gap counts come from the held paths. The leg-mean
    fill used in the planning note is not applied.
    """
    missing: set[str] = set()
    gap_count = 0
    off_grid = 0
    held = 0
    for week in schedule.trades:
        for symbol, weight in week.weights.items():
            held += 1
            path = week.paths[symbol][0 if weight > 0.0 else 1]
            gap_count += path.funding_gaps
            off_grid += path.off_grid_prints
            if path.funding_missing_name:
                missing.add(symbol)
    symbols = sorted(missing)
    return {
        "leg_mean_fill": False,
        "missing_books_zero": True,
        "n_held_positions": held,
        "n_names_with_no_funding_data": len(symbols),
        "names_with_no_funding_data": symbols,
        "funding_gap_count": gap_count,
        "off_grid_prints": off_grid,
        "name_pnl_rows": int(len(name_pnl)),
    }


def survivor_split(name_pnl: pd.DataFrame, trades: pd.DataFrame) -> dict[str, object]:
    """Report-only Trading vs Closed attribution. It does not gate."""
    groups = ("Trading", "Closed")
    out: dict[str, object] = {"report_only": True, "gates": False, "groups": {}}
    if name_pnl.empty:
        for name in groups:
            out["groups"][name] = {
                "pnl": 0.0,
                "price": 0.0,
                "funding": 0.0,
                "cost": 0.0,
                "n_leg_trades": 0,
                "share_of_leg_trades": 0.0,
            }
        return out
    trade_counts = _trades_by_status(name_pnl, trades)
    total_trades = sum(trade_counts.values()) or 1
    for name in groups:
        part = name_pnl[name_pnl["status"] == name]
        n_trades = int(trade_counts.get(name, 0))
        out["groups"][name] = {
            "pnl": float(part["pnl"].sum()) if len(part) else 0.0,
            "price": float(part["price"].sum()) if len(part) else 0.0,
            "funding": float(part["funding"].sum()) if len(part) else 0.0,
            "cost": float(part["cost"].sum()) if len(part) else 0.0,
            "n_leg_trades": n_trades,
            "share_of_leg_trades": n_trades / total_trades,
        }
    other = sorted(set(name_pnl["status"].astype(str)) - set(groups))
    out["other_status"] = other
    return out


def _trades_by_status(name_pnl: pd.DataFrame, trades: pd.DataFrame) -> dict[str, int]:
    if trades.empty:
        return {}
    status = (
        name_pnl.loc[:, ["rebalance_time", "symbol", "status"]]
        .drop_duplicates()
        .set_index(["rebalance_time", "symbol"])["status"]
    )
    counts: dict[str, int] = {}
    for row in trades.itertuples(index=False):
        key = (row.rebalance_time, row.symbol)
        label = str(status.get(key, ""))
        counts[label] = counts.get(label, 0) + 1
    return counts


def skips_frame(skips: list[SkipWeek]) -> pd.DataFrame:
    rows = [
        {
            "rebalance_time": skip.t,
            "reason": skip.reason,
            "n_valid": skip.n_valid,
            "k": skip.k,
            "booked_week": False,
        }
        for skip in skips
    ]
    return pd.DataFrame(
        rows,
        columns=["rebalance_time", "reason", "n_valid", "k", "booked_week"],
    )


def simulation_frames(sim: Simulation, proxy: pd.DataFrame) -> dict[str, pd.DataFrame]:
    weekly = attach_proxy(pd.DataFrame(sim.weekly), proxy)
    return {
        "weights": pd.DataFrame(sim.weights),
        "name_paths": pd.DataFrame(sim.paths),
        "weekly_returns": weekly,
        "leg_trades": pd.DataFrame(sim.trades),
        "eligible": pd.DataFrame(sim.eligible),
        "name_pnl": pd.DataFrame(sim.name_pnl),
    }
