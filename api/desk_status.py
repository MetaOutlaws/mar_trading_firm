"""Read-only desk displays: F111 census, header clocks, and the live book.

Nothing here places an order, edits ``approved_strategies.json``, or changes
a signal, gate, risk decision, or engine plan. The strategies panel must
follow the same mounted file the paper engine scans. A dated snapshot sitting
next to that file (for example an Oct 1 copy) is not the book.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import threading
from collections import deque
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


# One running fold per telemetry path. The old cache stored every parsed
# row and kept a new copy each time the file grew (mtime, size). On SGP1
# that file is ~216 MB, a parsed copy is several hundred MB, and a scan
# appends about every 15 minutes, so RSS climbed ~50 MB/min until the
# host OOM-killed the API. The fold keeps the aggregates the panel
# actually returns and reads only the bytes appended since the last poll.
_JSONL_CACHE: dict[str, "_TelemetryFold"] = {}
_JSONL_LOCK = threading.Lock()
_MAX_TELEMETRY_FOLDS = 4
# Rolling day is 24h. Two extra hours cover a desk clock slightly ahead
# of the newest stamp without a second pass over the file.
_REJECTION_RETAIN = timedelta(hours=26)
_READ_CHUNK = 1024 * 1024
# A torn last line is held until the writer finishes it. Past this size
# it is not a telemetry row, so drop it instead of growing without bound.
_MAX_PARTIAL_LINE = 1024 * 1024


def clear_jsonl_cache() -> None:
    """Drop folded telemetry. Tests use this so a rewritten file starts clean."""
    with _JSONL_LOCK:
        _JSONL_CACHE.clear()


def telemetry_cache_stats() -> dict[str, int]:
    """How many files are folded, and how many row objects those folds still hold.

    ``parsed_rows`` counts every object seen since the fold was reset.
    ``retained_rows`` is the census slice, the open hour, the blotter, and
    the rolling-day reasons. A poll must not make ``retained_rows`` track
    ``parsed_rows``.
    """
    with _JSONL_LOCK:
        folds = list(_JSONL_CACHE.values())
    return {
        "files": len(folds),
        "retained_rows": sum(fold.retained_rows for fold in folds),
        "parsed_rows": sum(fold.parsed_rows for fold in folds),
    }


class _TelemetryView:
    """What ``/api/f111`` needs from the file. Not the file itself."""

    def __init__(self) -> None:
        self.evaluated = 0
        self.available = 0
        self.closed_by: dict[str, int] = {}
        self.unavailable: list[dict[str, Any]] = []
        self.rej_hour: datetime | None = None
        self.events: list[tuple[datetime, str]] = []
        self.bar_close: datetime | None = None
        self.why_rows: list[dict[str, Any]] = []
        self.blotter: list[dict[str, Any]] = []
        self.realised_sum = 0.0
        self.realised_count = 0


class _TelemetryFold:
    """Incremental reduce of an append-only JSONL file.

    The first sync walks the file line by line and throws each object away
    after updating the fold. A later sync seeks to the previous offset and
    parses only the new tail. A shrink, a replaced inode, or a same-length
    rewrite starts over.
    """

    def __init__(self) -> None:
        self.parsed_rows = 0
        self.inode: int | None = None
        self.mtime_ns = 0
        self.offset = 0
        self.partial = b""
        self.retain_from: datetime | None = None
        self.horizon: datetime | None = None
        self._reset_aggregates()

    def _reset_aggregates(self) -> None:
        self.parsed_rows = 0
        self.cur_evaluated = 0
        self.cur_available = 0
        self.cur_closed: dict[str, int] = {}
        self.cur_unavailable: list[dict[str, Any]] = []
        self.trail_evaluated = 0
        self.trail_available = 0
        self.trail_closed: dict[str, int] = {}
        self.trail_unavailable: list[dict[str, Any]] = []
        self.rej_hour: datetime | None = None
        self.rej_counts: dict[str, int] = {}
        self.max_rej_stamp: datetime | None = None
        self.events: list[tuple[datetime, str]] = []
        self.bar_close: datetime | None = None
        self.why_hour: datetime | None = None
        self.why_rows: list[dict[str, Any]] = []
        self.blotter: deque[dict[str, Any]] = deque(maxlen=30)
        self.realised_sum = 0.0
        self.realised_count = 0
        self._row_time = None
        self._is_exit = None
        self._since_compact = 0

    def _reset_reader(self) -> None:
        """Forget the file position and the aggregates. Keep ``retain_from``."""
        self.inode = None
        self.mtime_ns = 0
        self.offset = 0
        self.partial = b""
        self.horizon = None
        self._reset_aggregates()

    @property
    def retained_rows(self) -> int:
        return (
            len(self.why_rows)
            + len(self.cur_unavailable)
            + len(self.trail_unavailable)
            + len(self.blotter)
            + len(self.events)
        )

    def view(self, path: Path, now: datetime) -> _TelemetryView:
        if not path.exists():
            self._reset_reader()
            self.retain_from = None
            return _TelemetryView()
        self.sync(path)
        day_start = _as_utc(now) - timedelta(hours=24)
        # A desk clock behind the newest bar needs rows the 26h horizon
        # already dropped. One rescan, keeping that clock's day, is enough.
        if self.horizon is not None and day_start < self.horizon and (
            self.retain_from is None or day_start < self.retain_from
        ):
            self.retain_from = day_start
            self._reset_reader()
            self.sync(path)
        return self._snapshot(day_start)

    def sync(self, path: Path) -> None:
        try:
            st = path.stat()
        except OSError:
            return
        if self._position_is_stale(st):
            self._reset_reader()
        if st.st_size < self.offset:
            self._reset_reader()
        try:
            with path.open("rb") as handle:
                handle.seek(self.offset)
                while True:
                    chunk = handle.read(_READ_CHUNK)
                    if not chunk:
                        break
                    self.offset += len(chunk)
                    self._consume(chunk)
                self._finish_partial()
                end = os.fstat(handle.fileno())
        except OSError:
            return
        self.inode = int(end.st_ino)
        self.mtime_ns = int(end.st_mtime_ns)
        if int(end.st_size) < self.offset:
            # The file was replaced under us. The next sync starts clean.
            self._reset_reader()
            return
        self._compact_events()

    def _position_is_stale(self, st: os.stat_result) -> bool:
        if self.inode is None:
            return False
        if int(st.st_ino) != self.inode:
            return True
        if int(st.st_size) < self.offset:
            return True
        # Same length, new mtime: a rewrite, not an append. Appends grow.
        if int(st.st_size) == self.offset and int(st.st_mtime_ns) != self.mtime_ns:
            return True
        return False

    def _consume(self, data: bytes) -> None:
        blob = self.partial + data
        parts = blob.split(b"\n")
        self.partial = parts.pop()
        if len(self.partial) > _MAX_PARTIAL_LINE:
            self.partial = b""
        for raw in parts:
            self._ingest_line(raw)

    def _finish_partial(self) -> None:
        """A file that does not end in a newline still has a last object.

        An unfinished object (the writer is mid-line) fails JSON and stays
        in ``partial`` for the next append. A finished object is folded and
        dropped, matching ``splitlines`` on a whole-file read.
        """
        if not self.partial or not self.partial.strip():
            self.partial = b""
            return
        try:
            payload = json.loads(self.partial.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        self.partial = b""
        if isinstance(payload, dict):
            self._ingest(payload)

    def _ingest_line(self, raw: bytes) -> None:
        raw = raw.strip()
        if not raw:
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if isinstance(payload, dict):
            self._ingest(payload)

    def _bind_parsers(self) -> None:
        if self._row_time is not None:
            return
        from api.why_no_trade import _f111_exit
        from core.execution.f111_paper import row_recorded_time

        self._row_time = row_recorded_time
        self._is_exit = _f111_exit

    def _ingest(self, row: dict[str, Any]) -> None:
        self._bind_parsers()
        self.parsed_rows += 1
        self._since_compact += 1
        registry = row.get("record_kind") == "registry"
        deploy = bool(row.get("deploy_marker"))
        if registry:
            self._note_registry(row)
        else:
            self._end_registry_run()
        if registry or deploy:
            if self._since_compact >= 4096:
                self._compact_events()
            return
        stamp = self._row_time(row)
        if _is_gate_rejection(row):
            self._note_rejection(row, stamp)
        self._note_bar_close(row, stamp)
        self._note_blotter(row)
        if (
            not self._is_exit(row)
            and row.get("symbol")
            and stamp is not None
        ):
            self._note_why(row, stamp)
        if self._since_compact >= 4096:
            self._compact_events()

    def _note_registry(self, row: dict[str, Any]) -> None:
        self.cur_evaluated += 1
        if row.get("instrument_unavailable"):
            reason = _rejection_reason(row)
            self.cur_closed[reason] = self.cur_closed.get(reason, 0) + 1
            features = row.get("feature_values")
            status = features.get("exchange_status") if isinstance(features, dict) else None
            slim: dict[str, Any] = {
                "symbol": row.get("symbol"),
                "side": row.get("side"),
                "instrument_unavailable": True,
                "rejection_reason": row.get("rejection_reason"),
            }
            if status is not None:
                slim["feature_values"] = {"exchange_status": status}
            self.cur_unavailable.append(slim)
            return
        self.cur_available += 1

    def _end_registry_run(self) -> None:
        if self.cur_evaluated <= 0:
            return
        self.trail_evaluated = self.cur_evaluated
        self.trail_available = self.cur_available
        self.trail_closed = dict(self.cur_closed)
        self.trail_unavailable = self.cur_unavailable
        self.cur_evaluated = 0
        self.cur_available = 0
        self.cur_closed = {}
        self.cur_unavailable = []

    def _note_rejection(self, row: dict[str, Any], stamp: datetime | None) -> None:
        if stamp is None:
            return
        hour = _hour_floor(stamp)
        if self.rej_hour is None or hour > self.rej_hour:
            self.rej_hour = hour
            self.rej_counts = {}
        if hour == self.rej_hour:
            reason = _rejection_reason(row)
            self.rej_counts[reason] = self.rej_counts.get(reason, 0) + 1
        else:
            reason = _rejection_reason(row)
        if self.max_rej_stamp is None or stamp > self.max_rej_stamp:
            self.max_rej_stamp = stamp
        self.events.append((stamp, reason))

    def _note_bar_close(self, row: dict[str, Any], stamp: datetime | None) -> None:
        if stamp is None:
            return
        if self.bar_close is not None and stamp <= self.bar_close:
            return
        asof = row.get("feature_asof_times")
        has_signal = bool(row.get("source_signal_time")) or (
            isinstance(asof, dict) and bool(asof.get("signal_close"))
        )
        if has_signal or self.bar_close is None:
            self.bar_close = stamp

    def _note_blotter(self, row: dict[str, Any]) -> None:
        realised = _number(row.get("realised_net_profit"))
        if realised is None:
            return
        self.realised_sum += realised
        self.realised_count += 1
        reason = row.get("rejection_reason")
        self.blotter.append(
            {
                "symbol": row.get("symbol"),
                "side": row.get("side"),
                "quantity": _number(row.get("quantity")),
                "entry_price": _number(row.get("entry_price")),
                "exit_price": _number(row.get("simulated_fill")),
                "closed_at": row.get("quote_time") or row.get("source_signal_time"),
                "net_pnl": realised,
                "reason": reason if isinstance(reason, str) else None,
            }
        )

    def _note_why(self, row: dict[str, Any], stamp: datetime) -> None:
        hour = _hour_floor(stamp)
        if self.why_hour is None or hour > self.why_hour:
            self.why_hour = hour
            self.why_rows = [row]
            return
        if hour == self.why_hour:
            self.why_rows.append(row)

    def _compact_events(self) -> None:
        self._since_compact = 0
        if self.max_rej_stamp is None:
            return
        cutoff = self.max_rej_stamp - _REJECTION_RETAIN
        if self.retain_from is not None and self.retain_from < cutoff:
            cutoff = self.retain_from
        if any(stamp < cutoff for stamp, _reason in self.events):
            self.events = [item for item in self.events if item[0] >= cutoff]
        self.horizon = cutoff

    def _snapshot(self, day_start: datetime) -> _TelemetryView:
        view = _TelemetryView()
        if self.cur_evaluated > 0:
            view.evaluated = self.cur_evaluated
            view.available = self.cur_available
            view.closed_by = dict(self.cur_closed)
            view.unavailable = list(self.cur_unavailable)
        else:
            view.evaluated = self.trail_evaluated
            view.available = self.trail_available
            view.closed_by = dict(self.trail_closed)
            view.unavailable = list(self.trail_unavailable)
        view.rej_hour = self.rej_hour
        view.events = [item for item in self.events if item[0] >= day_start or (
            self.rej_hour is not None and self.rej_hour <= item[0] < self.rej_hour + timedelta(hours=1)
        )]
        # The day filter is applied again by the panel. Keeping the latest
        # hour in this copy covers a quiet hour that started before the day.
        view.bar_close = self.bar_close
        view.why_rows = list(self.why_rows)
        view.blotter = list(self.blotter)
        view.realised_sum = self.realised_sum
        view.realised_count = self.realised_count
        return view


def _fold_for(path: Path) -> _TelemetryFold:
    try:
        key = str(path.resolve())
    except OSError:
        key = str(path)
    fold = _JSONL_CACHE.get(key)
    if fold is None:
        while len(_JSONL_CACHE) >= _MAX_TELEMETRY_FOLDS:
            _JSONL_CACHE.pop(next(iter(_JSONL_CACHE)))
        fold = _TelemetryFold()
        _JSONL_CACHE[key] = fold
        return fold
    # Refresh LRU order. The live file stays; a test path that went quiet goes.
    _JSONL_CACHE.pop(key)
    _JSONL_CACHE[key] = fold
    return fold


def read_telemetry(path: Path, *, now: datetime | None = None) -> _TelemetryView:
    """Fold ``path`` up to ``now``'s rolling day. Safe to call on every poll."""
    moment = _as_utc(now or _utcnow())
    with _JSONL_LOCK:
        return _fold_for(path).view(path, moment)


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


