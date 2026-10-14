"""Validated, paginated observed funding using the research minute-open proxy."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

FUNDING_BASIS = "bybit-observed-rate-times-settlement-minute-open-v1"


def observed_funding_fraction(
    *, symbol: str, side: int, entry_price: float, opened: datetime,
    now: datetime, data: Any, cache: dict[str, Any],
) -> tuple[float | None, str]:
    """Return an entry-notional fraction, debit positive; unknown on any gap.

    Cache only immutable valued settlements. A full response is paginated to
    prove window coverage. Failed/partial responses never become zero.
    """
    if now <= opened:
        return 0., FUNDING_BASIS + " (empty holding window)"
    if side not in (-1, 1) or not math.isfinite(entry_price) or entry_price <= 0:
        return None, "funding invalid position"
    start_ms = int(opened.timestamp() * 1000)
    cursor = int(now.timestamp() * 1000)
    rates: dict[int, float] = {}
    try:
        for _ in range(200):
            response = httpx.get(
                "https://api.bybit.com/v5/market/funding/history",
                params={"category": "linear", "symbol": symbol,
                        "startTime": start_ms, "endTime": cursor, "limit": 200},
                timeout=5., headers={"User-Agent": "mar-trading-firm/0.1"},
            )
            if response.status_code != 200:
                raise ValueError(f"HTTP {response.status_code}")
            payload = response.json()
            if payload.get("retCode") != 0:
                raise ValueError("unsuccessful funding response")
            records = payload["result"]["list"]
            if not isinstance(records, list):
                raise ValueError("malformed funding list")
            stamps = []
            for row in records:
                stamp = int(row["fundingRateTimestamp"])
                rate = float(row["fundingRate"])
                if not math.isfinite(rate) or stamp < 0:
                    raise ValueError("nonfinite funding record")
                stamps.append(stamp)
                if start_ms < stamp <= int(now.timestamp() * 1000):
                    if stamp in rates and rates[stamp] != rate:
                        raise ValueError("conflicting funding records")
                    rates[stamp] = rate
            if len(records) < 200 or (stamps and min(stamps) <= start_ms):
                break
            next_cursor = min(stamps) - 1
            if next_cursor >= cursor:
                raise ValueError("funding pagination made no progress")
            cursor = next_cursor
        else:
            raise ValueError("funding coverage limit reached")

        prior = {int(k) for k in cache if start_ms < int(k) <= int(now.timestamp() * 1000)}
        if not prior.issubset(rates):
            raise ValueError("funding response omitted a previously observed settlement")
        valued = {}
        for stamp, rate in sorted(rates.items()):
            key = str(stamp)
            cached = cache.get(key)
            if cached is not None and float(cached["rate"]) == rate:
                price = float(cached["price"])
            else:
                at = datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).replace(second=0, microsecond=0)
                if data is None or not hasattr(data, "fetch"):
                    raise ValueError("settlement minute price unavailable")
                candles = data.fetch(symbol, "1m", at, at)
                if candles is None or at not in candles.index or candles.index.has_duplicates:
                    raise ValueError("settlement minute price missing")
                price = float(candles.loc[at, "open"])
            if not math.isfinite(price) or price <= 0:
                raise ValueError("invalid settlement minute price")
            valued[key] = {"rate": rate, "price": price}
        # No partial cache/valuation is published on a failed request.
        cache.update(valued)
        amount_per_unit = sum(x["rate"] * x["price"] for x in valued.values())
        return side * amount_per_unit / entry_price, f"{FUNDING_BASIS} ({len(valued)} settlements)"
    except Exception as exc:
        return None, f"funding unknown: {exc}"
