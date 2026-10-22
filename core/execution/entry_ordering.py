"""Greedy beta-neutralising (GBN) order for same-cycle entry candidates.

Paper only. The flag ``ENTRY_ORDERING_GBN`` defaults off. While it is off the
engine never calls :func:`execute_entry_ordering`, so candidates reach the risk
engine in plan order exactly as they do today.

The rule is the frozen spec (RULE_SPEC.md, sha256 a5dc258f…). Within one cycle,
repeat until no candidates remain:

1. Size each remaining candidate with the current deployed sizer against the
   current book. The sizer is not reimplemented here. It already reads
   ``RiskLimits.max_total_exposure_pct``. SGP1 paper has run 0.80 since
   13:22 GST on 2026-10-22 (PR #160, ``aa01e948``). Nothing here hardcodes
   that cap, or the previous 0.50 cap.
2. ``B_after(c) = B_now + beta_c * s_c * N_c``. ``B`` is beta-weighted net
   exposure in USDT. ``s`` is +1 LONG / -1 SHORT. ``N_c`` is the sizer notional.
   Open positions contribute entry notional (``quantity * entry_price``), which
   is what the spec calls ``N_i``. The sizer's own gross room still uses the
   mark notional already on ``PortfolioState``; this module does not change that.
3. Send the candidate with the smallest ``|B_after|`` to the risk engine.
   Values equal to the cent (USDT, two decimal places) tie. The higher
   ``signal_score`` wins; a missing or non-finite score ranks below every
   scored candidate; the remaining tie is plan order.
4. Remove that candidate whether the risk engine approves or rejects it.
   The book updates only when the fill actually lands, because the next round
   re-reads the ledger.

Beta is the 30-day daily OLS beta of the symbol's log returns on BTCUSDT.
Closes are strictly before the cycle's UTC day. Up to 30 paired returns
(31 closes) are used. BTCUSDT is 1.0 and is not estimated.

Fail-safe (the conservative one): if any open position with non-zero entry
notional, or any candidate the sizer would give a non-zero notional, does not
have a beta — missing daily data, fewer than 20 paired daily returns, or a
BTC variance of zero — that whole cycle stays in plan order. A zero-notional
open leg, or a candidate sized to zero, does not need a beta and does not
force that fallback. Substituting 1.0 would still reorder the book on a
number we could not measure. Plan order is the deployed behaviour, so it is
the fallback. This is report-only: the candidate is still sent to the risk
engine, just not ahead of its plan-order neighbours.

If sizing, the beta lookup, or the book read raises while a cycle is being
ordered, the exception is logged and every candidate not yet submitted goes
in plan order. Names already sent to the risk engine in that cycle are not
sent again.

Daily closes are cached per ``(symbol, cycle UTC date)`` so a later cycle or
poll on the same day does not fetch them again.
"""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import pandas as pd

from config.settings import TradingMode, get_settings
from core.risk.engine import PortfolioState

logger = logging.getLogger(__name__)

#: Bybit linear BTC perpetual. Its beta is defined, not estimated.
BTC_SYMBOL = "BTCUSDT"

#: Paired daily log returns required before a beta is trusted.
MIN_DAILY_RETURNS = 20

#: "30-day" OLS: at most this many returns, from the last 31 paired closes.
MAX_DAILY_RETURNS = 30

#: Latest daily bars requested from the feed the paper engine already has.
#: One forming day plus 31 history, with room for gaps.
DAILY_LOOKBACK_BARS = 45

_warned_non_paper = False

#: Successful 1d frames, keyed by (symbol, cycle UTC date). Flag off never reads this.
_daily_close_cache: dict[tuple[str, date], Any] = {}
_daily_cache_lock = threading.Lock()


def clear_daily_beta_cache() -> None:
    """Drop cached daily closes. Tests use this so one case cannot feed the next."""
    with _daily_cache_lock:
        _daily_close_cache.clear()


