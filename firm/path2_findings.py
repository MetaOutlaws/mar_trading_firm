"""Path2 findings table for the Research page.

The desk reads ``data/research/path2_findings.json`` and renders it. This
module does not score cells, does not read briefs, and does not invent a
count, a rate, or a PASS/FAIL.

Rows are added only from a Marcus-sealed table, not from briefs. A metric
that is absent stays null so the page can mark it missing. ``green_year_note``
is a note and is never copied into ``verdict``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT

#: Marcus-sealed rows only. Not a live brief reader.
PATH2_FINDINGS_PATH = PROJECT_ROOT / "data" / "research" / "path2_findings.json"

#: Same sentence as the data file, so a missing file still states the rule.
SEALED_TABLE_NOTE = (
    "Rows are added only from a Marcus-sealed table, not from briefs."
)

#: Both sides of a cell. The page always renders these two, in this order.
SIDES = ("long", "short")

#: Metric columns, in research-page order, after the frozen thresholds.
METRIC_KEYS = (
    "n",
    "target_first_count",
    "target_first_rate",
    "gross",
    "net_after_0_31_rt",
    "same_shell_h18_base_net",
    "stress_stop_2_net",
)

#: Preferred order when a cell stores threshold pieces instead of a label.
_THRESHOLD_FIRST = ("target", "stop", "horizon")

#: The only verdict tokens the page will show. Anything else stays missing.
_VERDICTS = frozenset({"PASS", "FAIL"})


def empty_path2_findings(*, load_error: str | None = None) -> dict[str, Any]:
    """Zero-row payload. Used when the file is missing or unreadable."""
    return {
        "note": SEALED_TABLE_NOTE,
        "sealed": False,
        "cells": [],
        "load_error": load_error,
    }


def load_path2_findings(path: Path | None = None) -> dict[str, Any]:
    """Read the findings file. Never invent a cell, a rate, or a verdict."""
    src = path or PATH2_FINDINGS_PATH
    if not src.is_file():
        return empty_path2_findings(load_error="findings file is missing")
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return empty_path2_findings(load_error=f"findings file could not be read: {exc}")
    if not isinstance(raw, dict):
        return empty_path2_findings(load_error="findings file must be a JSON object")

    note = raw.get("note")
    note_text = note.strip() if isinstance(note, str) and note.strip() else SEALED_TABLE_NOTE
    # Only a real boolean true counts. A string or a missing key is not sealed.
    sealed = raw.get("sealed") is True
    cells_raw = raw.get("cells", [])
    if not isinstance(cells_raw, list):
        return {
            "note": note_text,
            "sealed": sealed,
            "cells": [],
            "load_error": "cells must be a list",
        }

    cells: list[dict[str, Any]] = []
    for index, item in enumerate(cells_raw):
        normalized = _normalize_cell(item, index)
        if normalized is not None:
            cells.append(normalized)
    return {
        "note": note_text,
        "sealed": sealed,
        "cells": cells,
        "load_error": None,
    }


def _normalize_cell(item: Any, index: int) -> dict[str, Any] | None:
    """One scored cell, with long and short always present."""
    if not isinstance(item, dict):
        return None
    sides_raw = item.get("sides")
    if not isinstance(sides_raw, dict):
        sides_raw = {}
    cell_id = _text(item.get("id")) or f"cell-{index + 1}"
    return {
        "id": cell_id,
        "family": _text(item.get("family")),
        "clock": _text(item.get("clock")),
        "thresholds_label": _thresholds_label(item.get("thresholds")),
        # Verdict is the sealed token only. The green-year note is not an input.
        "verdict": _verdict(item.get("verdict")),
        "green_year_note": _text(item.get("green_year_note")),
        "sides": {side: _normalize_side(sides_raw.get(side)) for side in SIDES},
    }


def _normalize_side(raw: Any) -> dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    return {key: _metric(src.get(key)) for key in METRIC_KEYS}


def _verdict(value: Any) -> str | None:
    """PASS or FAIL, exactly. Other words, including a green-year note, are blank."""
    if not isinstance(value, str):
        return None
    token = value.strip()
    if token in _VERDICTS:
        return token
    return None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _metric(value: Any) -> int | float | str | None:
    """Keep a sealed scalar. Drop values we would have to interpret or invent."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _thresholds_label(raw: Any) -> str | None:
    """Operator line for the frozen thresholds. Null when the cell has none."""
    if isinstance(raw, str):
        return _text(raw)
    if not isinstance(raw, dict):
        return None
    label = _text(raw.get("label"))
    if label:
        return label
    parts: list[str] = []
    seen = set(_THRESHOLD_FIRST)
    for key in _THRESHOLD_FIRST:
        piece = _metric(raw.get(key))
        if piece is None:
            continue
        parts.append(f"{key} {piece}")
    for key in sorted(raw):
        if key in seen or key == "label":
            continue
        piece = _metric(raw.get(key))
        if piece is None:
            continue
        parts.append(f"{key} {piece}")
    if not parts:
        return None
    return " · ".join(parts)
