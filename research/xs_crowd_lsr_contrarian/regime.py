"""BTC 4h EMA50/EMA200 ±1% band, and the no-losing-regime gate.

The band is the prereg's report, which Garwe ruled a hard gate. The loss
rule is copied from the sentiment_beta prereg (c90d9e3c): a regime with
at least 5 weeks and a negative mean weekly net fails. Fewer than 5 weeks
is report-only. An unlabelled week is not a regime.

EMA uses the standard recursive form (pandas ``ewm(span, adjust=False)``).
A 4h block needs its last hour. A missing hour drops the block. It is not
filled. The last closed 4h bar at or before the rebalance is the one used.
A bar that closes exactly at the rebalance counts as closed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.xs_crowd_lsr_contrarian.calendar import as_utc
from research.xs_crowd_lsr_contrarian.pins import MIN_REGIME_WEEKS, REGIME_BAND

REGIMES = ("BULL", "BEAR", "CHOP")


def classify_ema_band(ema50: float, ema200: float) -> str:
    """BULL / BEAR / CHOP from EMA50 versus EMA200 ± 1%."""
    if not np.isfinite(ema50) or not np.isfinite(ema200) or ema200 == 0.0:
        raise ValueError("EMA band needs finite EMAs")
    if ema50 > ema200 * (1.0 + REGIME_BAND):
        return "BULL"
    if ema50 < ema200 * (1.0 - REGIME_BAND):
        return "BEAR"
    return "CHOP"


def four_hour_closes(bars: pd.DataFrame) -> pd.Series:
    """Close of each completed 4h block, stamped at the block's close time.

    The block opened at 00:00/04:00/... uses the hourly bar opened three
    hours later. That bar's close is the 4h close.
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
    index = pd.DatetimeIndex(stamps)
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    out = pd.Series(closes, index=index, dtype="float64")
    return out[~out.index.duplicated(keep="last")].sort_index()


def regimes_for(bars: pd.DataFrame | None, stamps: list[pd.Timestamp]) -> dict[pd.Timestamp, str | None]:
    """Label every rebalance from one EMA pass.

    The label is None until 200 closed 4h bars exist at or before that stamp.
    """
    out: dict[pd.Timestamp, str | None] = {as_utc(stamp): None for stamp in stamps}
    if bars is None or bars.empty or not stamps:
        return out
    closes = four_hour_closes(bars)
    if closes.empty:
        return out
    ema50 = closes.ewm(span=50, adjust=False).mean()
    ema200 = closes.ewm(span=200, adjust=False).mean()
    index = closes.index
    for stamp in stamps:
        as_of = as_utc(stamp)
        pos = int(index.searchsorted(as_of, side="right")) - 1
        if pos < 199:
            out[as_of] = None
            continue
        out[as_of] = classify_ema_band(float(ema50.iloc[pos]), float(ema200.iloc[pos]))
    return out


def regime_at(bars: pd.DataFrame | None, as_of: pd.Timestamp) -> str | None:
    """Regime of the last closed 4h bar at or before ``as_of``.

    EMA50 and EMA200 need 200 closed 4h bars. Shorter history is unlabelled,
    not a guessed regime. A 4h close after ``as_of`` is not used.
    """
    if bars is None or bars.empty:
        return None
    closes = four_hour_closes(bars)
    usable = closes[closes.index <= as_utc(as_of)]
    if len(usable) < 200:
        return None
    ema50 = float(usable.ewm(span=50, adjust=False).mean().iloc[-1])
    ema200 = float(usable.ewm(span=200, adjust=False).mean().iloc[-1])
    return classify_ema_band(ema50, ema200)


def regime_gate(weekly: pd.DataFrame, column: str = "net_return") -> dict[str, object]:
    """No losing regime. Report-only when a label has fewer than 5 weeks.

    The gate fails when any of BULL, BEAR, CHOP has at least 5 weeks and a
    mean weekly net return strictly below zero. An empty label is absent,
    not a failure. Unlabelled weeks are ignored.
    """
    if weekly.empty or "regime" not in weekly.columns:
        return {"pass": True, "regimes": {}, "failing": [], "min_weeks": MIN_REGIME_WEEKS}
    labelled = weekly[weekly["regime"].isin(REGIMES)]
    report: dict[str, dict[str, object]] = {}
    failing: list[str] = []
    for regime, part in labelled.groupby("regime", sort=True):
        net = part[column].to_numpy(dtype="float64")
        n = int(net.size)
        mean = float(net.mean()) if n else float("nan")
        if n < MIN_REGIME_WEEKS:
            status = "report_only"
        elif mean < 0.0:
            status = "fail"
            failing.append(str(regime))
        else:
            status = "pass"
        report[str(regime)] = {"n_weeks": n, "mean_net_return": mean, "status": status}
    return {
        "pass": len(failing) == 0,
        "regimes": report,
        "failing": failing,
        "min_weeks": MIN_REGIME_WEEKS,
    }
