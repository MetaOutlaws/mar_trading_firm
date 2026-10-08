"""Live Soko trend label for paper regime sit-outs.

The desk does not yet have a dedicated Soko client in-repo. This module is the
injectable hook:

1. ``data/last_soko_trend.json`` (same pattern as Luke's last_sentiment.json)
2. Else the latest regime-analyst snapshot (``memory.latest_regime()``)

Supports:

* Legacy single-label blobs (``trend`` / ``regime`` / ``btc_trend`` …)
* ``soko_trend_v1`` with ``pairs[].trend`` per symbol and optional
  ``sleeves[].activation`` (``ON`` | ``SIT_OUT``)

``read_live_soko_trend()`` returns one lowercased label (or None). Paper
``build_plan`` sits out on that same value (``TradingPlan.soko_trend``).
A ``pairs[].trend`` or ``sleeves[].activation=ON`` must not reopen a
regime-gated sleeve the hook says is blocked, filter-excluded, or unseen
because the feed is missing. ``read_soko_trend_for_symbol`` remains for
callers that want the per-pair label; it is not the paper sit-out authority.

Closed vocabulary
    After alias mapping, only ``bull``, ``bear``, and ``chop`` are labels.
    Anything else (``neutral``, an empty string, a typo) is not a label.
    The first non-blank top-level field wins: an invalid ``trend`` does not
    fall through to ``btc_trend`` or to ``pairs[]``. The same rule applies
    to the BTC/pairs fallback and to the memory snapshot (``regime`` before
    ``btc_trend``).

Freshness
    The file clock is top-level ``as_of`` (ISO 8601). A trailing ``Z`` and an
    explicit numeric offset are both UTC. A timestamp with no offset is read
    as UTC. The memory clock is ``recorded_at`` on ``latest_regime()``; a
    snapshot with no timestamp is stale.

    A label older than ``SOKO_TREND_MAX_AGE_HOURS`` (settings field
    ``soko_trend_max_age_hours``, default 6) is stale. Missing and
    unparseable clocks are stale. A clock more than
    ``SOKO_TREND_FUTURE_SKEW`` (5 minutes) ahead of now is stale too: a
    far-future stamp would otherwise look fresh forever. A lead of 5 minutes
    or less is clock skew and counts as fresh. "Older than" is strict, so a
    label aged exactly the max is still fresh.

Priority
    A valid, fresh file wins and the memory snapshot is not consulted.
    Otherwise the snapshot is used only when its label is valid and fresh.
    When both are unusable, this returns None and logs one warning naming
    both reasons. None is the paper fail-closed signal: ``build_plan`` calls
    ``paper_record_sitout_reason``, which sits out every regime-gated sleeve
    (approved and paper-override) when the live trend is None, including a
    sleeve whose blocked list and activation filter are empty. Unrestricted
    sleeves stay on. Live ``build_plan`` does not read this hook.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT, get_settings

logger = logging.getLogger(__name__)

LAST_SOKO_TREND_PATH = PROJECT_ROOT / "data" / "last_soko_trend.json"

#: Soko / analyst aliases → the research regime vocabulary.
TREND_ALIASES = {
    "up": "bull",
    "down": "bear",
    "sideways": "chop",
    "bullish": "bull",
    "bearish": "bear",
    "range": "chop",
}

#: The only labels paper regime gates understand. Same set as
#: ``research.validate.KNOWN_REGIMES``.
VALID_TREND_LABELS = frozenset({"bull", "bear", "chop"})

#: How far ``as_of`` / ``recorded_at`` may sit in the future and still count
#: as fresh. Past this, the stamp is not a live reading.
SOKO_TREND_FUTURE_SKEW = timedelta(minutes=5)

_LABEL_KEYS = ("trend", "soko_trend", "label", "regime", "btc_trend")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def soko_trend_max_age() -> timedelta:
    """Configured max age. Env ``SOKO_TREND_MAX_AGE_HOURS``, default 6."""
    return timedelta(hours=float(get_settings().soko_trend_max_age_hours))


def _classify_trend_label(raw: Any) -> tuple[str | None, str | None]:
    """Return ``(label, invalid_raw)``.

    ``(None, None)`` when the value is missing or blank. ``(None, "neutral")``
    when a non-blank value is not bull/bear/chop after alias mapping. The
    invalid raw is the stripped lowercase text, so logs stay stable.
    """
    if raw is None:
        return None, None
    name = str(raw).strip().lower()
    if not name:
        return None, None
    mapped = TREND_ALIASES.get(name, name)
    if mapped in VALID_TREND_LABELS:
        return mapped, None
    return None, name


def normalize_trend_label(raw: Any) -> str | None:
    """Lowercase a trend/regime label, map aliases, keep only bull/bear/chop.

    Any other non-blank value is logged and treated as no label.
    """
    label, invalid = _classify_trend_label(raw)
    if invalid is not None:
        logger.warning("Invalid Soko trend label %r; treating as no label", invalid)
    return label


def _parse_utc_timestamp(value: Any) -> datetime | None:
    """Parse an ISO 8601 clock as UTC. None when the value is not a clock.

    Trailing ``Z`` / ``z`` and explicit offsets are accepted. A naive stamp
    is UTC, not local time.
    """
    if isinstance(value, datetime):
        stamp = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            stamp = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _hours(delta: timedelta) -> str:
    return f"{delta.total_seconds() / 3600.0:.1f}"


def _timestamp_problem(
    value: Any,
    *,
    now: datetime,
    max_age: timedelta,
    field: str,
) -> str | None:
    """None when ``value`` is fresh. Otherwise a short stale/future reason.

    Missing and unparseable clocks are stale. More than
    ``SOKO_TREND_FUTURE_SKEW`` ahead of ``now`` is stale. A smaller lead is
    clock skew. Age equal to ``max_age`` is still fresh; older than that is
    stale.
    """
    # Distinguish "key absent / blank" from "present but not a timestamp".
    if value is None or (isinstance(value, str) and not str(value).strip()):
        return f"{field} missing (stale)"
    stamp = _parse_utc_timestamp(value)
    if stamp is None:
        return f"{field} unparseable (stale)"
    ahead = stamp - now
    if ahead > SOKO_TREND_FUTURE_SKEW:
        return f"{field} future-dated by {_hours(ahead)} hours"
    age = now - stamp
    if age > max_age:
        return f"stale by {_hours(age)} hours"
    return None


@dataclass(frozen=True)
class _Source:
    """One trend source. ``reason`` is empty only when ``label`` is usable."""

    label: str | None
    reason: str


def _file_verdict(
    label: str | None,
    invalid: str | None,
    freshness: str | None,
) -> _Source:
    if invalid:
        reason = f"file label invalid {invalid!r}"
        if freshness:
            reason = f"{reason} ({freshness})"
        return _Source(None, reason)
    if label is None:
        if freshness:
            return _Source(None, f"file has no trend label ({freshness})")
        return _Source(None, "file has no trend label")
    if freshness:
        # "stale by N hours" or "as_of missing/unparseable/future-dated ...".
        return _Source(None, f"file {freshness}")
    return _Source(label, "")


def _memory_verdict(
    label: str | None,
    invalid: str | None,
    freshness: str | None,
) -> _Source:
    if invalid:
        reason = f"memory label invalid {invalid!r}"
        if freshness:
            reason = f"{reason} ({freshness})"
        return _Source(None, reason)
    if label is None:
        if freshness:
            return _Source(None, f"memory snapshot has no trend label ({freshness})")
        return _Source(None, "memory snapshot has no trend label")
    if freshness:
        return _Source(None, f"memory snapshot {freshness}")
    return _Source(label, "")


def _top_level_label(blob: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    """Return ``(label, invalid_raw, found)``.

    The first non-blank label field is authoritative. An invalid value is
    not skipped in favour of a later key (``btc_trend`` must not rescue a
    bad ``regime``). Blank keys are skipped so a human file can leave
    ``trend`` empty and still set ``regime``.
    """
    for key in _LABEL_KEYS:
        raw = blob.get(key)
        if raw is None:
            continue
        if isinstance(raw, str) and not raw.strip():
            continue
        label, invalid = _classify_trend_label(raw)
        return label, invalid, True
    return None, None, False


def _load_soko_blob(path: Path) -> dict[str, Any] | str | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Unreadable Soko trend file %s: %s", path, exc)
        return None
    if isinstance(data, (dict, str)):
        return data
    return None


def _pairs_trend_map(blob: dict[str, Any]) -> dict[str, str]:
    """Map SYMBOL -> bull/bear/chop from ``pairs[]``. Invalid trends are omitted."""
    out: dict[str, str] = {}
    pairs = blob.get("pairs")
    if not isinstance(pairs, list):
        return out
    for row in pairs:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        label, invalid = _classify_trend_label(row.get("trend"))
        if sym and label and not invalid:
            out[sym] = label
    return out


def _btc_or_single_pair_label(blob: dict[str, Any]) -> tuple[str | None, str | None]:
    """Global hint from ``pairs[]`` when the file has no top-level label.

    BTCUSDT then BTC win. A present-but-invalid BTC trend does not fall
    through to another pair. With no BTC row, a single pair is the hint.
    """
    pairs = blob.get("pairs")
    if not isinstance(pairs, list):
        return None, None
    by_symbol: dict[str, str] = {}
    for row in pairs:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        raw = row.get("trend")
        if not sym or raw is None:
            continue
        if isinstance(raw, str) and not raw.strip():
            continue
        by_symbol[sym] = str(raw).strip()
    for prefer in ("BTCUSDT", "BTC"):
        if prefer in by_symbol:
            return _classify_trend_label(by_symbol[prefer])
    if len(by_symbol) == 1:
        return _classify_trend_label(next(iter(by_symbol.values())))
    return None, None


def _label_from_file_body(data: dict[str, Any] | str) -> tuple[str | None, str | None]:
    """Return ``(label, invalid_raw)`` from a file body. Both None if absent."""
    if isinstance(data, str):
        return _classify_trend_label(data)
    label, invalid, found = _top_level_label(data)
    if found:
        return label, invalid
    return _btc_or_single_pair_label(data)


def _sleeve_activation_map(blob: dict[str, Any]) -> dict[str, str]:
    """Map approval key -> ON|SIT_OUT from ``sleeves[]`` when present."""
    out: dict[str, str] = {}
    sleeves = blob.get("sleeves")
    if not isinstance(sleeves, list):
        return out
    for row in sleeves:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        act = str(row.get("activation") or "").strip().upper()
        if key and act in {"ON", "SIT_OUT"}:
            out[key] = act
    return out


def _assess_file(path: Path, *, now: datetime, max_age: timedelta) -> _Source:
    if not path.exists():
        return _Source(None, "file missing")
    data = _load_soko_blob(path)
    if data is None:
        return _Source(None, "file unreadable")
    label, invalid = _label_from_file_body(data)
    as_of = data.get("as_of") if isinstance(data, dict) else None
    # A bare string has no clock. That is a missing as_of, which is stale.
    freshness = _timestamp_problem(
        as_of, now=now, max_age=max_age, field="as_of"
    )
    return _file_verdict(label, invalid, freshness)


def _assess_memory(*, now: datetime, max_age: timedelta) -> _Source:
    """Regime snapshot, or a reason it cannot be used.

    The snapshot clock is ``recorded_at`` (what ``latest_regime()`` stores).
    There is no second timestamp field. If ``recorded_at`` is absent, the
    snapshot is stale even when ``regime`` itself is bull/bear/chop.
    """
    try:
        from firm.memory import latest_regime

        snap = latest_regime()
    except Exception as exc:
        # Missing table / uninitialized DB is a dark feed, not a crash.
        return _Source(None, f"memory snapshot unavailable ({exc})")
    if snap is None:
        return _Source(None, "memory snapshot missing")
    if not isinstance(snap, dict):
        return _Source(None, "memory snapshot unusable")
    label, invalid, _found = _top_level_label(snap)
    freshness = _timestamp_problem(
        snap.get("recorded_at"),
        now=now,
        max_age=max_age,
        field="recorded_at",
    )
    return _memory_verdict(label, invalid, freshness)


def read_live_soko_trend(path: Path | None = None) -> str | None:
    """Lowercased live Soko/desk trend, or None when no source is usable.

    For ``soko_trend_v1`` without a top-level trend, falls back to BTC's
    ``pairs[].trend`` when present. Paper sit-out uses this return value,
    not a second read of ``pairs[]`` or ``sleeves[].activation``.

    None means the paper engine fails closed: every regime-gated sleeve
    sits out. See the module docstring for the age and vocabulary rules.
    One warning names why, when both the file and the memory snapshot are
    unusable.
    """
    dest = path or LAST_SOKO_TREND_PATH
    now = _utcnow()
    max_age = soko_trend_max_age()
    file_source = _assess_file(dest, now=now, max_age=max_age)
    if file_source.label:
        return file_source.label
    mem_source = _assess_memory(now=now, max_age=max_age)
    if mem_source.label:
        # A missing file is the normal "no Soko drop yet" case. A file that
        # exists but cannot be used should say why we ignored it.
        if file_source.reason and file_source.reason != "file missing":
            logger.info(
                "Soko trend file unusable (%s); using regime snapshot %r",
                file_source.reason,
                mem_source.label,
            )
        return mem_source.label
    detail = ", ".join(
        reason for reason in (file_source.reason, mem_source.reason) if reason
    )
    logger.warning(
        "Soko trend fail-closed: %s. Regime-gated paper sleeves will sit out.",
        detail or "no usable bull/bear/chop label",
    )
    return None


def read_soko_trend_for_symbol(
    symbol: str,
    path: Path | None = None,
) -> str | None:
    """Per-symbol trend from ``pairs[]`` (v1), else global ``read_live_soko_trend``.

    Matching is case-insensitive on symbol (``BTCUSDT``). A stale or
    clock-less file does not yield a pair label; the global hook decides.
    Invalid pair trends are not labels.
    """
    dest = path or LAST_SOKO_TREND_PATH
    sym = str(symbol or "").strip().upper()
    data = _load_soko_blob(dest)
    if isinstance(data, dict):
        fresh = (
            _timestamp_problem(
                data.get("as_of"),
                now=_utcnow(),
                max_age=soko_trend_max_age(),
                field="as_of",
            )
            is None
        )
        if fresh:
            pairs = _pairs_trend_map(data)
            if sym and sym in pairs:
                return pairs[sym]
            # Also accept bare base (BTC) if the file used it.
            if sym.endswith("USDT") and sym[:-4] in pairs:
                return pairs[sym[:-4]]
    # Legacy single-label file / regime snapshot fallback.
    return read_live_soko_trend(dest)


def read_soko_sleeve_activation(
    approval_key: str,
    path: Path | None = None,
) -> str | None:
    """Return ``ON`` / ``SIT_OUT`` from ``sleeves[]`` for this approval key, else None."""
    dest = path or LAST_SOKO_TREND_PATH
    key = str(approval_key or "").strip()
    if not key:
        return None
    data = _load_soko_blob(dest)
    if not isinstance(data, dict):
        return None
    return _sleeve_activation_map(data).get(key)
