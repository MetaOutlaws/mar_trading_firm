"""Dollar-neutral book for xs_prospect_value_weekly.

The skew path in ``book.apply_schedule`` is not used here. Skew keeps that
function and its outputs. This module is the funding sum, the BTC regime
label, and the two-level cost on an equal-weight dollar-neutral tercile book.

P&L per week, on $1 long and $1 short::

    price   = sum(weight * underlying_return)
            = mean(long leg) - mean(short leg)
    funding = sum(-weight * observed funding rates over that side's hold)
    net     = price + funding - cost

``price`` books a stopped coin as cash after the stop fill, so the flat
dollar weights still pick up the path. Funding is the sum of observed 8h
prints. A name is dropped only when the 8h before the entry open has no
print. A gap during the hold keeps the name: missing settlements are
counted and are not filled. Official cost is 0.31% of traded notional and
is the only cost the gates see. 0.158% is the report-only proxy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.xs_spread.costs import charge_leg, charge_leg_at

REGIME_BAND = 0.01
FUNDING_STEP = pd.Timedelta(hours=8)


def settlement_times(entry: pd.Timestamp, exit_time: pd.Timestamp) -> pd.DatetimeIndex:
    """8h UTC boundaries strictly after ``entry`` and at or before ``exit``."""
    entry = _as_utc(entry)
    exit_time = _as_utc(exit_time)
    if exit_time <= entry:
        return pd.DatetimeIndex([], tz="UTC")
    step = int(FUNDING_STEP.value)
    first = (int(entry.value) // step + 1) * step
    last = int(exit_time.value)
    if first > last:
        return pd.DatetimeIndex([], tz="UTC")
    stamps = np.arange(first, last + 1, step, dtype="int64")
    return pd.to_datetime(stamps, utc=True)


def _as_utc(stamp: pd.Timestamp) -> pd.Timestamp:
    stamp = pd.Timestamp(stamp)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _rates_utc(rates: pd.Series) -> pd.Series:
    index = rates.index
    if getattr(index, "tz", None) is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    return pd.Series(np.asarray(rates.to_numpy(dtype="float64")), index=index)


def funding_print_before_entry(rates: pd.Series | None, entry: pd.Timestamp) -> bool:
    """True when a finite print exists in the 8h before the entry open.

    The window is ``[entry - 8h, entry)``. A print exactly 8h earlier
    counts. A print at the entry open does not: it is not before entry.
    An observed rate of zero is a print.
    """
    if rates is None or len(rates) == 0:
        return False
    entry = _as_utc(entry)
    aligned = _rates_utc(rates)
    start = entry - FUNDING_STEP
    window = aligned[(aligned.index >= start) & (aligned.index < entry)]
    if window.empty:
        return False
    return bool(np.isfinite(window.to_numpy(dtype="float64")).any())


def funding_accrual(
    rates: pd.Series | None,
    entry: pd.Timestamp,
    exit_time: pd.Timestamp,
) -> tuple[float, int]:
    """Observed funding sum and the number of missing in-hold settlements.

    Expected settlements are the 8h UTC boundaries strictly after entry
    and at or before exit. A missing print is omitted from the sum and
    counted. An observed rate of zero is a print. A hold with no
    settlement returns ``(0.0, 0)``. Missing prints are not replaced with 0
    inside the count: the count is how many expected stamps had no finite rate.
    """
    expected = settlement_times(entry, exit_time)
    n_expected = len(expected)
    if n_expected == 0:
        return 0.0, 0
    if rates is None or len(rates) == 0:
        return 0.0, n_expected
    present = _rates_utc(rates).reindex(expected)
    values = present.to_numpy(dtype="float64")
    finite = np.isfinite(values)
    observed = float(values[finite].sum()) if bool(finite.any()) else 0.0
    return observed, int(n_expected - int(finite.sum()))


def forward_open_return(bars: pd.DataFrame, t: pd.Timestamp, t_next: pd.Timestamp) -> float:
    """Gross 7-day return from the entry open to the next rebalance open.

    This is the regression outcome, not the stopped path. A missing entry
    open or a missing open at ``t_next`` is NaN. The stop does not shorten it.
    """
    if bars.empty:
        return float("nan")
    index = bars.index
    entry_pos = int(index.searchsorted(t, side="left"))
    if entry_pos >= len(index) or index[entry_pos] >= t_next:
        return float("nan")
    end_pos = int(index.searchsorted(t_next, side="left"))
    if end_pos >= len(index) or index[end_pos] != t_next:
        return float("nan")
    entry_open = float(bars.iloc[entry_pos]["open"])
    exit_open = float(bars.iloc[end_pos]["open"])
    if not np.isfinite(entry_open) or not np.isfinite(exit_open) or entry_open <= 0 or exit_open <= 0:
        return float("nan")
    return exit_open / entry_open - 1.0


def four_hour_closes(bars: pd.DataFrame) -> pd.Series:
    """Close of each completed 4h block, stamped at the block's close time.

    The block opened at 00:00/04:00/... uses the hourly bar opened three
    hours later. A missing hour drops the block. It is not filled.
    """
    if bars.empty:
        return pd.Series(dtype="float64")
    block_opens = bars.index[bars.index.hour % 4 == 0]
    stamps: list[pd.Timestamp] = []
    closes: list[float] = []
    for open_time in block_opens:
        last_hour = open_time + pd.Timedelta(hours=3)
        close_time = open_time + pd.Timedelta(hours=4)
        if last_hour not in bars.index:
            continue
        price = float(bars.at[last_hour, "close"])
        if not np.isfinite(price) or price <= 0:
            continue
        stamps.append(pd.Timestamp(close_time))
        closes.append(price)
    if not stamps:
        return pd.Series(dtype="float64")
    out = pd.Series(closes, index=pd.DatetimeIndex(stamps), dtype="float64")
    return out[~out.index.duplicated(keep="last")].sort_index()


def classify_ema_band(ema50: float, ema200: float) -> str:
    """BULL / BEAR / CHOP from EMA50 versus EMA200 ± 1%."""
    if not np.isfinite(ema50) or not np.isfinite(ema200) or ema200 == 0.0:
        raise ValueError("EMA band needs finite EMAs")
    if ema50 > ema200 * (1.0 + REGIME_BAND):
        return "BULL"
    if ema50 < ema200 * (1.0 - REGIME_BAND):
        return "BEAR"
    return "CHOP"


def regime_at(bars: pd.DataFrame, as_of: pd.Timestamp) -> str | None:
    """Regime of the last closed 4h bar at or before ``as_of``.

    EMA50 and EMA200 need 200 closed 4h bars. Shorter history is unlabelled,
    not a guessed regime. A 4h close after ``as_of`` is not used.
    """
    closes = four_hour_closes(bars)
    as_of = _as_utc(as_of)
    usable = closes[closes.index <= as_of]
    if len(usable) < 200:
        return None
    ema50 = float(usable.ewm(span=50, adjust=False).mean().iloc[-1])
    ema200 = float(usable.ewm(span=200, adjust=False).mean().iloc[-1])
    return classify_ema_band(ema50, ema200)


def apply_tk_schedule(
    weights: pd.DataFrame,
    paths: pd.DataFrame,
    *,
    proxy_rate: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Weekly TK P&L at the official rate and at the report-only proxy.

    A name that stays on the same side pays 0.31% on ``|w - w_prev|`` only.
    A new name, an exit, a stop and a delist pay 0.31% on the full notional.
    A stop clears the name, so the next selection is a new entry.
    Funding is ``-weight * sum(rates)`` over that side's own hold. A missing
    funding sum is an error, not a zero.
    """
    if weights.empty:
        return _empty_weekly(), _empty_trades()
    if "long_funding_sum" not in paths.columns or "short_funding_sum" not in paths.columns:
        raise ValueError("TK paths are missing funding sums; refusing to zero-fill")
    w = weights.copy()
    p = paths.copy()
    w["rebalance_time"] = pd.to_datetime(w["rebalance_time"], utc=True)
    p["rebalance_time"] = pd.to_datetime(p["rebalance_time"], utc=True)
    times = list(dict.fromkeys(w["rebalance_time"].tolist()))
    path_groups = {t: g.set_index("symbol") for t, g in p.groupby("rebalance_time", sort=False)}
    weight_groups = {t: g.set_index("symbol") for t, g in w.groupby("rebalance_time", sort=False)}
    still_open: dict[str, tuple[str, float]] = {}
    weekly_rows: list[dict[str, object]] = []
    trade_rows: list[dict[str, object]] = []

    for i, t in enumerate(times):
        group = weight_groups[t]
        path_group = path_groups.get(t, pd.DataFrame())
        terminal = i == len(times) - 1
        next_group = None if terminal else weight_groups[times[i + 1]]
        price = 0.0
        funding = 0.0
        funding_gaps = 0
        long_gaps = 0
        short_gaps = 0
        cost = 0.0
        cost_proxy = 0.0
        n_entries = n_exits = n_stops = n_delist = n_rebalance = 0
        n_long = int((group["weight"] > 0).sum())
        n_short = int((group["weight"] < 0).sum())
        w_long = float(group.loc[group["weight"] > 0, "weight"].sum()) if n_long else 0.0
        w_short = float(-group.loc[group["weight"] < 0, "weight"].sum()) if n_short else 0.0
        next_open: dict[str, tuple[str, float]] = {}

        for symbol, row in group.iterrows():
            if symbol not in path_group.index:
                raise ValueError(f"{symbol} is in the TK book at {t} but has no path")
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
            fsum = float(path_row["long_funding_sum" if side == "long" else "short_funding_sum"])
            if not np.isfinite(fsum):
                raise ValueError(f"{symbol} funding is missing at {t}; refusing to zero-fill")
            gap_column = "long_funding_gaps" if side == "long" else "short_funding_gaps"
            gaps = int(path_row[gap_column]) if gap_column in path_row.index and pd.notna(path_row[gap_column]) else 0
            prev = still_open.get(str(symbol))
            same_side = prev is not None and prev[0] == side
            continues = False
            if next_group is not None and symbol in next_group.index:
                continues = str(next_group.loc[symbol, "side"]) == side
            charges: list[tuple[str, float]] = []
            if not same_side:
                charges.append(("entry", abs(weight)))
            elif abs(weight - prev[1]) > 0.0:
                # Same side, new equal weight because the leg count changed.
                charges.append(("rebalance", abs(weight - prev[1])))
            if reason == "stop":
                charges.append(("stop", abs(weight)))
            elif reason == "delist":
                charges.append(("delist", abs(weight)))
            elif terminal or not continues:
                charges.append(("exit", abs(weight)))
            for action, notional in charges:
                official = charge_leg(notional)
                proxy = charge_leg_at(notional, proxy_rate)
                cost += official
                cost_proxy += proxy
                fill_time = entry_time if action in {"entry", "rebalance"} else exit_time
                fill_price = entry_open if action in {"entry", "rebalance"} else exit_price
                trade_rows.append(
                    {
                        "rebalance_time": t,
                        "symbol": symbol,
                        "side": side,
                        "action": action,
                        "fill_time": fill_time,
                        "fill_price": fill_price,
                        "weight": weight,
                        "traded_notional": notional,
                        "cost_rate": official / notional if notional else 0.0,
                    }
                )
                if action == "entry":
                    n_entries += 1
                elif action == "rebalance":
                    n_rebalance += 1
                elif action == "stop":
                    n_stops += 1
                elif action == "delist":
                    n_delist += 1
                else:
                    n_exits += 1
            price += weight * underlying
            # Positive funding rate: longs pay, shorts receive.
            funding += -weight * fsum
            funding_gaps += gaps
            if side == "long":
                long_gaps += gaps
            else:
                short_gaps += gaps
            if reason == "hold" and not terminal:
                next_open[str(symbol)] = (side, weight)

        n_leg_trades = n_entries + n_exits + n_stops + n_delist + n_rebalance
        n_positions = n_long + n_short
        iso = pd.Timestamp(t).isocalendar()
        regime = ""
        if "regime" in group.columns:
            raw_regime = group["regime"].iloc[0]
            if isinstance(raw_regime, str) and raw_regime in {"BULL", "BEAR", "CHOP"}:
                regime = raw_regime
        weekly_rows.append(
            {
                "rebalance_time": t,
                "iso_year": int(iso.year),
                "iso_week": int(iso.week),
                "n_long": n_long,
                "n_short": n_short,
                "w_long": w_long,
                "w_short": w_short,
                "net_exposure": w_long - w_short,
                "gross_spread": price,
                "funding": funding,
                "funding_gap_count": funding_gaps,
                "long_funding_gap_count": long_gaps,
                "short_funding_gap_count": short_gaps,
                "cost": cost,
                "net_spread": price + funding - cost,
                "cost_proxy": cost_proxy,
                "net_spread_proxy": price + funding - cost_proxy,
                "n_entries": n_entries,
                "n_exits": n_exits,
                "n_stops": n_stops,
                "n_delist": n_delist,
                "n_rebalance": n_rebalance,
                "n_leg_trades": n_leg_trades,
                "turnover": (n_leg_trades / n_positions) if n_positions else 0.0,
                "regime": regime,
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
            "w_long",
            "w_short",
            "net_exposure",
            "gross_spread",
            "funding",
            "funding_gap_count",
            "long_funding_gap_count",
            "short_funding_gap_count",
            "cost",
            "net_spread",
            "cost_proxy",
            "net_spread_proxy",
            "n_entries",
            "n_exits",
            "n_stops",
            "n_delist",
            "n_rebalance",
            "n_leg_trades",
            "turnover",
            "regime",
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
            "traded_notional",
            "cost_rate",
        ]
    )
