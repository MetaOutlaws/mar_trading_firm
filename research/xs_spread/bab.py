"""Beta-neutral book for xs_bab_btc_weekly.

The dollar-neutral path in ``book.apply_schedule`` is not used here. Skew
keeps that function. This module is the Frazzini-Pedersen scaling, the
funding sum, the BTC regime label, and the two-level cost.

P&L per week, per $1 average gross per side::

    price = w_L * mean(long returns) - w_H * mean(short returns)
    net   = price + funding - cost

``price`` already contains the net dollar exposure ``(w_L - w_H)`` when
both legs move together. Funding is the sum of observed 8h prints on each
leg. A missing print is not filled with zero: the name is not tradable
that week. Official cost is 0.31% of traded notional and is the only cost
the gates see. The 0.181% SOL proxy is a second column.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.xs_spread.costs import charge_leg, charge_leg_at

REGIME_BAND = 0.01
FUNDING_STEP = pd.Timedelta(hours=8)


def beta_neutral_weights(
    scores: pd.Series,
    long_symbols: list[str],
    short_symbols: list[str],
    *,
    leverage_cap: float,
) -> pd.Series:
    """Scale two equal-weight legs to ex-ante beta neutrality.

    Raw notional is ``1 / mean beta``, capped at ``leverage_cap``, then
    both sides are multiplied so their average gross is $1. A non-positive
    mean beta has no long leverage, and the week is an empty book.
    """
    if leverage_cap <= 0:
        raise ValueError("leverage cap must be positive")
    long = [str(symbol) for symbol in long_symbols]
    short = [str(symbol) for symbol in short_symbols]
    if not long or not short:
        return pd.Series(dtype="float64", name="weight")
    mean_long = float(scores.loc[long].mean())
    mean_short = float(scores.loc[short].mean())
    if not np.isfinite(mean_long) or not np.isfinite(mean_short):
        return pd.Series(dtype="float64", name="weight")
    if mean_long <= 0.0 or mean_short <= 0.0:
        return pd.Series(dtype="float64", name="weight")
    raw_long = min(1.0 / mean_long, float(leverage_cap))
    raw_short = min(1.0 / mean_short, float(leverage_cap))
    scale = 2.0 / (raw_long + raw_short)
    w_long = scale * raw_long
    w_short = scale * raw_short
    out = pd.Series(0.0, index=long + short, dtype="float64")
    out.loc[long] = w_long / len(long)
    out.loc[short] = -w_short / len(short)
    out.index.name = "symbol"
    out.name = "weight"
    return out


def leg_sets_from_scores(scores: pd.Series, *, long_side: str) -> tuple[list[str], list[str]]:
    """Same tercile membership as the dollar book: ``k = n // 3``, ties by symbol."""
    from research.xs_spread.book import tercile_weights

    weights = tercile_weights(scores, long_side=long_side)
    if weights.empty:
        return [], []
    long = [str(symbol) for symbol in weights.index[weights > 0]]
    short = [str(symbol) for symbol in weights.index[weights < 0]]
    return long, short


def settlement_times(entry: pd.Timestamp, exit_time: pd.Timestamp) -> pd.DatetimeIndex:
    """8h UTC boundaries strictly after ``entry`` and at or before ``exit``."""
    entry = pd.Timestamp(entry)
    exit_time = pd.Timestamp(exit_time)
    if entry.tzinfo is None:
        entry = entry.tz_localize("UTC")
    else:
        entry = entry.tz_convert("UTC")
    if exit_time.tzinfo is None:
        exit_time = exit_time.tz_localize("UTC")
    else:
        exit_time = exit_time.tz_convert("UTC")
    if exit_time <= entry:
        return pd.DatetimeIndex([], tz="UTC")
    step = int(FUNDING_STEP.value)
    first = (int(entry.value) // step + 1) * step
    last = int(exit_time.value)
    if first > last:
        return pd.DatetimeIndex([], tz="UTC")
    stamps = np.arange(first, last + 1, step, dtype="int64")
    return pd.to_datetime(stamps, utc=True)


def funding_rate_sum(rates: pd.Series | None, entry: pd.Timestamp, exit_time: pd.Timestamp) -> float:
    """Sum of observed funding rates over the hold.

    Returns NaN when any expected 8h settlement has no print. An observed
    rate of zero is a print and is summed. It is not a fill for a hole.
    A hold that contains no settlement returns 0.
    """
    expected = settlement_times(entry, exit_time)
    if len(expected) == 0:
        return 0.0
    if rates is None or len(rates) == 0:
        return float("nan")
    index = rates.index
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    aligned = pd.Series(rates.to_numpy(dtype="float64"), index=index)
    present = aligned.reindex(expected)
    if present.isna().any() or not np.isfinite(present.to_numpy(dtype="float64")).all():
        return float("nan")
    return float(present.sum())


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
    not a guessed regime.
    """
    closes = four_hour_closes(bars)
    usable = closes[closes.index <= as_of]
    if len(usable) < 200:
        return None
    ema50 = float(usable.ewm(span=50, adjust=False).mean().iloc[-1])
    ema200 = float(usable.ewm(span=200, adjust=False).mean().iloc[-1])
    return classify_ema_band(ema50, ema200)


def apply_beta_schedule(
    weights: pd.DataFrame,
    paths: pd.DataFrame,
    *,
    proxy_rate: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Weekly BAB P&L at the official rate and at the report-only proxy.

    A name that stays on the same side pays 0.31% on ``|w - w_prev|`` only.
    A new name, an exit, a stop and a delist pay 0.31% on the full notional.
    Funding is ``-weight * sum(rates)`` over that side's own hold.
    """
    if weights.empty:
        return _empty_weekly(), _empty_trades()
    if "long_funding_sum" not in paths.columns or "short_funding_sum" not in paths.columns:
        raise ValueError("BAB paths are missing funding sums; refusing to zero-fill")
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
                raise ValueError(f"{symbol} is in the BAB book at {t} but has no path")
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
            prev = still_open.get(str(symbol))
            same_side = prev is not None and prev[0] == side
            continues = False
            if next_group is not None and symbol in next_group.index:
                continues = str(next_group.loc[symbol, "side"]) == side
            charges: list[tuple[str, float]] = []
            if not same_side:
                charges.append(("entry", abs(weight)))
            elif abs(weight - prev[1]) > 0.0:
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
                trade_rows.append(
                    {
                        "rebalance_time": t,
                        "symbol": symbol,
                        "side": side,
                        "action": action,
                        "fill_time": entry_time if action == "entry" else exit_time,
                        "fill_price": entry_open if action == "entry" else exit_price,
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
            funding += -weight * fsum
            if reason == "hold" and not terminal:
                next_open[str(symbol)] = (side, weight)

        n_leg_trades = n_entries + n_exits + n_stops + n_delist + n_rebalance
        n_positions = n_long + n_short
        iso = pd.Timestamp(t).isocalendar()
        regime = None
        if "regime" in group.columns:
            raw_regime = group["regime"].iloc[0]
            if isinstance(raw_regime, str) and raw_regime not in {"", "nan", "None"}:
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
                "regime": regime if isinstance(regime, str) else "",
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
