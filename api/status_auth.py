"""Authentication and per-IP rate limiting for the status page.

``STATUS_*`` variables are read from the process environment in this module.
They are not fields on ``config.settings.Settings``. Deploying or rotating
the status page does not require a settings change, and the paper worker
does not load these values through ``get_settings()``.

A blank ``STATUS_PAGE_TOKEN`` disables the page. Comparison hashes both
sides and then uses ``hmac.compare_digest``, so the check does not
short-circuit on the first differing character. This module does not log
the token or the Authorization header.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import os
import threading
import time
from collections import deque
from dataclasses import dataclass

# TestClient and a local reverse proxy. A public peer never trusts X-Real-IP.
_TRUSTED_PEER_NAMES = frozenset({"localhost", "testclient"})

# Same defaults the page used when these lived on Settings. Out-of-range
# rate values are rejected here so a bad env fails the status process
# without touching config/settings.py.
_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 8088
_DEFAULT_RATE_LIMIT = 30
_DEFAULT_RATE_WINDOW_SECONDS = 60.0
_RATE_LIMIT_MIN = 1
_RATE_LIMIT_MAX = 10_000
_RATE_WINDOW_MAX = 3600.0


def _env(name: str) -> str:
    """Stripped process environment value. Missing and blank are both empty."""
    return os.environ.get(name, "").strip()


def configured_token() -> str:
    """Stripped ``STATUS_PAGE_TOKEN``. Empty means the page is disabled."""
    return _env("STATUS_PAGE_TOKEN")


def status_page_host() -> str:
    """Bind address from ``STATUS_PAGE_HOST``. Default ``127.0.0.1``."""
    return _env("STATUS_PAGE_HOST") or _DEFAULT_HOST


def status_page_port() -> int:
    """Bind port from ``STATUS_PAGE_PORT``. Default 8088.

    A non-integer value raises. The status process should fail closed on a
    bad port rather than bind somewhere unexpected.
    """
    raw = _env("STATUS_PAGE_PORT")
    if not raw:
        return _DEFAULT_PORT
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("STATUS_PAGE_PORT must be an integer") from exc


def status_rate_limit() -> tuple[int, float]:
    """``(limit, window_seconds)`` from the status rate-limit env vars.

    Unset uses 30 requests per 60 seconds. A value outside the previous
    Settings bounds (limit 1..10000, window greater than 0 and at most 3600)
    raises, so the process does not start with a silently different window.
    """
    limit_raw = _env("STATUS_PAGE_RATE_LIMIT")
    window_raw = _env("STATUS_PAGE_RATE_WINDOW_SECONDS")
    if not limit_raw:
        limit = _DEFAULT_RATE_LIMIT
    else:
        try:
            limit = int(limit_raw)
        except ValueError as exc:
            raise ValueError("STATUS_PAGE_RATE_LIMIT must be an integer") from exc
        if limit < _RATE_LIMIT_MIN or limit > _RATE_LIMIT_MAX:
            raise ValueError(
                f"STATUS_PAGE_RATE_LIMIT must be between {_RATE_LIMIT_MIN} and {_RATE_LIMIT_MAX}"
            )
    if not window_raw:
        window = _DEFAULT_RATE_WINDOW_SECONDS
    else:
        try:
            window = float(window_raw)
        except ValueError as exc:
            raise ValueError("STATUS_PAGE_RATE_WINDOW_SECONDS must be a number") from exc
        if window <= 0 or window > _RATE_WINDOW_MAX:
            raise ValueError(
                "STATUS_PAGE_RATE_WINDOW_SECONDS must be greater than 0 and at most 3600"
            )
    return limit, window


def tokens_equal(presented: str, expected: str) -> bool:
    """Constant-time equality for two secret strings.

    SHA-256 digests are fixed length, so ``compare_digest`` does not leak the
    secret's length. An empty expected token never matches.
    """
    if not expected:
        return False
    left = hashlib.sha256(presented.encode("utf-8")).digest()
    right = hashlib.sha256(expected.encode("utf-8")).digest()
    return hmac.compare_digest(left, right)


def _basic_password(param: str) -> str:
    """Password half of a Basic credential. Username is ignored."""
    try:
        decoded = base64.b64decode(param, validate=True).decode("utf-8")
    except (ValueError, UnicodeError):
        return ""
    _user, sep, password = decoded.partition(":")
    if not sep:
        return ""
    return password


def presented_token(authorization: str | None) -> str:
    """Bearer token, or the Basic password when that is what the client sent."""
    if not authorization:
        return ""
    scheme, _, rest = authorization.strip().partition(" ")
    rest = rest.strip()
    kind = scheme.lower()
    if kind == "bearer":
        return rest
    if kind == "basic":
        return _basic_password(rest)
    return ""


def credentials_match(authorization: str | None, expected: str) -> bool:
    """True when the header carries the configured token."""
    return tokens_equal(presented_token(authorization), expected)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def client_key(peer: str | None, x_real_ip: str | None) -> str:
    """Rate-limit key.

    Caddy overwrites ``X-Real-IP`` with the real client. Trust that header
    only when the TCP peer is loopback, private, or the local test client.
    A request that arrives from a public address is limited by that address.
    """
    peer_text = (peer or "").strip()
    peer_ip = _parse_ip(peer_text)
    trust_forwarded = False
    if peer_ip is not None and (
        peer_ip.is_private or peer_ip.is_loopback or peer_ip.is_link_local
    ):
        trust_forwarded = True
    elif peer_text.lower() in _TRUSTED_PEER_NAMES:
        trust_forwarded = True
    if trust_forwarded:
        forwarded = _parse_ip(x_real_ip or "")
        if forwarded is not None:
            return str(forwarded)
    return peer_text or "unknown"


@dataclass(frozen=True)
class LimitDecision:
    """One rate-limit check. ``retry_after`` is seconds, at least 1 when denied."""

    allowed: bool
    retry_after: int


class SlidingWindowLimiter:
    """In-process per-key sliding window. One status process, one limiter."""

    def __init__(
        self,
        limit: int,
        window_seconds: float,
        *,
        clock=None,  # noqa: ANN001
        max_keys: int = 4096,
    ) -> None:
        self.limit = max(1, int(limit))
        self.window_seconds = float(window_seconds)
        self._clock = clock or time.monotonic
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> LimitDecision:
        moment = self._clock() if now is None else float(now)
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            cutoff = moment - self.window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if not hits:
                # Drop idle keys so a scan of random addresses cannot grow forever.
                self._hits.pop(key, None)
                hits = deque()
                self._hits[key] = hits
            if len(hits) >= self.limit:
                retry = self.window_seconds - (moment - hits[0])
                return LimitDecision(False, max(1, int(retry) + 1))
            hits.append(moment)
            self._trim_locked()
            return LimitDecision(True, 0)

    def _trim_locked(self) -> None:
        extra = len(self._hits) - self._max_keys
        if extra <= 0:
            return
        oldest = sorted(
            self._hits.items(),
            key=lambda item: item[1][-1] if item[1] else 0.0,
        )[:extra]
        for key, _hits in oldest:
            self._hits.pop(key, None)


def limiter_from_env() -> SlidingWindowLimiter:
    """Limiter built from ``STATUS_PAGE_RATE_*`` in the process environment."""
    limit, window = status_rate_limit()
    return SlidingWindowLimiter(limit, window)
