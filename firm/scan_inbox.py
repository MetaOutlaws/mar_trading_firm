"""Per-scan Inbox summaries from the paper worker.

One informational row after an F111 hourly bar-close pass, and one after a
book bar-close pass (the #112 poll, or the 900s cycle when that poll is not
the path that evaluated the bar). No model call. No PC. The row is a diary:

* kind ``informational`` — the Inbox does not draw approve or reject
* payload has no ``action``, so continuity and the research pipeline ignore it
* deduped on scan type + bar time, so a 15s poll that finishes a bar in two
  slices updates the same row
* at most four new rows per UTC hour; a further pass is merged into the
  newest row of that hour
* TTL is two hours. Listing the Inbox expires and deletes them, reusing the
  #113 pattern (pending → expired, decided by expiry) and then pruning the
  row so the table does not fill up

A failure here is logged and swallowed by the caller. It must not change a
signal, a gate, a risk decision, or the book.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from core.strategy.f111_config import STRATEGY_ID as F111_STRATEGY_ID
from core.strategy.gate_distance import (
    NEAREST_CARD,
    closest_failure,
    f111_checklist,
    normalize_hook,
    rank_misses,
)
from firm.memory_models import ProposalKind, ProposalStatus

logger = logging.getLogger(__name__)

SCAN_SUMMARY_TTL = timedelta(hours=2)
HOURLY_CAP = 4
SCAN_AGENT = "paper_worker"
GST = timezone(timedelta(hours=4))

# Names the operator asked to see, in that order. Other reasons stay as
# their own keys so a new gate is not flattened into "other".
_PREFERRED_REASONS = (
    "base_signal_blocked",
    "high_vol_filter",
    "extension_gate",
    "compression_gate",
    "regime sit-out",
    "risk cap",
    "unavailable instrument",
    "latency/stale bar",
    "existing position",
)

_EXACT_REASONS = {
    "base_signal_blocked": "base_signal_blocked",
    "high_vol_filter": "high_vol_filter",
    "extension_gate": "extension_gate",
    "compression_gate": "compression_gate",
    "stale_signal_not_backfilled": "latency/stale bar",
    "missing_candle_or_quote": "latency/stale bar",
    "outside_latency_window": "latency/stale bar",
    "forming_bar": "latency/stale bar",
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _as_utc(value).replace(microsecond=0).isoformat()


def _parse_time(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _as_utc(parsed)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _hour_key(moment: datetime) -> str:
    return _as_utc(moment).strftime("%Y-%m-%dT%H")


def _clock_labels(moment: datetime) -> tuple[str, str]:
    """Scan clock in UTC and in GST (UTC+4)."""
    utc = _as_utc(moment)
    gst = utc.astimezone(GST)
    return utc.strftime("%Y-%m-%d %H:%M UTC"), gst.strftime("%Y-%m-%d %H:%M GST")


def _age_phrase(seconds: Any) -> str:
    try:
        whole = int(seconds)
    except (TypeError, ValueError):
        return "age unknown"
    if whole < 0:
        whole = 0
    hours, rem = divmod(whole, 3600)
    minutes = rem // 60
    if hours:
        return f"age {hours}h {minutes}m"
    return f"age {minutes}m"


def bucket_reason(reason: Any, row: dict[str, Any] | None = None) -> str:
    """Map a raw rejection onto the operator's reason list.

    An empty reason is not a rejection (a pass, or a flat with no name).
    """
    row = row or {}
    if row.get("instrument_unavailable"):
        return "unavailable instrument"
    text = str(reason or "").strip()
    if not text or text.lower() in {"none", "null", "signal"}:
        return ""
    if text in _EXACT_REASONS:
        return _EXACT_REASONS[text]
    low = text.lower()
    if "regime sit-out" in low or "sit-out" in low or "sit_out" in low:
        return "regime sit-out"
    if any(
        token in low
        for token in (
            "stale",
            "latency",
            "outside_latency",
            "still forming",
            "forming_bar",
            "fetch failed",
            "no_history",
            "insufficient_history",
            "missing_candle",
            "candle_not_published",
        )
    ):
        return "latency/stale bar"
    if any(
        token in low
        for token in (
            "already holding",
            "duplicate open",
            "existing position",
            "position_already_open",
            "no pyramiding",
        )
    ):
        return "existing position"
    if any(
        token in low
        for token in (
            "open positions",
            "trades today",
            "exposure",
            "drawdown",
            "kill switch",
            "halted",
            "correlation risk",
            "risk cap",
            "max_concurrent",
        )
    ):
        return "risk cap"
    if "unavailable" in low or "missing from registry" in low:
        return "unavailable instrument"
    return text


def _features(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("feature_values")
    if isinstance(raw, dict):
        return raw
    raw = row.get("features")
    if isinstance(raw, dict):
        return raw
    return {}


def _decision_row(row: dict[str, Any]) -> bool:
    """Registry census and deploy markers are not sleeve decisions."""
    if not isinstance(row, dict):
        return False
    if row.get("record_kind") == "registry" or row.get("deploy_marker"):
        return False
    return bool(row.get("symbol"))


# Signals that cleared the strategy gates and then stopped for a reason the
# operator can act on. The exact text is kept; this set is only the flag.
_ACTIONABLE_BUCKETS = frozenset(
    {"risk cap", "existing position", "regime sit-out", "latency/stale bar"}
)


def near_misses_from_rows(rows: list[dict[str, Any]], limit: int = NEAREST_CARD) -> list[dict[str, Any]]:
    """Closest rejects, ranked by gap / threshold, where the row has the number.

    A pass is not a near miss. A rejection with no measured distance is
    omitted here and still counted by reason.
    """
    card = assemble_scan_card(rows, strategy=F111_STRATEGY_ID)
    return rank_misses(card["near_misses"], limit=limit)


def _count_reason(counts: dict[str, int], reason: Any, row: dict[str, Any] | None = None) -> None:
    name = bucket_reason(reason, row)
    if not name:
        return
    counts[name] = counts.get(name, 0) + 1


def _identity_from_note(note: dict[str, Any]) -> tuple[str, str, str]:
    """Symbol, side, and strategy. Book ids are ``symbol|timeframe|side|name``."""
    symbol = str(note.get("symbol") or "")
    side = str(note.get("side") or "")
    strategy = str(note.get("strategy") or "")
    parts = [part for part in str(note.get("sleeve_id") or "").split("|") if part]
    if len(parts) >= 4:
        symbol = symbol or parts[0]
        side = side or parts[2]
        strategy = strategy or parts[3]
    elif parts:
        symbol = symbol or parts[0]
    return symbol, side, strategy


def _miss_view(
    reading: dict[str, Any],
    *,
    symbol: str,
    side: str,
    strategy: str,
    reason: str,
) -> dict[str, Any]:
    """Card row: who missed, which gate, and the distance in that gate's units."""
    condition = str(reading.get("condition") or reading.get("metric") or reading.get("gate") or "")
    return {
        "symbol": symbol,
        "side": side,
        "strategy": strategy,
        "gate": str(reading.get("gate") or condition),
        "condition": condition,
        "reason": reason,
        "metric": str(reading.get("metric") or condition),
        "value": reading.get("value"),
        "threshold": reading.get("threshold"),
        "gap": reading.get("gap"),
        "normalized": reading.get("normalized"),
        "units": str(reading.get("units") or ""),
    }


