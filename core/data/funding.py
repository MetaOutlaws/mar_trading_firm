"""
Perpetual funding rates.

The legacy backtester modelled fees and slippage but *not* funding, which is a
material omission: its strategy held perps for up to 24 hours, meaning up to
three funding payments per trade. In a bull market, longs pay funding
persistently, so ignoring it flatters exactly the trades the legacy results were
most confident about.

Funding on Bybit linear perps settles every 8 hours. A long pays the rate when
it is positive and receives it when negative; a short is the mirror image.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pandas as pd

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

BYBIT_MAINNET = "https://api.bybit.com"

# Bybit caps funding history at 200 records per request.
MAX_RECORDS = 200

# Standard settlement cadence for Bybit linear perps.
FUNDING_INTERVAL = timedelta(hours=8)

# Used when a symbol has no funding history available. 0.01% per 8h is the
# Bybit baseline rate, i.e. ~10.95% annualised for a permanently-held long.
DEFAULT_FUNDING_RATE = 0.0001


@dataclass
class FundingHistory:
    """Funding rate series for one symbol, with cost lookup helpers."""

    symbol: str
    rates: pd.Series  # index: UTC timestamps, values: rate per 8h settlement

    def cost_for_holding(
        self, side: str, entry_time: datetime, exit_time: datetime, notional: float
    ) -> float:
        """Funding paid (positive) or received (negative) over a holding period.

        Args:
            side: "LONG" or "SHORT".
            entry_time: Position open time (UTC).
            exit_time: Position close time (UTC).
            notional: Position notional in quote currency.

        Returns:
            Net funding cost in quote currency. Positive means it cost money.
        """
        if self.rates.empty or exit_time <= entry_time:
            return 0.0

        # Only settlements strictly inside the holding window are charged.
        window = self.rates.loc[
            (self.rates.index > pd.Timestamp(entry_time))
            & (self.rates.index <= pd.Timestamp(exit_time))
        ]
        if window.empty:
            return 0.0

        # A long pays a positive rate; a short receives it.
        direction = 1.0 if side.upper() == "LONG" else -1.0
        return float(window.sum() * direction * notional)

    @property
    def mean_annualised(self) -> float:
        """Average funding rate expressed as an annual percentage for a long.

        Three settlements per day, 365 days.
        """
        if self.rates.empty:
            return 0.0
        return float(self.rates.mean() * 3 * 365 * 100)


class FundingRates:
    """Fetches and caches Bybit funding rate history."""

    def __init__(self, cache_dir: Path | None = None, timeout: float = 20.0) -> None:
        self.cache_dir = cache_dir or (PROJECT_ROOT / "data" / "cache" / "funding")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            timeout=timeout, headers={"User-Agent": "mar-trading-firm/0.1"}
        )
        self._memo: dict[str, FundingHistory] = {}

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FundingRates":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _cache_path(self, symbol: str) -> Path:
        return self.cache_dir / f"{symbol}_funding.parquet"

    def get(self, symbol: str, start: datetime, end: datetime) -> FundingHistory:
        """Return funding history for `symbol` covering [start, end]."""
        if symbol in self._memo:
            return self._memo[symbol]

        cached = self._read_cache(symbol)
        if not cached.empty and cached.index.min() <= pd.Timestamp(start) + FUNDING_INTERVAL:
            history = FundingHistory(symbol, cached)
            self._memo[symbol] = history
            return history

        series = self._download(symbol, start, end)
        if series.empty and not cached.empty:
            series = cached  # keep whatever we already had

        if not series.empty:
            self._write_cache(symbol, series)

        history = FundingHistory(symbol, series)
        self._memo[symbol] = history
        return history

    def _download(self, symbol: str, start: datetime, end: datetime) -> pd.Series:
        """Page backwards through funding history from `end` to `start`."""
        start = _as_utc(start)
        end = _as_utc(end)
        collected: dict[pd.Timestamp, float] = {}
        cursor_end = end

        # Bound the loop: 200 records * 8h is ~66 days per page.
        max_pages = 200
        for _ in range(max_pages):
            if cursor_end <= start:
                break
            try:
                response = self._client.get(
                    f"{BYBIT_MAINNET}/v5/market/funding/history",
                    params={
                        "category": "linear",
                        "symbol": symbol,
                        "startTime": int(start.timestamp() * 1000),
                        "endTime": int(cursor_end.timestamp() * 1000),
                        "limit": MAX_RECORDS,
                    },
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.warning("Funding fetch failed for %s: %s", symbol, exc)
                break

            if payload.get("retCode") != 0:
                logger.warning(
                    "Funding retCode=%s for %s: %s",
                    payload.get("retCode"), symbol, payload.get("retMsg"),
                )
                break

            records = payload.get("result", {}).get("list", []) or []
            if not records:
                break

            for record in records:
                stamp = pd.Timestamp(int(record["fundingRateTimestamp"]), unit="ms", tz="UTC")
                collected[stamp] = float(record["fundingRate"])

            # Records come newest-first; step the cursor just before the oldest.
            oldest = min(int(r["fundingRateTimestamp"]) for r in records)
            next_end = datetime.fromtimestamp(oldest / 1000, tz=timezone.utc) - timedelta(
                milliseconds=1
            )
            if next_end >= cursor_end:
                break  # no progress; avoid spinning
            cursor_end = next_end

            time.sleep(0.06)

        if not collected:
            logger.info(
                "No funding history for %s; costs will fall back to the %.4f%% default.",
                symbol, DEFAULT_FUNDING_RATE * 100,
            )
            return pd.Series(dtype="float64")

        series = pd.Series(collected).sort_index()
        series.index.name = "timestamp"
        logger.info(
            "Funding for %s: %d settlements, mean %.4f%% per 8h (%.1f%% annualised for a long)",
            symbol, len(series), series.mean() * 100, series.mean() * 3 * 365 * 100,
        )
        return series

    def _read_cache(self, symbol: str) -> pd.Series:
        path = self._cache_path(symbol)
        if not path.exists():
            return pd.Series(dtype="float64")
        try:
            frame = pd.read_parquet(path)
            series = frame["funding_rate"]
            series.index = pd.to_datetime(series.index, utc=True)
            return series.sort_index()
        except Exception as exc:
            logger.warning("Unreadable funding cache for %s: %s", symbol, exc)
            return pd.Series(dtype="float64")

    def _write_cache(self, symbol: str, series: pd.Series) -> None:
        try:
            series.to_frame("funding_rate").to_parquet(self._cache_path(symbol))
        except Exception as exc:
            logger.warning("Could not cache funding for %s: %s", symbol, exc)


def synthetic_funding(start: datetime, end: datetime, rate: float = DEFAULT_FUNDING_RATE) -> pd.Series:
    """Build a flat funding series, for tests and for symbols without history."""
    stamps = pd.date_range(_as_utc(start), _as_utc(end), freq="8h", tz="UTC")
    series = pd.Series(rate, index=stamps)
    series.index.name = "timestamp"
    return series


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)
