"""Live Soko trend label for paper regime sit-outs.

The desk does not yet have a dedicated Soko client in-repo. This module is the
injectable hook:

1. ``data/last_soko_trend.json`` (same pattern as Luke's last_sentiment.json)
2. Else the latest regime-analyst snapshot (``memory.latest_regime()``)

Returns a lowercased label (``bull`` / ``bear`` / ``chop``, or the raw
lowercased string). ``None`` means the feed is dark — paper ``build_plan``
then fail-closes regime-gated sleeves so we do not trade blind.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT

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


def normalize_trend_label(raw: Any) -> str | None:
    """Lowercase a trend/regime label and map common aliases."""
    if raw is None:
        return None
    name = str(raw).strip().lower()
    if not name:
        return None
    return TREND_ALIASES.get(name, name)


def _label_from_blob(blob: dict[str, Any]) -> str | None:
    """Accept a few key names so a human-written file still works."""
    for key in ("trend", "soko_trend", "label", "regime", "btc_trend"):
        label = normalize_trend_label(blob.get(key))
        if label:
            return label
    return None


def _read_soko_file(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Unreadable Soko trend file %s: %s", path, exc)
        return None
    if isinstance(data, str):
        return normalize_trend_label(data)
    if isinstance(data, dict):
        return _label_from_blob(data)
    return None


def _read_regime_snapshot() -> str | None:
    """Desk path already used by /api/regime and the Floor."""
    try:
        from firm.memory import latest_regime

        snap = latest_regime()
    except Exception as exc:
        # Missing table / uninitialized DB is a dark feed, not a crash.
        logger.warning("Could not read latest regime snapshot for Soko trend: %s", exc)
        return None
    if not isinstance(snap, dict):
        return None
    return _label_from_blob(snap)


def read_live_soko_trend(path: Path | None = None) -> str | None:
    """Lowercased live Soko/desk trend, or None when the feed is missing."""
    dest = path or LAST_SOKO_TREND_PATH
    label = _read_soko_file(dest)
    if label:
        return label
    return _read_regime_snapshot()
