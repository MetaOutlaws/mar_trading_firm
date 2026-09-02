"""
Bybit public positioning: open interest, funding, and account long/short.

OHLCV is the only series research can walk-forward. Funding is already a *cost*
on fills. This module is the missing *state*: is the crowd already in the trade?

The overlay is paper-only and fail-open:

- Skip a LONG when funding is rich *and* OI is expanding (crowded longs).
- Skip a SHORT when funding is deeply negative *and* OI is expanding (crowded shorts).
- Size 0.5x when account-ratio already leans with the trade.
- Never enlarge. Missing or stale fields mean pass, not a guessed fade.

That is a filter on expectancy, not a new sleeve. `funding_fade` stays Tier C
until a bar-aligned history exists for backtests; a live snapshot cannot
validate that family.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

BYBIT_MAINNET = "https://api.bybit.com"

LAST_POSITIONING_PATH = PROJECT_ROOT / "data" / "last_positioning.json"

#: Reuse a snapshot this long so paper, the regime analyst, and the dashboard
#: do not each hit Bybit on every poll.
CACHE_TTL = timedelta(minutes=10)

#: Funding at or beyond this (per 8h settlement) counts as crowded, *if* OI is
#: also expanding. 0.03% per 8h is 3x Bybit's 0.01% baseline.
FUNDING_CROWDED = 0.0003

#: Open-interest expansion over ~24h that confirms new money, not just a mark
#: move. Percent, not a fraction.
OI_EXPAND_PCT = 2.0

#: Account long ratio at or above this means retail is already long. Mirror for
#: shorts at `1 - BUY_LEAN`.
BUY_LEAN = 0.62

#: Paper size when accounts lean with the trade. Agents cannot raise this.
LEAN_SIZE_MULT = 0.5

MS_PER_HOUR = 3_600_000


@dataclass(frozen=True)
class CrowdingDecision:
    """What the overlay wants to do to one signal."""

    action: str  # pass | skip | size
    size_mult: float
    reason: str

    @staticmethod
    def passthrough() -> "CrowdingDecision":
        return CrowdingDecision("pass", 1.0, "")


def crowding_decision(row: dict[str, Any] | None, side: str) -> CrowdingDecision:
    """Deterministic crowding rule. Missing fields fail open (pass)."""
    if not row:
        return CrowdingDecision.passthrough()

    side_u = str(side or "").upper()
    if side_u not in {"LONG", "SHORT"}:
        return CrowdingDecision.passthrough()

    funding = _as_float(row.get("funding_rate"))
    oi_chg = _as_float(row.get("oi_change_24h_pct"))
    buy_ratio = _as_float(row.get("buy_ratio"))

    crowded_long = (
        funding is not None
        and oi_chg is not None
        and funding >= FUNDING_CROWDED
        and oi_chg > OI_EXPAND_PCT
    )
    crowded_short = (
        funding is not None
        and oi_chg is not None
        and funding <= -FUNDING_CROWDED
        and oi_chg > OI_EXPAND_PCT
    )

    if side_u == "LONG" and crowded_long:
        return CrowdingDecision(
            "skip",
            0.0,
            (
                f"crowding: skip LONG — funding {funding * 100:.3f}%/8h and "
                f"OI 24h {oi_chg:+.1f}% (crowded-with-the-crowd)"
            ),
        )
    if side_u == "SHORT" and crowded_short:
        return CrowdingDecision(
            "skip",
            0.0,
            (
                f"crowding: skip SHORT — funding {funding * 100:.3f}%/8h and "
                f"OI 24h {oi_chg:+.1f}% (crowded-with-the-crowd)"
            ),
        )

    if buy_ratio is None:
        return CrowdingDecision.passthrough()

    if side_u == "LONG" and buy_ratio >= BUY_LEAN:
        return CrowdingDecision(
            "size",
            LEAN_SIZE_MULT,
            (
                f"crowding: size {LEAN_SIZE_MULT:.2f}x LONG — "
                f"buy_ratio {buy_ratio:.0%} accounts already long"
            ),
        )
    if side_u == "SHORT" and buy_ratio <= (1.0 - BUY_LEAN):
        return CrowdingDecision(
            "size",
            LEAN_SIZE_MULT,
            (
                f"crowding: size {LEAN_SIZE_MULT:.2f}x SHORT — "
                f"buy_ratio {buy_ratio:.0%} accounts already short-leaning"
            ),
        )
    return CrowdingDecision.passthrough()


def crowding_label(row: dict[str, Any] | None) -> str:
    """Operator-facing tag for the dashboard, independent of a pending side."""
    if not row:
        return "unknown"
    funding = _as_float(row.get("funding_rate"))
    oi_chg = _as_float(row.get("oi_change_24h_pct"))
    buy_ratio = _as_float(row.get("buy_ratio"))
    if funding is None and oi_chg is None and buy_ratio is None:
        return "unknown"
    if funding is not None and oi_chg is not None:
        if funding >= FUNDING_CROWDED and oi_chg > OI_EXPAND_PCT:
            return "crowded long"
        if funding <= -FUNDING_CROWDED and oi_chg > OI_EXPAND_PCT:
            return "crowded short"
    if buy_ratio is not None:
        if buy_ratio >= BUY_LEAN:
            return "accounts lean long"
        if buy_ratio <= (1.0 - BUY_LEAN):
            return "accounts lean short"
    return "balanced"


class PositioningFeed:
    """Public Bybit client for OI, account-ratio, and ticker funding."""

    def __init__(self, client: httpx.Client | None = None, timeout: float = 20.0) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout, headers={"User-Agent": "mar-trading-firm/0.1"}
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PositioningFeed":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def fetch_symbol(self, symbol: str) -> dict[str, Any]:
        """One symbol's snapshot. Empty dict on failure (callers fail open)."""
        ticker = self._get(
            "/v5/market/tickers",
            {"category": "linear", "symbol": symbol},
        )
        oi_hist = self._get(
            "/v5/market/open-interest",
            {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": "1h",
                "limit": 48,
            },
        )
        ratio = self._get(
            "/v5/market/account-ratio",
            {"category": "linear", "symbol": symbol, "period": "1h", "limit": 5},
        )
        ticker_row = _first_list_row(ticker)
        funding = _as_float((ticker_row or {}).get("fundingRate"))
        oi_now = _as_float((ticker_row or {}).get("openInterest"))
        points = _oi_points(oi_hist)
        if oi_now is None and points:
            oi_now = points[-1][1]
        oi_chg = _oi_change_pct(points)
        ratio_row = _first_list_row(ratio)
        buy_ratio = _as_float((ratio_row or {}).get("buyRatio"))
        sell_ratio = _as_float((ratio_row or {}).get("sellRatio"))
        row = {
            "symbol": symbol,
            "open_interest": oi_now,
            "oi_change_24h_pct": None if oi_chg is None else round(oi_chg, 3),
            "funding_rate": funding,
            "funding_rate_8h_pct": None if funding is None else round(funding * 100, 4),
            "buy_ratio": buy_ratio,
            "sell_ratio": sell_ratio,
        }
        row["label"] = crowding_label(row)
        return row

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Return Bybit `result` or {} on any failure."""
        try:
            response = self._client.get(f"{BYBIT_MAINNET}{path}", params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            logger.warning("Positioning fetch %s %s failed: %s", path, params.get("symbol"), exc)
            return {}
        if payload.get("retCode") != 0:
            logger.warning(
                "Positioning retCode=%s for %s %s: %s",
                payload.get("retCode"),
                path,
                params.get("symbol"),
                payload.get("retMsg"),
            )
            return {}
        result = payload.get("result")
        return result if isinstance(result, dict) else {}


def snapshot_symbols(
    symbols: list[str],
    *,
    include_cross: bool = False,
    force: bool = False,
    feed: PositioningFeed | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Fetch (or reuse) a book snapshot and persist it for the dashboard."""
    wanted = sorted({str(s).upper() for s in symbols if s})
    dest = path or LAST_POSITIONING_PATH
    cached = load_last_positioning(dest)
    if not force and _cache_covers(cached, wanted, include_cross=False):
        if include_cross and cached is not None and not isinstance(cached.get("cross"), dict):
            cached = dict(cached)
            cached["cross"] = crypto_cross_metrics()
            persist_positioning(cached, dest)
        return cached  # type: ignore[return-value]

    owned = feed is None
    client = feed or PositioningFeed()
    rows: dict[str, Any] = {}
    try:
        for i, symbol in enumerate(wanted):
            try:
                rows[symbol] = client.fetch_symbol(symbol)
            except Exception as exc:
                logger.warning("Positioning snapshot failed for %s: %s", symbol, exc)
                rows[symbol] = {"symbol": symbol, "label": "unknown"}
            if i < len(wanted) - 1:
                time.sleep(0.06)
    finally:
        if owned:
            client.close()

    blob: dict[str, Any] = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "bybit_public",
        "overlay": {
            "enabled_on": "paper",
            "never_enlarge": True,
            "skip": (
                f"LONG if funding >= {FUNDING_CROWDED * 100:.2f}%/8h and "
                f"OI 24h > {OI_EXPAND_PCT:.0f}%; SHORT is the mirror"
            ),
            "size": (
                f"{LEAN_SIZE_MULT:.2f}x LONG if buy_ratio >= {BUY_LEAN:.0%}; "
                f"SHORT if buy_ratio <= {1.0 - BUY_LEAN:.0%}"
            ),
        },
        "symbols": rows,
    }
    if include_cross:
        blob["cross"] = crypto_cross_metrics()
    elif cached and isinstance(cached.get("cross"), dict):
        blob["cross"] = cached["cross"]
    persist_positioning(blob, dest)
    return blob


