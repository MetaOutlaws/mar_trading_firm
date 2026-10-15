"""Load a sealed token-expansion batch for the Research tab.

The results file is read whole. A missing file or a sha256 that does not
match the configured seal raises ``ExpansionSealError`` and returns nothing.
Verdicts are taken only from the optional verdict file. When that file is
unset or missing, every row is PENDING. Profit factor is never a verdict.

FAIL, VETO, and PENDING rows are not eligible for the active strategies table.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT, get_settings

# Verdicts that must not be published on the active strategies table.
BLOCKED_VERDICTS = frozenset({"FAIL", "VETO", "PENDING"})
# Closed set. Anything else in the verdict file fails the whole response.
ALLOWED_VERDICTS = frozenset({"PASS", "FAIL", "VETO", "PENDING"})
_PF_STRINGS = frozenset({"", "inf", "nan"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ROW_FIELDS = (
    "batch",
    "rule",
    "side",
    "clock",
    "token",
    "verdict",
    "seal_sha",
    "pf_main",
    "trades_main",
    "pf_holdout",
    "trades_holdout",
    "pf_exploratory",
    "trades_exploratory",
)


class ExpansionSealError(Exception):
    """The results file cannot be served. Callers must not return rows."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _resolve(raw: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_trade_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_profit_factor(value: object) -> bool:
    if isinstance(value, str):
        return value in _PF_STRINGS
    return _is_number(value)


def _identity(rule: object, side: object, clock: object, token: object) -> tuple[str, str, str, str]:
    return (
        str(rule).strip(),
        str(side).strip().upper(),
        str(clock).strip(),
        str(token).strip(),
    )


