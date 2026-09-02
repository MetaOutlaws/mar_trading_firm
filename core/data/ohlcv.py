"""
OHLCV market data: fetching, pagination, caching, and a canonical schema.

Every consumer in the firm -- backtester, live engine, agents -- receives candles
in one shape, so a bug in one path cannot be masked by a different shape in
another:

    index   : pandas.DatetimeIndex, UTC, named "timestamp", ascending, unique
    columns : open, high, low, close, volume, turnover  (all float64)

Bybit's public `/v5/market/kline` endpoint needs no authentication and serves
history back to 2021, which is what makes multi-regime validation possible
(2021 bull, 2022 bear, 2023 chop, 2024+ bull). The legacy project only had two
quarters of 2024 in BigQuery, which is why its backtests could not distinguish
edge from a bull-market tailwind.
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

CANONICAL_COLUMNS = ["open", "high", "low", "close", "volume", "turnover"]

# Bybit interval codes keyed by our timeframe labels.
INTERVAL_CODES: dict[str, str] = {
    "1m": "1",
    "3m": "3",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "2h": "120",
    "4h": "240",
    "6h": "360",
    "12h": "720",
    "1d": "D",
    "1w": "W",
}

# Duration of one candle, used for pagination arithmetic and gap detection.
TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "1w": timedelta(weeks=1),
}

# Legacy configs use "15min"; normalise so both spellings resolve.
TIMEFRAME_ALIASES = {"15min": "15m", "5min": "5m", "1min": "1m", "30min": "30m", "60min": "1h"}

BYBIT_MAINNET = "https://api.bybit.com"
BYBIT_TESTNET = "https://api-testnet.bybit.com"

# Bybit caps kline responses at 1000 rows per request.
MAX_ROWS_PER_REQUEST = 1000


def normalise_timeframe(timeframe: str) -> str:
    """Map timeframe spellings onto the canonical set."""
    tf = TIMEFRAME_ALIASES.get(timeframe, timeframe)
    if tf not in INTERVAL_CODES:
        raise ValueError(f"Unsupported timeframe {timeframe!r}. Known: {sorted(INTERVAL_CODES)}")
    return tf


def empty_frame() -> pd.DataFrame:
    """An empty DataFrame with the canonical schema."""
    frame = pd.DataFrame(columns=CANONICAL_COLUMNS, dtype="float64")
    frame.index = pd.DatetimeIndex([], tz="UTC", name="timestamp")
    return frame


@dataclass
class OHLCVCache:
    """Parquet-backed candle cache.

    Historical candles are immutable once closed, so caching turns a slow
    paginated download into a local read. Research sweeps re-read the same
    windows hundreds of times; without this, every walk-forward run would
    re-hammer the exchange.
    """

    root: Path = PROJECT_ROOT / "data" / "cache"

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, symbol: str, timeframe: str) -> Path:
        return self.root / f"{symbol}_{timeframe}.parquet"

    def read(self, symbol: str, timeframe: str) -> pd.DataFrame:
        path = self.path_for(symbol, timeframe)
        if not path.exists():
            return empty_frame()
        try:
            frame = pd.read_parquet(path)
        except Exception as exc:  # corrupt cache must not break a run
            logger.warning("Discarding unreadable cache %s: %s", path.name, exc)
            return empty_frame()
        return _canonicalise(frame)

    def write(self, symbol: str, timeframe: str, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        try:
            frame.to_parquet(self.path_for(symbol, timeframe))
        except Exception as exc:  # caching is an optimisation, never fatal
            logger.warning("Could not write cache for %s %s: %s", symbol, timeframe, exc)

    def merge(self, symbol: str, timeframe: str, fresh: pd.DataFrame) -> pd.DataFrame:
        """Union fresh candles into the cache and persist the result."""
        combined = _canonicalise(pd.concat([self.read(symbol, timeframe), fresh]))
        self.write(symbol, timeframe, combined)
        return combined


def _canonicalise(frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce any candle frame into the canonical schema.

    Deduplication keeps the *last* occurrence: when a live fetch overlaps the
    cache, the newer copy of a still-forming candle is the correct one.
    """
    if frame.empty:
        return empty_frame()

    frame = frame.copy()

    # Accept a timestamp column as well as an index.
    if "timestamp" in frame.columns:
        frame = frame.set_index("timestamp")

    index = pd.to_datetime(frame.index, utc=True)
    frame.index = pd.DatetimeIndex(index, name="timestamp")

    for column in CANONICAL_COLUMNS:
        if column not in frame.columns:
            frame[column] = float("nan")
    frame = frame[CANONICAL_COLUMNS].astype("float64")

    frame = frame[~frame.index.duplicated(keep="last")]
    return frame.sort_index()


