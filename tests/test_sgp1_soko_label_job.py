"""SGP1 Soko label job: classifier parity, atomic publish, failure, newer-as_of.

Network is mocked. Parity replays the committed Binance bars; it does not
fetch. Same-bar inputs are compared with a third-decimal tolerance. The live
job seeds EMA20 on the 59 closed bars left after a limit=60 fetch drops the
forming bar. The 30-day fixture was built on 60-bar windows.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import sgp1_soko_label_job as job

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "soko"
ENGINE = ROOT / "core" / "execution" / "engine.py"
ENGINE_SHA256 = (
    "f275183bf25f4e1bac1de718d78b11be84c86b18e26e8caa57fccf3f9f571493"
)

# One unit in the third decimal place. Same-bar replays are exact today.
SAME_BAR_ATOL = 0.001
# 59-bar live seed vs the fixture's 60-bar seed. Largest gap at authoring
# was 0.012 on price_vs_ema. Labels did not flip.
LIVE_SEED_ATOL = 0.015

# A desktop log row: the 04:00Z bar, observed at 05:32Z while 08:00 was forming.
NOW = datetime(2026, 10, 10, 5, 32, 44, tzinfo=timezone.utc)
AS_OF = "2026-10-10T04:00:00Z"


def _jsonl(name: str) -> list[dict]:
    path = FIXTURES / name
    text = path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _klines() -> list[list]:
    return _jsonl("btcusdt_4h_binance.jsonl")


def _index(klines: list[list]) -> dict[str, int]:
    return {job.bar_as_of(row): i for i, row in enumerate(klines)}


def _window(klines: list[list], index: dict[str, int], as_of: str, bars: int) -> list[list]:
    i = index[as_of]
    window = klines[i - bars + 1 : i + 1]
    assert len(window) == bars, (as_of, len(window))
    assert job.bar_as_of(window[-1]) == as_of
    return window


def _live_payload() -> list[list]:
    """limit=60 shape at NOW: 59 closed bars ending at 04:00Z, plus the forming 08:00 bar."""
    return _klines()[-60:]


def _record(capsys) -> dict:
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1, captured.out
    return json.loads(lines[0])


def _opener(payload, calls: list, *, fail: bool = False):
    def opener(url: str, timeout: float):
        calls.append((url, timeout))
        if fail or "binance" not in url:
            raise urllib.error.URLError("timed out")
        return payload

    return opener


def test_execution_engine_is_untouched() -> None:
    """The paper engine hash is the one this job was required to leave alone."""
    digest = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
    assert digest == ENGINE_SHA256
    source = (ROOT / "scripts" / "sgp1_soko_label_job.py").read_text(encoding="utf-8")
    assert "core.execution" not in source
    assert "approved_strategies" not in source


def test_bybit_fallback_defaults_off() -> None:
    assert job.bybit_fallback_enabled(None, None) is False
    assert job.bybit_fallback_enabled(None, "") is False
    assert job.bybit_fallback_enabled(None, "0") is False
    assert job.bybit_fallback_enabled(None, "yes") is True
    assert job.bybit_fallback_enabled(False, "yes") is False
    assert job.bybit_fallback_enabled(True, "0") is True


def test_main_resolves_fallback_flag(monkeypatch, tmp_path) -> None:
    seen: dict = {}

    def fake_run(path, bybit_fallback=False, **kwargs):
        seen["path"] = path
        seen["flag"] = bybit_fallback
        return 0

    monkeypatch.setattr(job, "run", fake_run)
    monkeypatch.delenv("SOKO_LABEL_BYBIT_FALLBACK", raising=False)
    dest = tmp_path / "last_soko_trend.json"
    assert job.main(["--path", str(dest)]) == 0
    assert seen["flag"] is False
    monkeypatch.setenv("SOKO_LABEL_BYBIT_FALLBACK", "on")
    job.main(["--path", str(dest)])
    assert seen["flag"] is True
    job.main(["--path", str(dest), "--no-bybit-fallback"])
    assert seen["flag"] is False


def test_history_30d_same_bar_parity() -> None:
    """Replay the fixture's own 60-bar windows. Labels 180/180, inputs within 0.001."""
    klines = _klines()
    index = _index(klines)
    rows = _jsonl("history_30d.jsonl")
    assert len(rows) == 180
    mismatches: list[dict] = []
    for rec in rows:
        got = job.classify_window(_window(klines, index, rec["as_of"], 60))
        if got.trend != rec["trend"]:
            mismatches.append(
                {
                    "as_of": rec["as_of"],
                    "field": "trend",
                    "expected": rec["trend"],
                    "got": got.trend,
                }
            )
        if got.stretch != rec["stretch"]:
            mismatches.append(
                {
                    "as_of": rec["as_of"],
                    "field": "stretch",
                    "expected": rec["stretch"],
                    "got": got.stretch,
                }
            )
        for flag in ("HH", "HL", "LH", "LL"):
            if getattr(got, flag) != rec[flag]:
                mismatches.append(
                    {
                        "as_of": rec["as_of"],
                        "field": flag,
                        "expected": rec[flag],
                        "got": getattr(got, flag),
                    }
                )
        numeric = {
            "ema20": (got.ema20, rec["ema20"]),
            "ema20_slope6_pct": (got.slope_pct, rec["ema20_slope6_pct"]),
            "price_vs_ema_pct": (got.price_vs_ema_pct, rec["price_vs_ema_pct"]),
            "atr_pct": (got.atr_pct, rec["atr_pct"]),
            "range_ratio": (got.range_ratio, rec["range_ratio"]),
            "flip_dist_atr": (got.flip_dist_atr, rec["flip_dist_atr"]),
            "close": (got.close, rec["close"]),
        }
        for field, (actual, expected) in numeric.items():
            delta = abs(float(actual) - float(expected))
            if delta > SAME_BAR_ATOL:
                mismatches.append(
                    {
                        "as_of": rec["as_of"],
                        "field": field,
                        "expected": expected,
                        "got": actual,
                        "delta": delta,
                    }
                )
    label_hits = sum(1 for rec in rows if rec["trend"])  # counted below from mismatches
    label_misses = [row for row in mismatches if row["field"] == "trend"]
    assert not mismatches, mismatches
    assert len(label_misses) == 0
    assert label_hits == 180
    assert Counter(rec["trend"] for rec in rows) == {"chop": 117, "bull": 34, "bear": 29}


