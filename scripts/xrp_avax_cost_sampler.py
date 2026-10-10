#!/usr/bin/env python3
"""Read-only Bybit v5 public sampler for XRPUSDT and AVAXUSDT linear perps.

This process measures book, trade, and ticker state for a cost study. It does
not trade, does not read API keys, and does not import the firm runtime.

Schedule (UTC, aligned to the Unix epoch, which is a 4h boundary):
  * one snapshot every 5 minutes
  * from 2 minutes before until 3 minutes after each 4h candle open
    (00/04/08/12/16/20 UTC), one snapshot every 15 seconds instead

Each snapshot, per symbol, is three unauthenticated GETs:
  * /v5/market/orderbook?category=linear&symbol=SYM&limit=50
  * /v5/market/recent-trade?category=linear&symbol=SYM&limit=1000
  * /v5/market/tickers?category=linear&symbol=SYM

Bybit's public HTTP IP budget is 600 requests per 5 seconds. This job caps
itself at 10 requests per 5 seconds and spaces calls by at least 250 ms, so a
burst (6 calls) stays under 2 requests/second. That is well under the IP cap.

Disk: one gzip JSONL per symbol per UTC date. A size cap (default 2 GiB of
those data files) stops further market-data writes and logs SIZE_CAP. Control
files (log, coverage, checksums) are not counted toward the cap.

The process plans its own end at start + 168 hours unless --end / --hours is
set, remembers that instant in sampler_run.json, and on the planned end writes
COVERAGE.md, SHA256SUMS, and a SAMPLER_DONE marker. A host reboot resumes until
the original planned end. SIGTERM (systemctl stop) writes coverage and
checksums but does not write SAMPLER_DONE, so a later start continues.

Stdlib only, so the SGP1 host can run it with system Python and without the
paper-trading environment.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence

# --- market and schedule -------------------------------------------------------

HOSTS: tuple[str, ...] = ("https://api.bybit.com", "https://api.bytick.com")
SYMBOLS: tuple[str, ...] = ("XRPUSDT", "AVAXUSDT")
CATEGORY = "linear"

# Desktop cost run used these same public paths (BTC/ETH/SOL, 26h). Kept stable
# so a later scorer can read either campaign the same way.
ORDERBOOK_LIMIT = 50
TRADE_LIMIT = 1000

REGULAR_S = 300.0
BURST_S = 15.0
BURST_PRE = 120.0
BURST_POST = 180.0
BAR_S = 4 * 3600.0  # 00/04/08/12/16/20 UTC. Epoch itself is one of these opens.
BAR_HOURS_UTC: tuple[int, ...] = (0, 4, 8, 12, 16, 20)

DEFAULT_HOURS = 168.0  # 7 days
DEFAULT_OUT = "/data/research/cost_sampler_xrp_avax"
DEFAULT_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB of *.jsonl / *.jsonl.gz

# Bybit documents 600 HTTP requests / 5 seconds / IP on the public hosts.
# Stay at or under ~2% of that, and also space calls so a 6-call snapshot
# cannot clump. 10 per 5s == 2 req/s average; 250 ms spacing == 4 req/s peak.
BYBIT_IP_LIMIT_PER_5S = 600
MIN_INTERVAL_S = 0.25
RATE_WINDOW_S = 5.0
MAX_PER_WINDOW = 10
BACKOFF_MIN_S = 5.0
BACKOFF_MAX_S = 120.0
HTTP_ATTEMPTS = 4
HTTP_TIMEOUT_S = 15.0

# A burst the process was fully awake for should land about 20 shots
# (the window is 300 s; 15 s spacing; the desktop run recorded 20, an
# instantaneous clock records 21). Fewer than this, with the whole window
# inside the run, is reported as PARTIAL rather than CAPTURED.
FULL_WINDOW_CAPTURED_MIN = 15
GAP_THRESHOLD_S = 360.0  # coverage lists holes longer than 6 minutes

USER_AGENT = "mo-cost-measurement/1.1 (public market data; xrp-avax; read-only)"
GST = timezone(timedelta(hours=4))  # Gulf Standard Time, no daylight saving

# Output paths that would land on trading state are refused before any write.
_BANNED_OUT_FRAGMENTS = (
    "approved_strategies.json",
    "core/execution/engine.py",
    "firm.db",
    "paper_cash.json",
)

ENDPOINTS: tuple[tuple[str, str], ...] = (
    (
        "orderbook",
        "/v5/market/orderbook?category={category}&symbol={symbol}&limit={limit}",
    ),
    (
        "recent_trade",
        "/v5/market/recent-trade?category={category}&symbol={symbol}&limit={limit}",
    ),
    (
        "ticker",
        "/v5/market/tickers?category={category}&symbol={symbol}",
    ),
)

SNAP_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)"
    r"\s+SNAP\s+(?P<kind>\S+)\s+ok=(?P<ok>\d+)/(?P<n>\d+)\s*$"
)

NowFn = Callable[[], float]
SleepFn = Callable[[float], None]
FetchFn = Callable[[str, float], tuple[int, dict[str, str], bytes]]


# --- time ----------------------------------------------------------------------

def iso_z(epoch: float) -> str:
    """UTC timestamp with a Z suffix and microseconds, matching the desktop log."""
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_utc(text: str) -> datetime:
    """Parse an ISO-8601 instant. Naive values are treated as UTC. Z is accepted."""
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def bar_floor(epoch: float, bar_s: float = BAR_S) -> float:
    """Greatest 4h boundary at or before `epoch` (epoch is well above zero)."""
    return epoch - (epoch % bar_s)


def nearest_bar_open(epoch: float, bar_s: float = BAR_S) -> float:
    """Closest 4h boundary. Exact midpoints belong to the later bar."""
    base = bar_floor(epoch, bar_s)
    if (epoch - base) * 2 >= bar_s:
        return base + bar_s
    return base


def burst_offset(epoch: float, bar_s: float = BAR_S) -> float:
    """Seconds relative to the nearest 4h open. Negative means before the open."""
    return epoch - nearest_bar_open(epoch, bar_s)


def in_burst(
    epoch: float,
    *,
    pre: float = BURST_PRE,
    post: float = BURST_POST,
    bar_s: float = BAR_S,
) -> bool:
    """True from `pre` seconds before a 4h open through `post` seconds after."""
    offset = burst_offset(epoch, bar_s)
    return -pre <= offset <= post


def next_burst_start(
    epoch: float,
    *,
    pre: float = BURST_PRE,
    post: float = BURST_POST,
    bar_s: float = BAR_S,
) -> float:
    """When the next burst window starts.

    If `epoch` is already inside a window, the start is `epoch` itself: the
    caller should shoot (or wait for the 15 s slot), not skip ahead a bar.
    """
    if in_burst(epoch, pre=pre, post=post, bar_s=bar_s):
        return epoch
    base = bar_floor(epoch, bar_s)
    this_start = base - pre
    if epoch < this_start:
        return this_start
    return base + bar_s - pre


def upcoming_bar_opens(
    epoch: float,
    count: int,
    *,
    pre: float = BURST_PRE,
    post: float = BURST_POST,
    bar_s: float = BAR_S,
) -> list[float]:
    """Next `count` 4h opens whose burst window has not already closed."""
    if count < 1:
        return []
    base = bar_floor(epoch, bar_s)
    open_epoch = base
    if epoch > open_epoch + post:
        open_epoch = base + bar_s
    opens: list[float] = []
    while len(opens) < count:
        opens.append(open_epoch)
        open_epoch += bar_s
    return opens


def iter_bar_opens(start: datetime, end: datetime) -> list[datetime]:
    """4h opens with start <= open <= end, in UTC."""
    start_utc = start.astimezone(timezone.utc)
    end_utc = end.astimezone(timezone.utc)
    hour = (start_utc.hour // 4) * 4
    cursor = start_utc.replace(hour=hour, minute=0, second=0, microsecond=0)
    if cursor < start_utc:
        cursor += timedelta(hours=4)
    opens: list[datetime] = []
    while cursor <= end_utc:
        opens.append(cursor)
        cursor += timedelta(hours=4)
    return opens


def format_schedule(epoch: float, count: int = 3) -> str:
    """Human schedule for the runbook's burst check. No network, no writes."""
    now = datetime.fromtimestamp(epoch, timezone.utc)
    gst = now.astimezone(GST)
    lines = [
        "now_utc=%s now_gst=%s in_burst=%s"
        % (
            now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            gst.strftime("%Y-%m-%dT%H:%M:%S"),
            "yes" if in_burst(epoch) else "no",
        )
    ]
    for open_epoch in upcoming_bar_opens(epoch, count):
        open_dt = datetime.fromtimestamp(open_epoch, timezone.utc)
        win_start = open_dt - timedelta(seconds=BURST_PRE)
        win_end = open_dt + timedelta(seconds=BURST_POST)
        lines.append(
            "bar_open_utc=%s bar_open_gst=%s window_utc=%s..%s"
            % (
                open_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                open_dt.astimezone(GST).strftime("%Y-%m-%dT%H:%M:%S"),
                win_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                win_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        )
    return "\n".join(lines) + "\n"


def _fmt_span(seconds: float) -> str:
    whole = int(round(seconds))
    minutes, secs = divmod(whole, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return "%dh%02dm%02ds" % (hours, minutes, secs)
    return "%dm%02ds" % (minutes, secs)


def _fmt_utc(moment: datetime, *, seconds: bool = True) -> str:
    pattern = "%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M"
    return moment.astimezone(timezone.utc).strftime(pattern)


def _fmt_gst(moment: datetime, *, seconds: bool = True) -> str:
    pattern = "%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M"
    return moment.astimezone(GST).strftime(pattern)


# --- paths and disk ------------------------------------------------------------

def assert_out_allowed(path: Path) -> Path:
    """Refuse an output directory that would sit on trading state.

    The sampler only ever writes under the directory it is given. This check
    is a backstop so a bad --out cannot land on the approval book, the engine
    source, or the paper ledger.
    """
    resolved = path.expanduser().resolve()
    lowered = str(resolved).lower().replace("\\", "/")
    for fragment in _BANNED_OUT_FRAGMENTS:
        if fragment in lowered:
            raise SystemExit(
                "refusing output path that touches trading state: %s" % resolved
            )
    return resolved


def daily_path(out: Path, symbol: str, epoch: float) -> Path:
    """UTC-date rotated gzip JSONL: SYMBOL_YYYYMMDD.jsonl.gz."""
    day = datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y%m%d")
    return out / ("%s_%s.jsonl.gz" % (symbol, day))


def market_data_bytes(out: Path) -> int:
    """Bytes of market-data files only. Log and manifests do not count."""
    if not out.is_dir():
        return 0
    total = 0
    for path in out.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name.endswith(".jsonl") or name.endswith(".jsonl.gz"):
            total += path.stat().st_size
    return total


def append_jsonl_gz(path: Path, record: dict) -> None:
    """Append one JSON line as its own gzip member.

    Gzip members concatenate. A crash mid-write loses at most the member in
    flight; readers see every earlier line. compresslevel=1 keeps CPU small
    on the 15 s burst without giving up most of the JSON ratio.
    """
    line = (json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    with gzip.open(path, "ab", compresslevel=1) as handle:
        handle.write(line)


def _atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def write_sha256sums(out: Path) -> Path:
    """Write SHA256SUMS for every file in `out` except the checksum file itself.

    Two spaces separate digest and name so `sha256sum -c SHA256SUMS` works.
    """
    rows: list[str] = []
    for path in sorted(p for p in out.iterdir() if p.is_file()):
        if path.name in ("SHA256SUMS", "SHA256SUMS.tmp"):
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        rows.append("%s  %s" % (digest.hexdigest(), path.name))
    text = ("\n".join(rows) + "\n") if rows else ""
    destination = out / "SHA256SUMS"
    _atomic_text(destination, text)
    return destination


# --- coverage ------------------------------------------------------------------

@dataclass
class _Snap:
    at: datetime
    kind: str
    ok: int
    total: int


def _parse_snaps(log_text: str) -> list[_Snap]:
    snaps: list[_Snap] = []
    for line in log_text.splitlines():
        match = SNAP_RE.match(line.strip())
        if match is None:
            continue
        snaps.append(
            _Snap(
                at=parse_utc(match.group("ts")),
                kind=match.group("kind"),
                ok=int(match.group("ok")),
                total=int(match.group("n")),
            )
        )
    snaps.sort(key=lambda snap: snap.at)
    return snaps


def _count_tag(log_text: str, tag: str) -> int:
    needle = " " + tag + " "
    return sum(1 for line in log_text.splitlines() if needle in (" " + line + " "))


def render_coverage(
    *,
    log_text: str,
    run: Optional[dict],
    generated: datetime,
    symbols: Sequence[str] = SYMBOLS,
) -> str:
    """COVERAGE.md body: snap totals, gaps over 6 minutes, missed 4h bursts.

    The window comes from sampler_run.json when the campaign recorded one, so
    a burst with zero shots still appears as MISSED. The desktop Part-2 note
    is the shape this report follows (UTC and GST, CAPTURED vs MISSED).
    """
    snaps = _parse_snaps(log_text)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    if run:
        if run.get("start_utc"):
            start = parse_utc(str(run["start_utc"]))
        if run.get("end_utc_planned"):
            end = parse_utc(str(run["end_utc_planned"]))
    if start is None and snaps:
        start = snaps[0].at
    if end is None and snaps:
        end = snaps[-1].at

    by_kind: dict[str, int] = {}
    ok_sum = 0
    req_sum = 0
    partial = 0
    for snap in snaps:
        by_kind[snap.kind] = by_kind.get(snap.kind, 0) + 1
        ok_sum += snap.ok
        req_sum += snap.total
        if snap.ok < snap.total:
            partial += 1

    gaps: list[tuple[_Snap, _Snap, float]] = []
    for left, right in zip(snaps, snaps[1:]):
        delta = (right.at - left.at).total_seconds()
        if delta > GAP_THRESHOLD_S:
            gaps.append((left, right, delta))

    burst_rows: list[str] = []
    missed = 0
    captured = 0
    partial_bursts = 0
    if start is not None and end is not None:
        for open_at in iter_bar_opens(start, end):
            win_lo = open_at - timedelta(seconds=BURST_PRE)
            win_hi = open_at + timedelta(seconds=BURST_POST)
            shots = [
                snap
                for snap in snaps
                if snap.kind == "burst4h" and win_lo <= snap.at <= win_hi
            ]
            full = start <= win_lo and end >= win_hi
            if not shots:
                status = "MISSED"
                missed += 1
                detail = "0"
            elif full and len(shots) < FULL_WINDOW_CAPTURED_MIN:
                status = "PARTIAL"
                partial_bursts += 1
                detail = str(len(shots))
            else:
                status = "CAPTURED"
                captured += 1
                detail = str(len(shots))
            req_ok = sum(snap.ok for snap in shots)
            req_n = sum(snap.total for snap in shots)
            req_cell = "%d/%d" % (req_ok, req_n) if shots else "—"
            burst_rows.append(
                "| %s | %s | %s | %s | %s |"
                % (
                    _fmt_utc(open_at, seconds=False),
                    _fmt_gst(open_at, seconds=False),
                    status,
                    detail,
                    req_cell,
                )
            )

    symbol_text = ", ".join(symbols)
    lines: list[str] = []
    lines.append("# Bybit sampler coverage (XRPUSDT / AVAXUSDT)")
    lines.append("")
    lines.append("Generated: %s UTC (%s GST)" % (_fmt_utc(generated), _fmt_gst(generated)))
    lines.append("Source log: `sampler.log`")
    if start is not None and end is not None:
        lines.append(
            "Run window: %s – %s (%s – %s GST)"
            % (_fmt_utc(start), _fmt_utc(end), _fmt_gst(start), _fmt_gst(end))
        )
    pid = (run or {}).get("pid")
    lines.append(
        "PID: %s · symbols: %s · category: linear · regular 5m · "
        "burst 15s in [-120, +180]s around 4h bar opens"
        % (pid if pid is not None else "—", symbol_text)
    )
    lines.append("")
    lines.append("Public endpoints only (no API key): 50-level orderbook, recent trades, tickers.")
    lines.append("")
    lines.append("## SNAP totals")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|------:|")
    lines.append("| SNAP lines | %d |" % len(snaps))
    for kind in ("once_test", "regular5m", "burst4h"):
        lines.append("| of which %s | %d |" % (kind, by_kind.get(kind, 0)))
    for kind in sorted(k for k in by_kind if k not in ("once_test", "regular5m", "burst4h")):
        lines.append("| of which %s | %d |" % (kind, by_kind[kind]))
    lines.append("| Requests OK | %d |" % ok_sum)
    lines.append("| Requests failed (in SNAP ok/N) | %d |" % (req_sum - ok_sum))
    lines.append("| Requests total | %d |" % req_sum)
    lines.append("| Partial SNAP lines (ok < N) | %d |" % partial)
    lines.append("")
    lines.append("REQ_FAIL log lines: %d" % _count_tag(log_text, "REQ_FAIL"))
    lines.append("RATE_LIMIT log lines: %d" % _count_tag(log_text, "RATE_LIMIT"))
    lines.append("GEO_BLOCK log lines: %d" % _count_tag(log_text, "GEO_BLOCK"))
    lines.append("SIZE_CAP log lines: %d" % _count_tag(log_text, "SIZE_CAP"))
    lines.append("")
    if partial:
        lines.append("Partial SNAP detail:")
        lines.append("")
        for snap in snaps:
            if snap.ok < snap.total:
                lines.append(
                    "- %s UTC (%s GST) — `%s ok=%d/%d`"
                    % (
                        _fmt_utc(snap.at),
                        _fmt_gst(snap.at),
                        snap.kind,
                        snap.ok,
                        snap.total,
                    )
                )
        lines.append("")

    lines.append("## Gaps over 6 minutes")
    lines.append("")
    lines.append(
        "Expected cadence is about 5 minutes between regular snaps, and 15 seconds "
        "inside a burst. Gaps longer than 6 minutes:"
    )
    lines.append("")
    if not gaps:
        lines.append("None.")
        lines.append("")
    else:
        lines.append("| # | Duration | From (UTC) | To (UTC) | From (GST) | To (GST) |")
        lines.append("|---|----------|------------|----------|------------|----------|")
        total_gap = 0.0
        for index, (left, right, delta) in enumerate(gaps, start=1):
            total_gap += delta
            lines.append(
                "| %d | %s | %s | %s | %s | %s |"
                % (
                    index,
                    _fmt_span(delta),
                    _fmt_utc(left.at),
                    _fmt_utc(right.at),
                    _fmt_gst(left.at),
                    _fmt_gst(right.at),
                )
            )
        lines.append("")
        lines.append("Total gap time over 6m threshold: %s." % _fmt_span(total_gap))
        lines.append("")

    lines.append("## 4h bar-open bursts (00 / 04 / 08 / 12 / 16 / 20 UTC)")
    lines.append("")
    lines.append(
        "Burst window: bar-open −120s to +180s. Only bars whose open falls inside "
        "the run window are listed."
    )
    lines.append("")
    if not burst_rows:
        lines.append("No 4h open inside the run window.")
        lines.append("")
    else:
        lines.append(
            "| Bar open (UTC) | Bar open (GST) | Status | burst4h snaps | Requests |"
        )
        lines.append(
            "|----------------|----------------|--------|---------------|----------|"
        )
        lines.extend(burst_rows)
        lines.append("")
        lines.append(
            "Captured: %d · Partial: %d · Missed: %d"
            % (captured, partial_bursts, missed)
        )
        lines.append("")
        lines.append(
            "PARTIAL means the run window covered the whole burst and fewer than "
            "%d burst snaps were stored (a full window is about 20)."
            % FULL_WINDOW_CAPTURED_MIN
        )
        lines.append("")

    lines.append("## First / last SNAP")
    lines.append("")
    if snaps:
        first, last = snaps[0], snaps[-1]
        lines.append(
            "- First: %s UTC (%s GST) %s"
            % (_fmt_utc(first.at), _fmt_gst(first.at), first.kind)
        )
        lines.append(
            "- Last: %s UTC (%s GST) %s"
            % (_fmt_utc(last.at), _fmt_gst(last.at), last.kind)
        )
    else:
        lines.append("- No SNAP lines.")
    end_lines = [line for line in log_text.splitlines() if " END " in (" " + line + " ")]
    if end_lines:
        lines.append("- %s" % end_lines[-1].strip())
    lines.append("")
    size_lines = [
        line.strip()
        for line in log_text.splitlines()
        if " SIZE_CAP " in (" " + line + " ")
    ]
    if size_lines:
        lines.append("## Size cap")
        lines.append("")
        lines.append(
            "Market-data writes stopped after the cap. Later control files are not counted."
        )
        lines.append("")
        for line in size_lines:
            lines.append("- `%s`" % line)
        lines.append("")
    lines.append("")
    return "\n".join(lines)


# --- rate limit and HTTP -------------------------------------------------------

class RateLimiter:
    """Spacing plus a short rolling window, with exponential backoff on 10006/429.

    `acquire` blocks (via the injected sleep) until a call is allowed.
    `note_rate_limit` is what the HTTP client consults after Bybit says no;
    the sleep for that penalty happens in the client so tests can see it.
    """

    def __init__(
        self,
        *,
        min_interval_s: float = MIN_INTERVAL_S,
        window_s: float = RATE_WINDOW_S,
        max_per_window: int = MAX_PER_WINDOW,
        now: NowFn,
        sleep: SleepFn,
    ) -> None:
        self.min_interval_s = min_interval_s
        self.window_s = window_s
        self.max_per_window = max_per_window
        self._now = now
        self._sleep = sleep
        self._stamps: list[float] = []
        self.backoff_s = 0.0

    def acquire(self) -> None:
        while True:
            now = self._now()
            self._stamps = [stamp for stamp in self._stamps if now - stamp < self.window_s]
            wait = 0.0
            if self._stamps and self.min_interval_s > 0:
                since = now - self._stamps[-1]
                if since < self.min_interval_s:
                    wait = max(wait, self.min_interval_s - since)
            if len(self._stamps) >= self.max_per_window:
                wait = max(wait, self.window_s - (now - self._stamps[0]))
            if wait <= 1e-9:
                break
            self._sleep(wait)
        self._stamps.append(self._now())

    def note_rate_limit(self) -> float:
        self.backoff_s = min(max(self.backoff_s * 2.0, BACKOFF_MIN_S), BACKOFF_MAX_S)
        return self.backoff_s

    def note_ok(self) -> None:
        self.backoff_s = 0.0


def build_request(url: str) -> urllib.request.Request:
    """GET with a User-Agent and nothing else. No key, no signature, no body."""
    return urllib.request.Request(
        url,
        data=None,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )


def urllib_fetch(url: str, timeout: float) -> tuple[int, dict[str, str], bytes]:
    """One GET. HTTP error statuses are returned, not raised, so the caller can retry."""
    request = build_request(url)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            headers = {key: value for key, value in response.headers.items()}
            status = getattr(response, "status", 200)
            return int(status), headers, body
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        headers = {key: value for key, value in exc.headers.items()} if exc.headers else {}
        return int(exc.code), headers, body


def _header_map(headers: dict[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def is_geo_block(status: int, body: bytes) -> bool:
    """CloudFront country block or HTTP 451. Not the same as a rate-limit 403."""
    if status == 451:
        return True
    if status != 403:
        return False
    text = body.lower()
    if b"too frequent" in text or b"too many" in text:
        return False
    return b"block access from your country" in text or b"cloudfront" in text


def is_rate_limited_http(status: int, body: bytes) -> bool:
    if status == 429:
        return True
    text = body.lower()
    return b"too frequent" in text or b"access too frequent" in text


def endpoint_path(name: str, symbol: str) -> str:
    if name == "orderbook":
        return ENDPOINTS[0][1].format(
            category=CATEGORY, symbol=symbol, limit=ORDERBOOK_LIMIT
        )
    if name == "recent_trade":
        return ENDPOINTS[1][1].format(
            category=CATEGORY, symbol=symbol, limit=TRADE_LIMIT
        )
    if name == "ticker":
        return ENDPOINTS[2][1].format(category=CATEGORY, symbol=symbol)
    raise KeyError(name)


class PublicClient:
    """Unauthenticated Bybit GET with host rotation, retries, and backoff."""

    def __init__(
        self,
        *,
        hosts: Sequence[str] = HOSTS,
        limiter: RateLimiter,
        now: NowFn,
        sleep: SleepFn,
        log: Callable[[str], None],
        fetch: FetchFn = urllib_fetch,
        timeout: float = HTTP_TIMEOUT_S,
        attempts: int = HTTP_ATTEMPTS,
    ) -> None:
        self.hosts = tuple(hosts)
        self.host_idx = 0
        self.limiter = limiter
        self._now = now
        self._sleep = sleep
        self._log = log
        self._fetch = fetch
        self.timeout = timeout
        self.attempts = attempts

    def get(self, path: str) -> dict:
        last_error = "no attempt"
        for attempt in range(1, self.attempts + 1):
            self.limiter.acquire()
            host = self.hosts[self.host_idx % len(self.hosts)]
            url = host + path
            sent = self._now()
            try:
                status, headers, body = self._fetch(url, self.timeout)
            except Exception as exc:  # network, DNS, timeout — retry, do not crash the week
                last_error = "%s %s" % (type(exc).__name__, exc)
                self._log("REQ_FAIL attempt=%d %s %s" % (attempt, path, last_error))
                self._sleep(2.0 * attempt)
                continue
            recv = self._now()
            lowered = _header_map(headers)
            rate_hdr = {
                key: value for key, value in lowered.items() if key.startswith("x-bapi-limit")
            }
            parsed: Optional[dict] = None
            try:
                loaded = json.loads(body.decode("utf-8"))
                if isinstance(loaded, dict):
                    parsed = loaded
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
            ret = parsed.get("retCode") if parsed else None
            limit_status = lowered.get("x-bapi-limit-status")
            record = {
                "host": host,
                "path": path,
                "http_status": status,
                "req_sent_ms": int(sent * 1000),
                "resp_recv_ms": int(recv * 1000),
                "rtt_ms": round((recv - sent) * 1000, 1),
                "rate_hdr": rate_hdr,
                "response": parsed
                if parsed is not None
                else {"retCode": None, "raw_len": len(body)},
            }
            if is_rate_limited_http(status, body) or ret == 10006:
                # 10006 / 429 / "access too frequent" stay on the same host.
                # Backoff doubles from 5 s up to 120 s across later hits.
                delay = self.limiter.note_rate_limit()
                last_error = "RATE_LIMIT http=%s retCode=%s" % (status, ret)
                self._log(
                    "RATE_LIMIT %s retCode=%s http=%s backoff=%.0fs"
                    % (path, ret, status, delay)
                )
                self._sleep(delay)
                continue
            if status in (403, 451):
                # Country block (the 2026-10-09 SGP1 failure) or a WAF 403.
                # Try the alternate public host. Do not add a proxy or a key.
                self.host_idx += 1
                tag = "GEO_BLOCK" if is_geo_block(status, body) else "HTTP_403"
                last_error = "%s HTTP %s %s" % (tag, status, host)
                self._log(
                    "%s attempt=%d %s host=%s http=%s" % (tag, attempt, path, host, status)
                )
                self._sleep(min(2.0 * attempt, 10.0))
                continue
            if status >= 400:
                last_error = "HTTP %s %s" % (status, host)
                self._log("REQ_FAIL attempt=%d %s %s" % (attempt, path, last_error))
                self._sleep(2.0 * attempt)
                continue
            if limit_status == "0":
                # Payload is usable, but the budget is exhausted. Keep the body
                # and wait before the next call so we do not immediately 10006.
                # Do not clear backoff on this response: the next penalty
                # should still double.
                delay = self.limiter.note_rate_limit()
                self._log(
                    "RATE_LIMIT %s limit_status=0 backoff=%.0fs" % (path, delay)
                )
                self._sleep(delay)
            if parsed is None or ret != 0:
                message = ""
                if parsed is not None:
                    message = str(parsed.get("retMsg") or "")[:200]
                self._log("API_ERR %s retCode=%s retMsg=%s" % (path, ret, message))
            elif limit_status != "0":
                self.limiter.note_ok()
            return record
        return {"path": path, "error": last_error}


# --- campaign ------------------------------------------------------------------

@dataclass
class Settings:
    out: Path
    symbols: tuple[str, ...] = SYMBOLS
    hours: Optional[float] = None
    end: Optional[datetime] = None
    once: bool = False
    max_bytes: int = DEFAULT_MAX_BYTES
    regular_s: float = REGULAR_S
    burst_s: float = BURST_S
    burst_pre_s: float = BURST_PRE
    burst_post_s: float = BURST_POST
    bar_s: float = BAR_S
    min_interval_s: float = MIN_INTERVAL_S
    window_s: float = RATE_WINDOW_S
    max_per_window: int = MAX_PER_WINDOW
    hosts: tuple[str, ...] = HOSTS


class Sampler:
    """One campaign: schedule, write, stop, manifest."""

    def __init__(
        self,
        settings: Settings,
        *,
        now: Optional[NowFn] = None,
        sleep: Optional[SleepFn] = None,
        fetch: Optional[FetchFn] = None,
        install_signals: bool = True,
    ) -> None:
        self.settings = settings
        self._now = now or time.time
        self._clock_sleep = sleep or time.sleep
        self._fetch = fetch or urllib_fetch
        self.install_signals = install_signals
        self._stop = False
        self.capped = False
        self.out = settings.out
        self._client: Optional[PublicClient] = None

    def now(self) -> float:
        return self._now()

    def _wait(self, seconds: float) -> None:
        """Sleep `seconds`, waking at least every 5 s so SIGTERM is not stuck behind a 5 min nap.

        Five-second slices are still idle: the box is not polling Bybit between snaps.
        """
        remaining = seconds
        while remaining > 0 and not self._stop:
            step = min(5.0, remaining)
            self._clock_sleep(step)
            remaining -= step

    def emit(self, message: str) -> None:
        line = "%s %s" % (iso_z(self.now()), message)
        try:
            with (self.out / "sampler.log").open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        except OSError:
            pass
        print(line, file=sys.stderr, flush=True)

    def _on_signal(self, signum: int, _frame: object) -> None:
        self._stop = True
        self.emit("SIGNAL %s" % signum)

    def _install_signals(self) -> None:
        if not self.install_signals:
            return
        signal.signal(signal.SIGTERM, self._on_signal)
        signal.signal(signal.SIGINT, self._on_signal)

    def _client_or_new(self) -> PublicClient:
        if self._client is None:
            limiter = RateLimiter(
                min_interval_s=self.settings.min_interval_s,
                window_s=self.settings.window_s,
                max_per_window=self.settings.max_per_window,
                now=self.now,
                sleep=self._clock_sleep,
            )
            self._client = PublicClient(
                hosts=self.settings.hosts,
                limiter=limiter,
                now=self.now,
                sleep=self._clock_sleep,
                log=self.emit,
                fetch=self._fetch,
            )
        return self._client

    def _trip_cap(self) -> None:
        if self.capped:
            return
        self.capped = True
        used = market_data_bytes(self.out)
        self.emit(
            "SIZE_CAP bytes=%d cap=%d stopped writing market data"
            % (used, self.settings.max_bytes)
        )

    def _count_ok(self, record: dict) -> int:
        ok = 0
        for name, _template in ENDPOINTS:
            response = (record.get(name) or {}).get("response") or {}
            if isinstance(response, dict) and response.get("retCode") == 0:
                ok += 1
        return ok

    def snapshot(self, kind: str) -> tuple[int, int]:
        """Write one gzip line per symbol. Returns (ok_requests, expected_requests)."""
        expected = len(self.settings.symbols) * len(ENDPOINTS)
        if self.capped or market_data_bytes(self.out) >= self.settings.max_bytes:
            if market_data_bytes(self.out) >= self.settings.max_bytes:
                self._trip_cap()
            return 0, expected
        client = self._client_or_new()
        taken = self.now()
        n_ok = 0
        wrote = 0
        for symbol in self.settings.symbols:
            if self.capped or self._stop:
                break
            record: dict = {
                "local_utc": iso_z(taken),
                "kind": kind,
                "symbol": symbol,
                "category": CATEGORY,
            }
            for name, _template in ENDPOINTS:
                record[name] = client.get(endpoint_path(name, symbol))
            book = (record.get("orderbook") or {}).get("response") or {}
            record["server_time_ms"] = book.get("time") if isinstance(book, dict) else None
            n_ok += self._count_ok(record)
            try:
                append_jsonl_gz(daily_path(self.out, symbol, taken), record)
                wrote += 1
            except OSError as exc:
                self.emit("DISK_ERR %s %s" % (type(exc).__name__, exc))
                self._trip_cap()
                break
            if market_data_bytes(self.out) >= self.settings.max_bytes:
                self._trip_cap()
                break
        if wrote:
            self.emit("SNAP %s ok=%d/%d" % (kind, n_ok, expected))
        return n_ok, expected

    def _run_path(self) -> Path:
        return self.out / "sampler_run.json"

    def _read_run(self) -> Optional[dict]:
        path = self._run_path()
        if not path.is_file():
            return None
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return loaded if isinstance(loaded, dict) else None

    def _write_run(self, how: str, end_epoch: float) -> None:
        existing = self._read_run()
        if how == "resume" and existing and existing.get("end_epoch") is not None:
            existing["pid"] = os.getpid()
            existing["resumed_utc"] = iso_z(self.now())
            _atomic_text(self._run_path(), json.dumps(existing, indent=2) + "\n")
            return
        start_epoch = self.now()
        document = {
            "pid": os.getpid(),
            "start_utc": iso_z(start_epoch),
            "start_epoch": start_epoch,
            "end_utc_planned": iso_z(end_epoch),
            "end_epoch": end_epoch,
            "symbols": list(self.settings.symbols),
            "category": CATEGORY,
            "regular_s": self.settings.regular_s,
            "burst_s": self.settings.burst_s,
            "burst_window_s": [-self.settings.burst_pre_s, self.settings.burst_post_s],
            "bar_hours_utc": list(BAR_HOURS_UTC),
            "max_bytes": self.settings.max_bytes,
            "hosts": list(self.settings.hosts),
            "auth": "none",
            "how": how,
            "endpoints": {
                "orderbook": "limit=%d" % ORDERBOOK_LIMIT,
                "recent_trade": "limit=%d" % TRADE_LIMIT,
                "ticker": "symbol",
            },
            "note": "read-only public market data; does not trade",
        }
        _atomic_text(self._run_path(), json.dumps(document, indent=2) + "\n")

    def resolve_end(self) -> tuple[str, float]:
        """Pick the campaign end.

        --end wins, then an explicit --hours (a fresh window from now), then a
        planned end already stored beside the data, then the 7-day default.
        The systemd unit passes neither flag so a reboot keeps the first plan.
        """
        if self.settings.end is not None:
            return "cli_end", self.settings.end.timestamp()
        if self.settings.hours is not None:
            if self.settings.hours < 0:
                raise SystemExit("--hours must be >= 0")
            return "cli_hours", self.now() + self.settings.hours * 3600.0
        existing = self._read_run()
        if existing and existing.get("end_epoch") is not None:
            return "resume", float(existing["end_epoch"])
        return "default_168h", self.now() + DEFAULT_HOURS * 3600.0

    def _already_done(self) -> bool:
        return (self.out / "SAMPLER_DONE").is_file()

    def finalize(self, *, done_marker: bool, reason: str) -> None:
        """Log END, optionally mark the campaign finished, write coverage and checksums."""
        self.emit("END reason=%s" % reason)
        if done_marker:
            _atomic_text(
                self.out / "SAMPLER_DONE",
                "%s reason=%s\n" % (iso_z(self.now()), reason),
            )
        coverage = render_coverage(
            log_text=_read_text(self.out / "sampler.log"),
            run=self._read_run(),
            generated=datetime.fromtimestamp(self.now(), timezone.utc),
            symbols=self.settings.symbols,
        )
        _atomic_text(self.out / "COVERAGE.md", coverage)
        write_sha256sums(self.out)

    def _once(self) -> int:
        n_ok, expected = self.snapshot("once_test")
        self.emit("ONCE ok=%d/%d" % (n_ok, expected))
        print("once_test ok=%d/%d" % (n_ok, expected))
        return 0 if expected and n_ok == expected else 1

    def _loop(self, end_epoch: float) -> None:
        """Shoot on the 5 min grid, and every 15 s inside a 4h burst window.

        Inside the window only burst shots run. A 5 min deadline that falls
        in the window is pushed forward by the burst that reaches it, so the
        two cadences never stack. Outside the window the 5 min grid runs alone.
        """
        start = self.now()
        next_reg = start
        next_burst = start
        settings = self.settings
        idle_spins = 0
        while self.now() < end_epoch and not self._stop:
            now = self.now()
            if self.capped:
                self._wait(end_epoch - now)
                continue
            inside = in_burst(
                now, pre=settings.burst_pre_s, post=settings.burst_post_s, bar_s=settings.bar_s
            )
            if inside and now + 1e-6 >= next_burst:
                self.snapshot("burst4h")
                next_burst = now + settings.burst_s
                # A 5 min deadline that arrives during the window is swallowed
                # by this burst so the two cadences do not stack.
                if now + 1e-6 >= next_reg:
                    next_reg = now + settings.regular_s
                idle_spins = 0
                continue
            if not inside and now + 1e-6 >= next_reg:
                self.snapshot("regular5m")
                next_reg = now + settings.regular_s
                idle_spins = 0
                continue
            if inside:
                # Stay on the 15 s slots. Waking for next_reg here would take
                # a regular snapshot between burst shots.
                delay = min(end_epoch - now, next_burst - now)
            else:
                wake = next_burst_start(
                    now,
                    pre=settings.burst_pre_s,
                    post=settings.burst_post_s,
                    bar_s=settings.bar_s,
                )
                delay = min(end_epoch - now, next_reg - now, wake - now)
            if delay <= 1e-9:
                idle_spins += 1
                if idle_spins > 3:
                    raise RuntimeError("scheduler made no progress at %s" % iso_z(now))
                self._clock_sleep(0.05)
                continue
            idle_spins = 0
            self._wait(delay)

    def run(self) -> int:
        self.out.mkdir(parents=True, exist_ok=True)
        self._install_signals()
        if self._already_done() and not self.settings.once:
            self.emit("ALREADY_DONE")
            return 0
        if self.settings.once:
            return self._once()
        how, end_epoch = self.resolve_end()
        self._write_run(how, end_epoch)
        if how == "resume" and self.now() >= end_epoch:
            self.emit("WINDOW_ELAPSED")
            self.finalize(done_marker=True, reason="end_time")
            return 0
        if how == "resume":
            self.emit("RESUME pid=%d end=%s" % (os.getpid(), iso_z(end_epoch)))
        else:
            self.emit(
                "START pid=%d how=%s end=%s symbols=%s max_bytes=%d"
                % (
                    os.getpid(),
                    how,
                    iso_z(end_epoch),
                    ",".join(self.settings.symbols),
                    self.settings.max_bytes,
                )
            )
        self._loop(end_epoch)
        reason = "stopped" if self._stop else "end_time"
        self.finalize(done_marker=reason == "end_time", reason=reason)
        return 0


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_args(argv: Optional[Sequence[str]] = None) -> tuple[Settings, bool]:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Bybit public sampler for XRPUSDT and AVAXUSDT linear perps. "
            "No API key. Does not trade."
        )
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="output directory (default: %(default)s)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=None,
        help="fresh window length in hours (default when no plan exists: 168). "
        "Omit this on the systemd unit so a reboot resumes the original end.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="absolute UTC end, ISO-8601 (example: 2026-10-17T00:00:00Z). Overrides --hours.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="take one snapshot and exit. Does not write SAMPLER_DONE or start the 7-day plan.",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="stop writing market data after this many bytes of jsonl (default: 2 GiB)",
    )
    parser.add_argument(
        "--print-schedule",
        action="store_true",
        help="print the next 4h burst windows in UTC and GST, then exit. No network.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.max_bytes <= 0:
        raise SystemExit("--max-bytes must be positive")
    end = parse_utc(args.end) if args.end else None
    settings = Settings(
        out=assert_out_allowed(Path(args.out)),
        hours=args.hours,
        end=end,
        once=bool(args.once),
        max_bytes=args.max_bytes,
    )
    return settings, bool(args.print_schedule)


def main(argv: Optional[Sequence[str]] = None) -> int:
    settings, print_only = parse_args(argv)
    if print_only:
        sys.stdout.write(format_schedule(time.time()))
        return 0
    sampler = Sampler(settings)
    try:
        return sampler.run()
    except SystemExit:
        raise
    except Exception as exc:
        # A crash before SAMPLER_DONE leaves the plan in place so systemd
        # Restart=on-failure can resume. Do not mark the campaign finished.
        sampler.emit("FATAL %s %s" % (type(exc).__name__, exc))
        print("FATAL %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
