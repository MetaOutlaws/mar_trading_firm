"""Paper-only loss-streak probation.

The global cool-down (``RiskLimits.max_consecutive_losses``) blocks every new
entry once the book has that many losing closes in a row, and it stays blocked
until some close has ``net_pnl > 0``. A book that keeps losing cannot produce
the win that would clear it.

When ``LOSS_STREAK_PROBATION`` is on, and the process is paper, that global
streak no longer blocks entries by itself. Each sleeve family plus side is
judged on its own record. Live and testnet ignore the flag: their global
cool-down is unchanged.

The new knobs live on ``Settings``, not on ``RiskLimits``, so the limits file
pin does not move. The sizer's cap math is not edited. Half size and the
one-at-a-time trial scale the sizer's result by 0.5.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from config.settings import TradingMode, get_settings

logger = logging.getLogger(__name__)

# Under heightened scrutiny a strategy with fewer closed trades than this
# is half-sized. The window setting cannot be configured below this either.
STRATEGY_EXPECTANCY_MIN_TRADES = 5

# Journal / log action names. Kept stable so tests and the operator read
# the same words.
ACTION_NORMAL = "normal"
ACTION_HALF = "half"
ACTION_TRIAL = "trial"
ACTION_BLOCKED = "blocked"

_warned_non_paper = False


def loss_streak_probation_enabled() -> bool:
    """True only when the flag is on and this process is paper.

    Live and testnet ignore the flag so a copied environment cannot lift
    the global cool-down on real orders. The default is off.
    """
    global _warned_non_paper
    settings = get_settings()
    if not bool(settings.loss_streak_probation):
        return False
    if settings.trading_mode is not TradingMode.PAPER:
        if not _warned_non_paper:
            _warned_non_paper = True
            logger.warning(
                "LOSS_STREAK_PROBATION is set but trading mode is %s; "
                "probation stays off and the global loss streak still blocks entries.",
                settings.trading_mode.value,
            )
        return False
    return True


def strategy_key(strategy: str, side: str) -> str:
    """Sleeve family plus side, e.g. ``ema_adx LONG``.

    The family is the strategy name stored on the trade. The side is
    upper-cased so ``long`` and ``LONG`` are one strategy. A long and a
    short of the same family are different strategies.
    """
    family = (strategy or "").strip()
    side_name = (side or "").strip().upper()
    if family and side_name:
        return f"{family} {side_name}"
    return family or side_name


def _as_utc(value: datetime | None) -> datetime:
    """Aware UTC. Missing stamps sort as the oldest instant, not as a crash."""
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ClosedFill:
    """One closed trade, reduced to the fields the streak needs.

    ``net_pnl`` is after fees. A value above zero resets the streak. Zero
    and negative continue it, matching the global cool-down.
    """

    strategy: str
    side: str
    net_pnl: float
    entry_time: datetime | None
    exit_time: datetime | None
    trade_id: int = 0


@dataclass(frozen=True)
class ProbationDecision:
    """What probation decided for one entry. ``journaled`` is false for a
    quiet pass outside scrutiny that did not hit the per-strategy block.
    """

    action: str
    reason: str
    risk_multiplier: float
    journaled: bool
    strategy: str
    raw_streak: int
    clustered_streak: int
    streak: int
    rolling_expectancy: float | None
    win_rate: float | None
    n: int
    global_streak: int
    scrutiny: bool


def trailing_losses(fills: Sequence[ClosedFill]) -> list[ClosedFill]:
    """Losing closes since this strategy's last ``net_pnl > 0`` close.

    Newest exit first. The first winner ends the walk. Older losses, from
    before that winner, are not part of the streak.
    """
    ordered = sorted(fills, key=lambda fill: (_as_utc(fill.exit_time), fill.trade_id), reverse=True)
    losses: list[ClosedFill] = []
    for fill in ordered:
        if fill.net_pnl > 0:
            break
        losses.append(fill)
    return losses


def cluster_loss_streak(losses: Sequence[ClosedFill]) -> int:
    """Count overlapping trailing losses as one cluster.

    Sort by entry time and walk. A loss whose entry is strictly before the
    current cluster's latest exit joins that cluster, and the cluster end
    becomes the later of the two exits. Any other loss starts a new cluster.
    The streak is the number of clusters. An empty list is zero.

    Back-to-back holds (entry exactly equal to the previous exit) are two
    clusters: "before" is strict, so they did not overlap.
    """
    if not losses:
        return 0
    ordered = sorted(
        losses,
        key=lambda fill: (
            _as_utc(fill.entry_time if fill.entry_time is not None else fill.exit_time),
            _as_utc(fill.exit_time),
            fill.trade_id,
        ),
    )
    clusters = 0
    cluster_end: datetime | None = None
    for loss in ordered:
        entry = _as_utc(loss.entry_time if loss.entry_time is not None else loss.exit_time)
        exit_at = _as_utc(loss.exit_time)
        if cluster_end is None or entry >= cluster_end:
            clusters += 1
            cluster_end = exit_at
        elif exit_at > cluster_end:
            cluster_end = exit_at
    return clusters


def rolling_nets(fills: Sequence[ClosedFill], window: int) -> list[float]:
    """Most recent ``window`` net_pnl values, newest exit first.

    Winners and losers both count. This is the expectancy sample, not the
    losing streak.
    """
    ordered = sorted(fills, key=lambda fill: (_as_utc(fill.exit_time), fill.trade_id), reverse=True)
    size = window if window > 0 else 0
    return [float(fill.net_pnl) for fill in ordered[:size]]


def _expectancy(nets: Sequence[float]) -> tuple[float | None, float | None]:
    """Mean net_pnl and win rate. A win is ``net_pnl > 0``. Empty is unknown."""
    n = len(nets)
    if n == 0:
        return None, None
    expectancy = sum(nets) / n
    win_rate = sum(1 for value in nets if value > 0) / n
    return expectancy, win_rate


def _effective_streak(losses: Sequence[ClosedFill], *, cluster: bool) -> int:
    if cluster:
        return cluster_loss_streak(losses)
    return len(losses)


def build_probation_book(
    fills: Sequence[ClosedFill],
    open_positions: Sequence[Any],
    *,
    block_at: int | None = None,
    window: int | None = None,
    cluster: bool | None = None,
) -> dict[str, dict[str, Any]]:
    """Per-strategy streak, rolling nets, and whether a trial is already open.

    Derived from closed trades plus the open rows. Nothing is cached in the
    process, so a restart sees the same book. ``cluster`` selects which
    streak decides that an open row was itself a trial. Both the raw count
    and the clustered count are always stored.
    """
    settings = get_settings()
    if block_at is None:
        block_at = int(settings.strategy_loss_block)
    if window is None:
        window = int(settings.strategy_expectancy_window)
    if cluster is None:
        cluster = bool(settings.loss_streak_cluster_overlapping)

    grouped: dict[str, list[ClosedFill]] = {}
    for fill in fills:
        grouped.setdefault(strategy_key(fill.strategy, fill.side), []).append(fill)

    open_by_key: dict[str, list[Any]] = {}
    for position in open_positions:
        key = strategy_key(
            str(getattr(position, "strategy", "") or ""),
            str(getattr(position, "side", "") or ""),
        )
        if not key:
            continue
        open_by_key.setdefault(key, []).append(position)

    book: dict[str, dict[str, Any]] = {}
    for key in set(grouped) | set(open_by_key):
        trades = grouped.get(key, [])
        losses = trailing_losses(trades)
        raw = len(losses)
        clustered = cluster_loss_streak(losses)
        nets = rolling_nets(trades, window)
        trial_open = _trial_open(
            trades,
            open_by_key.get(key, []),
            block_at=block_at,
            cluster=cluster,
        )
        book[key] = {
            "raw_streak": raw,
            "clustered_streak": clustered,
            "nets": nets,
            "trial_open": trial_open,
        }
    return book


def _trial_open(
    trades: Sequence[ClosedFill],
    positions: Sequence[Any],
    *,
    block_at: int,
    cluster: bool,
) -> bool:
    """True when an open row was entered while this strategy was already blocked.

    The streak at entry is the trailing losses whose exit is at or before
    ``opened_at``. A position opened before the streak reached the block is
    not a trial, so it does not consume the one trial slot.
    """
    for position in positions:
        opened = getattr(position, "opened_at", None)
        if opened is None:
            # No clock on the row. If the strategy is blocked now, hold the
            # slot rather than stacking a second trial.
            current = _effective_streak(trailing_losses(trades), cluster=cluster)
            if current >= block_at:
                return True
            continue
        as_of = _as_utc(opened)
        prior = [
            trade
            for trade in trades
            if trade.exit_time is not None and _as_utc(trade.exit_time) <= as_of
        ]
        then = _effective_streak(trailing_losses(prior), cluster=cluster)
        if then >= block_at:
            return True
    return False


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.6g}"


def judge_entry(
    *,
    strategy: str,
    side: str,
    global_streak: int,
    scrutiny_at: int,
    record: dict[str, Any] | None,
) -> ProbationDecision:
    """Decide normal, half, trial, or blocked for one strategy.

    The block is checked first. A positive rolling expectancy does not
    override it. Clustering, when enabled, changes only the streak compared
    to the block. Expectancy and the global streak are left as they are.
    """
    settings = get_settings()
    block_at = int(settings.strategy_loss_block)
    window = int(settings.strategy_expectancy_window)
    cluster = bool(settings.loss_streak_cluster_overlapping)
    key = strategy_key(strategy, side)

    raw = int(record.get("raw_streak", 0)) if record else 0
    clustered = int(record.get("clustered_streak", raw)) if record else 0
    streak = clustered if cluster else raw
    nets = list(record.get("nets", [])) if record else []
    if window >= 0:
        nets = nets[:window]
    n = len(nets)
    expectancy, win_rate = _expectancy(nets)
    trial_open = bool(record.get("trial_open")) if record else False
    scrutiny = global_streak >= scrutiny_at

    if streak >= block_at:
        if trial_open:
            action = ACTION_BLOCKED
            multiplier = 1.0
            reason = (
                f"{key} loss streak {streak} >= {block_at}; "
                "a trial is already open; blocked"
            )
        else:
            action = ACTION_TRIAL
            multiplier = 0.5
            reason = (
                f"{key} loss streak {streak} >= {block_at}; "
                "half-risk trial (one at a time)"
            )
    elif scrutiny:
        if n < STRATEGY_EXPECTANCY_MIN_TRADES or expectancy is None or expectancy < 0:
            action = ACTION_HALF
            multiplier = 0.5
            if n < STRATEGY_EXPECTANCY_MIN_TRADES:
                reason = (
                    f"{key} rolling sample n={n} < {STRATEGY_EXPECTANCY_MIN_TRADES}; "
                    "half size"
                )
            else:
                reason = (
                    f"{key} rolling expectancy {_fmt(expectancy)} < 0 "
                    f"over last {n} closes; half size"
                )
        else:
            action = ACTION_NORMAL
            multiplier = 1.0
            reason = (
                f"{key} rolling expectancy {_fmt(expectancy)} >= 0 "
                f"over last {n} closes; normal size"
            )
    else:
        action = ACTION_NORMAL
        multiplier = 1.0
        reason = ""

    journaled = scrutiny or action in (ACTION_BLOCKED, ACTION_TRIAL)
    return ProbationDecision(
        action=action,
        reason=reason,
        risk_multiplier=multiplier,
        journaled=journaled,
        strategy=key,
        raw_streak=raw,
        clustered_streak=clustered,
        streak=streak,
        rolling_expectancy=expectancy,
        win_rate=win_rate,
        n=n,
        global_streak=global_streak,
        scrutiny=scrutiny,
    )


def _journal_payload(decision: ProbationDecision) -> dict[str, Any]:
    return {
        "strategy": decision.strategy,
        "strategy_streak": decision.streak,
        "raw_streak": decision.raw_streak,
        "clustered_streak": decision.clustered_streak,
        "rolling_expectancy": decision.rolling_expectancy,
        "win_rate": decision.win_rate,
        "n": decision.n,
        "global_streak": decision.global_streak,
        "action": decision.action,
        "reason": decision.reason,
        "scrutiny": decision.scrutiny,
        "risk_multiplier": decision.risk_multiplier,
        "cluster_overlapping": bool(get_settings().loss_streak_cluster_overlapping),
    }


def record_probation_decision(intent: Any, state: Any, decision: ProbationDecision) -> None:
    """Log and journal one probation decision.

    ``RiskEngine.evaluate`` calls this for a half, trial, or scrutiny-normal
    decision only after the other gates have approved the order. A block is
    recorded as soon as it is decided, including when another gate also
    rejects the order, because that block is the reason the strategy cannot
    enter.
    """
    if not decision.journaled:
        return
    logger.info(
        "loss-streak probation: strategy=%s raw_streak=%s clustered_streak=%s "
        "streak=%s expectancy=%s win_rate=%s n=%s global_streak=%s action=%s reason=%s",
        decision.strategy,
        decision.raw_streak,
        decision.clustered_streak,
        decision.streak,
        _fmt(decision.rolling_expectancy),
        _fmt(decision.win_rate),
        decision.n,
        decision.global_streak,
        decision.action,
        decision.reason,
    )
    journal = getattr(state, "journal_risk_event", None)
    if callable(journal):
        journal(
            "loss_streak_probation",
            "warning" if decision.action in (ACTION_BLOCKED, ACTION_TRIAL, ACTION_HALF) else "info",
            symbol=str(getattr(intent, "symbol", "") or ""),
            detail=decision.reason,
            action_taken=decision.action,
            context=_journal_payload(decision),
        )


def apply_loss_streak_probation(intent: Any, state: Any, limits: Any) -> ProbationDecision | None:
    """Judge one entry. A block is logged and journaled here.

    Half, trial, and scrutiny-normal decisions are not journaled yet. The
    risk engine writes that row only when the order is actually approved, so
    a sector, gross, or duplicate rejection does not leave a probation row.
    Returns None when the flag is off or this process is not paper. Callers
    then keep today's path, including the global hard block.
    """
    if not loss_streak_probation_enabled():
        return None

    book = getattr(state, "probation_by_strategy", None) or {}
    record = book.get(
        strategy_key(getattr(intent, "strategy", ""), getattr(intent, "side", ""))
    ) if isinstance(book, dict) else None
    decision = judge_entry(
        strategy=getattr(intent, "strategy", ""),
        side=getattr(intent, "side", ""),
        global_streak=int(getattr(state, "consecutive_losses", 0) or 0),
        scrutiny_at=int(limits.max_consecutive_losses),
        record=record if isinstance(record, dict) else None,
    )
    if decision.action == ACTION_BLOCKED:
        record_probation_decision(intent, state, decision)
    return decision