def test_label_log_matches_live_59_bar_window() -> None:
    """Desktop log rows were classified on 59 closed bars. Every row must match."""
    klines = _klines()
    index = _index(klines)
    rows = _jsonl("label_log.jsonl")
    assert len(rows) == 68
    assert len({rec["as_of"] for rec in rows}) == 13
    mismatches: list[dict] = []
    for rec in rows:
        got = job.classify_window(_window(klines, index, rec["as_of"], 59))
        if got.trend != rec["label"]:
            mismatches.append(
                {
                    "as_of": rec["as_of"],
                    "field": "label",
                    "expected": rec["label"],
                    "got": got.trend,
                }
            )
        for flag in ("LH", "LL"):
            if getattr(got, flag) != rec[flag]:
                mismatches.append(
                    {
                        "as_of": rec["as_of"],
                        "field": flag,
                        "expected": rec[flag],
                        "got": getattr(got, flag),
                    }
                )
        numeric = {
            "btc_ema20_slope_pct": (got.slope_pct, rec["btc_ema20_slope_pct"]),
            "btc_price_vs_ema20_pct": (got.price_vs_ema_pct, rec["btc_price_vs_ema20_pct"]),
            "flip_dist_atr": (got.flip_dist_atr, rec["flip_dist_atr"]),
        }
        for field, (actual, expected) in numeric.items():
            delta = abs(float(actual) - float(expected))
            if delta > SAME_BAR_ATOL:
                mismatches.append(
                    {
                        "as_of": rec["as_of"],
                        "run_time": rec["run_time"],
                        "field": field,
                        "expected": expected,
                        "got": actual,
                        "delta": delta,
                    }
                )
    assert not mismatches, mismatches


def test_live_59_bar_seed_does_not_flip_history_labels() -> None:
    """The hourly job seeds 59 bars. That must not change the fixture's 180 labels.

    Rounded inputs can move in the third decimal, and a few bars move by about
    0.01, because the fixture window is 60 closes and the live window is 59.
    """
    klines = _klines()
    index = _index(klines)
    rows = _jsonl("history_30d.jsonl")
    mismatches: list[dict] = []
    for rec in rows:
        got = job.classify_window(_window(klines, index, rec["as_of"], 59))
        if got.trend != rec["trend"] or got.stretch != rec["stretch"]:
            mismatches.append(
                {
                    "as_of": rec["as_of"],
                    "field": "label",
                    "expected": (rec["trend"], rec["stretch"]),
                    "got": (got.trend, got.stretch),
                }
            )
        for flag in ("HH", "HL", "LH", "LL"):
            if getattr(got, flag) != rec[flag]:
                mismatches.append(
                    {
                        "as_of": rec["as_of"],
                        "field": flag,
                        "expected": rec[flag],
                        "got": getattr(got, flag),
                    }
                )
        numeric = {
            "ema20_slope6_pct": (got.slope_pct, rec["ema20_slope6_pct"]),
            "price_vs_ema_pct": (got.price_vs_ema_pct, rec["price_vs_ema_pct"]),
            "flip_dist_atr": (got.flip_dist_atr, rec["flip_dist_atr"]),
        }
        for field, (actual, expected) in numeric.items():
            delta = abs(float(actual) - float(expected))
            if delta > LIVE_SEED_ATOL:
                mismatches.append(
                    {
                        "as_of": rec["as_of"],
                        "field": field,
                        "expected": expected,
                        "got": actual,
                        "delta": delta,
                    }
                )
    assert not mismatches, mismatches


