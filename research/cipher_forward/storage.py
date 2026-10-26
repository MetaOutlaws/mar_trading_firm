"""Disk and ledger limits for the isolated paper service.

The main paper database shares this host. A full cipher-forward ledger must
not be what fills that volume. Thresholds are explicit so an operator can see
them in logs and in status.json; they are not strategy risk limits.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sys


# Below this much free space, stop writing and disable entries. 2 GiB matches
# the operator note in docs/cipher-forward/DEPLOYMENT.md.
MIN_FREE_BYTES = 2 * 1024 ** 3
# Append-only history is kept inside this SQLite size (db + wal + shm).
LEDGER_MAX_BYTES = 1 * 1024 ** 3
# Observations, equity samples, and stored cycle/history payloads older than
# this are eligible for retention. Positions, cash, decisions and signal rows
# are not.
LEDGER_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000
# Host path of the running paper book. The container sees the same volume
# through the read-only /main-paper mount.
DEFAULT_MAIN_PAPER_DB = Path('/data/state/data/firm.db')
CONTAINER_MAIN_PAPER_DB = Path('/main-paper/firm.db')


class StorageWriteBlocked(RuntimeError):
    """Raised when a ledger write is refused to keep the disk from filling."""


@dataclass(frozen=True)
class StorageSettings:
    min_free_bytes: int
    ledger_max_bytes: int
    ledger_max_age_ms: int
    main_paper_db: Path


@dataclass(frozen=True)
class StorageDecision:
    blocked: bool
    reason: str
    main_free_bytes: int | None
    ledger_free_bytes: int | None
    ledger_bytes: int
    main_volume: str | None
    ledger_volume: str | None
    over_size: bool


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == '':
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f'{name} must be a positive integer') from exc
    if value <= 0:
        raise ValueError(f'{name} must be a positive integer')
    return value


def storage_settings_from_env() -> StorageSettings:
    """Read operator overrides. Unset variables keep the documented defaults."""
    raw_path = os.environ.get('CIPHER_FORWARD_MAIN_PAPER_DB', '').strip()
    if raw_path:
        main = Path(raw_path)
    elif Path('/main-paper').exists():
        main = CONTAINER_MAIN_PAPER_DB
    else:
        main = DEFAULT_MAIN_PAPER_DB
    return StorageSettings(
        min_free_bytes=_positive_int('CIPHER_FORWARD_MIN_FREE_BYTES', MIN_FREE_BYTES),
        ledger_max_bytes=_positive_int('CIPHER_FORWARD_LEDGER_MAX_BYTES', LEDGER_MAX_BYTES),
        ledger_max_age_ms=_positive_int('CIPHER_FORWARD_LEDGER_MAX_AGE_MS', LEDGER_MAX_AGE_MS),
        main_paper_db=main,
    )


def existing_volume(path: Path) -> Path:
    """Nearest existing file or directory whose free space is the volume's.

    Walking all the way to the filesystem root would report the wrong disk
    when the paper data mount is absent, so the root is not a valid answer.
    """
    candidate = Path(path)
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate or parent == Path(candidate.anchor):
            raise OSError(f'cannot measure volume for {path}')
        candidate = parent
    if candidate == Path(candidate.anchor):
        raise OSError(f'cannot measure volume for {path}')
    return candidate


def ledger_nbytes(path: Path) -> int:
    """Bytes of the SQLite file plus its WAL and shared-memory sidecar."""
    path = Path(path)
    total = 0
    for candidate in (path, Path(str(path) + '-wal'), Path(str(path) + '-shm')):
        try:
            total += candidate.stat().st_size
        except FileNotFoundError:
            continue
    return total


def assess_storage(ledger_path, main_paper_db, *, min_free_bytes: int, ledger_max_bytes: int,
                   free_bytes=None, volume_of=None) -> StorageDecision:
    """Decide whether ledger writes are safe.

    Free space on the main paper database volume is always measured. Free
    space on the ledger volume is measured too, so a separate state disk
    cannot fill unnoticed and a shared disk cannot be checked only via the
    service directory.
    """
    free_bytes = free_bytes or (lambda path: shutil.disk_usage(path).free)
    volume_of = volume_of or existing_volume
    ledger_path = Path(ledger_path)
    main_paper_db = Path(main_paper_db)
    size = ledger_nbytes(ledger_path) if ledger_path.exists() else 0
    main_volume = ledger_volume = None
    main_free = ledger_free = None
    main_error = ledger_error = None
    try:
        main_volume = str(volume_of(main_paper_db))
        main_free = int(free_bytes(Path(main_volume)))
    except (OSError, ValueError) as exc:
        main_error = str(exc)
    try:
        ledger_volume = str(volume_of(ledger_path if ledger_path.exists() else ledger_path.parent))
        ledger_free = int(free_bytes(Path(ledger_volume)))
    except (OSError, ValueError) as exc:
        ledger_error = str(exc)
    over_size = size > ledger_max_bytes
    reasons = []
    if main_error:
        reasons.append(
            f'cannot measure main paper DB volume at {main_paper_db}: {main_error}')
    elif main_free is not None and main_free < min_free_bytes:
        reasons.append(
            f'main paper DB volume {main_volume} has {main_free} bytes free, '
            f'below {min_free_bytes}')
    if ledger_error:
        reasons.append(f'cannot measure ledger volume at {ledger_path}: {ledger_error}')
    elif ledger_free is not None and ledger_free < min_free_bytes:
        reasons.append(
            f'ledger volume {ledger_volume} has {ledger_free} bytes free, '
            f'below {min_free_bytes}')
    blocked = bool(reasons)
    if blocked:
        reason = (
            'stopping ledger writes and disabling entries to protect the main '
            f'paper DB; {"; ".join(reasons)}')
    else:
        reason = ''
    return StorageDecision(
        blocked=blocked, reason=reason, main_free_bytes=main_free,
        ledger_free_bytes=ledger_free, ledger_bytes=size,
        main_volume=main_volume, ledger_volume=ledger_volume, over_size=over_size)


def loud(reason: str) -> None:
    """One journal line. Docker collects stderr, so this is the operator log."""
    print(f'ERROR cipher-forward storage guard: {reason}', file=sys.stderr, flush=True)


class GuardAnnouncer:
    """Repeat the halt about once a minute so the log stays loud but bounded."""

    def __init__(self):
        self.last_ms = None
        self.reason = None

    def announce(self, reason: str, now_ms: int) -> bool:
        if (reason == self.reason and self.last_ms is not None
                and now_ms - self.last_ms < 60_000):
            return False
        loud(reason)
        self.last_ms = now_ms
        self.reason = reason
        return True


def disable_entries(state_dir: Path) -> None:
    """Create the existing entry-halt file. Do not remove it automatically."""
    flag = Path(state_dir) / 'entries_disabled'
    if not flag.exists():
        flag.touch(mode=0o600)