def _require_document(document: object) -> dict[str, Any]:
    """Reject a document that is not a complete batch. No row is kept."""
    if not isinstance(document, dict):
        raise ExpansionSealError(422, "token expansion results file is not a JSON object")
    for key in ("batch", "cost_view", "rows"):
        if key not in document:
            raise ExpansionSealError(422, f"token expansion results file is missing {key}")
    if not isinstance(document["batch"], str) or not document["batch"].strip():
        raise ExpansionSealError(422, "token expansion results batch is empty")
    if not isinstance(document["cost_view"], str) or not document["cost_view"].strip():
        raise ExpansionSealError(422, "token expansion results cost_view is empty")
    rows = document["rows"]
    if not isinstance(rows, list):
        raise ExpansionSealError(422, "token expansion results rows is not a list")
    seen: set[tuple[str, str, str, str]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ExpansionSealError(422, f"token expansion row {index} is not an object")
        missing = [field for field in _ROW_FIELDS if field not in row]
        if missing:
            raise ExpansionSealError(
                422,
                f"token expansion row {index} is missing {', '.join(missing)}",
            )
        identity = _identity(row["rule"], row["side"], row["clock"], row["token"])
        if not all(identity):
            raise ExpansionSealError(422, f"token expansion row {index} has an empty identity")
        if identity in seen:
            raise ExpansionSealError(422, f"token expansion row {index} repeats {identity[0]} {identity[3]}")
        seen.add(identity)
        seal = row["seal_sha"]
        if not isinstance(seal, dict) or any(
            not isinstance(seal.get(phase), str) or _SHA256.fullmatch(seal.get(phase, "")) is None
            for phase in ("main", "holdout", "exploratory")
        ):
            raise ExpansionSealError(422, f"token expansion row {index} has a bad seal")
        for field in ("pf_main", "pf_holdout", "pf_exploratory"):
            if not _is_profit_factor(row[field]):
                raise ExpansionSealError(422, f"token expansion row {index} has a bad {field}")
        for field in ("trades_main", "trades_holdout", "trades_exploratory"):
            if not _is_trade_count(row[field]):
                raise ExpansionSealError(422, f"token expansion row {index} has a bad {field}")
    return document


def _load_verdict_map(raw_path: str) -> tuple[dict[tuple[str, str, str, str], str], str | None, bool]:
    """Return verdicts, the configured path, and whether the file was found.

    A blank path or a missing file is not an error: every row stays PENDING.
    A present file that cannot be read as a complete verdict map fails closed.
    """
    if not raw_path.strip():
        return {}, None, False
    path = _resolve(raw_path.strip())
    source = str(path)
    if not path.exists():
        return {}, source, False
    if not path.is_file():
        raise ExpansionSealError(422, "token expansion verdict path is not a file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExpansionSealError(422, "token expansion verdict file is not valid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("verdicts"), list):
        raise ExpansionSealError(422, "token expansion verdict file has no verdicts list")
    mapped: dict[tuple[str, str, str, str], str] = {}
    for index, entry in enumerate(payload["verdicts"]):
        if not isinstance(entry, dict):
            raise ExpansionSealError(422, f"token expansion verdict {index} is not an object")
        try:
            identity = _identity(entry["rule"], entry["side"], entry["clock"], entry["token"])
        except KeyError as exc:
            raise ExpansionSealError(422, f"token expansion verdict {index} is missing {exc.args[0]}") from exc
        if not all(identity):
            raise ExpansionSealError(422, f"token expansion verdict {index} has an empty identity")
        if identity in mapped:
            raise ExpansionSealError(422, f"token expansion verdict {index} repeats a row")
        raw_verdict = entry.get("verdict", "PENDING")
        if raw_verdict is None or (isinstance(raw_verdict, str) and not raw_verdict.strip()):
            verdict = "PENDING"
        elif isinstance(raw_verdict, str):
            verdict = raw_verdict.strip().upper()
        else:
            raise ExpansionSealError(422, f"token expansion verdict {index} is not text")
        if verdict not in ALLOWED_VERDICTS:
            raise ExpansionSealError(422, f"token expansion verdict {index} is not an allowed status")
        mapped[identity] = verdict
    return mapped, source, True


def _public_row(row: dict[str, Any], verdict: str) -> dict[str, Any]:
    """Copy metrics and attach the overlay verdict.

    The artifact's own ``verdict`` is not copied. ``pf_2026`` is the
    exploratory window under the name operators use for that seal.
    """
    return {
        "batch": row["batch"],
        "rule": row["rule"],
        "side": str(row["side"]).strip().upper(),
        "clock": row["clock"],
        "token": row["token"],
        "verdict": verdict,
        "pf_main": row["pf_main"],
        "trades_main": row["trades_main"],
        "pf_holdout": row["pf_holdout"],
        "trades_holdout": row["trades_holdout"],
        "pf_exploratory": row["pf_exploratory"],
        "trades_exploratory": row["trades_exploratory"],
        "pf_2026": row["pf_exploratory"],
        "trades_2026": row["trades_exploratory"],
        "seal_sha": {
            "main": row["seal_sha"]["main"],
            "holdout": row["seal_sha"]["holdout"],
            "exploratory": row["seal_sha"]["exploratory"],
        },
    }


def active_strategy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rows allowed onto an active-strategies list.

    FAIL, VETO, and PENDING never pass. A high profit factor does not.
    """
    allowed: list[dict[str, Any]] = []
    for row in rows:
        verdict = str(row.get("verdict") or "PENDING").strip().upper()
        if verdict in BLOCKED_VERDICTS:
            continue
        if verdict not in ALLOWED_VERDICTS:
            continue
        allowed.append(row)
    return allowed


def drop_blocked_expansion_pairs(pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove token-expansion rows whose verdict cannot be active.

    A live-book pair has no expansion source mark, so it stays. This does
    not rewrite the book and does not infer a verdict from profit factor.
    """
    kept: list[dict[str, Any]] = []
    for pair in pairs:
        marked = pair.get("source") == "token_expansion" or bool(pair.get("expansion_batch"))
        batch = pair.get("batch")
        if batch in {"C1", "token_expansion"}:
            marked = True
        if not marked:
            kept.append(pair)
            continue
        verdict = str(pair.get("verdict") or "PENDING").strip().upper()
        if verdict in BLOCKED_VERDICTS:
            continue
        kept.append(pair)
    return kept


def load_token_expansion() -> dict[str, Any]:
    """Read the configured results file and overlay verdicts.

    Raises ``ExpansionSealError`` instead of returning a partial row list
    when the file is missing, the seal does not match, or the document is
    not a complete batch.
    """
    settings = get_settings()
    raw_path = (settings.token_expansion_results_path or "").strip()
    if not raw_path:
        raise ExpansionSealError(404, "token expansion results path is not configured")
    path = _resolve(raw_path)
    if not path.is_file():
        raise ExpansionSealError(404, "token expansion results file is missing")
    expected = (settings.token_expansion_results_sha256 or "").strip().lower()
    if not expected:
        raise ExpansionSealError(409, "token expansion results sha256 is not configured")
    # One read. The hash and the parser see the same bytes.
    try:
        blob = path.read_bytes()
    except OSError as exc:
        raise ExpansionSealError(404, "token expansion results file is missing") from exc
    digest = hashlib.sha256(blob).hexdigest()
    if digest != expected:
        raise ExpansionSealError(
            409,
            "token expansion results sha256 does not match the configured seal "
            f"(file {digest}, configured {expected})",
        )
    try:
        document = json.loads(blob.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ExpansionSealError(422, "token expansion results file is not valid JSON") from exc
    checked = _require_document(document)
    verdicts, verdict_source, verdict_file_found = _load_verdict_map(
        settings.token_expansion_verdicts_path or ""
    )
    rows: list[dict[str, Any]] = []
    for row in checked["rows"]:
        identity = _identity(row["rule"], row["side"], row["clock"], row["token"])
        # The artifact verdict is ignored on purpose, including a stored PASS.
        verdict = verdicts.get(identity, "PENDING")
        rows.append(_public_row(row, verdict))
    active = active_strategy_rows(rows)
    counts = {
        "rows": len(rows),
        "pending": sum(1 for row in rows if row["verdict"] == "PENDING"),
        "fail": sum(1 for row in rows if row["verdict"] == "FAIL"),
        "veto": sum(1 for row in rows if row["verdict"] == "VETO"),
        "pass": sum(1 for row in rows if row["verdict"] == "PASS"),
        "active": len(active),
    }
    return {
        "ok": True,
        "batch": checked["batch"],
        "cost_view": checked["cost_view"],
        "results_path": str(path),
        "results_sha256": digest,
        "verdict_source": verdict_source,
        "verdict_file_found": verdict_file_found,
        "verdict_policy": (
            "Verdicts load only from TOKEN_EXPANSION_VERDICTS_PATH. "
            "A missing file is PENDING. Profit factor is not a verdict."
        ),
        "rows": rows,
        "active_strategies": active,
        "counts": counts,
        "note": (
            "Display only. FAIL, VETO, and PENDING stay off the active strategies "
            "table. This does not edit the approval book. Live stays off."
        ),
    }