def test_forming_bar_is_dropped() -> None:
    payload = _live_payload()
    now_ms = job._now_ms(NOW)
    closed = job.closed_klines(payload, now_ms)
    assert len(payload) == 60
    assert int(payload[-1][6]) >= now_ms
    assert len(closed) == 59
    assert job.bar_as_of(closed[-1]) == AS_OF


def test_run_publishes_schema_and_perms(tmp_path, capsys) -> None:
    dest = tmp_path / "state" / "last_soko_trend.json"
    calls: list = []
    previous = os.umask(0o077)
    try:
        code = job.run(
            dest,
            now=NOW,
            opener=_opener(_live_payload(), calls),
            sleep=lambda _seconds: None,
        )
    finally:
        os.umask(previous)
    record = _record(capsys)
    assert code == 0
    assert record["status"] == "ok"
    assert record["written"] is True
    assert record["feed"] == "binance"
    assert record["closed_bars"] == 59
    assert record["label"] == "chop"
    assert record["as_of"] == AS_OF
    assert record["btc_ema20_slope_pct"] == -0.375
    assert record["btc_price_vs_ema20_pct"] == -0.587
    assert record["LH"] is False
    assert record["LL"] is False
    assert record["flip_dist_atr"] == 0.777
    assert calls and all(timeout == job.FETCH_TIMEOUT_S for _url, timeout in calls)
    assert all("bybit" not in url for url, _timeout in calls)
    body = json.loads(dest.read_text(encoding="utf-8"))
    assert body == {
        "schema": "soko_trend_v1",
        "trend": "chop",
        "as_of": AS_OF,
        "source": "sgp1_auto",
    }
    assert dest.read_bytes().endswith(b"\n")
    assert dest.stat().st_mode & 0o777 == 0o644


def test_temp_file_is_a_sibling(tmp_path, monkeypatch) -> None:
    dest = tmp_path / "last_soko_trend.json"
    seen: dict = {}
    real_replace = os.replace

    def spy(src, dst):
        seen["src"] = Path(src)
        seen["dst"] = Path(dst)
        return real_replace(src, dst)

    monkeypatch.setattr(job.os, "replace", spy)
    payload = job.build_payload("chop", AS_OF)
    assert job.atomic_publish(dest, payload, job.parse_as_of(AS_OF)) == "written"
    assert seen["src"].parent == dest.parent
    assert seen["src"].name.startswith(".last_soko_trend.json.")
    assert seen["dst"] == dest
    assert list(tmp_path.iterdir()) == [dest]


def test_short_write_leaves_destination_intact(tmp_path, monkeypatch) -> None:
    dest = tmp_path / "last_soko_trend.json"
    original = (
        b'{"schema": "soko_trend_v1", "trend": "bear", '
        b'"as_of": "2026-10-09T00:00:00Z", "source": "soko"}\n'
    )
    dest.write_bytes(original)
    real_write = os.write

    def short(fd, data):
        real_write(fd, data[:4])
        raise OSError("short write")

    monkeypatch.setattr(job.os, "write", short)
    payload = job.build_payload("chop", AS_OF)
    with pytest.raises(OSError, match="short write"):
        job.atomic_publish(dest, payload, job.parse_as_of(AS_OF))
    assert dest.read_bytes() == original
    assert [path.name for path in tmp_path.iterdir()] == ["last_soko_trend.json"]