def _f111_sleeve(row: dict[str, Any], index: int) -> dict[str, Any]:
    """One F111 decision row, with distances that do not call ``gate_decision``."""
    symbol = str(row.get("symbol") or "")
    side = str(row.get("side") or "")
    signal_id = str(row.get("source_signal_id") or "")
    sleeve_id = signal_id or f"{symbol}|{side}|{index}"
    has_fill = row.get("simulated_fill") not in (None, "")
    has_pending = bool(row.get("pending_retest_created_at"))
    exact = str(row.get("rejection_reason") or "").strip()
    if exact.lower() in {"none", "null"}:
        exact = ""
    reason = bucket_reason(exact, row)
    gates_passed = row.get("gate_decision") is True
    passed_clean = gates_passed and not reason
    features = _features(row)
    base_blocked = reason == "base_signal_blocked" or str(features.get("f111_rejection_reason") or "") == "base_signal_blocked"
    # A later block (risk, occupancy, stale) can sit on a row whose parent
    # reason was cleared. Only force the base gate when that is the rejection.
    if reason and reason != "base_signal_blocked":
        base_blocked = str(features.get("f111_rejection_reason") or "") == "base_signal_blocked" and not gates_passed
    checklist = f111_checklist(features, side=side, base_blocked=base_blocked and not gates_passed)
    return _annotate_sleeve(
        sleeve_id=sleeve_id,
        symbol=symbol,
        side=side,
        strategy=str(row.get("strategy") or F111_STRATEGY_ID),
        signal=bool(has_pending or (passed_clean and not has_fill)),
        ordered=bool(has_fill),
        pending=bool(has_pending),
        rejection="" if (passed_clean or has_fill or has_pending) else reason,
        exact_reason=exact,
        gates_passed=gates_passed,
        checklist=checklist,
        full_checklist=True,
        stale=reason == "latency/stale bar" or bool(row.get("missing_candle_or_quote")),
        unavailable=reason == "unavailable instrument" or bool(row.get("instrument_unavailable")),
    )


