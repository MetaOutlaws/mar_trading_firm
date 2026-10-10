"""XRP/AVAX public Bybit sampler: schedule, limiter, cap, stop, checksums.

Network is mocked. These tests do not read the approval book or the engine.
"""

from __future__ import annotations

import ast
import gzip
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.xrp_avax_cost_sampler import (
    BAR_S,
    BURST_POST,
    BURST_PRE,
    BURST_S,
    BYBIT_IP_LIMIT_PER_5S,
    DEFAULT_HOURS,
    DEFAULT_MAX_BYTES,
    DEFAULT_OUT,
    ENDPOINTS,
    MAX_PER_WINDOW,
    MIN_INTERVAL_S,
    SYMBOLS,
    PublicClient,
    RateLimiter,
    Sampler,
    Settings,
    append_jsonl_gz,
    build_request,
    burst_offset,
    daily_path,
    endpoint_path,
    format_schedule,
    in_burst,
    iter_bar_opens,
    next_burst_start,
    parse_args,
    render_coverage,
    upcoming_bar_opens,
    urllib_fetch,
    write_sha256sums,
)

UTC = timezone.utc


class Clock:
    """Virtual clock. sleep() only moves this clock; it does not block."""

    def __init__(self, epoch: float) -> None:
        self.epoch = float(epoch)
        self.slept: list[float] = []

    def now(self) -> float:
        return self.epoch

    def sleep(self, seconds: float) -> None:
        if seconds < 0:
            raise AssertionError("negative sleep %s" % seconds)
        self.slept.append(seconds)
        self.epoch += seconds