# Parsed live book, keyed by resolved path. A poll stats the file. The
# same inode, mtime, and size returns the parsed approvals. A new mtime
# hashes the bytes; the same sha256 keeps the parsed object and only the
# displayed mtime moves. ``get_universe`` is process-lifetime and is not
# this cache. Callers must not mutate ``approvals``.
_BOOK_LOCK = threading.Lock()
_BOOK_CACHE: dict[str, "_BookEntry"] = {}
_MAX_BOOK_CACHE = 4


class _BookEntry:
    def __init__(self) -> None:
        self.inode = 0
        self.mtime_ns = 0
        self.size = -1
        self.digest = ""
        self.payload: dict[str, Any] | None = None


def clear_book_cache() -> None:
    """Drop parsed approval books. Tests use this after rewriting a path."""
    with _BOOK_LOCK:
        _BOOK_CACHE.clear()


def _book_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _book_mtime_iso(st: os.stat_result) -> str:
    return datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()


def _empty_book(target: Path, error: str | None) -> dict[str, Any]:
    return {
        "source_path": str(target),
        "source_mtime": None,
        "generated_at": "",
        "verdict": "",
        "approvals": {},
        "error": error,
    }


def _book_entry(target: Path) -> _BookEntry | None:
    """Return the cached book, parsing only when the content hash changes."""
    key = _book_key(target)
    try:
        st = target.stat()
    except OSError:
        with _BOOK_LOCK:
            _BOOK_CACHE.pop(key, None)
        return None
    with _BOOK_LOCK:
        current = _BOOK_CACHE.get(key)
        if (
            current is not None
            and current.payload is not None
            and current.inode == int(st.st_ino)
            and current.mtime_ns == int(st.st_mtime_ns)
            and current.size == int(st.st_size)
        ):
            return current
    raw = target.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with _BOOK_LOCK:
        current = _BOOK_CACHE.get(key)
        if current is not None and current.payload is not None and current.digest == digest:
            current.inode = int(st.st_ino)
            current.mtime_ns = int(st.st_mtime_ns)
            current.size = int(st.st_size)
            current.payload["source_mtime"] = _book_mtime_iso(st)
            current.payload["source_path"] = str(target)
            return current
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        payload = _empty_book(target, f"unreadable: {exc}")
        parsed = None
    else:
        if not isinstance(parsed, dict):
            payload = _empty_book(target, "book is not a JSON object")
        else:
            payload = {
                "source_path": str(target),
                "source_mtime": _book_mtime_iso(st),
                "generated_at": str(parsed.get("_generated_at") or ""),
                "verdict": str(parsed.get("_verdict") or ""),
                "approvals": {
                    item_key: value
                    for item_key, value in parsed.items()
                    if isinstance(value, dict)
                },
                "error": None,
            }
    entry = _BookEntry()
    entry.inode = int(st.st_ino)
    entry.mtime_ns = int(st.st_mtime_ns)
    entry.size = int(st.st_size)
    entry.digest = digest
    entry.payload = payload
    with _BOOK_LOCK:
        while len(_BOOK_CACHE) >= _MAX_BOOK_CACHE and key not in _BOOK_CACHE:
            _BOOK_CACHE.pop(next(iter(_BOOK_CACHE)))
        _BOOK_CACHE[key] = entry
    return entry


