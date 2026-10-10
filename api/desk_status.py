"""Read-only desk displays: F111 census, header clocks, and the live book.

Nothing here places an order, edits ``approved_strategies.json``, or changes
a signal, gate, risk decision, or engine plan. The strategies panel must
follow the same mounted file the paper engine scans. A dated snapshot sitting
next to that file (for example an Oct 1 copy) is not the book.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT

# Clocks the #112 bar poll evaluates. The state file keys every sleeve; the
# header only needs the latest evaluation on each of these three.
BAR_CLOCKS = ("15m", "1h", "4h")

# Pending rows the F111 runtime is still watching. Filled and rejected rows
# stay in the state file as history; they are not an open retest.
_ACTIVE_RETEST = frozenset({"watching", "scheduled"})


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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Telemetry is append-only. A bad line is skipped, not a failed panel."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def is_live_book_name(name: str) -> bool:
    """True only for the engine's book filename.

    Backups (``approved_strategies.json.before-f111-...``) and dated snapshots
    (``approved_strategies.2026-10-01.json``) fail this check on purpose.
    """
    return name == "approved_strategies.json"


def live_approvals_path(path: Path | None = None) -> Path:
    """Resolved path of the book the engine scans.

    The configured name must be ``approved_strategies.json``. A symlink is
    followed, because on the host the bind-mount target can have another
    filename. A dated snapshot or a ``before-*`` backup is not a substitute
    when this path is missing, and it is refused if it is passed in directly.
    """
    if path is None:
        from config.universe import APPROVALS_PATH

        path = Path(APPROVALS_PATH)
    else:
        path = Path(path)
    if not is_live_book_name(path.name):
        raise RuntimeError(
            f"Refusing to read {path.name} as the strategy book. "
            "The dashboard uses config/approved_strategies.json (the mounted "
            "live book), not a dated snapshot or a before-* backup."
        )
    if path.is_symlink():
        return path.resolve(strict=True)
    return path


def read_live_approval_book(path: Path | None = None) -> dict[str, Any]:
    """Fresh parse of the live book. Does not use ``get_universe``'s cache.

    The cache is process-lifetime. A strategies panel that reads it can keep
    showing the file that was on disk when the API started, including a
    snapshot copied into the image. This opens the mounted path on every call.
    """
    target = live_approvals_path(path)
    empty: dict[str, Any] = {
        "source_path": str(target),
        "source_mtime": None,
        "generated_at": "",
        "verdict": "",
        "approvals": {},
        "error": None,
    }
    if not target.exists():
        empty["error"] = "missing"
        return empty
    try:
        raw = _read_json(target)
    except (json.JSONDecodeError, OSError) as exc:
        empty["error"] = f"unreadable: {exc}"
        return empty
    if not isinstance(raw, dict):
        empty["error"] = "book is not a JSON object"
        return empty
    try:
        mtime = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        mtime = None
    approvals = {key: value for key, value in raw.items() if isinstance(value, dict)}
    return {
        "source_path": str(target),
        "source_mtime": mtime,
        "generated_at": str(raw.get("_generated_at") or ""),
        "verdict": str(raw.get("_verdict") or ""),
        "approvals": approvals,
        "error": None,
    }


# Env wins, then a stamp file, then ``git rev-parse``. The SGP1 image has no
# ``.git``, so the last step returns unavailable unless deploy writes one of
# the earlier two. ``DEPLOYED_GIT_SHA`` and ``GIT_COMMIT`` stay as aliases.
_SHA_ENV_KEYS = ("GIT_SHA", "APP_GIT_SHA", "DEPLOYED_GIT_SHA", "GIT_COMMIT")
_SHA_TOKEN = re.compile(r"[0-9a-fA-F]{7,64}")


def _sha_token(text: str) -> str | None:
    """First hex token on its own line. Blank and prose files are not a sha."""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _SHA_TOKEN.fullmatch(line):
            return line
        return None
    return None


def _sha_files(root: Path) -> list[Path]:
    """Stamp files, first hit wins.

    ``/app/GIT_SHA`` is the container path. ``data/DEPLOYED_SHA`` is the same
    idea next to the state files when the app root is not ``/app``.
    """
    ordered = (
        Path("/app/GIT_SHA"),
        root / "GIT_SHA",
        root / "data" / "DEPLOYED_SHA",
    )
    seen: set[str] = set()
    out: list[Path] = []
    for path in ordered:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _sha_payload(sha: str, source: str, **extra: Any) -> dict[str, Any]:
    return {"sha": sha, "short": sha[:12], "source": source, **extra}


def deployed_git_sha(root: Path | None = None) -> dict[str, Any]:
    """Commit the running tree is on. Does not change what is deployed.

    Order: ``GIT_SHA`` or ``APP_GIT_SHA`` (then the older env aliases), then
    ``/app/GIT_SHA`` or ``data/DEPLOYED_SHA``, then ``git rev-parse HEAD``.
    A container without ``.git`` stays on the env or the file.
    """
    for key in _SHA_ENV_KEYS:
        token = _sha_token(os.environ.get(key, ""))
        if token:
            return _sha_payload(token, "env", env=key)
    repo = root or PROJECT_ROOT
    for path in _sha_files(repo):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        token = _sha_token(text)
        if token:
            return _sha_payload(token, "file", path=str(path))
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            text=True,
            timeout=2,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return {"sha": None, "short": None, "source": "unavailable"}
    token = _sha_token(sha)
    if not token:
        return {"sha": None, "short": None, "source": "unavailable"}
    return _sha_payload(token, "git")


def _soko_label(blob: dict[str, Any]) -> str | None:
    """Display label. Same top-level keys the paper hook reads, then BTC."""
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
    """Soko file label, ``as_of``, and age. Does not sit sleeves out."""
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


def cycle_display(cycle: dict[str, Any] | None, *, now: datetime | None = None) -> dict[str, Any]:
    """Last paper cycle clock. ``started_at`` is the cycle time."""
    moment = _as_utc(now or _utcnow())
    if not isinstance(cycle, dict):
        return {"started_at": None, "age_seconds": None}
    started_raw = cycle.get("started_at")
    started = _parse_time(started_raw)
    return {
        "started_at": started.isoformat() if started else (started_raw if isinstance(started_raw, str) else None),
        "age_seconds": _age_seconds(started, moment),
    }


def _normalise_clock(timeframe: str) -> str | None:
    from core.data.ohlcv import normalise_timeframe

    try:
        clock = normalise_timeframe(timeframe)
    except (TypeError, ValueError):
        return None
    if clock not in BAR_CLOCKS:
        return None
    return clock


def bar_close_display(payload: dict[str, Any] | None, *, now: datetime | None = None) -> dict[str, Any]:
    """Latest #112 evaluation time on 15m, 1h, and 4h.

    Sleeve keys are ``symbol|timeframe|side|strategy``. The newest
    ``evaluated_at`` on each clock is the last bar-close evaluation.
    """
    moment = _as_utc(now or _utcnow())
    out: dict[str, Any] = {clock: None for clock in BAR_CLOCKS}
    sleeves = {}
    if isinstance(payload, dict):
        raw = payload.get("sleeves")
        if isinstance(raw, dict):
            sleeves = raw
    for key, row in sleeves.items():
        if not isinstance(row, dict):
            continue
        parts = str(key).split("|")
        if len(parts) < 2:
            continue
        clock = _normalise_clock(parts[1])
        if clock is None:
            continue
        evaluated = _parse_time(row.get("evaluated_at"))
        current = out[clock]
        current_at = _parse_time(current.get("evaluated_at")) if isinstance(current, dict) else None
        if current_at is not None and evaluated is not None and evaluated < current_at:
            continue
        if current_at is not None and evaluated is None:
            continue
        out[clock] = {
            "evaluated_at": evaluated.isoformat() if evaluated else row.get("evaluated_at"),
            "bar_open": row.get("bar_open"),
            "age_seconds": _age_seconds(evaluated, moment),
            "sleeve": str(key),
        }
    return out


def desk_header(
    *,
    now: datetime | None = None,
    cycle: dict[str, Any] | None = None,
    soko_path: Path | None = None,
    bar_state_path: Path | None = None,
    git_root: Path | None = None,
) -> dict[str, Any]:
    """Header payload. Reads files; does not run a cycle."""
    from core.execution.engine import load_last_cycle
    from core.execution.paper_bar_eval import PAPER_BAR_STATE_PATH

    moment = _as_utc(now or _utcnow())
    if cycle is None:
        loaded = load_last_cycle()
        cycle = loaded if isinstance(loaded, dict) else None
    bar_path = Path(bar_state_path) if bar_state_path is not None else PAPER_BAR_STATE_PATH
    bar_payload: dict[str, Any] | None = None
    bar_error = None
    if bar_path.exists():
        try:
            loaded_bar = _read_json(bar_path)
            bar_payload = loaded_bar if isinstance(loaded_bar, dict) else None
            if bar_payload is None:
                bar_error = "bar state is not a JSON object"
        except (json.JSONDecodeError, OSError) as exc:
            bar_error = str(exc)
    else:
        bar_error = "missing"
    return {
        "git": deployed_git_sha(git_root),
        "cycle": cycle_display(cycle, now=moment),
        "soko": soko_display(soko_path, now=moment),
        "bar_close": bar_close_display(bar_payload, now=moment),
        "bar_state_path": str(bar_path),
        "bar_state_error": bar_error,
    }


def _latest_registry_block(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Last contiguous registry census in the telemetry file.

    ``step_market`` writes the 192 sleeve rows together, then the hourly
    gate rows. The census is the trailing registry block before later
    signals, not every registry row ever appended.
    """
    end: int | None = None
    for index in range(len(rows) - 1, -1, -1):
        if rows[index].get("record_kind") == "registry":
            end = index
            break
    if end is None:
        return []
    start = end
    while start > 0 and rows[start - 1].get("record_kind") == "registry":
        start -= 1
    return rows[start : end + 1]


