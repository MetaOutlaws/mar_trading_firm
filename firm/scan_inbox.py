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

from core.strategy.f111_semantics import (
    COMPRESSION_MIN_EXCLUSIVE,
    EXTENSION_MAX_INCLUSIVE,
    HIGH_VOL_MIN_INCLUSIVE,
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


def near_misses_from_rows(rows: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    """Closest rejects to a numeric gate, where the row actually carries one.

    Extension must be <= 1 prior ATR, compression must be above 0.50, and
    prior ATR / close must be at least 0.01. A pass is not a near miss.
    Rows without those numbers are skipped.
    """
    found: list[dict[str, Any]] = []
    for row in rows:
        if not _decision_row(row):
            continue
        reason = bucket_reason(row.get("rejection_reason"), row)
        features = _features(row)
        symbol = str(row.get("symbol") or "")
        side = str(row.get("side") or "")
        if reason == "extension_gate":
            value = _finite(features.get("extension_atr"))
            if value is None or value <= EXTENSION_MAX_INCLUSIVE:
                continue
            gap = value - EXTENSION_MAX_INCLUSIVE
            found.append(
                _miss(symbol, side, reason, "extension_atr", value, EXTENSION_MAX_INCLUSIVE, gap)
            )
        elif reason == "compression_gate":
            value = _finite(features.get("compression"))
            if value is None or value > COMPRESSION_MIN_EXCLUSIVE:
                continue
            gap = COMPRESSION_MIN_EXCLUSIVE - value
            found.append(
                _miss(
                    symbol,
                    side,
                    reason,
                    "compression",
                    value,
                    COMPRESSION_MIN_EXCLUSIVE,
                    gap,
                )
            )
        elif reason == "high_vol_filter":
            prior = _finite(features.get("prior_atr"))
            close = _finite(features.get("close"))
            if prior is None or close is None or close <= 0:
                continue
            value = prior / close
            if value >= HIGH_VOL_MIN_INCLUSIVE:
                continue
            gap = HIGH_VOL_MIN_INCLUSIVE - value
            found.append(
                _miss(symbol, side, reason, "prior_atr/close", value, HIGH_VOL_MIN_INCLUSIVE, gap)
            )
    found.sort(key=lambda item: (item["gap"], item["symbol"], item["side"], item["metric"]))
    return found[:limit]


def _miss(
    symbol: str,
    side: str,
    reason: str,
    metric: str,
    value: float,
    threshold: float,
    gap: float,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "side": side,
        "reason": reason,
        "metric": metric,
        "value": round(value, 6),
        "threshold": threshold,
        "gap": round(gap, 6),
    }


def _count_reason(counts: dict[str, int], reason: Any, row: dict[str, Any] | None = None) -> None:
    name = bucket_reason(reason, row)
    if not name:
        return
    counts[name] = counts.get(name, 0) + 1


def summarise_f111_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Reason counts, signals, and near misses from one hourly telemetry slice.

    Pure: no database and no exchange. Registry census rows are ignored.
    """
    all_misses = near_misses_from_rows(rows, limit=max(len(rows), 1))
    miss_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in all_misses:
        miss_by_key[(item["symbol"], item["side"], item["reason"])] = item
    counts: dict[str, int] = {}
    signals = 0
    entries = 0
    pending_opened = 0
    sleeve_rows: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not _decision_row(row):
            continue
        symbol = str(row.get("symbol") or "")
        side = str(row.get("side") or "")
        signal_id = str(row.get("source_signal_id") or "")
        sleeve_id = signal_id or f"{symbol}|{side}|{index}"
        # A fill row carries simulated_fill. A gate pass that only arms a
        # retest carries pending_retest_created_at and no fill.
        has_fill = row.get("simulated_fill") not in (None, "")
        has_pending = bool(row.get("pending_retest_created_at"))
        reason = bucket_reason(row.get("rejection_reason"), row)
        passed = row.get("gate_decision") is True and not reason
        if has_fill:
            entries += 1
        if has_pending:
            pending_opened += 1
            signals += 1
        elif passed and not has_fill:
            signals += 1
        rejection = "" if (passed or has_fill or has_pending) else reason
        if rejection:
            counts[rejection] = counts.get(rejection, 0) + 1
        miss = miss_by_key.get((symbol, side, reason))
        sleeve_rows.append(
            {
                "sleeve_id": sleeve_id,
                "signal": bool(has_pending or (passed and not has_fill)),
                "ordered": bool(has_fill),
                "pending": bool(has_pending),
                "rejection": rejection or (reason if not passed else ""),
                "near_miss": miss,
            }
        )
    top = sorted(
        (item for item in (row.get("near_miss") for row in sleeve_rows) if item),
        key=lambda item: (item["gap"], item["symbol"], item["side"], item["metric"]),
    )[:3]
    return {
        "f111_sleeves": len(sleeve_rows),
        "book_sleeves": 0,
        "signals": signals,
        "entries_opened": entries,
        "pending_retests_opened": pending_opened,
        "rejection_counts": counts,
        "near_misses": top,
        "sleeve_ids": [row["sleeve_id"] for row in sleeve_rows],
        "sleeve_rows": sleeve_rows,
    }


def summarise_sleeve_notes(notes: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts for one book or cycle pass, from the notes the evaluator kept.

    ``sleeve_id`` dedupes a sleeve that the next 15s poll sees again.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for note in notes:
        if not isinstance(note, dict):
            continue
        sleeve_id = str(note.get("sleeve_id") or "")
        if not sleeve_id:
            continue
        by_id[sleeve_id] = {
            "sleeve_id": sleeve_id,
            "signal": bool(note.get("signal")),
            "ordered": bool(note.get("ordered")),
            "rejection": bucket_reason(note.get("rejection")) if not note.get("ordered") else "",
            "near_miss": note.get("near_miss") if isinstance(note.get("near_miss"), dict) else None,
        }
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
        if isinstance(miss, dict) and _finite(miss.get("gap")) is not None:
            misses.append(miss)
    misses.sort(key=lambda item: (item.get("gap", 0), item.get("symbol", ""), item.get("side", "")))
    return {
        "signals": signals,
        "entries_opened": entries,
        "pending_retests_opened": pending_opened,
        "rejection_counts": counts,
        "near_misses": misses[:3],
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
    return (
        f"{item.get('symbol') or '—'} {item.get('side') or ''}".strip()
        + f" {item.get('metric')} {item.get('value')} vs {item.get('threshold')}"
        + f" (gap {item.get('gap')})"
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
        lines.append("Near misses: " + "; ".join(_format_near_miss(item) for item in near_misses) + ".")
    else:
        lines.append("Near misses: none.")
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
    )
    return all(payload.get(field) == rebuilt.get(field) for field in fields)


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
    text = format_summary_text(
        scan_type=scan_type,
        scan_time=scan_time,
        bar_time=bar,
        f111_sleeves=int(summary.get("f111_sleeves") or 0),
        book_sleeves=int(summary.get("book_sleeves") or 0),
        signals=int(summary.get("signals") or 0),
        entries_opened=int(summary.get("entries_opened") or 0),
        pending_retests=retests,
        rejection_counts=dict(summary.get("rejection_counts") or {}),
        near_misses=list(summary.get("near_misses") or []),
        soko=soko,
        pending_opened=int(summary.get("pending_retests_opened") or 0),
    )
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
                merged["summary"] = format_summary_text(
                    scan_type=str(merged.get("scan_type") or scan_type),
                    scan_time=scan_time,
                    bar_time=bar,
                    f111_sleeves=int(merged.get("f111_sleeves") or 0),
                    book_sleeves=int(merged.get("book_sleeves") or 0),
                    signals=int(merged.get("signals") or 0),
                    entries_opened=int(merged.get("entries_opened") or 0),
                    pending_retests=int(merged.get("pending_retests") or 0),
                    rejection_counts=dict(merged.get("rejection_counts") or {}),
                    near_misses=list(merged.get("near_misses") or []),
                    soko=soko or merged.get("soko"),
                    pending_opened=int(merged.get("pending_retests_opened") or 0),
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
    """Append one sleeve note. A bad note is logged and dropped."""
    try:
        notes.append(
            {
                "sleeve_id": str(fields.get("sleeve_id") or ""),
                "bar_time": fields.get("bar_time"),
                "signal": bool(fields.get("signal")),
                "ordered": bool(fields.get("ordered")),
                "rejection": str(fields.get("rejection") or ""),
            }
        )
    except Exception:
        logger.exception("Scan summary note failed; the evaluation stands")
