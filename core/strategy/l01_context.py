"""L01's causal, long-only 4h context, continuing the researched EMA seed.

Only complete UTC blocks of 240 distinct minute candles enter the EMA. The
seed prevents a moving lookback window from changing the approved rule. The
slow initial catch-up is an operator/data job, never a trading-loop backfill.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path

import pandas as pd

from config.settings import PROJECT_ROOT

SEED_PATH = PROJECT_ROOT / "config" / "l01_4h_research_seed.json"
SEED_SHA256 = "77e3ce7e500c59ef6b2f01e8cfb72a6970575de164328c59289090277ace49b3"
CONTEXT_DIR = PROJECT_ROOT / "data" / "l01_4h_context"
ALPHA = 2.0 / 51.0


class ContextUnavailable(ValueError):
    pass


def utc(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    return stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")


def validate_state(state: dict) -> None:
    count = state.get("complete_bars")
    tail = state.get("ema_tail") or []
    if not isinstance(count, int) or count < 1 or len(tail) != min(count, 4):
        raise ContextUnavailable("l01_context_invalid_state")
    if not all(math.isfinite(float(x)) and float(x) > 0 for x in tail):
        raise ContextUnavailable("l01_context_invalid_state")
    if not math.isfinite(float(state["close4"])) or float(state["close4"]) <= 0:
        raise ContextUnavailable("l01_context_invalid_state")
    available, processed = utc(state["available_at"]), utc(state["processed_through"])
    if available > processed or available != available.floor("4h") or processed != processed.floor("4h"):
        raise ContextUnavailable("l01_context_invalid_timestamp")


def advance(state: dict, minutes: pd.DataFrame, until) -> dict:
    """Continue adjust=False EMA50; incomplete internal 4h blocks are excluded.

    Require both requested edges. A partial/stale API response must not be
    mistaken for a completed history. Returned rows after `until` are ignored.
    """
    validate_state(state)
    out = copy.deepcopy(state)
    start, end = utc(state["processed_through"]), utc(until).floor("4h")
    if end < start:
        raise ContextUnavailable("l01_context_after_signal")
    if end == start:
        return out
    if minutes is None or minutes.empty or "close" not in minutes:
        raise ContextUnavailable("l01_context_missing_minutes")
    frame = minutes[["close"]].copy()
    frame.index = pd.to_datetime(frame.index, utc=True)
    frame = frame.loc[(frame.index >= start) & (frame.index < end)].sort_index()
    if frame.empty or frame.index.has_duplicates or (frame.index != frame.index.floor("min")).any():
        raise ContextUnavailable("l01_context_invalid_minutes")
    if frame.index[0] != start or frame.index[-1] != end - pd.Timedelta(minutes=1):
        raise ContextUnavailable("l01_context_incomplete_response")
    frame["close"] = pd.to_numeric(frame.close, errors="coerce")
    valid = frame.close.map(lambda x: pd.notna(x) and math.isfinite(x) and x > 0)
    frame.loc[~valid, "close"] = float("nan")
    bars = frame.resample("4h", label="right", closed="left").agg(
        close=("close", "last"), count=("close", "count")
    )
    out["skipped_incomplete_bars"] = int(out.get("skipped_incomplete_bars", 0))
    for stamp, row in bars.iterrows():
        if row["count"] != 240:
            out["skipped_incomplete_bars"] += 1
            continue
        value = (1.0 - ALPHA) * out["ema_tail"][-1] + ALPHA * float(row["close"])
        out["ema_tail"] = (out["ema_tail"] + [value])[-4:]
        out["complete_bars"] += 1
        out["close4"] = float(row["close"])
        out["available_at"] = stamp.isoformat()
    out["processed_through"] = end.isoformat()
    validate_state(out)
    return out


def decision(side: str, state: dict | None, signal_time) -> tuple[bool, str, dict]:
    """Only LONG is filtered. SHORT never needs context, even on feed failure."""
    if side == "SHORT":
        return True, "", {"l01_applies": False}
    if side != "LONG":
        return False, "l01_invalid_side", {"l01_applies": False}
    info = {"l01_applies": True}
    if state is None:
        return False, "l01_context_missing", info
    try:
        validate_state(state)
        at = utc(state["available_at"])
        target = utc(signal_time).floor("4h")
        if utc(state["processed_through"]) > target or at > target:
            return False, "l01_context_after_signal", info
        if at != target or utc(state["processed_through"]) != target:
            return False, "l01_context_stale", info
        if state["complete_bars"] < 53 or len(state["ema_tail"]) < 4:
            return False, "l01_context_warmup", info
        close, ema, lagged = state["close4"], state["ema_tail"][-1], state["ema_tail"][-4]
        info.update({"l01_close4": close, "l01_ema50": ema, "l01_ema50_lag3": lagged,
                     "l01_slope4": ema - lagged, "l01_available_at": at.isoformat(),
                     "l01_complete_bars": state["complete_bars"], "l01_seed_sha256": SEED_SHA256})
        ok = close > ema and ema > lagged
        return bool(ok), "" if ok else "l01_long_trend_gate", info
    except (KeyError, TypeError, ValueError, OverflowError):
        return False, "l01_context_invalid", info


class ContextStore:
    """One atomic file and lock per symbol, shared by data prep and the worker."""

    def __init__(self, root: Path = CONTEXT_DIR, seed_path: Path = SEED_PATH):
        self.root = root
        raw = seed_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != SEED_SHA256:
            raise ContextUnavailable("l01_seed_hash_mismatch")
        self.seed = json.loads(raw)["records"]

    def read(self, symbol: str) -> dict:
        if symbol not in self.seed:
            raise ContextUnavailable("l01_symbol_not_in_universe")
        path = self.root / f"{symbol}.json"
        if path.exists():
            data = json.loads(path.read_text())
            if data.get("seed_sha256") != SEED_SHA256 or data.get("symbol") != symbol:
                raise ContextUnavailable("l01_context_provenance_mismatch")
            state = data["state"]
        else:
            state = copy.deepcopy(self.seed[symbol])
        validate_state(state)
        return state

    def refresh(self, symbol: str, signal_time, data, *, max_catchup_hours: int | None = 8) -> dict:
        # Validate the symbol before it can become a path component.
        state = self.read(symbol)
        target = utc(signal_time).floor("4h")
        start = utc(state["processed_through"])
        if start >= target:
            return state
        if max_catchup_hours is not None and target - start > pd.Timedelta(hours=max_catchup_hours):
            raise ContextUnavailable("l01_context_prepare_required")
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / f"{symbol}.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ContextUnavailable("l01_context_refresh_in_progress") from exc
            state = self.read(symbol)
            while utc(state["processed_through"]) < target:
                start = utc(state["processed_through"])
                # Bounded chunks permit restart after an interrupted initial catch-up.
                end = min(target, start + pd.Timedelta(days=7))
                frame = data.fetch(symbol, "1m", start.to_pydatetime(),
                                   (end - pd.Timedelta(minutes=1)).to_pydatetime(), use_cache=True)
                try:
                    updated = advance(state, frame, end)
                except ContextUnavailable:
                    frame = data.fetch(symbol, "1m", start.to_pydatetime(),
                                       (end - pd.Timedelta(minutes=1)).to_pydatetime(), use_cache=False)
                    updated = advance(state, frame, end)
                payload = {"version": 1, "symbol": symbol, "seed_sha256": SEED_SHA256, "state": updated}
                fd, temp = tempfile.mkstemp(prefix=f".{symbol}-", dir=self.root)
                try:
                    with os.fdopen(fd, "w") as handle:
                        json.dump(payload, handle, allow_nan=False)
                        handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
                    os.replace(temp, self.root / f"{symbol}.json")
                finally:
                    if os.path.exists(temp):
                        os.unlink(temp)
                state = updated
            return state