def _fetch_daily_cached(
    fetch_daily: Callable[[str], Any], symbol: str, cycle_day: date
) -> Any:
    """Return the daily frame for ``symbol`` on ``cycle_day``, fetching at most once.

    The lock is held across the fetch so a cycle and a poll that start together
    share one Bybit read instead of both missing and both pulling.
    """
    key = (symbol, cycle_day)
    with _daily_cache_lock:
        cached = _daily_close_cache.get(key)
        if cached is not None:
            return cached
        frame = fetch_daily(symbol)
        _daily_close_cache[key] = frame
        return frame


def entry_ordering_gbn_enabled() -> bool:
    """True only when the flag is on and this process is paper.

    Live and testnet ignore the flag so a copied environment cannot reorder
    real orders. The default is off, which leaves plan order untouched.
    """
    global _warned_non_paper
    settings = get_settings()
    if not bool(settings.entry_ordering_gbn):
        return False
    if settings.trading_mode is not TradingMode.PAPER:
        if not _warned_non_paper:
            _warned_non_paper = True
            logger.warning(
                "ENTRY_ORDERING_GBN is set but trading mode is %s; "
                "GBN stays off (paper only, plan order).",
                settings.trading_mode.value,
            )
        return False
    return True


def cycle_day_utc(now: datetime) -> date:
    """UTC date of this cycle. Daily closes on this date are excluded."""
    if now.tzinfo is None:
        aware = now.replace(tzinfo=timezone.utc)
    else:
        aware = now.astimezone(timezone.utc)
    return aware.date()


def side_sign(side: str) -> int | None:
    """+1 LONG, -1 SHORT. Anything else cannot be signed."""
    label = str(side or "").upper()
    if label == "LONG":
        return 1
    if label == "SHORT":
        return -1
    return None


def finite_score(score: Any) -> float | None:
    """A recorded score, or None when the candidate is unscored.

    Zero is a score. None and non-finite values rank last, per the spec.
    """
    if score is None:
        return None
    try:
        value = float(score)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


@dataclass(frozen=True)
class BookLeg:
    """One open position as GBN adds it into B. ``entry_notional`` is positive."""

    symbol: str
    side: str
    entry_notional: float


@dataclass
class GbnCandidate:
    """One signal that would reach the risk engine this cycle, in plan order."""

    symbol: str
    side: str
    score: float | None
    plan_index: int
    #: Caller payload (the signal and the plan row). The orderer does not read it.
    payload: Any = None


@dataclass(frozen=True)
class SubmitResult:
    """What the risk engine (or a pre-risk duplicate block) did with one candidate."""

    approved: bool
    reasons: str = ""


def legs_from_portfolio(state: PortfolioState) -> list[BookLeg]:
    """Entry-notional legs. Mark notional stays on the sizer's portfolio state.

    ``PortfolioState.notional`` is quantity times the mark. The spec's ``N_i``
    is entry notional, so B uses ``quantity * entry_price`` instead.
    """
    legs: list[BookLeg] = []
    for position in state.open_positions:
        try:
            notional = abs(float(position.quantity) * float(position.entry_price))
        except (TypeError, ValueError):
            notional = 0.0
        if not math.isfinite(notional):
            notional = 0.0
        legs.append(
            BookLeg(
                symbol=str(position.symbol),
                side=str(position.side),
                entry_notional=notional,
            )
        )
    return legs


def closes_from_frame(frame: Any) -> pd.Series:
    """Close column from a candle frame. Empty when the feed returned nothing."""
    if isinstance(frame, pd.Series):
        return frame
    if frame is None or bool(getattr(frame, "empty", True)):
        return pd.Series(dtype="float64")
    columns = getattr(frame, "columns", [])
    if "close" not in columns:
        return pd.Series(dtype="float64")
    return frame["close"]


def _closes_before(series: pd.Series, cycle_day: date) -> dict[date, float]:
    """Positive closes whose bar date is strictly before ``cycle_day``."""
    found: dict[date, float] = {}
    if series is None or len(series) == 0:
        return found
    for ts, raw in series.items():
        stamp = pd.Timestamp(ts)
        if stamp.tzinfo is None:
            stamp = stamp.tz_localize("UTC")
        else:
            stamp = stamp.tz_convert("UTC")
        day = stamp.date()
        if day >= cycle_day:
            continue
        try:
            price = float(raw)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(price) or price <= 0.0:
            continue
        found[day] = price
    return found


