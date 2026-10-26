"""Read the Soko file for display. Does not sit sleeves out.

``firm.scan_inbox._read_soko`` and the desk header both call
``soko_display``. The desk re-exports that function from ``api.desk_status``
so the API name stays put. The engine imports this module, not ``api``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Clock and JSON helpers copied from the desk display. Importing them from
# ``api.desk_status`` would load the desk module (and, on a panel read, the
# dashboard cache) into the paper worker. Naive stamps are UTC, a trailing
# Z is UTC, and age is whole seconds truncated toward zero.


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _as_utc(parsed)


def _age_seconds(stamp: datetime | None, now: datetime) -> int | None:
    if stamp is None:
        return None
    return int((_as_utc(now) - _as_utc(stamp)).total_seconds())


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _soko_label(blob: dict[str, Any]) -> str | None:
    """Display label. Same top-level keys the paper hook reads, then BTC.

    A non-blank top-level value is shown even when it is not bull, bear, or
    chop, and it does not fall through to a later key. That is the desk
    label, not the sit-out gate. ``pairs`` is only the fallback when every
    top-level key is missing or blank, and a pair must be a real label.
    """
    from core.data.soko_trend import normalize_trend_label

    for key in ("trend", "soko_trend", "label", "regime", "btc_trend"):
        raw = blob.get(key)
        if raw is None:
            continue
        if isinstance(raw, str) and not raw.strip():
            continue
        label = normalize_trend_label(raw)
        return label or str(raw).strip() or None
    pairs = blob.get("pairs")
    if isinstance(pairs, list):
        for prefer in ("BTCUSDT", "BTC"):
            for row in pairs:
                if not isinstance(row, dict):
                    continue
                if str(row.get("symbol") or "").upper() != prefer:
                    continue
                label = normalize_trend_label(row.get("trend"))
                if label:
                    return label
    return None


def soko_display(path: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    """Soko file label, ``as_of``, and age. Does not sit sleeves out.

    The paper worker reads this from ``firm/scan_inbox.py`` (``_read_soko``,
    ``soko_display(now=now)``). ``api.desk_status`` re-exports this function.
    The JSONL and F111 caches do not wrap it, so the dict it returns stays
    label, as_of, age_seconds, source, and path.

    ``LAST_SOKO_TREND_PATH`` is looked up on each call so a test (and a
    process that points the hook at another file) changes the file this
    reads without reimporting the module.
    """
    from core.data.soko_trend import LAST_SOKO_TREND_PATH

    moment = _as_utc(now or _utcnow())
    dest = Path(path) if path is not None else LAST_SOKO_TREND_PATH
    if not dest.exists():
        return {
            "label": None,
            "as_of": None,
            "age_seconds": None,
            "source": "missing",
            "path": str(dest),
        }
    try:
        blob = _read_json(dest)
    except (json.JSONDecodeError, OSError):
        return {
            "label": None,
            "as_of": None,
            "age_seconds": None,
            "source": "unreadable",
            "path": str(dest),
        }
    if isinstance(blob, str):
        from core.data.soko_trend import normalize_trend_label

        return {
            "label": normalize_trend_label(blob) or blob.strip() or None,
            "as_of": None,
            "age_seconds": None,
            "source": "file",
            "path": str(dest),
        }
    if not isinstance(blob, dict):
        return {
            "label": None,
            "as_of": None,
            "age_seconds": None,
            "source": "unreadable",
            "path": str(dest),
        }
    as_of_raw = blob.get("as_of")
    as_of = _parse_time(as_of_raw) if isinstance(as_of_raw, str) else None
    return {
        "label": _soko_label(blob),
        "as_of": as_of.isoformat() if as_of else (as_of_raw if isinstance(as_of_raw, str) else None),
        "age_seconds": _age_seconds(as_of, moment),
        "source": "file",
        "path": str(dest),
    }