class BybitOHLCV:
    """Public Bybit kline reader with pagination and retry.

    Uses only the public market-data endpoint, so it needs no credentials and
    works identically in paper, testnet and live modes.
    """

    def __init__(
        self,
        testnet: bool = False,
        category: str = "linear",
        cache: OHLCVCache | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.base_url = BYBIT_TESTNET if testnet else BYBIT_MAINNET
        self.category = category
        self.cache = cache if cache is not None else OHLCVCache()
        self._client = httpx.Client(timeout=timeout, headers={"User-Agent": "mar-trading-firm/0.1"})

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "BybitOHLCV":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- low level ----------------------------------------------------------
    def _request_page(
        self, symbol: str, interval: str, start_ms: int, end_ms: int
    ) -> list[list[str]]:
        """Fetch one page of klines, retrying transient failures."""
        params = {
            "category": self.category,
            "symbol": symbol,
            "interval": interval,
            "start": start_ms,
            "end": end_ms,
            "limit": MAX_ROWS_PER_REQUEST,
        }

        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = self._client.get(f"{self.base_url}/v5/market/kline", params=params)
                response.raise_for_status()
                payload = response.json()

                ret_code = payload.get("retCode")
                if ret_code != 0:
                    # 10001 for an unlisted symbol is permanent; retrying wastes time.
                    message = payload.get("retMsg", "unknown")
                    if ret_code == 10001:
                        raise ValueError(f"{symbol}: {message}")
                    raise RuntimeError(f"Bybit retCode={ret_code}: {message}")

                return payload.get("result", {}).get("list", []) or []

            except ValueError:
                raise
            except Exception as exc:
                last_error = exc
                backoff = 2**attempt
                logger.debug(
                    "kline fetch failed (%s attempt %d): %s - retrying in %ds",
                    symbol, attempt + 1, exc, backoff,
                )
                time.sleep(backoff)

        raise RuntimeError(f"Failed to fetch klines for {symbol}: {last_error}")

    # -- public -------------------------------------------------------------
    def fetch(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch candles for `symbol` in [start, end].

        Args:
            symbol: Bybit linear perpetual symbol, e.g. "BTCUSDT".
            timeframe: One of INTERVAL_CODES (or a legacy alias like "15min").
            start: Inclusive UTC start.
            end: Inclusive UTC end. Defaults to now.
            use_cache: Serve from the local parquet cache where possible.

        Returns:
            Canonical OHLCV frame, possibly empty.
        """
        timeframe = normalise_timeframe(timeframe)
        interval = INTERVAL_CODES[timeframe]
        start = _as_utc(start)
        end = _as_utc(end or datetime.now(timezone.utc))

        if use_cache:
            cached = self.cache.read(symbol, timeframe)
            if _covers(cached, start, end, timeframe):
                logger.debug("Cache hit: %s %s %s..%s", symbol, timeframe, start.date(), end.date())
                return cached.loc[start:end]

        logger.info(
            "Fetching %s %s from %s to %s", symbol, timeframe, start.date(), end.date()
        )

        step = TIMEFRAME_DELTAS[timeframe]
        rows: list[list[str]] = []
        cursor = start

        while cursor <= end:
            # Request a window sized to the row cap so each call is full.
            window_end = min(cursor + step * (MAX_ROWS_PER_REQUEST - 1), end)
            page = self._request_page(
                symbol, interval, int(cursor.timestamp() * 1000), int(window_end.timestamp() * 1000)
            )
            if not page:
                # No data in this window. The symbol may not have existed yet;
                # skip ahead rather than stalling on a permanent hole.
                if window_end >= end:
                    break
                cursor = window_end + step
                continue

            rows.extend(page)

            # Bybit returns newest-first; the oldest row bounds what we received.
            oldest_ms = min(int(row[0]) for row in page)
            newest_ms = max(int(row[0]) for row in page)
            advanced = datetime.fromtimestamp(newest_ms / 1000, tz=timezone.utc) + step
            cursor = max(advanced, cursor + step)
            del oldest_ms

            time.sleep(0.06)  # ~16 req/s, well inside Bybit's public limit

        frame = _rows_to_frame(rows)
        if frame.empty:
            logger.warning("No candles returned for %s %s", symbol, timeframe)
            return frame

        if use_cache:
            frame = self.cache.merge(symbol, timeframe, frame)

        return frame.loc[start:end]

    def fetch_latest(self, symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        """Fetch the most recent `bars` candles. Used by the live engine.

        Bypasses the cache: the live engine must never act on a stale candle.
        """
        timeframe = normalise_timeframe(timeframe)
        step = TIMEFRAME_DELTAS[timeframe]
        end = datetime.now(timezone.utc)
        # Pad the window so partial candles and gaps still yield `bars` rows.
        start = end - step * (bars + 5)
        frame = self.fetch(symbol, timeframe, start, end, use_cache=False)
        return frame.tail(bars)

    def latest_price(self, symbol: str) -> float | None:
        """Last traded price from the public ticker endpoint."""
        try:
            response = self._client.get(
                f"{self.base_url}/v5/market/tickers",
                params={"category": self.category, "symbol": symbol},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("retCode") != 0:
                return None
            entries = payload.get("result", {}).get("list", [])
            return float(entries[0]["lastPrice"]) if entries else None
        except Exception as exc:
            logger.warning("Could not fetch ticker for %s: %s", symbol, exc)
            return None


def _rows_to_frame(rows: list[list[str]]) -> pd.DataFrame:
    """Convert raw Bybit kline arrays into the canonical frame.

    Bybit row layout: [startTime, open, high, low, close, volume, turnover].
    """
    if not rows:
        return empty_frame()

    frame = pd.DataFrame(
        rows, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"]
    )
    frame["timestamp"] = pd.to_datetime(frame["timestamp"].astype("int64"), unit="ms", utc=True)
    return _canonicalise(frame)


def _as_utc(moment: datetime) -> datetime:
    """Treat naive datetimes as UTC rather than local time.

    Silent local-time interpretation is a classic source of off-by-hours
    backtest bugs, so this is explicit.
    """
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _covers(frame: pd.DataFrame, start: datetime, end: datetime, timeframe: str) -> bool:
    """Whether a cached frame spans [start, end] densely enough to use.

    Allows a two-candle tolerance at each edge: exchanges have listing dates and
    occasional maintenance gaps, so demanding exact coverage would defeat the
    cache entirely.
    """
    if frame.empty:
        return False
    step = TIMEFRAME_DELTAS[timeframe]
    tolerance = step * 2
    return bool(frame.index.min() <= start + tolerance and frame.index.max() >= end - tolerance)


def closed_candles(
    frame: pd.DataFrame,
    timeframe: str,
    *,
    now: datetime | None = None,
) -> pd.DataFrame:
    """Drop the still-forming last bar so signals match the backtest (`<= t` closed).

    Bybit includes the in-progress candle. Trading that close is how paper
    entered ETH on a 15m wick that later rewrote itself.
    """
    if frame.empty:
        return frame
    timeframe = normalise_timeframe(timeframe)
    step = TIMEFRAME_DELTAS[timeframe]
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    last_open = frame.index[-1]
    if last_open.tzinfo is None:
        last_open = last_open.tz_localize("UTC")
    else:
        last_open = last_open.tz_convert("UTC")
    close_at = last_open.to_pydatetime()
    if close_at.tzinfo is None:
        close_at = close_at.replace(tzinfo=timezone.utc)
    close_at = close_at + step
    if now < close_at:
        return frame.iloc[:-1]
    return frame