def _dt(year: int, month: int, day: int, hour: int, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def _ok_body(symbol: str = "XRPUSDT", when_ms: int = 1_700_000_000_000) -> bytes:
    return json.dumps(
        {
            "retCode": 0,
            "retMsg": "OK",
            "result": {"s": symbol, "b": [["1", "2"]], "a": [["3", "4"]], "list": []},
            "time": when_ms,
        }
    ).encode("utf-8")


class FakeFetch:
    def __init__(self, responses: list | None = None) -> None:
        self.responses = list(responses or [])
        self.urls: list[str] = []

    def __call__(self, url: str, timeout: float) -> tuple[int, dict[str, str], bytes]:
        self.urls.append(url)
        if self.responses:
            item = self.responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        symbol = "AVAXUSDT" if "AVAXUSDT" in url else "XRPUSDT"
        return (
            200,
            {"X-Bapi-Limit": "600", "X-Bapi-Limit-Status": "590"},
            _ok_body(symbol),
        )


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    base = dict(
        out=tmp_path,
        hours=None,
        end=None,
        once=False,
        max_bytes=DEFAULT_MAX_BYTES,
        regular_s=300.0,
        burst_s=15.0,
        min_interval_s=0.0,
        window_s=5.0,
        max_per_window=10_000,
    )
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _sampler(tmp_path: Path, clock: Clock, fetch: FakeFetch, **overrides: object) -> Sampler:
    return Sampler(
        _settings(tmp_path, **overrides),
        now=clock.now,
        sleep=clock.sleep,
        fetch=fetch,
        install_signals=False,
    )


def _read_gz(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _snap_lines(out: Path) -> list[str]:
    text = (out / "sampler.log").read_text(encoding="utf-8")
    return [line for line in text.splitlines() if " SNAP " in line]


# --- schedule ------------------------------------------------------------------


def test_burst_window_is_two_minutes_before_through_three_after_each_4h_open() -> None:
    # 2026-10-10 04:00 UTC is a 4h open. So are 00/08/12/16/20. 02/06/10 are not.
    open_at = _dt(2026, 10, 10, 4, 0, 0)
    assert in_burst((open_at - timedelta(seconds=120)).timestamp())
    assert in_burst(open_at.timestamp())
    assert in_burst((open_at + timedelta(seconds=180)).timestamp())
    assert not in_burst((open_at - timedelta(seconds=121)).timestamp())
    assert not in_burst((open_at + timedelta(seconds=181)).timestamp())
    for hour in (0, 4, 8, 12, 16, 20):
        moment = _dt(2026, 10, 10, hour)
        assert in_burst(moment.timestamp())
        assert burst_offset(moment.timestamp()) == 0.0
    for hour in (2, 6, 10, 14, 18, 22):
        assert not in_burst(_dt(2026, 10, 10, hour).timestamp())


def test_next_burst_start_lands_on_the_window_edge() -> None:
    open_at = _dt(2026, 10, 10, 8, 0, 0).timestamp()
    early = open_at - 130
    assert next_burst_start(early) == open_at - BURST_PRE
    assert next_burst_start(open_at + 10) == open_at + 10  # already inside
    assert next_burst_start(open_at + BURST_POST + 1) == open_at + BAR_S - BURST_PRE
    # Midpoint between bars is not a burst; the next window is the following open.
    assert next_burst_start(open_at + BAR_S / 2) == open_at + BAR_S - BURST_PRE


def test_bar_opens_inside_the_run_window_only() -> None:
    # 04:12 start excludes the 04:00 open. 06:12 end excludes the later 08:00.
    start = _dt(2026, 10, 9, 4, 12, 0)
    end = _dt(2026, 10, 10, 6, 12, 0)
    opens = iter_bar_opens(start, end)
    assert opens[0] == _dt(2026, 10, 9, 8, 0, 0)
    assert opens[-1] == _dt(2026, 10, 10, 4, 0, 0)
    assert _dt(2026, 10, 9, 4, 0, 0) not in opens
    assert _dt(2026, 10, 10, 8, 0, 0) not in opens
    assert [item.hour for item in opens] == [8, 12, 16, 20, 0, 4]


def test_loop_burst_timing(tmp_path: Path) -> None:
    start = _dt(2026, 10, 10, 3, 57, 50)
    end = _dt(2026, 10, 10, 4, 3, 30)
    clock = Clock(start.timestamp())
    fetch = FakeFetch()
    sampler = _sampler(tmp_path, clock, fetch, end=end, regular_s=300.0, burst_s=15.0)
    assert sampler.run() == 0

    snaps = _snap_lines(tmp_path)
    kinds = [line.split(" SNAP ", 1)[1].split()[0] for line in snaps]
    assert kinds[0] == "regular5m"
    assert kinds[1:] == ["burst4h"] * 21
    burst_at = []
    for line in snaps[1:]:
        burst_at.append(datetime.fromisoformat(line.split()[0].replace("Z", "+00:00")))
    window_open = _dt(2026, 10, 10, 3, 58, 0)
    assert burst_at[0] == window_open
    assert burst_at[-1] == _dt(2026, 10, 10, 4, 3, 0)
    deltas = [(b - a).total_seconds() for a, b in zip(burst_at, burst_at[1:])]
    assert deltas == [15.0] * 20
    # The regular shot that would have fallen inside the window was pushed out.
    assert "regular5m" not in kinds[1:]
    assert clock.now() == end.timestamp()
    assert (tmp_path / "SAMPLER_DONE").read_text(encoding="utf-8").endswith("reason=end_time\n")


def test_regular_cadence_outside_a_burst(tmp_path: Path) -> None:
    start = _dt(2026, 10, 10, 5, 0, 0)
    clock = Clock(start.timestamp())
    fetch = FakeFetch()
    sampler = _sampler(
        tmp_path,
        clock,
        fetch,
        end=start + timedelta(seconds=900),
        regular_s=300.0,
    )
    sampler.run()
    kinds = [line.split(" SNAP ", 1)[1].split()[0] for line in _snap_lines(tmp_path)]
    assert kinds == ["regular5m", "regular5m", "regular5m"]
    stamps = [
        datetime.fromisoformat(line.split()[0].replace("Z", "+00:00"))
        for line in _snap_lines(tmp_path)
    ]
    assert stamps == [start, start + timedelta(minutes=5), start + timedelta(minutes=10)]


def test_print_schedule_names_the_next_4h_windows() -> None:
    moment = _dt(2026, 10, 10, 5, 10, 0).timestamp()
    text = format_schedule(moment, count=2)
    assert "in_burst=no" in text
    assert "bar_open_utc=2026-10-10T08:00:00Z" in text
    assert "window_utc=2026-10-10T07:58:00Z..2026-10-10T08:03:00Z" in text
    assert "bar_open_gst=2026-10-10T12:00:00" in text
    opens = upcoming_bar_opens(moment, 3)
    assert opens[0] == _dt(2026, 10, 10, 8).timestamp()
    assert opens[1] - opens[0] == BAR_S


def test_snapshot_uses_public_linear_paths_and_both_symbols(tmp_path: Path) -> None:
    clock = Clock(_dt(2026, 10, 10, 5).timestamp())
    fetch = FakeFetch()
    sampler = _sampler(tmp_path, clock, fetch, once=True)
    assert sampler.run() == 0
    assert len(fetch.urls) == 6
    joined = " ".join(fetch.urls)
    for symbol in SYMBOLS:
        assert symbol in joined
        assert "/v5/market/orderbook?category=linear&symbol=%s&limit=50" % symbol in joined
        assert "/v5/market/recent-trade?category=linear&symbol=%s&limit=1000" % symbol in joined
        assert "/v5/market/tickers?category=linear&symbol=%s" % symbol in joined
    assert "api_key" not in joined
    assert "sign=" not in joined
    assert "BTCUSDT" not in joined
    lines = _read_gz(next(tmp_path.glob("XRPUSDT_*.jsonl.gz")))
    assert lines[0]["kind"] == "once_test"
    assert lines[0]["server_time_ms"] == 1_700_000_000_000
    assert (tmp_path / "SAMPLER_DONE").exists() is False


def test_daily_gzip_rotation_splits_on_utc_date(tmp_path: Path) -> None:
    late = _dt(2026, 10, 10, 23, 50).timestamp()
    early = _dt(2026, 10, 11, 0, 10).timestamp()
    assert daily_path(tmp_path, "XRPUSDT", late).name == "XRPUSDT_20261010.jsonl.gz"
    assert daily_path(tmp_path, "AVAXUSDT", early).name == "AVAXUSDT_20261011.jsonl.gz"
    clock = Clock(late)
    fetch = FakeFetch()
    sampler = _sampler(tmp_path, clock, fetch, once=True)
    sampler.out.mkdir(parents=True, exist_ok=True)
    sampler.snapshot("regular5m")
    clock.epoch = early
    sampler.snapshot("regular5m")
    assert (tmp_path / "XRPUSDT_20261010.jsonl.gz").is_file()
    assert (tmp_path / "XRPUSDT_20261011.jsonl.gz").is_file()
    assert len(_read_gz(tmp_path / "XRPUSDT_20261010.jsonl.gz")) == 1
    assert len(_read_gz(tmp_path / "XRPUSDT_20261011.jsonl.gz")) == 1


# --- rate limiter --------------------------------------------------------------


def test_budget_stays_under_the_public_ip_limit() -> None:
    assert BYBIT_IP_LIMIT_PER_5S == 600
    assert MAX_PER_WINDOW <= BYBIT_IP_LIMIT_PER_5S * 0.02
    assert MIN_INTERVAL_S >= 0.2
    per_snapshot = len(SYMBOLS) * len(ENDPOINTS)
    assert per_snapshot == 6
    assert per_snapshot / BURST_S < 1.0


def test_min_interval_and_window_cap() -> None:
    clock = Clock(0.0)
    limiter = RateLimiter(
        min_interval_s=0.25,
        window_s=5.0,
        max_per_window=3,
        now=clock.now,
        sleep=clock.sleep,
    )
    limiter.acquire()
    limiter.acquire()
    assert clock.now() == pytest.approx(0.25)
    limiter.acquire()
    assert clock.now() == pytest.approx(0.5)
    limiter.acquire()  # window is full; wait until the oldest stamp ages out
    assert clock.now() == pytest.approx(5.0)
    # Six calls at the production spacing take 1.25 s, inside a 15 s burst slot.
    clock2 = Clock(0.0)
    paced = RateLimiter(
        min_interval_s=MIN_INTERVAL_S,
        window_s=5.0,
        max_per_window=MAX_PER_WINDOW,
        now=clock2.now,
        sleep=clock2.sleep,
    )
    for _ in range(6):
        paced.acquire()
    assert clock2.now() == pytest.approx(MIN_INTERVAL_S * 5)


def test_backoff_doubles_from_5s_and_caps_at_120s() -> None:
    clock = Clock(0.0)
    limiter = RateLimiter(
        min_interval_s=0.0, window_s=5.0, max_per_window=100, now=clock.now, sleep=clock.sleep
    )
    seen = []
    for _ in range(8):
        seen.append(limiter.note_rate_limit())
    assert seen == [5.0, 10.0, 20.0, 40.0, 80.0, 120.0, 120.0, 120.0]
    limiter.note_ok()
    assert limiter.backoff_s == 0.0
    assert limiter.note_rate_limit() == 5.0


def _client(clock: Clock, fetch: FakeFetch) -> PublicClient:
    return PublicClient(
        limiter=RateLimiter(
            min_interval_s=0.0,
            window_s=5.0,
            max_per_window=100,
            now=clock.now,
            sleep=clock.sleep,
        ),
        now=clock.now,
        sleep=clock.sleep,
        log=lambda _msg: None,
        fetch=fetch,
    )


def test_retcode_10006_retries_with_backoff_then_accepts(tmp_path: Path) -> None:
    clock = Clock(0.0)
    body_limit = json.dumps({"retCode": 10006, "retMsg": "Too many visits!"}).encode()
    fetch = FakeFetch(
        [
            (200, {"X-Bapi-Limit-Status": "0"}, body_limit),
            (200, {"X-Bapi-Limit-Status": "9"}, _ok_body()),
        ]
    )
    client = _client(clock, fetch)
    record = client.get("/v5/market/tickers?category=linear&symbol=XRPUSDT")
    assert record["response"]["retCode"] == 0
    assert clock.slept == [5.0]
    assert len(fetch.urls) == 2
    assert fetch.urls[0].startswith("https://api.bybit.com")
    assert fetch.urls[1].startswith("https://api.bybit.com")  # rate limit does not rotate


def test_http_429_backs_off_without_raising() -> None:
    clock = Clock(0.0)
    fetch = FakeFetch(
        [
            (429, {}, b"access too frequent"),
            (200, {"X-Bapi-Limit-Status": "8"}, _ok_body()),
        ]
    )
    record = _client(clock, fetch).get(endpoint_path("orderbook", "XRPUSDT"))
    assert record["response"]["retCode"] == 0
    assert clock.slept == [5.0]


def test_geo_403_rotates_to_the_alternate_host() -> None:
    clock = Clock(0.0)
    blocked = b"<html>CloudFront configured to block access from your country</html>"
    fetch = FakeFetch(
        [
            (403, {}, blocked),
            (200, {"X-Bapi-Limit-Status": "9"}, _ok_body("AVAXUSDT")),
        ]
    )
    record = _client(clock, fetch).get(endpoint_path("recent_trade", "AVAXUSDT"))
    assert record["response"]["retCode"] == 0
    assert fetch.urls[0].startswith("https://api.bybit.com")
    assert fetch.urls[1].startswith("https://api.bytick.com")
    assert clock.slept == [2.0]


def test_exhausted_retries_return_an_error_record() -> None:
    clock = Clock(0.0)
    fetch = FakeFetch([OSError("dns down")] * 4)
    record = _client(clock, fetch).get(endpoint_path("ticker", "XRPUSDT"))
    assert "error" in record
    assert "dns down" in record["error"]
    assert len(fetch.urls) == 4
    assert clock.slept == [2.0, 4.0, 6.0, 8.0]


def test_limit_status_zero_keeps_the_body_and_does_not_clear_backoff() -> None:
    clock = Clock(0.0)
    fetch = FakeFetch(
        [(200, {"X-Bapi-Limit-Status": "0"}, _ok_body())]
    )
    client = _client(clock, fetch)
    record = client.get(endpoint_path("ticker", "XRPUSDT"))
    assert record["response"]["retCode"] == 0
    assert clock.slept == [5.0]
    assert client.limiter.backoff_s == 5.0


def test_request_carries_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict = {}

    class _Response:
        status = 200
        headers = {"X-Bapi-Limit-Status": "9"}

        def read(self) -> bytes:
            return _ok_body()

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    def fake_urlopen(request, timeout=0):  # noqa: ANN001
        seen["request"] = request
        return _Response()

    monkeypatch.setattr(
        "scripts.xrp_avax_cost_sampler.urllib.request.urlopen", fake_urlopen
    )
    status, _headers, body = urllib_fetch(
        "https://api.bybit.com/v5/market/tickers?category=linear&symbol=XRPUSDT",
        5,
    )
    request = seen["request"]
    assert status == 200
    assert json.loads(body)["retCode"] == 0
    assert request.get_method() == "GET"
    assert request.data is None
    assert request.get_header("Authorization") is None
    built = build_request("https://api.bybit.com/v5/market/tickers?category=linear&symbol=XRPUSDT")
    header_names = {key.lower() for key, _value in built.header_items()}
    assert "authorization" not in header_names
    assert "user-agent" in header_names


# --- size cap, self-stop, checksums --------------------------------------------


def test_size_cap_stops_further_writes_and_fetches(tmp_path: Path) -> None:
    start = _dt(2026, 10, 10, 5, 0, 0)
    clock = Clock(start.timestamp())
    fetch = FakeFetch()
    sampler = _sampler(
        tmp_path,
        clock,
        fetch,
        end=start + timedelta(seconds=50),
        regular_s=10.0,
        max_bytes=1,
    )
    assert sampler.run() == 0
    # First symbol is stored (the write that crosses the cap). The second
    # symbol, and every later snapshot, is not fetched.
    assert len(fetch.urls) == 3
    assert all("XRPUSDT" in url for url in fetch.urls)
    files = list(tmp_path.glob("*.jsonl.gz"))
    assert len(files) == 1
    assert len(_read_gz(files[0])) == 1
    log = (tmp_path / "sampler.log").read_text(encoding="utf-8")
    assert log.count(" SIZE_CAP ") == 1
    assert "stopped writing market data" in log
    assert (tmp_path / "SAMPLER_DONE").is_file()
    assert clock.now() == (start + timedelta(seconds=50)).timestamp()


def test_self_stop_writes_marker_coverage_and_checksums(tmp_path: Path) -> None:
    start = _dt(2026, 10, 10, 5, 0, 0)
    clock = Clock(start.timestamp())
    fetch = FakeFetch()
    end = start + timedelta(seconds=10)
    sampler = _sampler(tmp_path, clock, fetch, end=end, regular_s=300.0)
    assert sampler.run() == 0
    assert clock.now() == end.timestamp()
    marker = (tmp_path / "SAMPLER_DONE").read_text(encoding="utf-8")
    assert "reason=end_time" in marker
    coverage = (tmp_path / "COVERAGE.md").read_text(encoding="utf-8")
    assert "XRPUSDT" in coverage
    assert "AVAXUSDT" in coverage
    sums = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8")
    names = [line.split("  ", 1)[1] for line in sums.splitlines()]
    assert "SHA256SUMS" not in names
    assert "SAMPLER_DONE" in names
    assert "COVERAGE.md" in names
    assert "sampler.log" in names
    for line in sums.splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
    check = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check.returncode == 0, check.stdout + check.stderr


def test_signal_stop_writes_checksums_without_the_done_marker(tmp_path: Path) -> None:
    start = _dt(2026, 10, 10, 5, 0, 0)
    clock = Clock(start.timestamp())
    fetch = FakeFetch()
    sampler = _sampler(
        tmp_path,
        clock,
        fetch,
        end=start + timedelta(hours=1),
        regular_s=300.0,
    )

    def sleep_and_stop(seconds: float) -> None:
        clock.sleep(seconds)
        if seconds >= 5:
            sampler._stop = True

    sampler._clock_sleep = sleep_and_stop
    assert sampler.run() == 0
    assert not (tmp_path / "SAMPLER_DONE").exists()
    assert (tmp_path / "COVERAGE.md").is_file()
    assert (tmp_path / "SHA256SUMS").is_file()
    assert "END reason=stopped" in (tmp_path / "sampler.log").read_text(encoding="utf-8")
    # One regular shot, then the first 5 s slice of the wait observes the stop.
    assert len(_snap_lines(tmp_path)) == 1


def test_done_marker_prevents_a_second_campaign(tmp_path: Path) -> None:
    (tmp_path / "SAMPLER_DONE").write_text("2026-10-10T00:00:00.000000Z reason=end_time\n")
    clock = Clock(_dt(2026, 10, 10, 6).timestamp())
    fetch = FakeFetch()
    sampler = _sampler(tmp_path, clock, fetch, end=_dt(2026, 10, 11, 0))
    assert sampler.run() == 0
    assert fetch.urls == []
    assert "ALREADY_DONE" in (tmp_path / "sampler.log").read_text(encoding="utf-8")


def test_resume_keeps_the_planned_end_and_elapsed_window_finalizes(tmp_path: Path) -> None:
    start = _dt(2026, 10, 10, 3, 0, 0)
    planned_end = _dt(2026, 10, 10, 5, 0, 0)
    clock = Clock(_dt(2026, 10, 10, 4, 0, 0).timestamp())
    plan = {
        "pid": 1,
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "start_epoch": start.timestamp(),
        "end_utc_planned": planned_end.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "end_epoch": planned_end.timestamp(),
        "symbols": ["XRPUSDT", "AVAXUSDT"],
    }
    (tmp_path / "sampler_run.json").write_text(json.dumps(plan), encoding="utf-8")
    fetch = FakeFetch()
    sampler = _sampler(tmp_path, clock, fetch, hours=None, end=None, regular_s=10_000.0)
    how, end_epoch = sampler.resolve_end()
    assert how == "resume"
    assert end_epoch == planned_end.timestamp()
    assert sampler.run() == 0
    saved = json.loads((tmp_path / "sampler_run.json").read_text(encoding="utf-8"))
    assert saved["end_epoch"] == planned_end.timestamp()
    assert saved["start_utc"] == plan["start_utc"]
    assert "RESUME" in (tmp_path / "sampler.log").read_text(encoding="utf-8")
    assert (tmp_path / "SAMPLER_DONE").is_file()

    # A later start, after the planned end and after the marker is removed,
    # still finalizes that same window instead of opening a new 7-day one.
    (tmp_path / "SAMPLER_DONE").unlink()
    clock.epoch = planned_end.timestamp() + 30
    fetch2 = FakeFetch()
    late = _sampler(tmp_path, clock, fetch2, hours=None, end=None)
    assert late.run() == 0
    assert fetch2.urls == []
    assert "WINDOW_ELAPSED" in (tmp_path / "sampler.log").read_text(encoding="utf-8")


def test_explicit_end_overrides_hours_and_default_is_seven_days(tmp_path: Path) -> None:
    assert DEFAULT_HOURS == 168.0
    assert DEFAULT_MAX_BYTES == 2 * 1024**3
    assert DEFAULT_OUT == "/data/research/cost_sampler_xrp_avax"
    assert SYMBOLS == ("XRPUSDT", "AVAXUSDT")
    clock = Clock(_dt(2026, 10, 10, 0).timestamp())
    fetch = FakeFetch()
    bare = _sampler(tmp_path, clock, fetch)
    how, end_epoch = bare.resolve_end()
    assert how == "default_168h"
    assert end_epoch == clock.now() + 168 * 3600
    ended = _dt(2026, 10, 17, 0, 0, 0)
    chosen = _sampler(tmp_path, clock, fetch, hours=1.0, end=ended)
    how, end_epoch = chosen.resolve_end()
    assert how == "cli_end"
    assert end_epoch == ended.timestamp()


def test_refuses_an_output_path_on_trading_state(tmp_path: Path) -> None:
    banned = tmp_path / "approved_strategies.json"
    with pytest.raises(SystemExit):
        parse_args(["--out", str(banned), "--print-schedule"])
    engine = tmp_path / "core" / "execution" / "engine.py"
    with pytest.raises(SystemExit):
        parse_args(["--out", str(engine)])


def test_sha256sums_matches_file_bytes(tmp_path: Path) -> None:
    append_jsonl_gz(tmp_path / "XRPUSDT_20261010.jsonl.gz", {"symbol": "XRPUSDT", "n": 1})
    (tmp_path / "sampler.log").write_text("hello\n", encoding="utf-8")
    write_sha256sums(tmp_path)
    text = (tmp_path / "SHA256SUMS").read_text(encoding="utf-8")
    assert "SHA256SUMS" not in text.split()
    for line in text.splitlines():
        digest, name = line.split("  ", 1)
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest


# --- coverage ------------------------------------------------------------------


def _log_line(moment: datetime, message: str) -> str:
    return "%s %s" % (moment.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), message)


def test_coverage_lists_missed_bursts_and_gaps_over_six_minutes() -> None:
    start = _dt(2026, 10, 10, 3, 0, 0)
    end = _dt(2026, 10, 10, 9, 0, 0)
    lines: list[str] = []
    # Regular snaps every 5 minutes, with a 40 minute hole, and a full burst at 04:00.
    cursor = start
    hole_lo = _dt(2026, 10, 10, 5, 0, 0)
    hole_hi = _dt(2026, 10, 10, 5, 40, 0)
    while cursor <= end:
        if hole_lo < cursor < hole_hi:
            cursor += timedelta(minutes=5)
            continue
        lines.append(_log_line(cursor, "SNAP regular5m ok=6/6"))
        cursor += timedelta(minutes=5)
    burst = _dt(2026, 10, 10, 3, 58, 0)
    for _ in range(20):
        lines.append(_log_line(burst, "SNAP burst4h ok=6/6"))
        burst += timedelta(seconds=15)
    # One partial regular, so the detail section has something to show.
    lines.append(_log_line(_dt(2026, 10, 10, 6, 15, 0), "SNAP regular5m ok=5/6"))
    lines.append(
        _log_line(_dt(2026, 10, 10, 6, 20, 0), "REQ_FAIL attempt=1 /v5/market/tickers dns")
    )
    lines.append(
        _log_line(
            _dt(2026, 10, 10, 6, 21, 0),
            "SIZE_CAP bytes=10 cap=20 stopped writing market data",
        )
    )
    run = {
        "pid": 42,
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "end_utc_planned": end.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "symbols": ["XRPUSDT", "AVAXUSDT"],
    }
    text = render_coverage(
        log_text="\n".join(lines) + "\n",
        run=run,
        generated=_dt(2026, 10, 10, 9, 5, 0),
    )
    assert "PID: 42" in text
    assert "| 2026-10-10 04:00 | 2026-10-10 08:00 | CAPTURED | 20 |" in text
    assert "| 2026-10-10 08:00 | 2026-10-10 12:00 | MISSED | 0 | — |" in text
    assert "Missed: 1" in text
    assert "40m00s" in text
    assert "2026-10-10 05:00:00" in text
    assert "2026-10-10 05:40:00" in text
    assert "ok=5/6" in text
    assert "REQ_FAIL log lines: 1" in text
    assert "SIZE_CAP log lines: 1" in text
    # A 5 minute step is not a gap.
    assert "5m00s" not in text


def test_gap_threshold_is_strictly_over_six_minutes() -> None:
    start = _dt(2026, 10, 10, 1, 0, 0)
    almost = start + timedelta(seconds=360)
    over = start + timedelta(seconds=361)
    run = {
        "start_utc": start.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "end_utc_planned": over.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }
    quiet = "\n".join(
        [
            _log_line(start, "SNAP regular5m ok=6/6"),
            _log_line(almost, "SNAP regular5m ok=6/6"),
        ]
    )
    assert "None." in render_coverage(log_text=quiet, run=run, generated=over)
    loud = "\n".join(
        [
            _log_line(start, "SNAP regular5m ok=6/6"),
            _log_line(over, "SNAP regular5m ok=6/6"),
        ]
    )
    rendered = render_coverage(log_text=loud, run=run, generated=over)
    assert "6m01s" in rendered


# --- process boundaries --------------------------------------------------------


def test_module_imports_stdlib_only_and_does_not_name_trading_state() -> None:
    source_path = Path(__file__).resolve().parents[1] / "scripts" / "xrp_avax_cost_sampler.py"
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    assert roots <= {
        "__future__",
        "argparse",
        "gzip",
        "hashlib",
        "json",
        "os",
        "re",
        "signal",
        "sys",
        "time",
        "urllib",
        "datetime",
        "pathlib",
        "typing",
        "dataclasses",
    }
    # The deny-list names those paths so a bad --out cannot land on them.
    # Nothing else in the sampler may mention trading state, docker, or keys.
    deny = source.split("_BANNED_OUT_FRAGMENTS", 1)[1].split(")", 1)[0]
    body = source.replace(deny, "")
    for banned in ("docker", "subprocess", "pybit", "api_key", "API_KEY", "approved_strategies"):
        assert banned not in body
    assert "core/execution/engine.py" not in body


def test_systemd_unit_is_a_non_root_host_service() -> None:
    unit = (
        Path(__file__).resolve().parents[1]
        / "deploy"
        / "systemd"
        / "cost-sampler-xrp-avax.service"
    )
    text = unit.read_text(encoding="utf-8")
    assert "User=costsampler" in text
    assert "Group=costsampler" in text
    assert "User=root" not in text
    assert "docker" not in text.lower()
    assert "approved_strategies" not in text
    assert "engine.py" not in text
    assert "/data/research/cost_sampler_xrp_avax" in text
    assert "/opt/cost-sampler/xrp_avax_cost_sampler.py" in text
    # No --hours on the command: a reboot must resume the planned end.
    exec_lines = [line for line in text.splitlines() if line.startswith("ExecStart=")]
    assert exec_lines and all("--hours" not in line for line in exec_lines)
    assert "Restart=on-failure" in text
    assert "ProtectSystem=strict" in text


def test_parse_args_defaults(tmp_path: Path) -> None:
    settings, print_only = parse_args(["--out", str(tmp_path), "--print-schedule"])
    assert print_only is True
    assert settings.once is False
    assert settings.hours is None
    assert settings.end is None
    assert settings.max_bytes == DEFAULT_MAX_BYTES
    assert settings.symbols == SYMBOLS
