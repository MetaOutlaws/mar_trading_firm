"""Shared Bybit 1h/4h tape loader for the clone screen and the planning sim.

The hard window is 2022-01-01 00:00:00 UTC through 2025-12-31 23:00:00 UTC,
inclusive. Any bar timestamp after that instant raises. A 2026 timestamp is
after the cap, so it raises too. This module does not fetch.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

HOUR_MS = 3_600_000
FOUR_HOUR_MS = 4 * HOUR_MS
TIMEFRAMES = ('1h', '4h')
TIMEFRAME_STEP_MS = {'1h': HOUR_MS, '4h': FOUR_HOUR_MS}
TAPE_ENV = 'CIPHER_FORWARD_TAPE_DIR'
REQUIRED_COLUMNS = ('open_time_ms', 'open', 'high', 'low', 'close', 'volume', 'turnover')
PRICE_COLUMNS = ('open', 'high', 'low', 'close', 'volume', 'turnover')

# Inclusive bounds. The open time of a bar is the timestamp that is checked.
WINDOW_START = datetime(2022, 1, 1, 0, 0, tzinfo=timezone.utc)
HARD_END = datetime(2025, 12, 31, 23, 0, tzinfo=timezone.utc)
YEAR_2026 = datetime(2026, 1, 1, tzinfo=timezone.utc)
WINDOW_START_MS = int(WINDOW_START.timestamp() * 1000)
HARD_END_MS = int(HARD_END.timestamp() * 1000)
YEAR_2026_MS = int(YEAR_2026.timestamp() * 1000)

_ROOT = Path(__file__).resolve().parents[2]


class BarAfterHardCap(ValueError):
    """A bar timestamp is after 2025-12-31 23:00:00 UTC."""


class BarsOnOrAfter2026(BarAfterHardCap):
    """A bar timestamp is on or after 2026-01-01 UTC. That is also past the cap."""


class BarBeforeWindow(ValueError):
    """A bar timestamp is before 2022-01-01 00:00:00 UTC."""


class TapeNotStaged(FileNotFoundError):
    """CIPHER_FORWARD_TAPE_DIR is unset or the directory is not there."""


class TapeRejected(ValueError):
    """The staged file is not the required OHLCV contract."""


def assert_bar_timestamp(ms: int) -> None:
    """Raise unless ms is inside the inclusive hard window.

    Exactly 2025-12-31 23:00:00 UTC is allowed. One millisecond later raises.
    """
    if isinstance(ms, bool) or not isinstance(ms, int):
        raise TapeRejected('bar timestamp is not an int millisecond')
    if ms >= YEAR_2026_MS:
        raise BarsOnOrAfter2026(f'bar timestamp {ms} is on or after 2026-01-01 UTC')
    if ms > HARD_END_MS:
        raise BarAfterHardCap(f'bar timestamp {ms} is after 2025-12-31 23:00:00 UTC')
    if ms < WINDOW_START_MS:
        raise BarBeforeWindow(f'bar timestamp {ms} is before 2022-01-01 00:00:00 UTC')


def iso_week(ms: int) -> str:
    moment = datetime.fromtimestamp(ms / 1000, timezone.utc)
    year, week, _day = moment.isocalendar()
    return f'{year:04d}-W{week:02d}'


def tape_dir() -> Path | None:
    """The staged directory, or None when the env var is unset or empty."""
    raw = os.environ.get(TAPE_ENV, '').strip()
    if not raw:
        return None
    return Path(raw)


def required_symbols() -> tuple[str, ...]:
    """The protocol universe, in protocol order. BTCUSDT is one of them."""
    protocol = json.loads((_ROOT / 'docs/cipher-forward/protocol.json').read_text())
    symbols = tuple(protocol['universe'])
    if len(symbols) != 96 or 'BTCUSDT' not in symbols:
        raise TapeRejected('protocol universe is not the 96-name tape, with BTCUSDT')
    if len(set(symbols)) != len(symbols):
        raise TapeRejected('protocol universe has a duplicate symbol')
    return symbols


def tape_contract() -> dict:
    """What Ops stages. The loader does not fetch and does not invent turnover."""
    return dict(
        env=TAPE_ENV,
        window_start='2022-01-01T00:00:00Z',
        window_end='2025-12-31T23:00:00Z',
        window_end_inclusive=True,
        raises_after='2025-12-31T23:00:00Z',
        symbols=list(required_symbols()),
        symbol_count=96,
        timeframes=list(TIMEFRAMES),
        columns=list(REQUIRED_COLUMNS),
        open_time_meaning='Bybit v5 kline start (bar open), UTC milliseconds',
        turnover_meaning='Bybit v5 turnover (quote volume). volume*close is not accepted',
        layout=(
            '$CIPHER_FORWARD_TAPE_DIR/1h/<SYMBOL>.parquet or .csv, and '
            '$CIPHER_FORWARD_TAPE_DIR/4h/<SYMBOL>.parquet or .csv'
        ),
        one_file_per_symbol_timeframe=True,
        parquet_or_csv_not_both=True,
        timestamp_alias='a UTC timestamp index or a timestamp column is the same open time',
        contiguous=True,
        listing_may_start_after_window_open=True,
        fetches=False,
    )


def _stamp_ms(value) -> int:
    """Integer milliseconds from an int, a whole float, or a UTC timestamp."""
    import pandas as pd
    if isinstance(value, bool):
        raise TapeRejected('bar timestamp is not a bool')
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != int(value):
            raise TapeRejected('bar timestamp is not a whole millisecond')
        return int(value)
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize('UTC')
    else:
        stamp = stamp.tz_convert('UTC')
    return int(stamp.timestamp() * 1000)


def _frame_from_table(table, path: Path):
    """Require the OHLCV columns and an open time. Do not fill turnover."""
    import pandas as pd
    frame = table.copy()
    if 'open_time_ms' not in frame.columns:
        if isinstance(frame.index, pd.DatetimeIndex):
            frame = frame.reset_index()
            first = frame.columns[0]
            frame = frame.rename(columns={first: 'open_time_ms'})
        elif 'timestamp' in frame.columns:
            frame = frame.rename(columns={'timestamp': 'open_time_ms'})
        else:
            raise TapeRejected(f'{path.name} has no open_time_ms or timestamp')
    missing = [name for name in PRICE_COLUMNS if name not in frame.columns]
    if missing:
        raise TapeRejected(f'{path.name} is missing {missing}; turnover is not computed')
    out = frame.loc[:, ['open_time_ms', *PRICE_COLUMNS]].copy()
    out['open_time_ms'] = [_stamp_ms(value) for value in out['open_time_ms']]
    for name in PRICE_COLUMNS:
        out[name] = out[name].astype('float64')
    return out


def _validate_series(frame, timeframe: str, path: Path):
    step = TIMEFRAME_STEP_MS[timeframe]
    if frame.empty:
        raise TapeRejected(f'{path.name} has no bars')
    stamps = [int(value) for value in frame['open_time_ms']]
    for stamp in stamps:
        assert_bar_timestamp(stamp)
        if stamp % step:
            raise TapeRejected(f'{path.name} bar {stamp} is not aligned to {timeframe}')
    if len(set(stamps)) != len(stamps):
        raise TapeRejected(f'{path.name} has a duplicate open time')
    ordered = sorted(stamps)
    if ordered != stamps:
        raise TapeRejected(f'{path.name} is not sorted by open time')
    for prev, nxt in zip(ordered, ordered[1:]):
        if nxt - prev != step:
            raise TapeRejected(f'{path.name} has a gap or overlap at {nxt}')
    prices = frame.loc[:, ['open', 'high', 'low', 'close', 'volume', 'turnover']]
    import numpy as np
    if not np.isfinite(prices.to_numpy()).all():
        raise TapeRejected(f'{path.name} has a non-finite OHLCV or turnover')
    if (frame['open'] <= 0).any() or (frame['high'] <= 0).any() or (frame['low'] <= 0).any() or (frame['close'] <= 0).any():
        raise TapeRejected(f'{path.name} has a non-positive price')
    if (frame['volume'] < 0).any() or (frame['turnover'] < 0).any():
        raise TapeRejected(f'{path.name} has a negative volume or turnover')
    if (frame['high'] < frame[['open', 'close', 'low']].max(axis=1)).any():
        raise TapeRejected(f'{path.name} has a high below another price')
    if (frame['low'] > frame[['open', 'close']].min(axis=1)).any():
        raise TapeRejected(f'{path.name} has a low above open or close')
    return frame.reset_index(drop=True)


def read_bar_file(path: Path, timeframe: str):
    """Read one parquet or CSV file and refuse any bar outside the hard window."""
    import pandas as pd
    path = Path(path)
    if timeframe not in TIMEFRAME_STEP_MS:
        raise TapeRejected(f'unknown timeframe {timeframe}')
    if path.suffix == '.parquet':
        table = pd.read_parquet(path)
    elif path.suffix == '.csv':
        table = pd.read_csv(path)
    else:
        raise TapeRejected(f'{path.name} is not parquet or csv')
    return _validate_series(_frame_from_table(table, path), timeframe, path)


def _symbol_path(root: Path, timeframe: str, symbol: str) -> Path:
    folder = root / timeframe
    parquet = folder / f'{symbol}.parquet'
    csv = folder / f'{symbol}.csv'
    if parquet.is_file() and csv.is_file():
        raise TapeRejected(f'{symbol} {timeframe} has both parquet and csv')
    if parquet.is_file():
        return parquet
    if csv.is_file():
        return csv
    raise TapeNotStaged(f'missing {timeframe}/{symbol}.parquet or .csv')


def load_tape(root: Path | None = None) -> dict:
    """Load every protocol symbol at 1h and 4h. Raises on a late bar. Does not fetch."""
    if root is None:
        root = tape_dir()
    if root is None or not Path(root).is_dir():
        raise TapeNotStaged(
            f'{TAPE_ENV} is not a directory. No bars were read and nothing was fetched.')
    root = Path(root)
    loaded = {}
    for symbol in required_symbols():
        loaded[symbol] = {}
        for timeframe in TIMEFRAMES:
            path = _symbol_path(root, timeframe, symbol)
            loaded[symbol][timeframe] = read_bar_file(path, timeframe)
    return loaded