def _book_sleeve(note: dict[str, Any]) -> dict[str, Any]:
    symbol, side, strategy = _identity_from_note(note)
    ordered = bool(note.get("ordered"))
    exact = "" if ordered else str(note.get("rejection") or "").strip()
    reason = "" if ordered else bucket_reason(exact)
    signal = bool(note.get("signal"))
    gates_passed = bool(note.get("gates_passed")) or signal or ordered
    readings, full = normalize_hook(note.get("diagnostics"))
    if not readings and isinstance(note.get("near_miss"), dict):
        readings = [note["near_miss"]]
        full = False
    return _annotate_sleeve(
        sleeve_id=str(note.get("sleeve_id") or ""),
        symbol=symbol,
        side=side,
        strategy=strategy,
        signal=signal,
        ordered=ordered,
        pending=bool(note.get("pending")),
        rejection=reason,
        exact_reason=exact,
        gates_passed=gates_passed,
        checklist=readings,
        full_checklist=full,
        stale=reason == "latency/stale bar",
        unavailable=reason == "unavailable instrument",
    )


def _annotate_sleeve(
    *,
    sleeve_id: str,
    symbol: str,
    side: str,
    strategy: str,
    signal: bool,
    ordered: bool,
    pending: bool,
    rejection: str,
    exact_reason: str,
    gates_passed: bool,
    checklist: list[dict[str, Any]],
    full_checklist: bool,
    stale: bool,
    unavailable: bool,
) -> dict[str, Any]:
    """Attach the closest miss, the all-but-one flag, and an actionable block."""
    failed = [row for row in checklist if isinstance(row, dict) and row.get("passed") is False]
    scored = [row for row in checklist if isinstance(row, dict) and row.get("passed") is not None]
    closest = closest_failure(failed)
    # The rejecting gate, when we measured it. Otherwise the closest failure
    # the hook could name. No number means the card keeps the reason only.
    named = None
    if rejection:
        named = next((row for row in failed if str(row.get("gate") or "") == rejection), None)
        if named is None:
            named = next((row for row in failed if str(row.get("condition") or "") == rejection), None)
    chosen = named if named is not None and _finite(named.get("normalized")) is not None else closest
    miss = None
    if chosen is not None and not ordered and not signal:
        miss = _miss_view(chosen, symbol=symbol, side=side, strategy=strategy, reason=rejection or str(chosen.get("gate") or ""))
    all_but_one = None
    if full_checklist and not ordered and not gates_passed and len(scored) >= 2 and len(failed) == 1:
        shown = miss or _miss_view(
            failed[0],
            symbol=symbol,
            side=side,
            strategy=strategy,
            reason=rejection or str(failed[0].get("gate") or ""),
        )
        all_but_one = shown
    blocked = None
    if gates_passed and not ordered and rejection in _ACTIONABLE_BUCKETS:
        blocked = {
            "symbol": symbol,
            "side": side,
            "strategy": strategy,
            "reason": exact_reason or rejection,
            "bucket": rejection,
            "actionable": True,
        }
    return {
        "sleeve_id": sleeve_id,
        "symbol": symbol,
        "side": side,
        "strategy": strategy,
        "signal": signal,
        "ordered": ordered,
        "pending": pending,
        "rejection": rejection,
        "exact_reason": exact_reason,
        "gates_passed": gates_passed,
        "near_miss": miss,
        "all_but_one": all_but_one,
        "blocked_after_gates": blocked,
        "stale_bar": stale,
        "unavailable_instrument": unavailable,
    }


def assemble_scan_card(rows: list[dict[str, Any]], *, strategy: str = "") -> dict[str, Any]:
    """Card fields from F111 telemetry rows. Pure: no database and no gate call."""
    sleeve_rows = [
        _f111_sleeve(row, index)
        for index, row in enumerate(rows)
        if _decision_row(row)
    ]
    if strategy:
        for row in sleeve_rows:
            row["strategy"] = row.get("strategy") or strategy
    return _tally_sleeve_rows(sleeve_rows, book_sleeves=0, f111_sleeves=len(sleeve_rows))