def test_fsync_failure_keeps_last_file(tmp_path, monkeypatch, capsys) -> None:
    dest = tmp_path / "last_soko_trend.json"
    original = (
        b'{"schema": "soko_trend_v1", "trend": "bear", '
        b'"as_of": "2026-10-09T00:00:00Z", "source": "soko"}\n'
    )
    dest.write_bytes(original)

    def boom(_fd):
        raise OSError("fsync failed")

    monkeypatch.setattr(job.os, "fsync", boom)
    calls: list = []
    code = job.run(
        dest,
        now=NOW,
        opener=_opener(_live_payload(), calls),
        sleep=lambda _seconds: None,
    )
    record = _record(capsys)
    assert code == 1
    assert record["status"] == "error"
    assert record["written"] is False
    assert "fsync failed" in record["error"]
    assert dest.read_bytes() == original
    assert list(tmp_path.iterdir()) == [dest]


def test_rename_failure_keeps_last_file(tmp_path, monkeypatch) -> None:
    dest = tmp_path / "last_soko_trend.json"
    dest.write_bytes(
        b'{"schema": "soko_trend_v1", "trend": "bull", '
        b'"as_of": "2026-10-01T00:00:00Z", "source": "soko"}\n'
    )
    original = dest.read_bytes()

    def boom(_src, _dst):
        raise OSError("rename failed")

    monkeypatch.setattr(job.os, "replace", boom)
    payload = job.build_payload("chop", AS_OF)
    with pytest.raises(OSError, match="rename failed"):
        job.atomic_publish(dest, payload, job.parse_as_of(AS_OF))
    assert dest.read_bytes() == original
    assert list(tmp_path.iterdir()) == [dest]


def test_network_failure_keeps_last_file_and_skips_bybit(tmp_path, capsys) -> None:
    dest = tmp_path / "last_soko_trend.json"
    original = (
        b'{"schema": "soko_trend_v1", "trend": "bear", '
        b'"as_of": "2026-10-09T20:00:00Z", "source": "soko"}\n'
    )
    dest.write_bytes(original)
    calls: list = []
    slept: list[float] = []
    code = job.run(
        dest,
        bybit_fallback=False,
        now=NOW,
        opener=_opener(_live_payload(), calls, fail=True),
        sleep=slept.append,
    )
    record = _record(capsys)
    assert code == 1
    assert record["status"] == "error"
    assert record["written"] is False
    assert "binance" in record["error"]
    assert dest.read_bytes() == original
    assert len(calls) == job.FETCH_RETRIES + 1
    assert slept == [5.0, 10.0, 20.0]
    assert all("binance" in url for url, _timeout in calls)
    assert all("bybit" not in url for url, _timeout in calls)


def test_network_failure_does_not_create_a_file(tmp_path, capsys) -> None:
    dest = tmp_path / "missing" / "last_soko_trend.json"
    calls: list = []
    code = job.run(
        dest,
        now=NOW,
        opener=_opener([], calls, fail=True),
        sleep=lambda _seconds: None,
    )
    record = _record(capsys)
    assert code == 1
    assert record["written"] is False
    assert not dest.exists()
    assert not dest.parent.exists()


def test_both_feeds_down_keeps_the_file(tmp_path, capsys) -> None:
    dest = tmp_path / "last_soko_trend.json"
    original = (
        b'{"schema": "soko_trend_v1", "trend": "bear", '
        b'"as_of": "2026-10-09T00:00:00Z", "source": "soko"}\n'
    )
    dest.write_bytes(original)

    def opener(url: str, timeout: float):
        raise urllib.error.URLError(url)

    code = job.run(
        dest,
        bybit_fallback=True,
        now=NOW,
        opener=opener,
        sleep=lambda _seconds: None,
    )
    record = _record(capsys)
    assert code == 1
    assert record["written"] is False
    assert "binance klines failed" in record["error"]
    assert "bybit klines failed" in record["error"]
    assert dest.read_bytes() == original


def test_bybit_fallback_used_only_when_enabled(tmp_path, capsys) -> None:
    dest = tmp_path / "last_soko_trend.json"
    bars = _live_payload()
    bybit_rows = []
    for row in bars:
        bybit_rows.append([str(int(row[0])), row[1], row[2], row[3], row[4], row[5]])
    bybit_rows.reverse()
    bybit_body = {"retCode": 0, "result": {"list": bybit_rows}}
    calls: list = []

    def opener(url: str, timeout: float):
        calls.append(url)
        if "binance" in url:
            raise urllib.error.URLError("binance down")
        if "bybit" in url:
            return bybit_body
        raise AssertionError(url)

    code = job.run(
        dest,
        bybit_fallback=True,
        now=NOW,
        opener=opener,
        sleep=lambda _seconds: None,
    )
    record = _record(capsys)
    assert code == 0
    assert record["feed"] == "bybit"
    assert record["written"] is True
    assert record["label"] == "chop"
    assert json.loads(dest.read_text(encoding="utf-8"))["source"] == "sgp1_auto"
    assert sum("bybit" in url for url in calls) == 1
    assert sum("binance" in url for url in calls) == job.FETCH_RETRIES + 1


