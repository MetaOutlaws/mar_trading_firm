"""
Luke-fed Crypto Twitter sentiment snapshot.

The Sentiment tab must work on the paper box without XAI_API_KEY or an X API
key. Luke's scraper writes `data/last_sentiment.json`; this module loads it the
same way positioning loads `data/last_positioning.json`.

xAI Grok search (SentimentAnalyst) stays an optional fallback when a key exists
and the file is missing or stale.

Write path (atomic — copy this if you write the file from another process):

    dest = data/last_sentiment.json
    tmp  = dest + ".tmp"
    write JSON to tmp, flush, fsync, then os.replace(tmp, dest)

A crash mid-write must never leave a truncated snapshot the desk would parse.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

LAST_SENTIMENT_PATH = PROJECT_ROOT / "data" / "last_sentiment.json"

#: Prefer the file over SQLite while the snapshot is this fresh.
CACHE_TTL = timedelta(minutes=30)

VALID_MOODS = frozenset({"risk_on", "risk_off", "chop", "greed", "fear"})
VALID_HYPE = frozenset({"building", "peaking", "exhausted", "fading", "absent"})
VALID_BIAS = frozenset({"bullish", "bearish", "neutral"})

#: Bybit linear symbols: BTCUSDT, 1000PEPEUSDT, etc.
_BYBIT_SYMBOL = re.compile(r"^[A-Z0-9]{3,24}$")


class SentimentSchemaError(ValueError):
    """Luke snapshot failed the desk contract."""


class SentimentReadingModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    symbol: str
    score: float = Field(ge=-1.0, le=1.0)
    hype_stage: str
    narrative: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)
    price_at_reading: float = 0.0

    @field_validator("symbol", mode="before")
    @classmethod
    def _symbol_bybit(cls, value: Any) -> str:
        symbol = str(value or "").strip().upper()
        if not _BYBIT_SYMBOL.match(symbol):
            raise ValueError(f"symbol must be Bybit-style (e.g. BTCUSDT), got {value!r}")
        return symbol

    @field_validator("hype_stage", mode="before")
    @classmethod
    def _hype(cls, value: Any) -> str:
        stage = str(value or "").strip().lower()
        if stage not in VALID_HYPE:
            raise ValueError(f"hype_stage must be one of {sorted(VALID_HYPE)}")
        return stage

    @field_validator("sources", mode="before")
    @classmethod
    def _sources(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return []


class TrendingTokenModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    token: str
    symbol: str
    rank: int = 0
    mentions: int = 0
    score: float = Field(default=0.0, ge=-1.0, le=1.0)

    @field_validator("token", "symbol", mode="before")
    @classmethod
    def _upper(cls, value: Any) -> str:
        return str(value or "").strip().upper()

    @field_validator("symbol")
    @classmethod
    def _symbol_bybit(cls, value: str) -> str:
        if not _BYBIT_SYMBOL.match(value):
            raise ValueError(f"trending.symbol must be Bybit-style, got {value!r}")
        return value


class InfluencerModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    handle: str
    bias: str
    followers: int = 0
    note: str = ""

    @field_validator("handle", mode="before")
    @classmethod
    def _handle(cls, value: Any) -> str:
        handle = str(value or "").strip()
        if handle.startswith("@"):
            handle = handle[1:]
        if not handle:
            raise ValueError("influencer handle is required")
        return handle

    @field_validator("bias", mode="before")
    @classmethod
    def _bias(cls, value: Any) -> str:
        bias = str(value or "").strip().lower()
        if bias not in VALID_BIAS:
            raise ValueError(f"bias must be one of {sorted(VALID_BIAS)}")
        return bias


class SentimentSnapshotModel(BaseModel):
    """On-disk contract for `data/last_sentiment.json`."""

    model_config = ConfigDict(extra="ignore")

    as_of: str
    source: str = "luke_ct_scraper"
    model: str = "ct-scraper"
    market_narrative: str = ""
    mood: str
    readings: list[SentimentReadingModel] = Field(default_factory=list)
    trending: list[TrendingTokenModel] = Field(default_factory=list)
    influencers: list[InfluencerModel] = Field(default_factory=list)

    @field_validator("mood", mode="before")
    @classmethod
    def _mood(cls, value: Any) -> str:
        mood = str(value or "").strip().lower()
        if mood not in VALID_MOODS:
            raise ValueError(f"mood must be one of {sorted(VALID_MOODS)}")
        return mood

    @field_validator("as_of")
    @classmethod
    def _as_of_iso(cls, value: str) -> str:
        if parse_iso(value) is None:
            raise ValueError("as_of must be ISO-8601")
        return value


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def snapshot_is_fresh(
    blob: dict[str, Any] | None,
    *,
    now: datetime | None = None,
    ttl: timedelta = CACHE_TTL,
) -> bool:
    """True when `as_of` is within TTL. Missing/invalid timestamps are stale."""
    if not blob:
        return False
    as_of = parse_iso(blob.get("as_of"))
    if as_of is None:
        return False
    clock = now or datetime.now(timezone.utc)
    return clock - as_of <= ttl


def _keep_valid(items: Any, model: type[BaseModel], label: str) -> list[dict[str, Any]]:
    """Drop individual bad rows instead of rejecting Luke's whole file."""
    kept: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return kept
    for item in items:
        try:
            kept.append(model.model_validate(item).model_dump())
        except Exception as exc:
            logger.warning("Dropping invalid sentiment %s: %s", label, exc)
    return kept