def summarise_f111_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reason counts, distances, and the all-but-one list from one hourly slice.

    Pure: no database and no exchange. Registry census rows are ignored.
    """
    return assemble_scan_card(list(rows or []), strategy=F111_STRATEGY_ID)


def summarise_sleeve_notes(notes: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts for one book or cycle pass, from the notes the evaluator kept.

    ``sleeve_id`` dedupes a sleeve that the next 15s poll sees again.
    A strategy that returned no diagnostic falls back to the reason text.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for note in notes:
        if not isinstance(note, dict):
            continue
        sleeve_id = str(note.get("sleeve_id") or "")
        if not sleeve_id:
            continue
        by_id[sleeve_id] = _book_sleeve(note)
    return _tally_sleeve_rows(list(by_id.values()), book_sleeves=len(by_id), f111_sleeves=0)


def _tally_sleeve_rows(
    sleeve_rows: list[dict[str, Any]],
    *,
    book_sleeves: int,
    f111_sleeves: int,
) -> dict[str, Any]:
    """Recount a deduped sleeve list. The same id never contributes twice."""
    counts: dict[str, int] = {}
    signals = 0
    entries = 0
    pending_opened = 0
    misses: list[dict[str, Any]] = []
    all_but_one: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    stale: list[str] = []
    unavailable: list[str] = []
    for row in sleeve_rows:
        if row.get("signal"):
            signals += 1
        if row.get("ordered"):
            entries += 1
        if row.get("pending"):
            pending_opened += 1
        rejection = str(row.get("rejection") or "")
        if rejection and not row.get("ordered"):
            counts[rejection] = counts.get(rejection, 0) + 1
        miss = row.get("near_miss")
        if isinstance(miss, dict) and _finite(miss.get("normalized")) is not None:
            misses.append(miss)
        one = row.get("all_but_one")
        if isinstance(one, dict):
            all_but_one.append(one)
        block = row.get("blocked_after_gates")
        if isinstance(block, dict):
            blocked.append(block)
        label = " ".join(part for part in (str(row.get("symbol") or ""), str(row.get("side") or "")) if part).strip()
        if row.get("stale_bar"):
            stale.append(label or str(row.get("sleeve_id") or ""))
        if row.get("unavailable_instrument"):
            unavailable.append(label or str(row.get("sleeve_id") or ""))
    ranked = rank_misses(misses, limit=NEAREST_CARD)
    all_but_one.sort(key=lambda item: (str(item.get("symbol") or ""), str(item.get("side") or "")))
    blocked.sort(key=lambda item: (str(item.get("symbol") or ""), str(item.get("bucket") or "")))
    return {
        "signals": signals,
        "entries_opened": entries,
        "pending_retests_opened": pending_opened,
        "rejection_counts": counts,
        "near_misses": ranked,
        "all_but_one": {"count": len(all_but_one), "sleeves": all_but_one},
        "blocked_after_gates": blocked,
        "freshness": {
            "stale_bar": len(stale),
            "unavailable_instrument": len(unavailable),
            "stale_symbols": stale[:10],
            "unavailable_symbols": unavailable[:10],
        },
        "sleeve_ids": [str(row.get("sleeve_id") or "") for row in sleeve_rows],
        "sleeve_rows": sleeve_rows,
        "book_sleeves": book_sleeves,
        "f111_sleeves": f111_sleeves,
    }


def _ordered_counts(counts: dict[str, int]) -> list[tuple[str, int]]:
    preferred = [(name, counts[name]) for name in _PREFERRED_REASONS if counts.get(name)]
    rest = sorted(
        (name, value) for name, value in counts.items() if name not in _PREFERRED_REASONS and value
    )
    return preferred + rest


def _format_near_miss(item: dict[str, Any]) -> str:
    who = f"{item.get('symbol') or '—'} {item.get('side') or ''}".strip()
    strategy = str(item.get("strategy") or "").strip()
    gate = str(item.get("condition") or item.get("gate") or item.get("metric") or "")
    head = f"{who} {strategy} {gate}".strip()
    return (
        f"{head} value {item.get('value')} vs {item.get('threshold')}"
        + f" (gap {item.get('gap')}, {item.get('normalized')} of the threshold)"
    )


def _format_all_but_one(card: dict[str, Any] | None) -> str:
    if not isinstance(card, dict) or not card.get("count"):
        return "Passed all but one gate: none."
    sleeves = card.get("sleeves") if isinstance(card.get("sleeves"), list) else []
    shown = []
    for item in sleeves[:10]:
        if not isinstance(item, dict):
            continue
        who = f"{item.get('symbol') or '—'} {item.get('side') or ''}".strip()
        gate = item.get("condition") or item.get("gate") or ""
        shown.append(f"{who} {gate}".strip())
    extra = ""
    if len(sleeves) > 10:
        extra = f" (+{len(sleeves) - 10} more)"
    body = "; ".join(shown) if shown else "listed on the row"
    return f"Passed all but one gate: {int(card['count'])}. {body}{extra}."


def _format_blocked(rows: list[dict[str, Any]] | None) -> str:
    if not rows:
        return "Passed the gates, then blocked: none."
    parts = []
    for item in rows[:10]:
        who = f"{item.get('symbol') or '—'} {item.get('side') or ''}".strip()
        parts.append(f"{who} {item.get('bucket')}: {item.get('reason')} (actionable)")
    extra = f" (+{len(rows) - 10} more)" if len(rows) > 10 else ""
    return "Passed the gates, then blocked: " + "; ".join(parts) + extra + "."


def _format_freshness(freshness: dict[str, Any] | None) -> str:
    if not isinstance(freshness, dict):
        return "Freshness: stale bar 0, unavailable instrument 0."
    return (
        f"Freshness: stale bar {int(freshness.get('stale_bar') or 0)}, "
        f"unavailable instrument {int(freshness.get('unavailable_instrument') or 0)}."
    )


def _format_soko(soko: dict[str, Any] | None) -> str:
    if not isinstance(soko, dict):
        return "Soko: unavailable."
    label = soko.get("label")
    if not label:
        return "Soko: unavailable."
    return f"Soko: {label}, {_age_phrase(soko.get('age_seconds'))}."


def format_summary_text(
    *,
    scan_type: str,
    scan_time: datetime,
    bar_time: datetime,
    f111_sleeves: int,
    book_sleeves: int,
    signals: int,
    entries_opened: int,
    pending_retests: int,
    rejection_counts: dict[str, int],
    near_misses: list[dict[str, Any]],
    soko: dict[str, Any] | None,
    pending_opened: int | None = None,
    all_but_one: dict[str, Any] | None = None,
    blocked_after_gates: list[dict[str, Any]] | None = None,
    freshness: dict[str, Any] | None = None,
) -> str:
    """Plain-language body. The Inbox preview shows the first lines."""
    utc, gst = _clock_labels(scan_time)
    bar_utc, bar_gst = _clock_labels(bar_time)
    kind = {"f111": "F111", "book": "Book", "cycle": "Cycle"}.get(scan_type, scan_type)
    lines = [
        f"{kind} scan {utc} ({gst}). Bar {bar_utc} ({bar_gst}).",
        f"Sleeves evaluated: F111 {int(f111_sleeves)}, book {int(book_sleeves)}.",
        (
            f"Signals {int(signals)}, entries opened {int(entries_opened)}, "
            f"pending retests {int(pending_retests)}."
        ),
    ]
    if pending_opened is not None and int(pending_opened) != int(pending_retests):
        lines.append(f"Pending retests opened this pass: {int(pending_opened)}.")
    pairs = _ordered_counts(rejection_counts)
    if pairs:
        lines.append("Rejections: " + ", ".join(f"{name} {count}" for name, count in pairs) + ".")
    else:
        lines.append("Rejections: none.")
    if near_misses:
        lines.append(
            "Nearest misses: " + "; ".join(_format_near_miss(item) for item in near_misses) + "."
        )
    else:
        lines.append("Nearest misses: none with a measured distance.")
    lines.append(_format_all_but_one(all_but_one))
    lines.append(_format_blocked(blocked_after_gates))
    lines.append(_format_freshness(freshness))
    lines.append(_format_soko(soko))
    return "\n".join(lines)


def _title(scan_type: str, scan_time: datetime) -> str:
    utc, gst = _clock_labels(scan_time)
    kind = {"f111": "F111", "book": "Book", "cycle": "Cycle"}.get(scan_type, "Scan")
    return f"{kind} scan {utc} / {gst}"[:200]


def _read_soko(now: datetime) -> dict[str, Any]:
    """Same file the desk header reads. A failure leaves the label unknown."""
    try:
        from api.desk_status import soko_display

        shown = soko_display(now=now)
    except Exception:
        logger.exception("Soko label was not read for the scan summary")
        return {"label": None, "as_of": None, "age_seconds": None}
    return {
        "label": shown.get("label"),
        "as_of": shown.get("as_of"),
        "age_seconds": shown.get("age_seconds"),
    }


def _proposals_table_ready() -> bool:
    """False when this process has no firm schema yet (unit tests, a dry import).

    Missing schema is not a trading failure. The paper worker calls init_db
    before the loop, so a live paper process does write.
    """
    try:
        from sqlalchemy import inspect

        from config.settings import get_settings
        from core.db import get_engine

        url = get_settings().database_url
        if url.startswith("sqlite:///"):
            from pathlib import Path

            from config.settings import PROJECT_ROOT

            raw = url[len("sqlite:///") :]
            path = Path(raw)
            if not path.is_absolute():
                path = PROJECT_ROOT / path
            if not path.exists():
                return False
        return bool(inspect(get_engine()).has_table("proposals"))
    except Exception:
        logger.exception("Scan summary could not see the proposals table")
        return False


def expire_and_prune_scan_summaries(now: datetime | None = None) -> dict[str, int]:
    """Expire informational rows past their TTL, then delete them.

    The status flip matches ``expire_stale_proposals`` / the #113 escalation
    expiry (pending → expired, decided by expiry). The delete is what keeps
    the Inbox from filling up: a two-hour diary must not accumulate. Other
    proposal kinds are not touched.
    """
    if not _proposals_table_ready():
        return {"expired": 0, "pruned": 0}
    from sqlalchemy import select

    from core.db import session_scope
    from firm.memory_models import Proposal

    moment = _as_utc(now or datetime.now(timezone.utc))
    expired = 0
    pruned = 0
    with session_scope() as session:
        rows = session.scalars(
            select(Proposal).where(Proposal.kind == ProposalKind.INFORMATIONAL.value)
        ).all()
        for row in rows:
            past = False
            if row.expires_at is not None:
                past = _as_utc(row.expires_at) <= moment
            if row.status == ProposalStatus.PENDING.value and past:
                row.status = ProposalStatus.EXPIRED.value
                row.decided_by = "expiry"
                row.decided_at = moment
                row.decision_reason = "scan summary TTL elapsed"
                expired += 1
            if past or row.status == ProposalStatus.EXPIRED.value:
                session.delete(row)
                pruned += 1
    if pruned:
        logger.info("Pruned %s expired scan summaries (%s newly expired)", pruned, expired)
    return {"expired": expired, "pruned": pruned}


def _payload_keys(payload: dict[str, Any]) -> list[str]:
    keys = payload.get("dedupe_keys")
    if isinstance(keys, list):
        found = [str(item) for item in keys if item]
    else:
        found = []
    primary = str(payload.get("dedupe_key") or "")
    if primary and primary not in found:
        found.insert(0, primary)
    return found


def _blank_scan_payload(
    *,
    scan_type: str,
    bar_time: datetime,
    scan_time: datetime,
    summary: dict[str, Any],
    pending_retests: int,
    soko: dict[str, Any],
    text: str,
) -> dict[str, Any]:
    bar_iso = _iso(bar_time)
    key = f"{scan_type}|{bar_iso}"
    utc, gst = _clock_labels(scan_time)
    return {
        "informational": True,
        "scan_summary": True,
        "dedupe_key": key,
        "dedupe_keys": [key],
        "scan_type": scan_type,
        "bar_time": bar_iso,
        "scan_time_utc": utc,
        "scan_time_gst": gst,
        "hour": _hour_key(scan_time),
        "f111_sleeves": int(summary.get("f111_sleeves") or 0),
        "book_sleeves": int(summary.get("book_sleeves") or 0),
        "signals": int(summary.get("signals") or 0),
        "entries_opened": int(summary.get("entries_opened") or 0),
        "pending_retests": int(pending_retests),
        "pending_retests_opened": int(summary.get("pending_retests_opened") or 0),
        "rejection_counts": dict(summary.get("rejection_counts") or {}),
        "near_misses": list(summary.get("near_misses") or []),
        "all_but_one": summary.get("all_but_one") or {"count": 0, "sleeves": []},
        "blocked_after_gates": list(summary.get("blocked_after_gates") or []),
        "freshness": summary.get("freshness") or {
            "stale_bar": 0,
            "unavailable_instrument": 0,
            "stale_symbols": [],
            "unavailable_symbols": [],
        },
        "sleeve_ids": list(summary.get("sleeve_ids") or []),
        "sleeve_rows": list(summary.get("sleeve_rows") or []),
        "soko": soko,
        "summary": text,
        "merged_scans": [],
    }


def _merge_sleeve_summary(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Union sleeves by id and recount. A repeated poll does not double a reason."""
    by_id: dict[str, dict[str, Any]] = {}
    for source in (existing.get("sleeve_rows"), incoming.get("sleeve_rows")):
        if not isinstance(source, list):
            continue
        for row in source:
            if not isinstance(row, dict):
                continue
            sleeve_id = str(row.get("sleeve_id") or "")
            if sleeve_id:
                by_id[sleeve_id] = row
    if not by_id:
        return existing
    scan_type = str(existing.get("scan_type") or incoming.get("scan_type") or "")
    if scan_type == "f111":
        f111, book = len(by_id), 0
    else:
        f111, book = 0, len(by_id)
    tallied = _tally_sleeve_rows(list(by_id.values()), book_sleeves=book, f111_sleeves=f111)
    merged = dict(existing)
    merged.update(tallied)
    # F111 reports how many retests are still watching, not only how many
    # this slice opened. Keep the latest watching count when we have one.
    if scan_type == "f111" and incoming.get("pending_retests") is not None:
        merged["pending_retests"] = int(incoming["pending_retests"])
    return merged


