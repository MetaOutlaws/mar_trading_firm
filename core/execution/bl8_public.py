"""Paced public-market reads for the isolated BL8 observer.

Bybit's published IP budget is 600 requests in 5 seconds (120/s), and they ask
callers not to sit on that edge. A 96-symbol burst at about one request per
symbol in a single second came back ``retCode`` 10006. These defaults stay far
under that budget: 2 requests in flight, a new request at most every 0.2s
(5/s). Each symbol needs three calls (instrument, hourly kline, four-hour
kline), so 96 symbols are 288 calls, about 58 seconds when answers are prompt.

The hourly trading engine is not involved. This module opens no orders.
"""
from __future__ import annotations

import json
import random
import threading
import time
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# Three public GETs per symbol: instruments-info, 60-minute kline, 240-minute kline.
SCAN_CALLS_PER_SYMBOL = 3
DEFAULT_CONCURRENCY = 2
DEFAULT_MIN_INTERVAL_S = 0.2
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_BACKOFF_BASE_S = 0.5
DEFAULT_BACKOFF_CAP_S = 30.0
# A reset header is honored, but a broken timestamp cannot stall a worker for days.
DEFAULT_HEADER_WAIT_CAP_S = 600.0
DEFAULT_REQUEUE_S = 5.0
RATE_LIMIT_RETCODES = frozenset({10006, 10018})


def expected_scan_seconds(symbols: int, min_interval_s: float = DEFAULT_MIN_INTERVAL_S) -> float:
    """Pacing floor for one full universe pass, ignoring retry sleeps."""
    return symbols * SCAN_CALLS_PER_SYMBOL * min_interval_s


class RateLimited(Exception):
    """Public endpoint asked us to slow down, and the attempt cap was used up."""

    def __init__(self, message: str, *, attempts: int, status: int | None = None, ret_code: int | None = None):
        super().__init__(f'{message} after {attempts} attempts')
        self.attempts = attempts
        self.status = status
        self.ret_code = ret_code


class RequestPacer:
    """Spaces request starts and caps how many are in flight together."""

    def __init__(self, min_interval_s: float, concurrency: int, *, monotonic=time.monotonic, sleep=time.sleep):
        if concurrency < 1:
            raise ValueError('public concurrency must be at least 1')
        if min_interval_s < 0:
            raise ValueError('public min interval must be non-negative')
        self.min_interval_s = float(min_interval_s)
        self.concurrency = int(concurrency)
        self._slots = threading.BoundedSemaphore(self.concurrency)
        self._lock = threading.Lock()
        self._next = 0.0
        self._monotonic = monotonic
        self._sleep = sleep

    def reserve(self):
        """Block until this caller may start one request. Pair with ``release``."""
        self._slots.acquire()
        try:
            with self._lock:
                now = self._monotonic()
                wait = self._next - now
                self._next = max(now, self._next) + self.min_interval_s
            if wait > 0:
                self._sleep(wait)
        except BaseException:
            self._slots.release()
            raise

    def release(self):
        self._slots.release()


def _headers(source) -> dict:
    if source is None:
        return {}
    items = source.items() if hasattr(source, 'items') else dict(source).items()
    return {str(key).lower(): value for key, value in items}


def _header(headers: dict, name: str):
    return headers.get(name.lower())


def _parse_retry_after(value: str, now_s: float):
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed is None:
        return None
    return parsed.timestamp() - now_s


def rate_limit_delay(headers: dict, attempt: int, now_s: float, rng, *, base_s: float, cap_s: float, header_cap_s: float) -> float:
    """Seconds to wait before the next try. A reset header wins over the backoff curve."""
    reset = _header(headers, 'X-Bapi-Limit-Reset-Timestamp')
    if reset not in (None, ''):
        try:
            wait = (int(str(reset).strip()) / 1000.0) - now_s
        except ValueError:
            wait = None
        if wait is not None and wait > 0:
            return min(wait, header_cap_s) + rng() * 0.25
    retry_after = _header(headers, 'Retry-After')
    if retry_after not in (None, ''):
        parsed = _parse_retry_after(retry_after, now_s)
        if parsed is not None and parsed > 0:
            return min(parsed, header_cap_s) + rng() * 0.25
    delay = min(cap_s, base_s * (2 ** max(0, attempt - 1)))
    return delay + rng() * delay * 0.25


def is_rate_limited(status: int, parsed, raw_text: str) -> bool:
    """10006, 10018, HTTP 429, and HTTP 403 responses that say the caller is too fast."""
    code = parsed.get('retCode') if isinstance(parsed, dict) else None
    try:
        code = int(code) if code is not None else None
    except (TypeError, ValueError):
        code = None
    if code in RATE_LIMIT_RETCODES:
        return True
    if status == 429:
        return True
    if status == 403:
        text = raw_text.lower()
        return 'too frequent' in text or 'too many' in text or 'rate limit' in text
    return False