def ols_beta_to_btc(
    symbol_closes: pd.Series,
    btc_closes: pd.Series,
    cycle_day: date,
) -> tuple[float | None, str]:
    """OLS beta of daily log returns on BTC, or ``(None, reason)``.

    The window is the last 31 paired closes strictly before ``cycle_day``
    (30 returns), matching the frozen replay. A shorter overlap is used when
    that is all the feed has, down to 20 returns (21 closes). Below that the
    beta is not computed.
    """
    symbol = _closes_before(symbol_closes, cycle_day)
    btc = _closes_before(btc_closes, cycle_day)
    days = sorted(set(symbol) & set(btc))
    # 31 closes → 30 returns. Take the most recent window only.
    days = days[-(MAX_DAILY_RETURNS + 1) :]
    if len(days) < MIN_DAILY_RETURNS + 1:
        return None, (
            f"fewer than {MIN_DAILY_RETURNS} paired daily returns "
            f"({max(0, len(days) - 1)} before {cycle_day.isoformat()})"
        )
    asset = [math.log(symbol[days[i]] / symbol[days[i - 1]]) for i in range(1, len(days))]
    market = [math.log(btc[days[i]] / btc[days[i - 1]]) for i in range(1, len(days))]
    mean_asset = sum(asset) / len(asset)
    mean_market = sum(market) / len(market)
    variance = sum((point - mean_market) ** 2 for point in market)
    if not math.isfinite(variance) or variance <= 0.0:
        return None, "BTC daily variance is zero"
    covariance = sum(
        (left - mean_asset) * (right - mean_market) for left, right in zip(asset, market)
    )
    beta = covariance / variance
    if not math.isfinite(beta):
        return None, "non-finite beta"
    return beta, ""


def load_betas(
    fetch_daily: Callable[[str], Any],
    symbols: set[str],
    cycle_day: date,
) -> tuple[dict[str, float], dict[str, str]]:
    """Betas for ``symbols`` using daily closes the caller already knows how to fetch.

    ``fetch_daily`` is ``engine._data.fetch_latest(symbol, "1d", bars=...)``.
    A successful frame is reused for every later call with the same symbol and
    the same cycle UTC date. The next UTC date fetches again. BTCUSDT is 1.0
    and is still fetched when another symbol needs a market leg. Failures are
    names, not exceptions: the cycle falls back to plan order. A failed fetch
    is not cached, so a later cycle the same day can try once more.
    """
    betas: dict[str, float] = {}
    failures: dict[str, str] = {}
    needed = {symbol for symbol in symbols if symbol}
    if BTC_SYMBOL in needed:
        betas[BTC_SYMBOL] = 1.0
        needed.discard(BTC_SYMBOL)
    if not needed:
        return betas, failures

    def fetch(symbol: str) -> Any:
        return _fetch_daily_cached(fetch_daily, symbol, cycle_day)

    try:
        btc_closes = closes_from_frame(fetch(BTC_SYMBOL))
    except Exception as exc:
        reason = f"BTC daily closes unavailable ({exc})"
        for symbol in sorted(needed):
            failures[symbol] = reason
        return betas, failures
    for symbol in sorted(needed):
        try:
            frame = fetch(symbol)
        except Exception as exc:
            failures[symbol] = f"daily closes unavailable ({exc})"
            continue
        beta, reason = ols_beta_to_btc(closes_from_frame(frame), btc_closes, cycle_day)
        if beta is None:
            failures[symbol] = reason
        else:
            betas[symbol] = beta
    return betas, failures


def book_beta_usdt(legs: Sequence[BookLeg], betas: Mapping[str, float]) -> float:
    """``B = sum beta * s * entry_notional``. Zero-notional legs add nothing."""
    total = 0.0
    for leg in legs:
        notional = float(leg.entry_notional)
        if notional == 0.0 or not math.isfinite(notional):
            continue
        sign = side_sign(leg.side)
        if sign is None:
            raise ValueError(f"open position {leg.symbol} has side {leg.side!r}")
        total += float(betas[leg.symbol]) * sign * notional
    return total