def _same_body(payload: dict[str, Any], rebuilt: dict[str, Any]) -> bool:
    fields = (
        "f111_sleeves",
        "book_sleeves",
        "signals",
        "entries_opened",
        "pending_retests",
        "rejection_counts",
        "sleeve_ids",
        "near_misses",
        "all_but_one",
        "blocked_after_gates",
        "freshness",
    )
    return all(payload.get(field) == rebuilt.get(field) for field in fields)


def _summary_text(
    scan_type: str,
    scan_time: datetime,
    bar_time: datetime,
    summary: dict[str, Any],
    pending_retests: int,
    soko: dict[str, Any] | None,
) -> str:
    shown = soko if isinstance(soko, dict) else None
    return format_summary_text(
        scan_type=scan_type,
        scan_time=scan_time,
        bar_time=bar_time,
        f111_sleeves=int(summary.get("f111_sleeves") or 0),
        book_sleeves=int(summary.get("book_sleeves") or 0),
        signals=int(summary.get("signals") or 0),
        entries_opened=int(summary.get("entries_opened") or 0),
        pending_retests=int(pending_retests),
        rejection_counts=dict(summary.get("rejection_counts") or {}),
        near_misses=list(summary.get("near_misses") or []),
        soko=shown,
        pending_opened=int(summary.get("pending_retests_opened") or 0),
        all_but_one=summary.get("all_but_one") if isinstance(summary.get("all_but_one"), dict) else None,
        blocked_after_gates=list(summary.get("blocked_after_gates") or []),
        freshness=summary.get("freshness") if isinstance(summary.get("freshness"), dict) else None,
    )