def validate_sentiment_blob(data: Any) -> dict[str, Any]:
    """Return a normalised snapshot dict, or raise SentimentSchemaError.

    Top-level `as_of` and `mood` are required. Invalid readings / trending /
    influencers are dropped so one bad row cannot darken the desk.
    """
    if not isinstance(data, dict):
        raise SentimentSchemaError("sentiment snapshot must be a JSON object")
    cleaned = dict(data)
    cleaned["readings"] = _keep_valid(data.get("readings"), SentimentReadingModel, "reading")
    cleaned["trending"] = _keep_valid(data.get("trending"), TrendingTokenModel, "trending")
    cleaned["influencers"] = _keep_valid(data.get("influencers"), InfluencerModel, "influencer")
    try:
        parsed = SentimentSnapshotModel.model_validate(cleaned)
    except Exception as exc:
        raise SentimentSchemaError(str(exc)) from exc
    return parsed.model_dump()


def persist_sentiment(blob: dict[str, Any], path: Path | None = None) -> None:
    """Atomic write-then-rename so a crash cannot leave a truncated snapshot."""
    dest = path or LAST_SENTIMENT_PATH
    normalised = validate_sentiment_blob(blob)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    payload = json.dumps(normalised, indent=2)
    try:
        with tmp.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, dest)
    except OSError as exc:
        logger.warning("Could not persist sentiment snapshot: %s", exc)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def load_last_sentiment(path: Path | None = None) -> dict[str, Any] | None:
    """Load Luke's snapshot. None if missing, unreadable, or schema-invalid.

    Does not apply TTL — same split as positioning (`load` vs cache freshness).
    Floor / `/api/sentiment` call `desk_snapshot` to prefer a fresh file.
    """
    dest = path or LAST_SENTIMENT_PATH
    if not dest.exists():
        return None
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Unreadable sentiment snapshot %s: %s", dest, exc)
        return None
    try:
        return validate_sentiment_blob(data)
    except SentimentSchemaError as exc:
        logger.warning("Invalid sentiment snapshot %s: %s", dest, exc)
        return None


def empty_desk_payload(*, empty_reason: str = "missing") -> dict[str, Any]:
    return {
        "as_of": None,
        "source": "",
        "model": "",
        "fresh": False,
        "stale": False,
        "empty_reason": empty_reason,
        "market_narrative": "",
        "mood": "",
        "readings": [],
        "trending": [],
        "influencers": [],
    }


def _reading_row(item: dict[str, Any], *, recorded_at: str, model: str) -> dict[str, Any]:
    """Shape that matches `memory.latest_sentiment` so the heatmap stays shared."""
    return {
        "symbol": item.get("symbol"),
        "score": round(float(item.get("score") or 0.0), 3),
        "narrative": item.get("narrative") or "",
        "hype_stage": item.get("hype_stage") or "",
        "confidence": round(float(item.get("confidence") or 0.0), 3),
        "sources": item.get("sources") or [],
        "recorded_at": recorded_at,
        "price_at_reading": float(item.get("price_at_reading") or 0.0),
        "forward_return_4h": None,
        "forward_return_24h": None,
        "model": model,
    }