def crypto_cross_metrics() -> dict[str, Any]:
    """ETH/BTC from existing Bybit candles — crypto-macro without a new venue."""
    try:
        from core.data.ohlcv import BybitOHLCV

        with BybitOHLCV() as source:
            btc = source.fetch_latest("BTCUSDT", "1d", bars=14)
            eth = source.fetch_latest("ETHUSDT", "1d", bars=14)
    except Exception as exc:
        logger.warning("ETH/BTC cross failed: %s", exc)
        return {}
    if btc.empty or eth.empty or "close" not in btc or "close" not in eth:
        return {}
    btc_last = float(btc["close"].iloc[-1])
    eth_last = float(eth["close"].iloc[-1])
    if btc_last <= 0 or eth_last <= 0:
        return {}
    ratio = eth_last / btc_last
    ratio_7 = None
    chg_7 = None
    if len(btc) >= 8 and len(eth) >= 8:
        btc_7 = float(btc["close"].iloc[-8])
        eth_7 = float(eth["close"].iloc[-8])
        if btc_7 > 0 and eth_7 > 0:
            ratio_7 = eth_7 / btc_7
            chg_7 = (ratio / ratio_7 - 1.0) * 100.0
    return {
        "eth_btc": round(ratio, 6),
        "eth_btc_7d": None if ratio_7 is None else round(ratio_7, 6),
        "eth_btc_7d_pct": None if chg_7 is None else round(chg_7, 3),
    }