def _is_gate_rejection(row: dict[str, Any]) -> bool:
    """A failed gate or a data gap. Registry census rows are not gates."""
    if row.get("record_kind") == "registry":
        return False
    if row.get("deploy_marker"):
        return False
    if row.get("gate_decision") is True:
        return False
    reason = row.get("rejection_reason")
    if isinstance(reason, str) and reason:
        return True
    return row.get("gate_decision") is False


def _rejection_reason(row: dict[str, Any]) -> str:
    reason = row.get("rejection_reason")
    if isinstance(reason, str) and reason:
        return reason
    return "unspecified"


def _count_reasons(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        reason = _rejection_reason(row)
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _gate_rows(rows: list[dict[str, Any]]) -> list[tuple[dict[str, Any], datetime | None]]:
    from core.execution.f111_paper import row_recorded_time

    out: list[tuple[dict[str, Any], datetime | None]] = []
    for row in rows:
        if row.get("record_kind") == "registry" or row.get("deploy_marker"):
            continue
        # Bar-close time is the hourly close the scan judged. Recorded time
        # also covers observed_at / emitted_at when a row has them.
        out.append((row, row_recorded_time(row)))
    return out


def _hour_floor(stamp: datetime) -> datetime:
    stamp = _as_utc(stamp)
    return stamp.replace(minute=0, second=0, microsecond=0)


def f111_status(
    *,
    now: datetime | None = None,
    telemetry_path: Path | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """F111 panel: 192 sleeves, census split, gate reasons, retests.

    Source files are the configured state and telemetry paths
    (``data/f111_paper_state.json`` and ``data/f111_telemetry.jsonl``).
    On SGP1 those live under the state mount, typically
    ``/data/state/data/...``.
    """
    from core.strategy.f111_config import STATE_PATH, TELEMETRY_PATH, load_f111_config

    moment = _as_utc(now or _utcnow())
    telemetry = Path(telemetry_path) if telemetry_path is not None else TELEMETRY_PATH
    state = Path(state_path) if state_path is not None else STATE_PATH
    expected = 192
    config_error = None
    try:
        config, _digest = load_f111_config()
        expected = int(config.get("expected_scan_sleeves") or 192)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        config_error = str(exc)

    rows = _read_jsonl(telemetry)
    census = _latest_registry_block(rows)
    available = 0
    closed_by: dict[str, int] = {}
    for row in census:
        if row.get("instrument_unavailable"):
            reason = _rejection_reason(row)
            closed_by[reason] = closed_by.get(reason, 0) + 1
        else:
            available += 1
    closed = sum(closed_by.values())

    rejections = [(row, stamp) for row, stamp in _gate_rows(rows) if _is_gate_rejection(row)]
    stamped = [(row, stamp) for row, stamp in rejections if stamp is not None]
    latest_hour_rows: list[dict[str, Any]] = []
    latest_hour_start: datetime | None = None
    if stamped:
        latest_hour_start = _hour_floor(max(stamp for _row, stamp in stamped if stamp is not None))
        latest_hour_end = latest_hour_start + timedelta(hours=1)
        latest_hour_rows = [
            row
            for row, stamp in stamped
            if stamp is not None and latest_hour_start <= stamp < latest_hour_end
        ]
    day_start = moment - timedelta(hours=24)
    last_day_rows = [
        row for row, stamp in stamped if stamp is not None and stamp >= day_start
    ]

    bar_close: datetime | None = None
    for row, stamp in _gate_rows(rows):
        if stamp is not None and (bar_close is None or stamp > bar_close):
            # Prefer the hourly close the scan evaluated over a later minute
            # touch on the same file. ``row_recorded_time`` already returns
            # source_signal_time (the bar close) before other clocks.
            if row.get("source_signal_time") or (isinstance(row.get("feature_asof_times"), dict) and row["feature_asof_times"].get("signal_close")):
                bar_close = stamp
            elif bar_close is None:
                bar_close = stamp

    pending_retests = 0
    protection = 0
    state_error = None
    if state.exists():
        try:
            payload = _read_json(state)
        except (json.JSONDecodeError, OSError) as exc:
            payload = None
            state_error = str(exc)
        if isinstance(payload, dict):
            pending = payload.get("pending") or []
            if isinstance(pending, list):
                pending_retests = sum(
                    1
                    for row in pending
                    if isinstance(row, dict)
                    and str(row.get("status") or "watching") in _ACTIVE_RETEST
                )
            held = payload.get("protection") or {}
            if isinstance(held, dict):
                protection = len(held)
        elif payload is not None:
            state_error = "state is not a JSON object"
    else:
        state_error = "missing"

    return {
        "expected_sleeves": expected,
        "config_error": config_error,
        "telemetry_path": str(telemetry),
        "state_path": str(state),
        "state_error": state_error,
        "registry": {
            "evaluated": len(census),
            "available": available,
            "closed": closed,
            "closed_by_reason": dict(sorted(closed_by.items(), key=lambda item: (-item[1], item[0]))),
        },
        "rejections": {
            "latest_hour": {
                "hour_start": latest_hour_start.isoformat() if latest_hour_start else None,
                "rows": len(latest_hour_rows),
                "by_reason": _count_reasons(latest_hour_rows),
            },
            "last_24h": {
                "since": day_start.isoformat(),
                "rows": len(last_day_rows),
                "by_reason": _count_reasons(last_day_rows),
            },
        },
        "last_bar_close_evaluation": bar_close.isoformat() if bar_close else None,
        "pending_retests": pending_retests,
        "protection": protection,
    }
