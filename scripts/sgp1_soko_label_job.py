#!/usr/bin/env python3
"""Hourly SGP1 Soko regime label. Stdlib only. Does not import the trading engine.

Paper reads ``/data/state/data/last_soko_trend.json`` (``core.data.soko_trend``).
This process writes that file from outside the paper container, so a deploy
does not restart paper and does not touch ``engine.py``.

Live window (desktop ``refresh.sh`` + ``classify_closed_bars.py``):

* GET ``data-api.binance.vision`` ``/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=60``
* 3 retries, 30s timeout, exponential backoff starting at 5s
* drop the forming bar (``close_time >= now``), which leaves 59 closed bars
* seed EMA20 on that closed window; price is the last closed close
* ``as_of`` is that bar's close time plus 1 ms

Rules (``classify_soko_regime_20261008_am.py``, thresholds unchanged):

* slope = (EMA20[-1] / EMA20[-7] - 1) * 100
* last 6 bars vs the prior 6: HH/LH on max high, HL/LL on min low
* BEAR if slope <= -0.35 and price < EMA20 and LH and LL
* BULL if slope >= +0.35 and price > EMA20 and HH and HL
* otherwise chop

The file is ``soko_trend_v1`` with source ``sgp1_auto``. A desktop push that
already has this ``as_of`` or a newer one is left byte-for-byte alone.
Bybit v5 is an optional fallback and stays off unless
``SOKO_LABEL_BYBIT_FALLBACK`` is set. Parity is defined on Binance.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Paper's reader resolves PROJECT_ROOT/data/last_soko_trend.json. On SGP1 that
# directory is the host state mount, not a path inside the paper process.
DEFAULT_PATH = Path("/data/state/data/last_soko_trend.json")
SCHEMA = "soko_trend_v1"
SOURCE = "sgp1_auto"
VALID_TRENDS = frozenset({"bull", "bear", "chop"})

BINANCE_KLINES_URL = (
    "https://data-api.binance.vision/api/v3/klines"
    "?symbol=BTCUSDT&interval=4h&limit=60"
)
BYBIT_KLINES_URL = (
    "https://api.bybit.com/v5/market/kline"
    "?category=linear&symbol=BTCUSDT&interval=240&limit=60"
)

# Same budget as the desktop curl: --retry 3 --retry-delay 5 -m 30.
# Delay grows 5s, 10s, 20s so a stuck API does not hammer the host.
FETCH_TIMEOUT_S = 30.0
FETCH_RETRIES = 3
FETCH_BACKOFF_S = 5.0
# classify_closed_bars.py refuses a window shorter than this.
MIN_CLOSED_BARS = 30
FOUR_H_MS = 4 * 60 * 60 * 1000

Opener = Callable[[str, float], Any]
Sleeper = Callable[[float], None]


class KlineFetchError(Exception):
    """Binance (and Bybit, if enabled) did not return a usable closed window."""


@dataclass(frozen=True)
class Classification:
    """One closed-bar label. Trend is already lowercase for the file."""

    trend: str
    stretch: str
    as_of: str
    close: float
    ema20: float
    slope_pct: float
    price_vs_ema_pct: float
    atr_pct: float
    range_ratio: float
    HH: bool
    HL: bool
    LH: bool
    LL: bool
    flip_dist_atr: float
    closed_bars: int


@dataclass(frozen=True)
class ExistingFile:
    """What is on disk before we decide to publish."""

    present: bool
    readable: bool
    as_of: datetime | None
    trend: str | None


def ema(series: list[float], period: int) -> list[float]:
    """EMA seeded with the first close. Same recurrence as Soko's script."""
    if not series:
        return []
    k = 2 / (period + 1)
    out = [series[0]]
    for value in series[1:]:
        out.append(value * k + out[-1] * (1 - k))
    return out


def true_ranges(ohlc: list[tuple[float, float, float, float]]) -> list[float]:
    """Wilder true range. The first bar has no previous close, so TR is high-low."""
    ranges: list[float] = []
    prev_close: float | None = None
    for _open, high, low, close in ohlc:
        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        ranges.append(tr)
        prev_close = close
    return ranges


def wilder_atr(ranges: list[float], period: int = 14) -> list[float | None]:
    """Wilder ATR. Seed is the simple mean of the first ``period`` true ranges."""
    if len(ranges) < period:
        return [None] * len(ranges)
    atr: list[float | None] = [None] * (period - 1)
    # First seed, then Wilder's recurrence: ((n-1)*prev + TR) / n.
    prev = sum(ranges[:period]) / period
    atr.append(prev)
    for i in range(period, len(ranges)):
        prev = (prev * (period - 1) + ranges[i]) / period
        atr.append(prev)
    return atr


