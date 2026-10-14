"""Authentication and per-IP rate limiting for the status page.

The token is read from settings (``STATUS_PAGE_TOKEN`` in the server ``.env``).
A blank token disables the page. Comparison hashes both sides and then uses
``hmac.compare_digest``, so the check does not short-circuit on the first
differing character. This module does not log the token or the Authorization
header.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import threading
import time
from collections import deque
from dataclasses import dataclass

from config.settings import get_settings

# TestClient and a local reverse proxy. A public peer never trusts X-Real-IP.
_TRUSTED_PEER_NAMES = frozenset({"localhost", "testclient"})


def configured_token() -> str:
    """Stripped status token. Empty means the page is disabled."""
    return get_settings().status_page_token.strip()


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


def limiter_from_settings() -> SlidingWindowLimiter:
    settings = get_settings()
    return SlidingWindowLimiter(
        settings.status_page_rate_limit,
        settings.status_page_rate_window_seconds,
    )