def read_live_approval_book(path: Path | None = None) -> dict[str, Any]:
    """Live book for the desk. Does not use ``get_universe``'s cache.

    ``get_universe`` lives for the process. A strategies panel that used it
    could keep the file from API start, including a snapshot baked into the
    image. This stats the mounted path on every call and parses it only when
    the bytes change. The returned wrapper is a new dict; ``approvals`` is
    the cached mapping and must not be mutated.
    """
    target = live_approvals_path(path)
    if not target.exists():
        with _BOOK_LOCK:
            _BOOK_CACHE.pop(_book_key(target), None)
        return _empty_book(target, "missing")
    try:
        entry = _book_entry(target)
    except OSError as exc:
        return _empty_book(target, f"unreadable: {exc}")
    if entry is None or entry.payload is None:
        return _empty_book(target, "missing")
    return dict(entry.payload)


def approval_book_stat(path: Path | None = None) -> tuple[str, int, str]:
    """Path, mtime_ns, and sha256. A missing book is an empty sha.

    Same identity ``book_fingerprint`` used to compute by reading the file
    on every cache-key build. A quiet poll now stats. The hash is the one
    stored when the bytes last changed.
    """
    try:
        target = live_approvals_path(path)
    except OSError:
        return ("", 0, "")
    if not target.exists():
        return (str(target), 0, "")
    entry = _book_entry(target)
    if entry is None or not entry.digest:
        return (str(target), 0, "")
    return (str(target), int(entry.mtime_ns), entry.digest)