def _record_near_misses(scan_type: str, bar_time: datetime, now: datetime, misses: list[dict[str, Any]]) -> None:
    """24h log. A failure is logged inside the writer and does not escape."""
    from firm.near_miss_log import append_near_misses

    append_near_misses(misses, scan_type=scan_type, bar_time=bar_time, now=now)


def publish_scan_summary(
    *,
    scan_type: str,
    bar_time: datetime,
    summary: dict[str, Any],
    now: datetime | None = None,
    pending_retests: int | None = None,
    soko: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert, refresh, or merge one informational Inbox row.

    ``now`` is the scan clock (UTC). Tests pass it so expiry does not depend
    on the wall clock. Returns ``{"action": ..., "id": ...}``.
    """
    if not _proposals_table_ready():
        return {"action": "skipped", "reason": "no_firm_db", "id": None}
    from sqlalchemy import select

    from core.db import session_scope
    from firm import memory
    from firm.memory_models import Proposal

    scan_time = _as_utc(now or datetime.now(timezone.utc))
    bar = _as_utc(bar_time)
    expire_and_prune_scan_summaries(scan_time)
    if soko is None:
        soko = _read_soko(scan_time)
    retests = (
        int(pending_retests)
        if pending_retests is not None
        else int(summary.get("pending_retests_opened") or 0)
    )
    summary = dict(summary)
    summary["pending_retests"] = retests
    text = _summary_text(scan_type, scan_time, bar, summary, retests, soko)
    payload = _blank_scan_payload(
        scan_type=scan_type,
        bar_time=bar,
        scan_time=scan_time,
        summary=summary,
        pending_retests=retests,
        soko=soko,
        text=text,
    )
    key = payload["dedupe_key"]
    hour = payload["hour"]
    _record_near_misses(scan_type, bar, scan_time, list(payload.get("near_misses") or []))

    with session_scope() as session:
        rows = session.scalars(
            select(Proposal)
            .where(Proposal.kind == ProposalKind.INFORMATIONAL.value)
            .where(Proposal.status == ProposalStatus.PENDING.value)
        ).all()
        match = None
        for row in rows:
            body = row.payload if isinstance(row.payload, dict) else {}
            if key in _payload_keys(body):
                match = row
                break
        if match is not None:
            body = dict(match.payload or {})
            if body.get("dedupe_key") == key:
                merged = _merge_sleeve_summary(dict(body), payload)
                merged["summary"] = _summary_text(
                    str(merged.get("scan_type") or scan_type),
                    scan_time,
                    bar,
                    merged,
                    int(merged.get("pending_retests") or 0),
                    soko if isinstance(soko, dict) else merged.get("soko"),
                )
                merged["soko"] = soko or merged.get("soko")
                if _same_body(body, merged):
                    return {"action": "unchanged", "id": int(match.id)}
                match.payload = merged
                match.rationale = str(merged["summary"])
                return {"action": "updated", "id": int(match.id)}
            # The key lives on a row that absorbed this pass because the hour
            # was already full. Refresh that merged section only.
            sections = [dict(item) for item in (body.get("merged_scans") or []) if isinstance(item, dict)]
            replaced = False
            for section in sections:
                if section.get("dedupe_key") == key:
                    section.update(payload)
                    section["summary"] = text
                    replaced = True
                    break
            if not replaced:
                sections.append(payload)
            body["merged_scans"] = sections
            body["dedupe_keys"] = _payload_keys(body)
            if key not in body["dedupe_keys"]:
                body["dedupe_keys"].append(key)
            match.payload = body
            match.rationale = _rationale_with_merged(str(body.get("summary") or match.rationale or ""), sections)
            return {"action": "updated", "id": int(match.id)}

        in_hour = []
        for row in rows:
            body = row.payload if isinstance(row.payload, dict) else {}
            if str(body.get("hour") or "") == hour:
                in_hour.append(row)
        if len(in_hour) >= HOURLY_CAP:
            host = max(in_hour, key=lambda row: (row.created_at or scan_time, int(row.id or 0)))
            body = dict(host.payload or {})
            sections = [dict(item) for item in (body.get("merged_scans") or []) if isinstance(item, dict)]
            sections.append(payload)
            keys = _payload_keys(body)
            if key not in keys:
                keys.append(key)
            body["dedupe_keys"] = keys
            body["merged_scans"] = sections
            host.payload = body
            host.rationale = _rationale_with_merged(str(body.get("summary") or host.rationale or ""), sections)
            title = str(host.title or "")
            if "more this hour" not in title:
                host.title = f"{title} (+more this hour)"[:200]
            logger.info("Scan summary merged into %s (hourly cap %s): %s", host.id, HOURLY_CAP, key)
            return {"action": "merged", "id": int(host.id)}

    pid = memory.record_proposal(
        agent=SCAN_AGENT,
        kind=ProposalKind.INFORMATIONAL,
        title=_title(scan_type, scan_time),
        payload=payload,
        rationale=text,
        confidence=0.0,
        ttl=SCAN_SUMMARY_TTL,
    )
    with session_scope() as session:
        row = session.get(Proposal, pid)
        if row is not None:
            # Anchor the TTL to the scan clock, not a second later from the
            # insert helper, so a test clock and the worker clock agree.
            row.expires_at = scan_time + SCAN_SUMMARY_TTL
    logger.info(
        "Scan summary %s %s f111=%s book=%s signals=%s entries=%s retests=%s",
        scan_type,
        _iso(bar),
        payload["f111_sleeves"],
        payload["book_sleeves"],
        payload["signals"],
        payload["entries_opened"],
        payload["pending_retests"],
    )
    return {"action": "inserted", "id": pid}


def _rationale_with_merged(primary: str, sections: list[dict[str, Any]]) -> str:
    extras = []
    for section in sections:
        text = str(section.get("summary") or "").strip()
        if text:
            extras.append(text)
    if not extras:
        return primary
    return primary.rstrip() + "\n\nAlso this hour:\n" + "\n---\n".join(extras)


def publish_f111_hourly(
    rows: list[dict[str, Any]],
    *,
    now: datetime,
    pending_retests: int | None = None,
    bar_time: datetime | None = None,
) -> dict[str, Any]:
    """One F111 row for the hourly bar that just closed."""
    scan_time = _as_utc(now)
    # The pass runs on the first poll after the hour. That boundary is the
    # close of the bar the sleeve just evaluated.
    closed = _as_utc(bar_time) if bar_time is not None else scan_time.replace(
        minute=0, second=0, microsecond=0
    )
    summary = summarise_f111_rows(list(rows or []))
    return publish_scan_summary(
        scan_type="f111",
        bar_time=closed,
        summary=summary,
        now=scan_time,
        pending_retests=pending_retests,
    )


def publish_book_notes(notes: list[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    """One book row per distinct bar close in this pass."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for note in notes or []:
        if not isinstance(note, dict):
            continue
        bar = _parse_time(note.get("bar_time"))
        if bar is None:
            continue
        grouped.setdefault(_iso(bar), []).append(note)
    results = []
    scan_time = _as_utc(now or datetime.now(timezone.utc))
    for bar_iso, group in grouped.items():
        bar = _parse_time(bar_iso)
        if bar is None:
            continue
        summary = summarise_sleeve_notes(group)
        results.append(
            publish_scan_summary(
                scan_type="book",
                bar_time=bar,
                summary=summary,
                now=scan_time,
            )
        )
    return results


def publish_cycle_notes(notes: list[dict[str, Any]], *, now: datetime | None = None) -> dict[str, Any] | None:
    """One cycle row when the 900s path evaluated sleeves the bar poll did not."""
    usable = [note for note in (notes or []) if isinstance(note, dict) and note.get("sleeve_id")]
    if not usable:
        return None
    scan_time = _as_utc(now or datetime.now(timezone.utc))
    summary = summarise_sleeve_notes(usable)
    summary["book_sleeves"] = 0
    summary["f111_sleeves"] = 0
    # Cycle sleeves are not the F111 book and not a single bar-close book.
    # Count them as book sleeves only when the note says so; the default
    # summarise marks them as book. A cycle pass is the book scan that did
    # not land on the #112 poll, so they stay on the book side of the line.
    summary["book_sleeves"] = len(summary.get("sleeve_ids") or [])
    return publish_scan_summary(
        scan_type="cycle",
        bar_time=scan_time.replace(microsecond=0),
        summary=summary,
        now=scan_time,
    )


def flush_scan_notes(
    book_notes: list[dict[str, Any]] | None,
    cycle_notes: list[dict[str, Any]] | None,
    *,
    now: datetime | None = None,
) -> None:
    """Write the cycle's notes. Never raises into the trading loop."""
    try:
        if book_notes:
            publish_book_notes(book_notes, now=now)
        if cycle_notes:
            publish_cycle_notes(cycle_notes, now=now)
    except Exception:
        logger.exception("Scan summary was not written; trading is unchanged")


def remember_scan_note(notes: list[dict[str, Any]], **fields: Any) -> None:
    """Append one sleeve note. A bad note is logged and dropped.

    ``diagnostics`` is the optional strategy hook. It is not a signal.
    """
    try:
        diagnostics = fields.get("diagnostics")
        notes.append(
            {
                "sleeve_id": str(fields.get("sleeve_id") or ""),
                "bar_time": fields.get("bar_time"),
                "signal": bool(fields.get("signal")),
                "ordered": bool(fields.get("ordered")),
                "rejection": str(fields.get("rejection") or ""),
                "symbol": str(fields.get("symbol") or ""),
                "side": str(fields.get("side") or ""),
                "strategy": str(fields.get("strategy") or ""),
                "gates_passed": bool(fields.get("gates_passed")),
                "diagnostics": diagnostics if isinstance(diagnostics, list) else None,
            }
        )
    except Exception:
        logger.exception("Scan summary note failed; the evaluation stands")
