"""BTC 4h regime band from Garwe's LSR v2 countersign.

The classifier takes EMA values the caller already has. It does not read
bars, prices, or a live label. A week-cluster is labelled only at a Monday
00:00 UTC open, and a timestamp on or after 2026-01-01 UTC is refused.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence

# Copied verbatim from Garwe's ruling (a).
REGIME_RULE = (
    "Desk rule from Garwe LSR v2 countersign 8c3bd709 A3: BTC 4h EMA50 vs EMA200, "
    "+/-1% band; loss as in c90d9e3c. BEAR = EMA50 < EMA200*0.99; BULL = EMA50 > EMA200*1.01; "
    "CHOP otherwise. Each week-cluster is labelled by the regime at its Monday 00:00 UTC open. "
    "Soko's live label is not used. No-losing-regime gate: each of BULL, BEAR and CHOP needs "
    ">=4 non-empty clusters, otherwise the result is INCOMPLETE, not PASS."
)

REGIMES = ("BULL", "BEAR", "CHOP")
MIN_NONEMPTY_CLUSTERS = 4
REFUSAL_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


class RegimeInputError(ValueError):
    """The EMA pair or the week stamp cannot be labelled."""


def classify_regime(ema50: float, ema200: float) -> str:
    """BEAR below the band, BULL above it, CHOP on the boundary and inside it."""
    if isinstance(ema50, bool) or isinstance(ema200, bool):
        raise RegimeInputError("EMA values must be numbers")
    try:
        fast = float(ema50)
        slow = float(ema200)
    except (TypeError, ValueError) as exc:
        raise RegimeInputError("EMA values must be numbers") from exc
    if fast != fast or slow != slow or slow == 0.0:
        raise RegimeInputError("EMA band needs finite non-zero EMA200")
    # Strict inequalities match the ruling. Equality stays CHOP.
    if fast < slow * 0.99:
        return "BEAR"
    if fast > slow * 1.01:
        return "BULL"
    return "CHOP"


def classify_ema_series(ema50: Sequence[float], ema200: Sequence[float]) -> list[str]:
    """Label a synthetic EMA50 series against the paired EMA200 series."""
    if len(ema50) != len(ema200):
        raise RegimeInputError("EMA series must be the same length")
    return [classify_regime(fast, slow) for fast, slow in zip(ema50, ema200)]


def _monday_open(stamp: datetime) -> datetime:
    if stamp.tzinfo is None:
        raise RegimeInputError("week stamp needs a timezone")
    moment = stamp.astimezone(timezone.utc)
    if moment >= REFUSAL_AT:
        raise RegimeInputError("regime label refuses timestamps on or after 2026-01-01 UTC")
    midnight = (moment.hour, moment.minute, moment.second, moment.microsecond) == (0, 0, 0, 0)
    if moment.weekday() != 0 or not midnight:
        raise RegimeInputError("week-cluster regime is the Monday 00:00 UTC open")
    return moment


def label_week_cluster(monday_open: datetime, ema50: float, ema200: float) -> str:
    """Regime at one week-cluster's Monday 00:00 UTC open.

    The EMAs are the caller's values at that open. This does not load a bar.
    """
    _monday_open(monday_open)
    return classify_regime(ema50, ema200)


def label_week_clusters(monday_opens: Sequence[datetime], ema50: Sequence[float], ema200: Sequence[float]) -> list[str]:
    """Label each Monday open from the EMA pair at that open."""
    if not (len(monday_opens) == len(ema50) == len(ema200)):
        raise RegimeInputError("week stamps and EMA series must be the same length")
    return [label_week_cluster(stamp, fast, slow) for stamp, fast, slow in zip(monday_opens, ema50, ema200)]


def no_losing_regime_gate(nonempty_counts: Mapping[str, int]) -> dict:
    """Count gate only. A short regime is INCOMPLETE, and that is not a PASS.

    Loss, as cited from c90d9e3c, is not evaluated. This function does not
    read weekly P&L or bars.
    """
    short = [name for name in REGIMES if int(nonempty_counts.get(name, 0)) < MIN_NONEMPTY_CLUSTERS]
    if short:
        return dict(result="INCOMPLETE", passed=False, short=short, loss_evaluated=False)
    return dict(
        result="NOT_SCORED",
        passed=False,
        short=[],
        loss_evaluated=False,
        reason="each regime has at least 4 non-empty clusters; loss as in c90d9e3c is not evaluated",
    )