# One slot for ``data/last_cycle.json``. ``/api/cycle`` and the desk header
# both read it. The paper engine still uses ``load_last_cycle`` and is not
# pointed at this slot.
_CYCLE_LOCK = threading.Lock()
_CYCLE_SLOT: dict[str, Any] = {"token": None, "digest": "", "payload": None}


def clear_cycle_cache() -> None:
    """Drop the cached last-cycle plan."""
    with _CYCLE_LOCK:
        _CYCLE_SLOT["token"] = None
        _CYCLE_SLOT["digest"] = ""
        _CYCLE_SLOT["payload"] = None


def read_cached_last_cycle() -> dict[str, Any] | None:
    """Last persisted plan for the desk. Parses only when the file changes.

    The token is inode, mtime, and size. A rewrite with the same bytes keeps
    the parsed dict after a sha256 check. Trading code does not call this.
    """
    from core.execution.engine import LAST_CYCLE_PATH

    path = Path(LAST_CYCLE_PATH)
    try:
        st = path.stat()
    except OSError:
        clear_cycle_cache()
        return None
    try:
        identity = str(path.resolve())
    except OSError:
        identity = str(path)
    token = (identity, int(st.st_ino), int(st.st_mtime_ns), int(st.st_size))
    with _CYCLE_LOCK:
        if _CYCLE_SLOT["token"] == token:
            payload = _CYCLE_SLOT["payload"]
            return payload if isinstance(payload, dict) else None
    try:
        raw = path.read_bytes()
    except OSError:
        clear_cycle_cache()
        return None
    digest = hashlib.sha256(raw).hexdigest()
    with _CYCLE_LOCK:
        if _CYCLE_SLOT["digest"] == digest and isinstance(_CYCLE_SLOT["payload"], dict):
            _CYCLE_SLOT["token"] = token
            return _CYCLE_SLOT["payload"]
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        parsed = None
    if not isinstance(parsed, dict):
        parsed = None
    with _CYCLE_LOCK:
        _CYCLE_SLOT["token"] = token
        _CYCLE_SLOT["digest"] = digest
        _CYCLE_SLOT["payload"] = parsed
    return parsed


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
    """Soko file label, ``as_of``, and age. Does not sit sleeves out.

    The paper worker imports this from ``firm/scan_inbox.py`` (``_read_soko``,
    ``soko_display(now=now)``). The JSONL and F111 caches do not wrap it, so
    the dict it returns stays label, as_of, age_seconds, source, and path.
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
    from core.execution.paper_bar_eval import PAPER_BAR_STATE_PATH

    moment = _as_utc(now or _utcnow())
    if cycle is None:
        loaded = read_cached_last_cycle()
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


# Shown on /api/cycle next to the three labeled counts. Display only.
_SCAN_COUNT_NOTE = (
    "Active is the last paper scan (plan entries; regime sit-outs are already "
    "removed). Book overrides are paper_override rows in the live approvals "
    "file. Sitting out (regime) is every regime_sitouts row on that cycle. "
    "Sitting-out overrides are the sit-out rows whose book record has "
    "paper_override true. When every other override became a plan row, "
    "active overrides equal book overrides minus sitting-out overrides "
    "(reconciles is true). An unregistered sleeve or a duplicate plan identity "
    "is in neither list, so reconciles is false. Approved sit-outs reduce "
    "the approved half of Active, not the override half."
)


def cycle_scan_counts(
    cycle: dict[str, Any] | None,
    book: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Label the last scan against the live book. Does not change the plan.

    ``build_plan`` (paper) appends a ``paper_override`` row to ``plan.entries``
    only when ``paper_record_sitout_reason`` returns None. Sit-outs go to
    ``regime_sitouts`` and are absent from the persisted ``plan``. A desk that
    counts ``plan`` therefore shows fewer overrides than the book. With six
    regime-gated override sit-outs, active overrides are book overrides minus
    those six (56 and 6 produce active 50) when nothing else dropped out.
    """
    from config.universe import Universe

    approvals: dict[str, Any] = {}
    if book is None:
        try:
            book = read_live_approval_book()
        except Exception:
            book = {}
    if isinstance(book, dict):
        raw = book.get("approvals")
        if isinstance(raw, dict):
            approvals = raw
    try:
        universe = Universe(approvals=approvals)
        book_approved = len(universe.approved_records)
        book_overrides = len(universe.paper_override_records)
    except Exception:
        book_approved = 0
        book_overrides = 0

    plan: list[dict[str, Any]] = []
    sitouts: list[dict[str, Any]] = []
    soko: str | None = None
    if isinstance(cycle, dict):
        plan = [row for row in (cycle.get("plan") or []) if isinstance(row, dict)]
        sitouts = [
            row for row in (cycle.get("regime_sitouts") or []) if isinstance(row, dict)
        ]
        raw_trend = cycle.get("soko_trend")
        if isinstance(raw_trend, str) and raw_trend.strip():
            soko = raw_trend.strip()

    # ``approved`` on a persisted plan row is pair-level (any approved sleeve
    # on that symbol+side). Count a row in only one half of "12+50".
    active_approved = sum(1 for row in plan if row.get("approved") is True)
    active_overrides = sum(
        1
        for row in plan
        if row.get("paper_override") is True and row.get("approved") is not True
    )
    sitting_out_overrides = 0
    for row in sitouts:
        key = row.get("key")
        record = approvals.get(key) if isinstance(key, str) else None
        if isinstance(record, dict) and record.get("paper_override") is True:
            sitting_out_overrides += 1

    return {
        "book_approved": book_approved,
        "book_overrides": book_overrides,
        "sitting_out_regime": len(sitouts),
        "sitting_out_overrides": sitting_out_overrides,
        "active_approved": active_approved,
        "active_overrides": active_overrides,
        "active": f"{active_approved}+{active_overrides}",
        "soko_trend": soko,
        "reconciles": active_overrides + sitting_out_overrides == book_overrides,
        "note": _SCAN_COUNT_NOTE,
    }