def structure_flags(
    highs: list[float], lows: list[float], win: int = 6
) -> tuple[bool, bool, bool, bool]:
    """HH, HL, LH, LL for the last ``win`` bars against the ``win`` before them.

    Equal extremes are neither higher nor lower. A tie is not a trend structure.
    """
    if len(highs) < 2 * win:
        return False, False, False, False
    recent_h = highs[-win:]
    prior_h = highs[-2 * win : -win]
    recent_l = lows[-win:]
    prior_l = lows[-2 * win : -win]
    hh = max(recent_h) > max(prior_h)
    hl = min(recent_l) > min(prior_l)
    lh = max(recent_h) < max(prior_h)
    ll = min(recent_l) < min(prior_l)
    return hh, hl, lh, ll


def _ohlc(klines: list[list[Any]]) -> list[tuple[float, float, float, float]]:
    return [(float(k[1]), float(k[2]), float(k[3]), float(k[4])) for k in klines]


def _margins(
    klines: list[list[Any]],
) -> tuple[dict[str, float], dict[str, float], float]:
    """ATR distance of each BEAR/BULL condition. Positive means the rule holds.

    Copied from ``classify_closed_bars.py``. ``flip_dist_atr`` is the smallest
    of these margins, which is what the desktop label log records.
    """
    ohlc = _ohlc(klines)
    closes = [close for *_rest, close in ohlc]
    highs = [high for _open, high, _low, _close in ohlc]
    lows = [low for _open, _high, low, _close in ohlc]
    ema20 = ema(closes, 20)
    ema_now, ema6 = ema20[-1], ema20[-7]
    atr_now = wilder_atr(true_ranges(ohlc), 14)[-1]
    if atr_now is None or atr_now == 0:
        raise ValueError("ATR unavailable for flip distance")
    price = closes[-1]
    slope = (ema_now / ema6 - 1) * 100
    recent_high, prior_high = max(highs[-6:]), max(highs[-12:-6])
    recent_low, prior_low = min(lows[-6:]), min(lows[-12:-6])
    bear = {
        "slope": (-0.35 - slope) / 100 * ema6 / atr_now,
        "price_below_ema": (ema_now - price) / atr_now,
        "LH": (prior_high - recent_high) / atr_now,
        "LL": (prior_low - recent_low) / atr_now,
    }
    bull = {
        "slope": (slope - 0.35) / 100 * ema6 / atr_now,
        "price_above_ema": (price - ema_now) / atr_now,
        "HH": (recent_high - prior_high) / atr_now,
        "HL": (recent_low - prior_low) / atr_now,
    }
    return bear, bull, atr_now


def _flip_distance(trend: str, bear: dict[str, float], bull: dict[str, float]) -> float:
    """How close the current label is to breaking, in ATR units."""
    if trend == "BEAR":
        return min(bear.values())
    if trend == "BULL":
        return min(bull.values())
    # CHOP: smallest shortfall that would satisfy every condition of one side.
    bear_short = max(0.0, -min(bear.values()))
    bull_short = max(0.0, -min(bull.values()))
    return min(bear_short, bull_short)


def _classify_row(klines: list[list[Any]], last_price: float) -> dict[str, Any]:
    """Trend and stretch. Thresholds match the 2026-10-08 Soko classifier."""
    ohlc = _ohlc(klines)
    closes = [close for _open, _high, _low, close in ohlc]
    highs = [high for _open, high, _low, _close in ohlc]
    lows = [low for _open, _high, low, _close in ohlc]

    ema20_series = ema(closes, 20)
    ema20_now = ema20_series[-1]
    ema20_6 = ema20_series[-7]
    slope_pct = (ema20_now / ema20_6 - 1) * 100
    price_vs_ema = (last_price / ema20_now - 1) * 100
    abs_pve = abs(price_vs_ema)

    ranges = true_ranges(ohlc)
    atr_now = wilder_atr(ranges, 14)[-1]
    if atr_now is None:
        raise ValueError("ATR unavailable")
    atr_pct = (atr_now / last_price) * 100
    mean_tr6 = sum(ranges[-6:]) / 6
    mean_tr20 = sum(ranges[-20:]) / 20
    range_ratio = mean_tr6 / mean_tr20 if mean_tr20 else 0.0
    hh, hl, lh, ll = structure_flags(highs, lows, 6)
    move6 = (closes[-1] / closes[-7] - 1) * 100

    if slope_pct <= -0.35 and last_price < ema20_now and lh and ll:
        trend = "BEAR"
    elif slope_pct >= 0.35 and last_price > ema20_now and hh and hl:
        trend = "BULL"
    else:
        trend = "CHOP"

    # Stretch is informational. It is not written into soko_trend_v1.
    if abs_pve >= 2.0 or (abs_pve >= 1.5 and abs_pve >= 0.55 * atr_pct):
        stretch = "EXTENDED"
    elif range_ratio < 0.50 and abs_pve < 0.50 and abs(move6) < 2.0:
        stretch = "COMPRESSED"
    else:
        stretch = "MID"

    return {
        "trend": trend,
        "stretch": stretch,
        "ema20": round(ema20_now, 2),
        "slope_pct": round(slope_pct, 3),
        "atr_pct": round(atr_pct, 3),
        "range_ratio": round(range_ratio, 3),
        "HH": hh,
        "HL": hl,
        "LH": lh,
        "LL": ll,
        "_debug": {"price_vs_ema": price_vs_ema},
    }