class PublicClient:
    """GET helper: pace, then retry only when Bybit (or the edge) says we are too fast."""

    def __init__(
        self,
        *,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        concurrency: int = DEFAULT_CONCURRENCY,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        backoff_base_s: float = DEFAULT_BACKOFF_BASE_S,
        backoff_cap_s: float = DEFAULT_BACKOFF_CAP_S,
        header_cap_s: float = DEFAULT_HEADER_WAIT_CAP_S,
        opener=urlopen,
        timeout: float = 5,
        monotonic=time.monotonic,
        sleep=time.sleep,
        now_s=time.time,
        rng=None,
        pacer: RequestPacer | None = None,
    ):
        if max_attempts < 1:
            raise ValueError('public max attempts must be at least 1')
        self.max_attempts = int(max_attempts)
        self.backoff_base_s = float(backoff_base_s)
        self.backoff_cap_s = float(backoff_cap_s)
        self.header_cap_s = float(header_cap_s)
        self.opener = opener
        self.timeout = timeout
        self.sleep = sleep
        self.now_s = now_s
        self.rng = rng or random.random
        self.pacer = pacer or RequestPacer(min_interval_s, concurrency, monotonic=monotonic, sleep=sleep)

    def get(self, url: str, request_headers: dict | None = None):
        last_status = None
        last_code = None
        last_detail = 'rate limited'
        for attempt in range(1, self.max_attempts + 1):
            self.pacer.reserve()
            try:
                status, headers, raw = self._read(url, request_headers or {})
            finally:
                self.pacer.release()
            text = raw.decode('utf-8', errors='replace')
            try:
                parsed = json.loads(text) if text else None
            except json.JSONDecodeError:
                parsed = None
            if is_rate_limited(status, parsed, text):
                last_status = status
                last_code = parsed.get('retCode') if isinstance(parsed, dict) else None
                last_detail = f'HTTP {status} retCode {last_code}'
                if attempt == self.max_attempts:
                    break
                delay = rate_limit_delay(
                    headers, attempt, self.now_s(), self.rng,
                    base_s=self.backoff_base_s, cap_s=self.backoff_cap_s, header_cap_s=self.header_cap_s,
                )
                self.sleep(max(0.0, delay))
                continue
            if parsed is None or not isinstance(parsed, dict):
                raise ValueError(f'public market response was not JSON (HTTP {status})')
            if parsed.get('retCode') != 0:
                raise ValueError(f'public market response {parsed.get("retCode")}')
            return parsed
        raise RateLimited(last_detail, attempts=self.max_attempts, status=last_status, ret_code=_int_or_none(last_code))

    def _read(self, url: str, request_headers: dict):
        request = Request(url, headers=request_headers)
        try:
            with self.opener(request, timeout=self.timeout) as response:
                status = int(getattr(response, 'status', 200) or 200)
                return status, _headers(getattr(response, 'headers', None)), response.read()
        except HTTPError as exc:
            return int(exc.code), _headers(exc.headers), exc.read()


def _int_or_none(value):
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def scan_complete(universe, events) -> bool:
    """True only when every symbol's latest context attempt succeeded.

    ``events`` is ``(time, kind, symbol)`` in observation order. ``kind`` is
    ``context`` or ``error``. A symbol that has not been seen, or whose newest
    row is an error, keeps the scan incomplete.
    """
    latest = {}
    for stamp, kind, symbol in events:
        previous = latest.get(symbol)
        if previous is None or stamp >= previous[0]:
            latest[symbol] = (stamp, kind)
    wanted = set(universe)
    if set(latest) != wanted:
        return False
    return all(kind == 'context' for _, kind in latest.values())


def client_from_env(env=None, **overrides) -> PublicClient:
    """Concurrency and spacing come from the environment, then from explicit overrides."""
    env = os_environ_view(env)
    settings = {
        'concurrency': _env_int(env, 'BL8_PUBLIC_CONCURRENCY', DEFAULT_CONCURRENCY),
        'min_interval_s': _env_float(env, 'BL8_PUBLIC_MIN_INTERVAL_S', DEFAULT_MIN_INTERVAL_S),
        'max_attempts': _env_int(env, 'BL8_PUBLIC_MAX_ATTEMPTS', DEFAULT_MAX_ATTEMPTS),
        'backoff_base_s': _env_float(env, 'BL8_PUBLIC_BACKOFF_BASE_S', DEFAULT_BACKOFF_BASE_S),
        'backoff_cap_s': _env_float(env, 'BL8_PUBLIC_BACKOFF_CAP_S', DEFAULT_BACKOFF_CAP_S),
        'header_cap_s': _env_float(env, 'BL8_PUBLIC_HEADER_WAIT_CAP_S', DEFAULT_HEADER_WAIT_CAP_S),
    }
    settings.update(overrides)
    return PublicClient(**settings)


def requeue_seconds(env=None) -> float:
    return _env_float(os_environ_view(env), 'BL8_SCAN_REQUEUE_S', DEFAULT_REQUEUE_S)


def os_environ_view(env):
    if env is None:
        import os
        return os.environ
    return env


def _env_int(env, name, default):
    raw = env.get(name)
    if raw in (None, ''):
        return default
    value = int(raw)
    if value < 1:
        raise ValueError(f'{name} must be at least 1')
    return value


def _env_float(env, name, default):
    raw = env.get(name)
    if raw in (None, ''):
        return default
    value = float(raw)
    if value < 0:
        raise ValueError(f'{name} must be non-negative')
    return value