def desk_regime(path: Path | None = None, *, now: datetime | None = None) -> dict[str, Any]:
    """Live regime for the desk: the Soko file the engine gates on.

    ``read_live_soko_trend`` falls back to the regime-analyst snapshot when
    the file is missing or stale. This display does not. A dark file stays
    dark, and the old LLM row is only ``legacy_llm``. Employee prompts still
    call ``latest_regime()`` themselves.
    """
    payload = soko_display(path, now=now)
    legacy: dict[str, Any] | None = None
    try:
        from firm.memory import latest_regime

        snap = latest_regime()
        legacy = snap if isinstance(snap, dict) else None
    except Exception:
        legacy = None
    payload["legacy_llm"] = legacy
    return payload


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


def _number(value: Any) -> float | None:
    """Finite JSON number. Booleans are not counts or prices."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and value != value:
        return None
    return float(value)


def _f111_open_positions(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Open F111 floors from the paper state file. Not the hourly ledger."""
    if not isinstance(payload, dict):
        return []
    held = payload.get("protection") or {}
    if not isinstance(held, dict):
        return []
    rows: list[dict[str, Any]] = []
    for symbol, row in held.items():
        item = row if isinstance(row, dict) else {}
        side = item.get("side_name")
        if not isinstance(side, str) or not side.strip():
            sign = item.get("side")
            if sign == 1:
                side = "LONG"
            elif sign == -1:
                side = "SHORT"
            else:
                side = None
        rows.append(
            {
                "symbol": item.get("symbol") or str(symbol),
                "side": side,
                "quantity": _number(item.get("quantity")),
                "entry_price": _number(item.get("entry_price")),
                "mark_price": None,
                "stop": _number(item.get("initial_stop")),
                "target": _number(item.get("target")),
                "opened_at": item.get("opened_at") if isinstance(item.get("opened_at"), str) else None,
                "unrealised_pnl": None,
                "reason": None,
            }
        )
    return rows


