"""Live Soko trend label for paper regime sit-outs.

The desk does not yet have a dedicated Soko client in-repo. This module is the
injectable hook:

1. ``data/last_soko_trend.json`` (same pattern as Luke's last_sentiment.json)
2. Else the latest regime-analyst snapshot (``memory.latest_regime()``)

Supports:

* Legacy single-label blobs (``trend`` / ``regime`` / ``btc_trend`` …)
* ``soko_trend_v1`` with ``pairs[].trend`` per symbol and optional
  ``sleeves[].activation`` (``ON`` | ``SIT_OUT``)

``read_live_soko_trend()`` still returns one lowercased label (or None) for
callers/tests that expect a global string. Paper ``build_plan`` should prefer
``read_soko_trend_for_symbol`` / ``read_soko_sleeve_activation`` so sit-outs
follow the Asia tape per pair rather than a single global trend.
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
    """Map SYMBOL -> lowercased trend from ``pairs[]`` (soko_trend_v1)."""
    out: dict[str, str] = {}
    pairs = blob.get("pairs")
    if not isinstance(pairs, list):
        return out
    for row in pairs:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "").strip().upper()
        label = normalize_trend_label(row.get("trend"))
        if sym and label:
            out[sym] = label
    return out


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


def _read_soko_file(path: Path) -> str | None:
    data = _load_soko_blob(path)
    if data is None:
        return None
    if isinstance(data, str):
        return normalize_trend_label(data)
    if isinstance(data, dict):
        # Legacy / top-level first.
        top = _label_from_blob(data)
        if top:
            return top
        # v1 without top-level: prefer BTC pair as a coarse global hint only.
        pairs = _pairs_trend_map(data)
        for prefer in ("BTCUSDT", "BTC"):
            if prefer in pairs:
                return pairs[prefer]
        if len(pairs) == 1:
            return next(iter(pairs.values()))
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
    """Lowercased live Soko/desk trend, or None when the feed is missing.

    For ``soko_trend_v1`` without a top-level trend, falls back to BTC's
    ``pairs[].trend`` when present. Prefer ``read_soko_trend_for_symbol`` for
    paper sit-out decisions.
    """
    dest = path or LAST_SOKO_TREND_PATH
    label = _read_soko_file(dest)
    if label:
        return label
    return _read_regime_snapshot()


def read_soko_trend_for_symbol(
    symbol: str,
    path: Path | None = None,
) -> str | None:
    """Per-symbol trend from ``pairs[]`` (v1), else global ``read_live_soko_trend``.

    Matching is case-insensitive on symbol (``BTCUSDT``).
    """
    dest = path or LAST_SOKO_TREND_PATH
    sym = str(symbol or "").strip().upper()
    data = _load_soko_blob(dest)
    if isinstance(data, dict):
        pairs = _pairs_trend_map(data)
        if sym and sym in pairs:
            return pairs[sym]
        # Also accept bare base (BTC) if file used it.
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