def test_newer_as_of_wins_tie_and_older_stay(tmp_path, capsys) -> None:
    dest = tmp_path / "last_soko_trend.json"
    calls: list = []
    opener = _opener(_live_payload(), calls)

    older = (
        b'{"schema": "soko_trend_v1", "trend": "bear", '
        b'"as_of": "2026-10-09T00:00:00Z", "source": "soko"}\n'
    )
    dest.write_bytes(older)
    assert job.run(dest, now=NOW, opener=opener, sleep=lambda _s: None) == 0
    published = _record(capsys)
    assert published["written"] is True
    assert published["prev_label"] == "bear"
    assert json.loads(dest.read_text(encoding="utf-8"))["source"] == "sgp1_auto"

    tied = (
        b'{"schema": "soko_trend_v1", "trend": "bear", '
        b'"as_of": "2026-10-10T04:00:00Z", "source": "soko"}\n'
    )
    dest.write_bytes(tied)
    assert job.run(dest, now=NOW, opener=opener, sleep=lambda _s: None) == 0
    kept = _record(capsys)
    assert kept["written"] is False
    assert kept["reason"] == "as_of_not_newer"
    assert kept["status"] == "ok"
    assert dest.read_bytes() == tied

    # Same instant, explicit offset. Still a tie, so the desktop bytes stay.
    offset_tie = (
        b'{"schema": "soko_trend_v1", "trend": "bull", '
        b'"as_of": "2026-10-10T06:00:00+02:00", "source": "soko"}\n'
    )
    dest.write_bytes(offset_tie)
    assert job.run(dest, now=NOW, opener=opener, sleep=lambda _s: None) == 0
    assert _record(capsys)["reason"] == "as_of_not_newer"
    assert dest.read_bytes() == offset_tie

    newer = (
        b'{"schema": "soko_trend_v1", "trend": "bull", '
        b'"as_of": "2026-10-10T08:00:00Z", "source": "soko"}\n'
    )
    dest.write_bytes(newer)
    assert job.run(dest, now=NOW, opener=opener, sleep=lambda _s: None) == 0
    assert _record(capsys)["written"] is False
    assert dest.read_bytes() == newer


def test_recheck_keeps_a_desktop_push_that_lands_mid_write(tmp_path, monkeypatch) -> None:
    dest = tmp_path / "last_soko_trend.json"
    older = (
        '{"schema": "soko_trend_v1", "trend": "bear", '
        '"as_of": "2026-10-09T00:00:00Z", "source": "soko"}\n'
    )
    newer = (
        b'{"schema": "soko_trend_v1", "trend": "bull", '
        b'"as_of": "2026-10-10T08:00:00Z", "source": "soko"}\n'
    )
    dest.write_text(older, encoding="utf-8")
    real = job.inspect_existing
    calls = {"n": 0}

    def flip(path: Path):
        calls["n"] += 1
        if calls["n"] == 2:
            path.write_bytes(newer)
        return real(path)

    monkeypatch.setattr(job, "inspect_existing", flip)
    payload = job.build_payload("chop", AS_OF)
    assert job.atomic_publish(dest, payload, job.parse_as_of(AS_OF)) == "kept_existing"
    assert dest.read_bytes() == newer
    assert list(tmp_path.iterdir()) == [dest]


def test_invalid_payload_is_not_written(tmp_path) -> None:
    dest = tmp_path / "last_soko_trend.json"
    bad = {
        "schema": "soko_trend_v1",
        "trend": "neutral",
        "as_of": AS_OF,
        "source": "sgp1_auto",
    }
    with pytest.raises(ValueError):
        job.atomic_publish(dest, bad, job.parse_as_of(AS_OF))
    assert not dest.exists()


def test_undated_file_is_replaced(tmp_path, capsys) -> None:
    dest = tmp_path / "last_soko_trend.json"
    dest.write_bytes(b"{not-json")
    calls: list = []
    code = job.run(
        dest,
        now=NOW,
        opener=_opener(_live_payload(), calls),
        sleep=lambda _seconds: None,
    )
    record = _record(capsys)
    assert code == 0
    assert record["written"] is True
    assert json.loads(dest.read_text(encoding="utf-8"))["trend"] == "chop"