def _usable_notional(raw: float) -> float:
    """Sizer output GBN can multiply. Negative and non-finite values count as zero."""
    try:
        notional = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(notional) or notional < 0.0:
        return 0.0
    return notional


def _blockers(
    candidates: Sequence[GbnCandidate],
    legs: Sequence[BookLeg],
    betas: Mapping[str, float],
    failures: Mapping[str, str],
    size_notional: Callable[[GbnCandidate], float],
) -> dict[str, str]:
    """Why this cycle must not reorder. Empty means every required beta exists.

    A beta-load failure counts only for a leg with non-zero entry notional, or
    for a candidate the sizer would give a non-zero notional. Zero-size names
    do not move ``B`` and do not force plan order. The book is checked first so
    a missing open-leg beta does not size the candidates.
    """
    blockers: dict[str, str] = {}
    for leg in legs:
        try:
            notional = float(leg.entry_notional)
        except (TypeError, ValueError):
            notional = 0.0
        if not math.isfinite(notional) or notional == 0.0:
            continue
        if side_sign(leg.side) is None:
            blockers[leg.symbol] = f"invalid side {leg.side!r}"
        elif leg.symbol not in betas:
            blockers[leg.symbol] = failures.get(leg.symbol) or "beta unavailable"
    if blockers:
        return blockers
    for candidate in candidates:
        if side_sign(candidate.side) is None:
            blockers[candidate.symbol] = f"invalid side {candidate.side!r}"
            continue
        if candidate.symbol in betas:
            continue
        if _usable_notional(size_notional(candidate)) == 0.0:
            continue
        blockers[candidate.symbol] = failures.get(candidate.symbol) or "beta unavailable"
    return blockers


def _candidate_text(candidates: Sequence[GbnCandidate]) -> str:
    parts = []
    for candidate in sorted(candidates, key=lambda item: (item.plan_index, item.symbol)):
        score = "none" if candidate.score is None else f"{candidate.score:.6g}"
        parts.append(
            f"{candidate.plan_index}:{candidate.symbol}:{candidate.side}:score={score}"
        )
    return ",".join(parts)