def _f111_blotter(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Closed F111 paper exits recorded on telemetry. Display only."""
    closed: list[dict[str, Any]] = []
    for row in rows:
        if row.get("record_kind") == "registry" or row.get("deploy_marker"):
            continue
        realised = _number(row.get("realised_net_profit"))
        if realised is None:
            continue
        closed.append(
            {
                "symbol": row.get("symbol"),
                "side": row.get("side"),
                "quantity": _number(row.get("quantity")),
                "entry_price": _number(row.get("entry_price")),
                "exit_price": _number(row.get("simulated_fill")),
                "closed_at": row.get("quote_time") or row.get("source_signal_time"),
                "net_pnl": realised,
                "reason": row.get("rejection_reason") if isinstance(row.get("rejection_reason"), str) else None,
            }
        )
    return closed


def f111_status(
    *,
    now: datetime | None = None,
    telemetry_path: Path | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """F111 panel, served from the short desk cache when the scan is unchanged.

    A second request with the same book and scan id returns the first build,
    including ``computed_at`` and ``age``, instead of walking telemetry again.
    ``GET /api/f111`` calls this. The observer snapshot's F111 card does too,
    so those two share one build. The paper process does not call this.
    """
    from api.dashboard_cache import f111_cache_key, panel_cache

    key = f111_cache_key(telemetry_path, state_path)
    return panel_cache.fetch(
        "f111",
        key,
        lambda: _f111_status_uncached(
            now=now,
            telemetry_path=telemetry_path,
            state_path=state_path,
        ),
    )


def _f111_status_uncached(
    *,
    now: datetime | None = None,
    telemetry_path: Path | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """F111 panel: 192 sleeves, census split, gate reasons, retests.

    Source files are the configured state and telemetry paths
    (``data/f111_paper_state.json`` and ``data/f111_telemetry.jsonl``).
    On SGP1 those live under the state mount, typically
    ``/data/state/data/...``. The desk cache calls this once per scan.
    """
    from core.strategy.f111_config import STATE_PATH, TELEMETRY_PATH, load_f111_config

    moment = _as_utc(now or _utcnow())
    telemetry = Path(telemetry_path) if telemetry_path is not None else TELEMETRY_PATH
    state = Path(state_path) if state_path is not None else STATE_PATH
    expected = 192
    config: dict[str, Any] = {}
    digest: str | None = None
    config_error = None
    try:
        config, digest = load_f111_config()
        expected = int(config.get("expected_scan_sleeves") or 192)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        config_error = str(exc)
        config = {}
        digest = None

    # The fold, not the raw file. Repeated polls must not keep another copy.
    view = read_telemetry(telemetry, now=moment)
    available = view.available
    closed_by = view.closed_by
    closed = sum(closed_by.values())
    latest_hour_start = view.rej_hour
    latest_hour_end = (
        latest_hour_start + timedelta(hours=1) if latest_hour_start is not None else None
    )
    latest_hour_rows = [
        {"rejection_reason": reason}
        for stamp, reason in view.events
        if latest_hour_start is not None
        and latest_hour_end is not None
        and latest_hour_start <= stamp < latest_hour_end
    ]
    day_start = moment - timedelta(hours=24)
    last_day_rows = [
        {"rejection_reason": reason} for stamp, reason in view.events if stamp >= day_start
    ]
    bar_close = view.bar_close

    pending_retests = 0
    protection = 0
    state_error = None
    state_payload: dict[str, Any] | None = None
    if state.exists():
        try:
            payload = _read_json(state)
        except (json.JSONDecodeError, OSError) as exc:
            payload = None
            state_error = str(exc)
        if isinstance(payload, dict):
            state_payload = payload
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

    from api.why_no_trade import build_f111_why

    blotter = view.blotter
    why_no_trade = build_f111_why(view.why_rows, view.unavailable)
    realised_values = [view.realised_sum] if view.realised_count else []
    sizing_policy = None
    strategy_version = None
    if config_error is None and config:
        strategy_version = config.get("strategy_version")
        sizing_policy = config.get("sizing_policy") or strategy_version

    return {
        "expected_sleeves": expected,
        "config_error": config_error,
        "telemetry_path": str(telemetry),
        "state_path": str(state),
        "state_error": state_error,
        "registry": {
            "evaluated": view.evaluated,
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
        "last_scan_age_seconds": _age_seconds(bar_close, moment),
        "pending_retests": pending_retests,
        "protection": protection,
        # Observer card reads these. They are this sleeve's own state file,
        # not a query against the hourly blotter.
        "open_positions": _f111_open_positions(state_payload),
        "blotter": blotter[-30:],
        "paper_pnl": {
            "cash_usdt": None,
            "equity_usdt": None,
            "unrealized_usdt": None,
            "realized_usdt": sum(realised_values) if realised_values else None,
            "basis": "sum of realised_net_profit on F111 telemetry exits"
            if realised_values
            else "no realised F111 exits in telemetry",
        },
        "configuration_sha256": digest,
        "sizing_policy": sizing_policy,
        "strategy_version": strategy_version,
        "telemetry_present": telemetry.exists(),
        "why_no_trade": why_no_trade,
    }
