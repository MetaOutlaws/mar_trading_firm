"""Public request pacing for the isolated paper worker.

Each Market builds its own RequestPacer. A pacer spaces request starts by
min_interval and caps how many are in flight, so concurrency does not raise
the start rate. Funded quotes peak at 4 requests/second. The hourly scan
uses the same 0.25s spacing, so it peaks at 4 requests/second, and it is
requested six minutes after the hour. The scan as-of time stays the hour
boundary.
"""
from __future__ import annotations

SCAN_OFFSET_MS = 6 * 60_000
FUNDED_MIN_INTERVAL_S = 0.25
FUNDED_CONCURRENCY = 2
FUNDED_PEAK_REQ_PER_S = 4
SCAN_MIN_INTERVAL_S = 0.25
SCAN_CONCURRENCY = 6
SCAN_PEAK_REQ_PER_S = 4
