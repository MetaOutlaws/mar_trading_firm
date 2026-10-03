"""In-memory collision checks for offline host-book staging.

Paper books on the nyc3 and sgp1 droplets each allocate integer primary
keys inside their own SQLite (or Postgres) file. ``positions.id = 1`` on
nyc3 is a different position from ``positions.id = 1`` on sgp1. The cash
journal in ``data/paper_cash.json`` has the same split: a September
accounting epoch and an October accounting epoch are two ledgers, and
``replay_events`` will sum them if their event lists are concatenated.

This module only classifies rows the operator has already loaded into
memory. It does not open a database, a socket, or a file, and it does
not return a merged book. The write-up of the staging procedure is
``docs/OFFLINE_HOST_BOOK_STAGING.md``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

# Droplet labels. nyc3 is a read-only export source. sgp1 is the running
# book. Neither name is a legal write destination for this checker.
SOURCE_SERVERS = frozenset({"nyc3", "sgp1"})

# Accounting generations that must stay apart. These label a whole export,
# not the calendar month of each ``opened_at``.
ACCOUNTING_EPOCHS = frozenset({"2026-09", "2026-10"})

# Integer-keyed book tables. Other firm tables have the same class of
# hazard and are intentionally absent: this checker must not become a
# general host merge.
BOOK_TABLES = frozenset({"positions", "trades", "equity_snapshots", "cash_events"})

# The only destination labels that are not a host book. Empty means the
# caller is inventorying rows and is not proposing a write.
STAGING_DESTINATIONS = frozenset({"", "staging", "offline-staging"})

_IDENTITY_FIELDS = frozenset({"source_server", "epoch", "table", "id"})

# Ban-list, not a SQL parser. Patterns fail closed: a statement that
# merely *mentions* one of these forms is rejected.
_BANNED_MERGE_SQL = (
    re.compile(r"\bINSERT\s+OR\s+REPLACE\b", re.IGNORECASE),
    re.compile(r"\bREPLACE\s+INTO\b", re.IGNORECASE),
    re.compile(r"\bINSERT\s+OR\s+IGNORE\b", re.IGNORECASE),
    re.compile(r"\bON\s+CONFLICT\b[\s\S]*?\bDO\s+(?:UPDATE|NOTHING|REPLACE)\b", re.IGNORECASE),
)
# DROP / TRUNCATE / DELETE would destroy a host book. nyc3 must survive
# any later staging work, and sgp1 must not be edited in place.
_DESTRUCTIVE_SQL = (
    re.compile(r"\bDROP\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
)


@dataclass(frozen=True, order=True)
class CompositeIdentity:
    """Identity of one exported row.

    Inside a single table the key is ``source_server + epoch + row_id``.
    ``table`` is carried so ``positions.id`` is never compared with
    ``trades.id``; both sequences start at 1 on every host.
    """

    source_server: str
    epoch: str
    table: str
    row_id: int

    def as_key(self) -> tuple[str, str, int]:
        """The composite key within ``table``: source server, epoch, id."""
        return (self.source_server, self.epoch, self.row_id)


@dataclass(frozen=True)
class IdCollision:
    """One integer id claimed by more than one composite identity.

    This is the case ``INSERT OR REPLACE`` and a naive ``INSERT ... SELECT``
    on the primary key would collapse. Both identities must be kept.
    """

    table: str
    row_id: int
    identities: tuple[CompositeIdentity, ...]


@dataclass(frozen=True)
class CollisionReport:
    """Findings for one in-memory inventory.

    ``blocks_naive_merge`` means "do not write these rows as one book
    keyed by integer id, and do not replay their cash as one journal."
    It does not mean "delete a side." A collision is resolved by storing
    both rows under :class:`CompositeIdentity` in an offline staging file
    that is neither droplet.
    """

    id_collisions: tuple[IdCollision, ...]
    servers_present: tuple[str, ...]
    epochs_present: tuple[str, ...]
    host_mix: bool
    epoch_mix: bool
    duplicate_exports: tuple[CompositeIdentity, ...]
    payload_conflicts: tuple[CompositeIdentity, ...]
    banned_statement: bool
    destructive_statement: bool
    banned_destination: bool

    @property
    def blocks_naive_merge(self) -> bool:
        """True when a union, replace, or host write would corrupt a book."""
        return bool(
            self.id_collisions
            or self.host_mix
            or self.epoch_mix
            or self.payload_conflicts
            or self.banned_statement
            or self.destructive_statement
            or self.banned_destination
        )


def composite_identity(
    source_server: str,
    epoch: str,
    table: str,
    row_id: int,
) -> CompositeIdentity:
    """Build one composite identity, rejecting unknown labels.

    Unknown servers, epochs, and tables raise ``ValueError``. Guessing a
    label would silently invent a third book.
    """
    server = _require_label(source_server, SOURCE_SERVERS, "source_server")
    epoch_label = _require_label(epoch, ACCOUNTING_EPOCHS, "epoch")
    table_name = _require_label(table, BOOK_TABLES, "table")
    return CompositeIdentity(
        source_server=server,
        epoch=epoch_label,
        table=table_name,
        row_id=_require_row_id(row_id),
    )


def detect_book_collisions(
    rows: Sequence[Mapping[str, object]],
    *,
    statement: str = "",
    destination: str = "",
) -> CollisionReport:
    """Classify exported rows. Does not merge, drop, or rewrite them.

    Each row needs ``source_server``, ``epoch``, ``table``, and ``id``.
    For ``cash_events``, ``id`` is the 0-based index of that event inside
    the export that produced it. Do not renumber across hosts or epochs.

    ``statement`` is optional SQL text a human is considering. The banned
    forms (``INSERT OR REPLACE`` and the upserts that overwrite or drop)
    and the destructive forms (``DROP``, ``TRUNCATE``, ``DELETE FROM``)
    are flagged. Nothing is executed.

    ``destination`` is a label, not a path that is opened. ``staging``
    and ``offline-staging`` are the only write labels. ``nyc3``,
    ``sgp1``, and any other label are banned, so a typo cannot become a
    write onto a droplet. Empty destination means inventory only.
    """
    grouped: dict[CompositeIdentity, list[Mapping[str, object]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise TypeError("each row must be a mapping")
        identity = composite_identity(
            _required(row, "source_server"),
            _required(row, "epoch"),
            _required(row, "table"),
            _required(row, "id"),
        )
        grouped.setdefault(identity, []).append(row)

    duplicate_exports: list[CompositeIdentity] = []
    payload_conflicts: list[CompositeIdentity] = []
    for identity, copies in grouped.items():
        if len(copies) < 2:
            continue
        payloads = [_payload(copy) for copy in copies]
        if all(payload == payloads[0] for payload in payloads[1:]):
            duplicate_exports.append(identity)
        else:
            payload_conflicts.append(identity)

    by_integer_id: dict[tuple[str, int], list[CompositeIdentity]] = {}
    for identity in grouped:
        by_integer_id.setdefault((identity.table, identity.row_id), []).append(identity)

    id_collisions: list[IdCollision] = []
    for (table, row_id), identities in by_integer_id.items():
        distinct = {(item.source_server, item.epoch) for item in identities}
        if len(distinct) < 2:
            continue
        id_collisions.append(
            IdCollision(
                table=table,
                row_id=row_id,
                identities=tuple(sorted(identities)),
            )
        )

    servers = tuple(sorted({item.source_server for item in grouped}))
    epochs = tuple(sorted({item.epoch for item in grouped}))
    return CollisionReport(
        id_collisions=tuple(sorted(id_collisions, key=lambda item: (item.table, item.row_id))),
        servers_present=servers,
        epochs_present=epochs,
        host_mix=len(servers) > 1,
        epoch_mix=len(epochs) > 1,
        duplicate_exports=tuple(sorted(duplicate_exports)),
        payload_conflicts=tuple(sorted(payload_conflicts)),
        banned_statement=_matches_any(statement, _BANNED_MERGE_SQL),
        destructive_statement=_matches_any(statement, _DESTRUCTIVE_SQL),
        banned_destination=_destination_banned(destination),
    )


def _required(row: Mapping[str, object], field: str) -> object:
    if field not in row:
        raise ValueError(f"row is missing {field}")
    return row[field]


def _require_label(value: object, allowed: frozenset[str], field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    label = value.strip().lower()
    if field == "epoch":
        # Epochs are case-sensitive calendar labels; only trim whitespace.
        label = value.strip()
    if label not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"unknown {field} {value!r}; expected one of: {allowed_text}")
    return label


def _require_row_id(value: object) -> int:
    # ``bool`` is a subclass of ``int``; True would otherwise become id 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("id must be an int")
    if value < 0:
        raise ValueError("id must be >= 0")
    return value


def _payload(row: Mapping[str, object]) -> dict[str, object]:
    """Row body compared across duplicate exports.

    An explicit ``payload`` mapping wins. Otherwise every non-identity
    field is the body. Identity fields are not part of the body, so two
    exports of the same position still match.
    """
    if "payload" in row:
        payload = row["payload"]
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        return dict(payload)
    return {key: row[key] for key in row if key not in _IDENTITY_FIELDS}


def _matches_any(statement: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    if not isinstance(statement, str):
        raise TypeError("statement must be a string")
    if statement.strip() == "":
        return False
    return any(pattern.search(statement) for pattern in patterns)


def _destination_banned(destination: str) -> bool:
    if not isinstance(destination, str):
        raise TypeError("destination must be a string")
    token = destination.strip().lower().replace("_", "-")
    token = " ".join(token.split())
    if token in STAGING_DESTINATIONS:
        return False
    # Fail closed. Naming nyc3 or sgp1 is banned, and so is any label
    # this checker does not explicitly recognise as offline staging.
    return True
