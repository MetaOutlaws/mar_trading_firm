"""Luke CT sentiment snapshot: load preference, TTL, and schema."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.data.sentiment import (
    CACHE_TTL,
    SentimentSchemaError,
    desk_snapshot,
    import_snapshot_if_newer,
    load_last_sentiment,
    persist_sentiment,
    snapshot_is_fresh,
    validate_sentiment_blob,
)
from config.settings import PROJECT_ROOT


def _as_of(age: timedelta | None = None) -> str:
    stamp = datetime.now(timezone.utc)
    if age is not None:
        stamp -= age
    return stamp.isoformat()


def _blob(**overrides: object) -> dict:
    base: dict = {
        "as_of": _as_of(),
        "source": "luke_ct_scraper",
        "model": "ct-scraper",
        "market_narrative": "Majors two-way, memes quieter.",
        "mood": "chop",
        "readings": [
            {
                "symbol": "BTCUSDT",
                "score": 0.35,
                "hype_stage": "building",
                "narrative": "Range defence",
                "confidence": 0.6,
                "sources": ["https://x.com/example/status/1"],
                "price_at_reading": 0,
            }
        ],
        "trending": [
            {"token": "BTC", "symbol": "BTCUSDT", "rank": 1, "mentions": 120, "score": 0.4}
        ],
        "influencers": [
            {"handle": "example_macro", "bias": "bullish", "followers": 1000, "note": "bid"}
        ],
    }
    base.update(overrides)
    return base


def _write(path: Path, blob: dict) -> None:
    path.write_text(json.dumps(blob), encoding="utf-8")


def test_example_file_matches_contract() -> None:
    example = PROJECT_ROOT / "data" / "last_sentiment.example.json"
    data = json.loads(example.read_text(encoding="utf-8"))
    parsed = validate_sentiment_blob(data)
    assert parsed["source"] == "luke_ct_scraper"
    assert parsed["mood"] == "chop"
    assert parsed["headline"]
    assert parsed["takeaways"][0].startswith("Watch:")
    assert parsed["takeaways"][1].startswith("Fit:")
    assert parsed["readings"][0]["symbol"] == "BTCUSDT"
    assert -1.0 <= parsed["readings"][0]["score"] <= 1.0


def test_validate_rejects_bad_mood() -> None:
    with pytest.raises(SentimentSchemaError):
        validate_sentiment_blob(_blob(mood="to_the_moon"))


def test_validate_rejects_bad_as_of() -> None:
    with pytest.raises(SentimentSchemaError):
        validate_sentiment_blob(_blob(as_of="not-a-timestamp"))


def test_validate_drops_out_of_range_score_keeps_rest() -> None:
    blob = _blob(
        readings=[
            {
                "symbol": "BTCUSDT",
                "score": 1.5,
                "hype_stage": "building",
                "narrative": "too hot",
                "confidence": 0.5,
                "sources": [],
                "price_at_reading": 0,
            },
            {
                "symbol": "ETHUSDT",
                "score": -0.2,
                "hype_stage": "fading",
                "narrative": "ok",
                "confidence": 0.4,
                "sources": [],
                "price_at_reading": 0,
            },
        ]
    )
    parsed = validate_sentiment_blob(blob)
    symbols = [row["symbol"] for row in parsed["readings"]]
    assert symbols == ["ETHUSDT"]


def test_validate_drops_bad_hype_stage() -> None:
    blob = _blob(
        readings=[
            {
                "symbol": "BTCUSDT",
                "score": 0.1,
                "hype_stage": "moon",
                "narrative": "nope",
                "confidence": 0.5,
                "sources": [],
                "price_at_reading": 0,
            }
        ]
    )
    parsed = validate_sentiment_blob(blob)
    assert parsed["readings"] == []


def test_validate_normalises_symbol_case() -> None:
    blob = _blob(
        readings=[
            {
                "symbol": "btcusdt",
                "score": 0.1,
                "hype_stage": "absent",
                "narrative": "",
                "confidence": 0.2,
                "sources": [],
                "price_at_reading": 0,
            }
        ]
    )
    parsed = validate_sentiment_blob(blob)
    assert parsed["readings"][0]["symbol"] == "BTCUSDT"


def test_load_returns_none_for_missing_and_garbage(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert load_last_sentiment(missing) is None
    garbage = tmp_path / "bad.json"
    garbage.write_text("{not json", encoding="utf-8")
    assert load_last_sentiment(garbage) is None
    invalid = tmp_path / "invalid.json"
    _write(invalid, _blob(mood="yolo"))
    assert load_last_sentiment(invalid) is None


def test_persist_is_atomic_and_loadable(tmp_path: Path) -> None:
    dest = tmp_path / "last_sentiment.json"
    persist_sentiment(_blob(), dest)
    assert dest.exists()
    assert not dest.with_name(dest.name + ".tmp").exists()
    loaded = load_last_sentiment(dest)
    assert loaded is not None
    assert loaded["mood"] == "chop"
    assert snapshot_is_fresh(loaded)


def test_fresh_file_preferred_over_sqlite(tmp_path: Path) -> None:
    dest = tmp_path / "last_sentiment.json"
    persist_sentiment(_blob(readings=[
        {
            "symbol": "BTCUSDT",
            "score": 0.9,
            "hype_stage": "peaking",
            "narrative": "from luke",
            "confidence": 0.8,
            "sources": [],
            "price_at_reading": 0,
        }
    ]), dest)
    sqlite = [
        {
            "symbol": "BTCUSDT",
            "score": 0.1,
            "narrative": "from sqlite",
            "hype_stage": "fading",
            "confidence": 0.2,
            "sources": [],
            "recorded_at": _as_of(),
            "price_at_reading": 0,
            "forward_return_4h": None,
            "forward_return_24h": None,
        }
    ]
    desk = desk_snapshot(sqlite, path=dest)
    assert desk["fresh"] is True
    assert desk["stale"] is False
    assert desk["readings"][0]["score"] == pytest.approx(0.9)
    assert desk["readings"][0]["narrative"] == "from luke"
    assert desk["mood"] == "chop"
    assert desk["trending"][0]["token"] == "BTC"
    assert desk["influencers"][0]["handle"] == "example_macro"
    assert desk["source"] == "luke_ct_scraper"


def test_stale_file_falls_back_to_sqlite(tmp_path: Path) -> None:
    dest = tmp_path / "last_sentiment.json"
    blob = _blob(
        as_of=_as_of(CACHE_TTL + timedelta(minutes=1)),
        readings=[
            {
                "symbol": "BTCUSDT",
                "score": 0.9,
                "hype_stage": "peaking",
                "narrative": "stale luke",
                "confidence": 0.8,
                "sources": [],
                "price_at_reading": 0,
            }
        ],
    )
    persist_sentiment(blob, dest)
    sqlite = [
        {
            "symbol": "ETHUSDT",
            "score": -0.25,
            "narrative": "sqlite fallback",
            "hype_stage": "fading",
            "confidence": 0.4,
            "sources": [],
            "recorded_at": _as_of(),
            "price_at_reading": 0,
            "forward_return_4h": None,
            "forward_return_24h": None,
        }
    ]
    desk = desk_snapshot(sqlite, path=dest)
    assert desk["fresh"] is False
    assert desk["stale"] is True
    assert desk["readings"][0]["symbol"] == "ETHUSDT"
    assert desk["readings"][0]["score"] == pytest.approx(-0.25)
    assert desk["mood"] == "chop"
    assert desk["market_narrative"]
    assert desk["source"] == "sqlite"


def test_stale_file_empty_sqlite_sets_stale_flag(tmp_path: Path) -> None:
    dest = tmp_path / "last_sentiment.json"
    persist_sentiment(_blob(as_of=_as_of(CACHE_TTL + timedelta(minutes=5))), dest)
    desk = desk_snapshot([], path=dest)
    assert desk["stale"] is True
    assert desk["fresh"] is False
    assert desk["readings"] == []
    assert desk["mood"] == "chop"


def test_missing_file_uses_sqlite_and_missing_reason(tmp_path: Path) -> None:
    dest = tmp_path / "absent.json"
    sqlite = [
        {
            "symbol": "SOLUSDT",
            "score": 0.2,
            "narrative": "only sqlite",
            "hype_stage": "building",
            "confidence": 0.3,
            "sources": [],
            "recorded_at": _as_of(),
            "price_at_reading": 0,
            "forward_return_4h": None,
            "forward_return_24h": None,
        }
    ]
    desk = desk_snapshot(sqlite, path=dest)
    assert desk["readings"][0]["symbol"] == "SOLUSDT"
    assert desk["empty_reason"] == ""
    assert desk["fresh"] is False

    empty = desk_snapshot([], path=dest)
    assert empty["empty_reason"] == "missing"
    assert empty["readings"] == []


def test_import_snapshot_if_newer_writes_once(firm_db) -> None:
    from firm import memory

    blob = _blob(as_of="2026-09-07T08:00:00+00:00")
    assert import_snapshot_if_newer(blob) == 1
    rows = memory.latest_sentiment()
    assert rows[0]["symbol"] == "BTCUSDT"
    assert rows[0]["score"] == pytest.approx(0.35)
    assert rows[0]["recorded_at"].startswith("2026-09-07T08:00:00")
    assert import_snapshot_if_newer(blob) == 0
    assert len(memory.latest_sentiment()) == 1


def test_sentiment_for_desk_imports_then_prefers_file(firm_db, tmp_path) -> None:
    from core.data.sentiment import sentiment_for_desk
    from firm import memory

    dest = tmp_path / "last_sentiment.json"
    persist_sentiment(_blob(), dest)
    memory.record_sentiment(
        symbol="BTCUSDT",
        score=-0.9,
        narrative="old sqlite",
        hype_stage="exhausted",
        confidence=0.1,
        sources=[],
        model="grok-search",
        price_at_reading=0.0,
        recorded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    payload = sentiment_for_desk(path=dest)
    assert payload["fresh"] is True
    assert payload["readings"][0]["score"] == pytest.approx(0.35)
    assert payload["market_narrative"]
    stored = memory.latest_sentiment()
    assert any(row["narrative"] == "Range defence" for row in stored)


def test_api_sentiment_returns_desk_object(firm_db, tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    dest = tmp_path / "last_sentiment.json"
    persist_sentiment(_blob(), dest)
    monkeypatch.setattr("core.data.sentiment.LAST_SENTIMENT_PATH", dest)
    from api.app import app

    client = TestClient(app)
    response = client.get("/api/sentiment")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert "readings" in body
    assert "mood" in body
    assert "trending" in body
    assert "influencers" in body
    assert "market_narrative" in body
    assert "headline" in body
    assert "takeaways" in body
    assert body["mood"] == "chop"


def test_import_skips_when_sqlite_is_newer(firm_db) -> None:
    from firm import memory

    memory.record_sentiment(
        symbol="BTCUSDT",
        score=0.05,
        narrative="xai",
        hype_stage="absent",
        confidence=0.2,
        sources=[],
        model="grok-search",
        price_at_reading=0.0,
        recorded_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
    )
    blob = _blob(as_of="2026-09-07T08:00:00+00:00")
    assert import_snapshot_if_newer(blob) == 0
    assert memory.latest_sentiment()[0]["narrative"] == "xai"


def test_classic_blob_defaults_empty_l1_fields() -> None:
    parsed = validate_sentiment_blob(_blob())
    assert parsed["headline"] == ""
    assert parsed["takeaways"] == []
    assert parsed["market_narrative"] == "Majors two-way, memes quieter."


def test_headline_and_takeaways_passthrough(tmp_path: Path) -> None:
    blob = _blob(
        headline="BTC two-way at range high",
        takeaways=[
            "Watch: ETH lag vs BTC",
            "Fit: majors over meme-beta",
            "Watch: extra should be dropped",
            {"kind": "Watch", "text": "nested object must be dropped"},
        ],
    )
    parsed = validate_sentiment_blob(blob)
    assert parsed["headline"] == "BTC two-way at range high"
    assert parsed["takeaways"] == ["Watch: ETH lag vs BTC", "Fit: majors over meme-beta"]

    dest = tmp_path / "last_sentiment.json"
    persist_sentiment(blob, dest)
    desk = desk_snapshot([], path=dest)
    assert desk["headline"] == "BTC two-way at range high"
    assert desk["takeaways"] == ["Watch: ETH lag vs BTC", "Fit: majors over meme-beta"]


def test_api_sentiment_emits_headline_takeaways(firm_db, tmp_path, monkeypatch) -> None:
    from fastapi.testclient import TestClient

    dest = tmp_path / "last_sentiment.json"
    persist_sentiment(
        _blob(
            headline="CT rotating into majors",
            takeaways=["Watch: ETH lag", "Fit: less leverage-cosplay"],
        ),
        dest,
    )
    monkeypatch.setattr("core.data.sentiment.LAST_SENTIMENT_PATH", dest)
    from api.app import app

    client = TestClient(app)
    body = client.get("/api/sentiment").json()
    assert body["headline"] == "CT rotating into majors"
    assert body["takeaways"] == ["Watch: ETH lag", "Fit: less leverage-cosplay"]
    assert body["mood"] == "chop"
    assert body["market_narrative"]


def test_null_followers_does_not_drop_influencer() -> None:
    blob = _blob(
        influencers=[
            {"handle": "example_macro", "bias": "bullish", "followers": None, "note": "BTC · bid"}
        ]
    )
    parsed = validate_sentiment_blob(blob)
    assert parsed["influencers"][0]["handle"] == "example_macro"
    assert parsed["influencers"][0]["followers"] is None
    assert parsed["influencers"][0]["note"] == "BTC · bid"