def persist_positioning(blob: dict[str, Any], path: Path | None = None) -> None:
    dest = path or LAST_POSITIONING_PATH
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not persist positioning snapshot: %s", exc)


def load_last_positioning(path: Path | None = None) -> dict[str, Any] | None:
    dest = path or LAST_POSITIONING_PATH
    if not dest.exists():
        return None
    try:
        data = json.loads(dest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def _cache_covers(cached: dict[str, Any] | None, wanted: list[str], include_cross: bool) -> bool:
    if not cached or not wanted:
        return False
    as_of = _parse_iso(cached.get("as_of"))
    if as_of is None:
        return False
    if datetime.now(timezone.utc) - as_of > CACHE_TTL:
        return False
    have = set((cached.get("symbols") or {}).keys())
    if not set(wanted) <= have:
        return False
    if include_cross and not isinstance(cached.get("cross"), dict):
        return False
    return True


def _oi_points(result: dict[str, Any]) -> list[tuple[int, float]]:
    rows = result.get("list") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return []
    points: list[tuple[int, float]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        ts = _as_int(item.get("timestamp"))
        oi = _as_float(item.get("openInterest"))
        if ts is None or oi is None:
            continue
        points.append((ts, oi))
    points.sort(key=lambda pair: pair[0])
    return points


def _oi_change_pct(points: list[tuple[int, float]]) -> float | None:
    """Percent change from ~24h ago. Needs at least 18h of span."""
    if len(points) < 2:
        return None
    latest_ts, latest_oi = points[-1]
    if latest_oi <= 0:
        return None
    target = latest_ts - 24 * MS_PER_HOUR
    prior: tuple[int, float] | None = None
    for ts, oi in points:
        if ts <= target:
            prior = (ts, oi)
        else:
            break
    if prior is None:
        prior = points[0]
    old_ts, old_oi = prior
    if old_oi <= 0:
        return None
    age_h = (latest_ts - old_ts) / MS_PER_HOUR
    if age_h < 18:
        return None
    return (latest_oi / old_oi - 1.0) * 100.0


def _first_list_row(result: dict[str, Any]) -> dict[str, Any] | None:
    rows = result.get("list") if isinstance(result, dict) else None
    if not isinstance(rows, list) or not rows:
        return None
    first = rows[0]
    return first if isinstance(first, dict) else None


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)