def _fmt(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "na"
    return f"{value:.2f}"


def execute_entry_ordering(
    candidates: list[GbnCandidate],
    *,
    enabled: bool,
    betas: Mapping[str, float],
    beta_failures: Mapping[str, str],
    book_legs: Callable[[], list[BookLeg]],
    size_notional: Callable[[GbnCandidate], float],
    submit: Callable[[GbnCandidate], SubmitResult],
    cycle_day: date,
    gross_cap: float | None = None,
) -> str:
    """Submit ``candidates`` in GBN order, or in plan order when GBN cannot run.

    ``enabled=False`` submits in plan order and does not size, read betas, or
    log. Callers that want today's behaviour should not call this at all; the
    flag-off engine path does not. The branch is here so tests can show the
    function itself does not reorder when disabled.

    An exception from sizing, the beta lookup, or the book read logs and
    switches the rest of the cycle to plan order. Candidates already submitted
    stay submitted.

    Returns ``plan``, ``plan_fallback``, ``gbn``, or ``empty``.
    """
    if not candidates:
        return "empty"
    plan = sorted(candidates, key=lambda item: (item.plan_index, item.symbol))
    if not enabled:
        for candidate in plan:
            submit(candidate)
        return "plan"

    try:
        legs = list(book_legs())
        blockers = _blockers(plan, legs, betas, beta_failures, size_notional)
    except Exception:
        logger.exception(
            "GBN could not read the book or size a candidate; this cycle stays in plan order"
        )
        blockers = {"*": "book or size unreadable"}
    use_gbn = not blockers
    mode = "gbn" if use_gbn else "plan_fallback"
    fallback = "-" if use_gbn else "; ".join(f"{name}: {why}" for name, why in sorted(blockers.items()))
    cap_text = "na" if gross_cap is None else f"{float(gross_cap):.2f}"
    shadow = _candidate_text(plan)
    logger.info(
        "GBN cycle mode=%s day=%s gross_cap=%s candidate_set=%s "
        "shadow_plan_order=%s fallback=%s",
        mode,
        cycle_day.isoformat(),
        cap_text,
        shadow,
        shadow,
        fallback,
    )

    remaining = list(plan)
    rank = 0
    while remaining:
        rank += 1
        chosen_notional: float | None = None
        chosen_beta: float | None = None
        b_before: float | None = None
        b_after_pred: float | None = None
        chosen: GbnCandidate | None = None
        if use_gbn:
            try:
                current = list(book_legs())
                b_before = float(book_beta_usdt(current, betas))
                # Bind the book for this round. Later rounds read the ledger again.
                b_now = b_before

                def sort_key(
                    candidate: GbnCandidate, b_now: float = b_now
                ) -> tuple[float, int, float, int]:
                    sign = side_sign(candidate.side)
                    if sign is None:
                        return (float("inf"), 1, 0.0, candidate.plan_index)
                    notional = _usable_notional(size_notional(candidate))
                    # A zero-size name does not need a beta: it cannot move B.
                    if notional == 0.0:
                        after = b_now
                    else:
                        after = b_now + float(betas[candidate.symbol]) * sign * notional
                    # Equal to the cent. Higher score sorts first; unscored last.
                    scored = candidate.score is not None
                    return (
                        round(abs(after), 2),
                        0 if scored else 1,
                        -(candidate.score if scored else 0.0),
                        candidate.plan_index,
                    )

                # ``sorted`` leaves ``remaining`` untouched when the key raises,
                # so a failed preview cannot drop a name or freeze a half-sort.
                ordered = sorted(remaining, key=sort_key)
                picked = ordered[0]
                sign = side_sign(picked.side)
                if sign is None:
                    raise ValueError(f"candidate {picked.symbol} has side {picked.side!r}")
                chosen_notional = _usable_notional(size_notional(picked))
                if chosen_notional == 0.0:
                    chosen_beta = (
                        float(betas[picked.symbol]) if picked.symbol in betas else None
                    )
                    b_after_pred = b_before
                else:
                    chosen_beta = float(betas[picked.symbol])
                    b_after_pred = b_before + chosen_beta * sign * chosen_notional
                chosen = picked
                remaining = ordered[1:]
            except Exception:
                logger.exception(
                    "GBN sizing or beta failed; candidates not yet sent go in plan order"
                )
                use_gbn = False
                mode = "plan_fallback"
                chosen = None
                chosen_notional = None
                chosen_beta = None
                b_before = None
                b_after_pred = None
        if chosen is None:
            remaining.sort(key=lambda item: (item.plan_index, item.symbol))
            chosen = remaining.pop(0)
        result = submit(chosen)
        b_after: float | None = None
        if use_gbn:
            try:
                b_after = book_beta_usdt(list(book_legs()), betas)
            except Exception:
                logger.exception(
                    "GBN could not read B after submitting %s; "
                    "the rest of this cycle stays in plan order",
                    chosen.symbol,
                )
                use_gbn = False
                mode = "plan_fallback"
        score_text = "none" if chosen.score is None else f"{chosen.score:.6g}"
        logger.info(
            "GBN decision rank=%d symbol=%s side=%s score=%s plan_index=%d "
            "notional=%s beta=%s B_before=%s abs_B_before=%s "
            "B_after_pred=%s abs_B_after_pred=%s B_after=%s abs_B_after=%s "
            "approved=%s reasons=%s",
            rank,
            chosen.symbol,
            chosen.side,
            score_text,
            chosen.plan_index,
            _fmt(chosen_notional),
            _fmt(chosen_beta) if chosen_beta is not None else "na",
            _fmt(b_before),
            _fmt(abs(b_before) if b_before is not None else None),
            _fmt(b_after_pred),
            _fmt(abs(b_after_pred) if b_after_pred is not None else None),
            _fmt(b_after),
            _fmt(abs(b_after) if b_after is not None else None),
            str(bool(result.approved)).lower(),
            result.reasons or "-",
        )
    return mode