def bar_as_of(kline: list[Any]) -> str:
    """``as_of`` is the bar close time plus 1 ms, formatted as UTC ``Z``."""
    return datetime.fromtimestamp(
        (int(kline[6]) + 1) / 1000, timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def classify_window(klines: list[list[Any]]) -> Classification:
    """Classify one already-closed window. The caller chooses the seed length.

    The live job passes the 59 closed bars left after dropping the forming
    bar. The 30-day fixture was built on 60-bar windows; pass those through
    here when replaying it. Do not mix the two lengths in one comparison.
    """
    if len(klines) < MIN_CLOSED_BARS:
        raise ValueError(f"too few closed bars: {len(klines)}")
    price = float(klines[-1][4])
    row = _classify_row(klines, price)
    debug = row.pop("_debug")
    bear, bull, _atr = _margins(klines)
    flip = _flip_distance(row["trend"], bear, bull)
    trend = str(row["trend"]).lower()
    if trend not in VALID_TRENDS:
        raise ValueError(f"classifier returned {trend!r}")
    return Classification(
        trend=trend,
        stretch=str(row["stretch"]),
        as_of=bar_as_of(klines[-1]),
        close=price,
        ema20=float(row["ema20"]),
        slope_pct=float(row["slope_pct"]),
        price_vs_ema_pct=round(float(debug["price_vs_ema"]), 3),
        atr_pct=float(row["atr_pct"]),
        range_ratio=float(row["range_ratio"]),
        HH=bool(row["HH"]),
        HL=bool(row["HL"]),
        LH=bool(row["LH"]),
        LL=bool(row["LL"]),
        flip_dist_atr=round(flip, 3),
        closed_bars=len(klines),
    )


def closed_klines(klines: list[list[Any]], now_ms: int) -> list[list[Any]]:
    """Drop still-forming klines. Binance close time is index 6, in milliseconds."""
    return [row for row in klines if int(row[6]) < now_ms]


def parse_as_of(value: Any) -> datetime | None:
    """Parse an ISO clock as UTC. Naive stamps are UTC. None if it is not a clock."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def format_utc(stamp: datetime) -> str:
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_payload(payload: dict[str, Any]) -> None:
    """Refuse to publish anything that is not the four-field v1 object."""
    if set(payload) != {"schema", "trend", "as_of", "source"}:
        raise ValueError("soko_trend_v1 must contain schema, trend, as_of, source")
    if payload["schema"] != SCHEMA:
        raise ValueError(f"schema must be {SCHEMA}")
    if payload["trend"] not in VALID_TRENDS:
        raise ValueError(f"trend must be bull, bear, or chop, got {payload['trend']!r}")
    if payload["source"] != SOURCE:
        raise ValueError(f"source must be {SOURCE}")
    if parse_as_of(payload["as_of"]) is None:
        raise ValueError(f"as_of is not a timestamp: {payload['as_of']!r}")


def build_payload(trend: str, as_of: str) -> dict[str, str]:
    payload = {
        "schema": SCHEMA,
        "trend": trend,
        "as_of": as_of,
        "source": SOURCE,
    }
    validate_payload(payload)
    return payload


def inspect_existing(path: Path) -> ExistingFile:
    """Read the current file. Unreadable contents are reported, not raised."""
    if not path.exists():
        return ExistingFile(False, True, None, None)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return ExistingFile(True, False, None, None)
    if not isinstance(data, dict):
        return ExistingFile(True, False, None, None)
    raw_trend = data.get("trend")
    trend = raw_trend.strip().lower() if isinstance(raw_trend, str) else None
    return ExistingFile(True, True, parse_as_of(data.get("as_of")), trend)


def should_replace(existing: ExistingFile, new_as_of: datetime) -> bool:
    """True only when we may publish over ``existing``.

    A dated file is replaced only when ``new_as_of`` is strictly later.
    Ties and older stamps stay, so a desktop push of the same bar wins.
    A missing file, or a file with no parseable ``as_of``, has nothing dated
    to protect and is replaced.
    """
    if not existing.present:
        return True
    if existing.as_of is None:
        return True
    return new_as_of > existing.as_of


def _fsync_dir(directory: Path) -> None:
    """Make the rename durable. A failure here does not roll back a publish."""
    try:
        dir_fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def atomic_publish(dest: Path, payload: dict[str, Any], new_as_of: datetime) -> str:
    """Validate, write a sibling temp file, fsync, then rename.

    Returns ``written`` or ``kept_existing``. On any error before rename the
    destination bytes are unchanged and the temp file is removed. Rename is
    atomic on the same filesystem, so readers never see a partial JSON object.
    """
    validate_payload(payload)
    if not should_replace(inspect_existing(dest), new_as_of):
        return "kept_existing"

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    data = (json.dumps(payload) + "\n").encode("utf-8")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        # chmod after open so umask cannot leave the published file private.
        os.chmod(tmp, 0o644)
        # A desktop push may have landed while we were classifying.
        if not should_replace(inspect_existing(dest), new_as_of):
            tmp.unlink(missing_ok=True)
            return "kept_existing"
        os.replace(tmp, dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(dest.parent)
    return "written"


def urllib_opener(url: str, timeout: float) -> Any:
    """GET JSON. Network and HTTP errors propagate to the retry loop."""
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "sgp1-soko-label/1",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body.decode("utf-8"))


def _retry(url: str, opener: Opener, sleep: Sleeper, parse: Callable[[Any], list]) -> list:
    """Try ``FETCH_RETRIES + 1`` times. Sleep 5s, 10s, 20s between failures."""
    last: Exception | None = None
    attempts = FETCH_RETRIES + 1
    for attempt in range(attempts):
        try:
            return parse(opener(url, FETCH_TIMEOUT_S))
        except Exception as exc:
            last = exc
            if attempt < attempts - 1:
                sleep(FETCH_BACKOFF_S * (2**attempt))
    raise KlineFetchError(str(last)) from last


def _require_closed(rows: list[list[Any]], now_ms: int, source: str) -> list[list[Any]]:
    closed = closed_klines(rows, now_ms)
    if len(closed) < MIN_CLOSED_BARS:
        raise KlineFetchError(f"{source}: too few closed bars: {len(closed)}")
    return closed


def _parse_binance(payload: Any, now_ms: int) -> list[list[Any]]:
    if not isinstance(payload, list) or not payload:
        raise KlineFetchError("binance response was not a kline list")
    for row in payload:
        if not isinstance(row, list) or len(row) < 7:
            raise KlineFetchError("binance kline row is short")
    return _require_closed(payload, now_ms, "binance")


def _parse_bybit(payload: Any, now_ms: int) -> list[list[Any]]:
    """Map Bybit v5 rows onto the Binance kline shape the classifier reads.

    Bybit returns newest-first ``[start, open, high, low, close, volume, turnover]``.
    Close time is ``start + 4h - 1ms`` so ``as_of`` (close + 1ms) lands on the
    same 4h boundary as Binance.
    """
    if not isinstance(payload, dict):
        raise KlineFetchError("bybit response was not an object")
    if payload.get("retCode") not in (0, "0"):
        raise KlineFetchError(f"bybit retCode={payload.get('retCode')}")
    result = payload.get("result")
    rows = result.get("list") if isinstance(result, dict) else None
    if not isinstance(rows, list) or not rows:
        raise KlineFetchError("bybit kline list missing")
    converted: list[list[Any]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            raise KlineFetchError("bybit kline row is short")
        open_ms = int(row[0])
        volume = row[5] if len(row) > 5 else "0"
        converted.append(
            [open_ms, row[1], row[2], row[3], row[4], volume, open_ms + FOUR_H_MS - 1]
        )
    converted.sort(key=lambda item: int(item[0]))
    return _require_closed(converted, now_ms, "bybit")


def load_closed_bars(
    now_ms: int,
    opener: Opener,
    sleep: Sleeper,
    *,
    bybit_fallback: bool,
) -> tuple[list[list[Any]], str]:
    """Return closed Binance-shaped bars and the feed name that produced them.

    Bybit is contacted only after Binance has failed all of its attempts, and
    only when ``bybit_fallback`` is true. The default is Binance alone.
    """
    # The except target is deleted when the block ends, so keep our own name.
    binance_error: Exception | None = None
    try:
        bars = _retry(
            BINANCE_KLINES_URL,
            opener,
            sleep,
            lambda payload: _parse_binance(payload, now_ms),
        )
        return bars, "binance"
    except Exception as exc:
        binance_error = exc
        if not bybit_fallback:
            raise KlineFetchError(f"binance klines failed: {exc}") from exc
    try:
        bars = _retry(
            BYBIT_KLINES_URL,
            opener,
            sleep,
            lambda payload: _parse_bybit(payload, now_ms),
        )
    except Exception as exc:
        raise KlineFetchError(
            f"binance klines failed: {binance_error}; bybit klines failed: {exc}"
        ) from exc
    return bars, "bybit"


def _now_ms(now: datetime) -> int:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return int(now.timestamp() * 1000)


def emit(record: dict[str, Any]) -> None:
    """One JSON object, one line. Journald keeps this as the run log."""
    sys.stdout.write(json.dumps(record) + "\n")
    sys.stdout.flush()


def run(
    path: Path | str,
    *,
    bybit_fallback: bool = False,
    now: datetime | None = None,
    opener: Opener | None = None,
    sleep: Sleeper | None = None,
) -> int:
    """Classify and maybe publish. 0 on a completed classification, 1 on failure.

    Network and API failures leave the destination file untouched. A completed
    classification that loses the ``as_of`` race also leaves it untouched and
    still exits 0: the desktop file is the one paper should keep.
    """
    dest = Path(path)
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    fetch = opener or urllib_opener
    pause = sleep or time.sleep
    record: dict[str, Any] = {
        "status": "error",
        "run_time": format_utc(clock),
        "written": False,
        "path": str(dest),
    }
    code = 1
    try:
        closed, feed = load_closed_bars(
            _now_ms(clock), fetch, pause, bybit_fallback=bybit_fallback
        )
        classified = classify_window(closed)
        payload = build_payload(classified.trend, classified.as_of)
        before = inspect_existing(dest)
        new_as_of = parse_as_of(classified.as_of)
        if new_as_of is None:
            raise ValueError(f"classifier as_of is not a timestamp: {classified.as_of!r}")
        outcome = atomic_publish(dest, payload, new_as_of)
        record = {
            "status": "ok",
            "run_time": format_utc(clock),
            "as_of": classified.as_of,
            "label": classified.trend,
            "prev_label": before.trend,
            "prev_as_of": format_utc(before.as_of) if before.as_of else None,
            "btc_ema20_slope_pct": classified.slope_pct,
            "btc_price_vs_ema20_pct": classified.price_vs_ema_pct,
            "LH": classified.LH,
            "LL": classified.LL,
            "flip_dist_atr": classified.flip_dist_atr,
            "stretch": classified.stretch,
            "closed_bars": classified.closed_bars,
            "feed": feed,
            "written": outcome == "written",
            "changed": before.trend != classified.trend,
            "path": str(dest),
        }
        if outcome != "written":
            record["reason"] = "as_of_not_newer"
        code = 0
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        code = 1
    emit(record)
    return code


_TRUE_ENV = frozenset({"1", "true", "yes", "on"})


def bybit_fallback_enabled(cli: bool | None, env_value: str | None) -> bool:
    """CLI wins when it is passed. Otherwise the env flag, default off."""
    if cli is not None:
        return bool(cli)
    return str(env_value or "").strip().lower() in _TRUE_ENV


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the SGP1 Soko BTCUSDT 4h regime label."
    )
    parser.add_argument(
        "--path",
        default=os.environ.get("SOKO_TREND_PATH", str(DEFAULT_PATH)),
        help="Destination JSON. Env SOKO_TREND_PATH overrides the default.",
    )
    parser.add_argument(
        "--bybit-fallback",
        dest="bybit_fallback",
        action="store_const",
        const=True,
        default=None,
        help="Use Bybit v5 only if Binance fails. Off by default.",
    )
    parser.add_argument(
        "--no-bybit-fallback",
        dest="bybit_fallback",
        action="store_const",
        const=False,
        help="Force Binance only, ignoring SOKO_LABEL_BYBIT_FALLBACK.",
    )
    args = parser.parse_args(argv)
    enabled = bybit_fallback_enabled(
        args.bybit_fallback, os.environ.get("SOKO_LABEL_BYBIT_FALLBACK")
    )
    return run(args.path, bybit_fallback=enabled)


if __name__ == "__main__":
    sys.exit(main())