def desk_snapshot(
    sqlite_readings: list[dict[str, Any]] | None = None,
    *,
    path: Path | None = None,
    now: datetime | None = None,
    ttl: timedelta = CACHE_TTL,
    on_import: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Floor / API payload: fresh Luke file beats SQLite; extras always from file.

    * Fresh file (as_of within TTL): heatmap readings come from the file.
    * Stale or missing file: heatmap readings fall back to SQLite.
    * mood / narrative / trending / influencers come from the file whenever it
      parsed, even if stale, so the last known CT tape is still visible.
    * `on_import` runs when the file loaded so callers can copy readings into
      `memory.record_sentiment` for forward-return history.
    """
    blob = load_last_sentiment(path)
    clock = now or datetime.now(timezone.utc)
    fresh = snapshot_is_fresh(blob, now=clock, ttl=ttl)
    sqlite_readings = list(sqlite_readings or [])

    if blob is not None and on_import is not None:
        try:
            on_import(blob)
        except Exception:
            logger.exception("Sentiment snapshot import into SQLite failed")

    extras_source = blob or {}
    as_of = extras_source.get("as_of")
    model = extras_source.get("model") or ""
    source = extras_source.get("source") or ""

    if fresh and blob is not None:
        recorded_at = str(as_of or clock.isoformat())
        readings = [
            _reading_row(item, recorded_at=recorded_at, model=model or "ct-scraper")
            for item in (blob.get("readings") or [])
        ]
        used_source = source or "luke_ct_scraper"
    else:
        readings = sqlite_readings
        used_source = "sqlite" if readings else (source or "")

    has_extras = bool(
        (extras_source.get("market_narrative") or "").strip()
        or extras_source.get("mood")
        or extras_source.get("trending")
        or extras_source.get("influencers")
    )
    empty_reason = ""
    if not readings and not has_extras:
        if blob is None:
            empty_reason = "missing"
        elif not fresh:
            empty_reason = "stale"

    return {
        "as_of": as_of,
        "source": used_source,
        "model": model,
        "fresh": fresh,
        "stale": bool(blob) and not fresh,
        "empty_reason": empty_reason,
        "market_narrative": extras_source.get("market_narrative") or "",
        "mood": extras_source.get("mood") or "",
        "readings": readings,
        "trending": extras_source.get("trending") or [],
        "influencers": extras_source.get("influencers") or [],
    }


def import_snapshot_if_newer(blob: dict[str, Any]) -> int:
    """Copy file readings into `sentiment_scores` when the snapshot is newer.

    Dashboard polls must not duplicate rows: we compare file `as_of` to the
    newest SQLite `recorded_at`. Returns the number of rows inserted.
    """
    from firm import memory

    as_of = parse_iso(blob.get("as_of"))
    if as_of is None:
        return 0
    latest = memory.latest_sentiment(limit=1)
    if latest:
        previous = parse_iso(latest[0].get("recorded_at"))
        if previous is not None and previous >= as_of:
            return 0
    model = str(blob.get("model") or "ct-scraper")
    inserted = 0
    for item in blob.get("readings") or []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        memory.record_sentiment(
            symbol=symbol,
            score=float(item.get("score") or 0.0),
            narrative=str(item.get("narrative") or ""),
            hype_stage=str(item.get("hype_stage") or ""),
            confidence=float(item.get("confidence") or 0.0),
            sources=list(item.get("sources") or []),
            model=model,
            price_at_reading=float(item.get("price_at_reading") or 0.0),
            recorded_at=as_of,
        )
        inserted += 1
    return inserted


def sentiment_for_desk(
    *,
    path: Path | None = None,
    now: datetime | None = None,
    import_to_memory: bool = True,
) -> dict[str, Any]:
    """What `/api/floor` and `/api/sentiment` return for the Sentiment tab."""
    from firm import memory

    if import_to_memory:
        blob = load_last_sentiment(path)
        if blob is not None:
            try:
                import_snapshot_if_newer(blob)
            except Exception:
                logger.exception("Sentiment snapshot import into SQLite failed")
    return desk_snapshot(
        memory.latest_sentiment(limit=20),
        path=path,
        now=now,
        on_import=None,
    )
