"""Why the latest observer scan did not trade. Display only.

Built from rows the scan already wrote. Nothing here places an order,
edits a threshold, or writes the hourly book. BL8 distances are read from
the klines on the context row (``raw_context``) or from a ``checks`` report
when one is stored. F111 distances use the feature values already on the
telemetry row.
"""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any

from core.strategy.gate_distance import NEAREST_CARD, f111_checklist

HOUR_MS = 3_600_000
# Frozen BL8 rule: mean/close - 1 must clear this. Same constant the worker
# compares. This module does not feed that comparison.
MEAN_DISTANCE_MIN = 0.0102
_FAILED_CAP = 8
_ATTEMPT_CAP = 40
_UNAVAILABLE_CAP = 96

_F111_GATES = (
    ("high_vol_filter", "High-vol filter", "high-vol filter"),
    ("compression_gate", "Compression", "compression"),
    ("extension_gate", "Extension", "extension"),
    ("base_signal_blocked", "Base signal", "base signal"),
)
_BL8_GATES = (
    ("green_candle", "Green candle", "green candle"),
    ("band_width", "Band width", "band width"),
    ("prior_below_band", "Prior close below the lower band", "prior-close band"),
    ("reclaim_band", "Close back above the lower band", "lower-band reclaim"),
    ("below_mean", "Close still under the mean", "below-the-mean"),
    ("mean_distance", "Distance to the mean", "distance to the mean"),
    ("above_stop", "Close above the stop", "stop"),
)
_DATA_REASONS = frozenset(
    {
        "missing_feature",
        "missing_context",
        "stale_context",
        "no_history",
        "insufficient_history",
        "hourly bar still forming",
        "missing_candle_or_quote",
    }
)
_EXIT_REASONS = frozenset(
    {"initial_stop", "protected_stop", "target", "stop_loss", "take_profit"}
)


def unavailable_why(reason: str) -> dict[str, Any]:
    """The scan could not be read. Counts stay empty."""
    return {
        "ok": False,
        "reason": reason,
        "summary": reason,
        "scan_at": None,
        "funnel": [],
        "closest_misses": [],
        "attempts": [],
        "unavailable": [],
        "unavailable_count": None,
        "attempts_truncated": False,
        "unavailable_truncated": False,
    }


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _token(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    for suffix in ("USDT", "USDC", "USD"):
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text or "—"


def _side_label(side: Any) -> str:
    text = str(side or "").strip().upper()
    if text in {"LONG", "BUY", "1", "+1"}:
        return "long"
    if text in {"SHORT", "SELL", "-1"}:
        return "short"
    return text.lower() if text else "—"


def _side_name(side: Any) -> str:
    label = _side_label(side)
    if label == "long":
        return "LONG"
    if label == "short":
        return "SHORT"
    return str(side or "—")


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


def _gap_text(gap: float | None, units: str, *, short: bool) -> str:
    if gap is None:
        return "distance not recorded"
    direction = "short of" if short else "over"
    if units in {"fraction", "return"}:
        pct = abs(gap) * 100.0
        shown = f"{pct:.1f}%" if pct >= 0.1 else f"{pct:.2f}%"
        return f"{shown} {direction} the threshold"
    if units == "ATR":
        return f"{abs(gap):.2f} ATR {direction} the threshold"
    if units:
        return f"{abs(gap):.4g} {units} {direction} the threshold"
    return f"gap {abs(gap):.4g} {direction} the threshold"


def _reading(
    *,
    gate: str,
    value: float | None,
    threshold: float | None,
    gap: float | None,
    passed: bool,
    units: str,
    short: bool,
) -> dict[str, Any]:
    scale = abs(threshold) if threshold not in (None, 0.0) else 1.0
    norm = None if gap is None else gap / scale
    return {
        "gate": gate,
        "value": _round(value),
        "threshold": None if threshold is None else threshold,
        "gap": _round(gap),
        "normalized": _round(norm),
        "passed": passed,
        "units": units,
        "short": short,
        "gap_text": _gap_text(gap, units, short=short),
    }


def _sum20(values: list[float]) -> float:
    """Same pairwise reduction the BL8 worker uses for the 20-close band.

    Report only. The worker does not call this.
    """
    if len(values) != 20:
        raise ValueError("band window must contain 20 closes")
    reduced = [float(value) for value in values[:8]]
    for index in range(8):
        reduced[index] += float(values[index + 8])
    total = ((reduced[0] + reduced[1]) + (reduced[2] + reduced[3])) + (
        (reduced[4] + reduced[5]) + (reduced[6] + reduced[7])
    )
    for value in values[16:]:
        total += float(value)
    return total


def score_bl8_hours(hours: list[dict[str, float]]) -> list[dict[str, Any]] | None:
    """Score the seven BL8 scan gates. A short history is not a fake failure."""
    if len(hours) < 25:
        return None
    window = [float(bar["c"]) for bar in hours[-22:-2]]
    if len(window) != 20:
        return None
    mean = _sum20(window) / 20.0
    deviations = [value - mean for value in window]
    sd = math.sqrt(_sum20([value * value for value in deviations]) / 20.0)
    ranges: list[float] = []
    for index in range(len(hours) - 15, len(hours) - 1):
        cur = hours[index]
        prev = hours[index - 1]
        ranges.append(
            max(
                float(cur["h"]) - float(cur["l"]),
                abs(float(cur["h"]) - float(prev["c"])),
                abs(float(cur["l"]) - float(prev["c"])),
            )
        )
    if len(ranges) != 14:
        return None
    atr = statistics.fmean(ranges)
    if not math.isfinite(atr) or atr <= 0 or not math.isfinite(sd):
        return None
    bar = hours[-1]
    prev = hours[-2]
    close = float(bar["c"])
    opened = float(bar["o"])
    prev_close = float(prev["c"])
    if min(close, opened, prev_close) <= 0:
        return None
    lower = mean - 2.0 * sd
    stop = min(float(bar["l"]), float(prev["l"])) - 0.5 * atr
    distance = mean / close - 1.0
    readings = [
        _cmp_above("green_candle", close, opened, exclusive=True, units="price"),
        _cmp_above("band_width", sd, 0.0, exclusive=True, units="std"),
        _cmp_below("prior_below_band", prev_close, lower, exclusive=True, units="price"),
        _cmp_above("reclaim_band", close, lower, exclusive=True, units="price"),
        _cmp_below("below_mean", close, mean, exclusive=True, units="price"),
        _cmp_above("mean_distance", distance, MEAN_DISTANCE_MIN, exclusive=False, units="fraction"),
        _cmp_above("above_stop", close, stop, exclusive=True, units="price"),
    ]
    return readings


def _cmp_above(gate: str, value: float, limit: float, *, exclusive: bool, units: str) -> dict[str, Any]:
    passed = value > limit if exclusive else value >= limit
    gap = 0.0 if passed else limit - value
    return _reading(
        gate=gate,
        value=value,
        threshold=limit,
        gap=gap,
        passed=passed,
        units=units,
        short=True,
    )


def _cmp_below(gate: str, value: float, limit: float, *, exclusive: bool, units: str) -> dict[str, Any]:
    passed = value < limit if exclusive else value <= limit
    gap = 0.0 if passed else value - limit
    return _reading(
        gate=gate,
        value=value,
        threshold=limit,
        gap=gap,
        passed=passed,
        units=units,
        short=False,
    )


def _bars_from_context(payload: dict[str, Any]) -> list[dict[str, float]] | None:
    raw = payload.get("raw_context")
    if not isinstance(raw, list) or not raw or not isinstance(raw[0], dict):
        return None
    result = raw[0].get("result")
    rows = result.get("list") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return None
    asof = _num(payload.get("signal_ms"))
    bars: dict[int, dict[str, float]] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) < 5:
            continue
        try:
            close_t = int(row[0]) + HOUR_MS
            bar = {
                "t": float(close_t),
                "o": float(row[1]),
                "h": float(row[2]),
                "l": float(row[3]),
                "c": float(row[4]),
            }
        except (TypeError, ValueError):
            continue
        if asof is not None and close_t > asof:
            continue
        if not all(math.isfinite(bar[key]) for key in ("o", "h", "l", "c")):
            continue
        bars[close_t] = bar
    ordered = [bars[key] for key in sorted(bars)]
    if len(ordered) < 25:
        return None
    return ordered


def _stored_checks(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    """A report block on the row, when the scan stored one."""
    raw = payload.get("checks")
    if isinstance(raw, dict):
        raw = raw.get("checks")
    if not isinstance(raw, list) or not raw:
        return None
    readings: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        gate = str(item.get("gate") or item.get("condition") or "").strip()
        if not gate:
            continue
        passed = item.get("passed")
        if not isinstance(passed, bool):
            continue
        value = _num(item.get("value"))
        threshold = _num(item.get("threshold"))
        gap = _num(item.get("gap"))
        units = str(item.get("units") or "")
        short = item.get("short")
        if not isinstance(short, bool):
            short = True if gap is None else gap >= 0 and (threshold is None or (value or 0) <= (threshold or 0))
        if gap is None and value is not None and threshold is not None and not passed:
            gap = abs(value - threshold)
        readings.append(
            _reading(
                gate=gate,
                value=value,
                threshold=threshold,
                gap=gap,
                passed=passed,
                units=units,
                short=bool(short),
            )
        )
    return readings or None


def _bl8_readings(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    stored = _stored_checks(payload)
    if stored:
        return stored
    bars = _bars_from_context(payload)
    if not bars:
        return None
    return score_bl8_hours(bars)


def _instrument_status(payload: dict[str, Any]) -> str | None:
    instrument = payload.get("instrument")
    if isinstance(instrument, dict):
        status = instrument.get("status")
        return str(status) if status else None
    if isinstance(instrument, list) and instrument and isinstance(instrument[0], dict):
        status = instrument[0].get("status")
        return str(status) if status else None
    return None


def _iso_ms(value: Any) -> float | None:
    number = _num(value)
    if number is not None:
        return number
    if not isinstance(value, str) or not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.timestamp() * 1000.0


def _scan_bounds(
    contexts: list[tuple[datetime | None, dict[str, Any]]],
) -> tuple[float, float] | None:
    signal_times: list[float] = []
    observed: list[float] = []
    for stamp, payload in contexts:
        ms = _num(payload.get("signal_ms"))
        if ms is not None:
            signal_times.append(ms)
        if stamp is not None:
            observed.append(stamp.timestamp() * 1000.0)
    if signal_times:
        start = max(signal_times)
    elif observed:
        start = max(observed) // HOUR_MS * HOUR_MS
    else:
        return None
    return start, start + HOUR_MS


def _in_window(ms: float | None, bounds: tuple[float, float] | None) -> bool:
    if bounds is None or ms is None:
        return False
    start, end = bounds
    return start <= ms < end


def _context_in_scan(
    stamp: datetime | None,
    payload: dict[str, Any],
    bounds: tuple[float, float],
) -> bool:
    signal = _num(payload.get("signal_ms"))
    if signal is not None:
        return _in_window(signal, bounds)
    observed = stamp.timestamp() * 1000.0 if stamp is not None else None
    return _in_window(observed, bounds)


def _attempt_bucket(reason: str) -> str:
    text = reason.lower()
    if any(token in text for token in ("notional", "exchange_minimum", "min_notional")):
        return "min notional"
    if any(token in text for token in ("exposure", "depth_exceeds", "paper_limit", "risk")):
        return "risk limit"
    if any(token in text for token in ("busy", "existing", "occupied", "position_already")):
        return "existing position"
    if any(token in text for token in ("cooldown", "missed_action", "missed_late")):
        return "cooldown"
    if "fill_gate" in text:
        return "fill gate"
    if "entries_disabled" in text or "scan_disabled" in text:
        return "entries paused"
    return reason.replace("_", " ")


def _symbol_from_uid(uid: Any, fallback: Any = None) -> str:
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    if isinstance(uid, str) and uid.strip():
        return uid.split("|", 1)[0]
    return ""


def _step(
    step_id: str,
    label: str,
    kind: str,
    passed: list[dict[str, Any]],
    failed: list[dict[str, Any]],
    *,
    sentence: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    ranked = sorted(
        failed,
        key=lambda row: (
            row.get("normalized") is None,
            row.get("normalized") if row.get("normalized") is not None else 0,
            str(row.get("symbol") or ""),
            str(row.get("side") or ""),
        ),
    )
    shown = []
    for row in ranked[:_FAILED_CAP]:
        shown.append(
            {
                "symbol": row.get("symbol"),
                "token": row.get("token"),
                "side": row.get("side"),
                "detail": row.get("detail") or "",
            }
        )
    return {
        "id": step_id,
        "label": label,
        "sentence": sentence or label.lower(),
        "kind": kind,
        "count": len(passed),
        "drop_off": len(failed),
        "failed_count": len(failed),
        "failed": shown,
        "note": note,
    }


def _miss_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol"),
        "token": row.get("token"),
        "side": row.get("side"),
        "side_label": _side_label(row.get("side")),
        "gate": row.get("gate"),
        "gate_label": row.get("gate_label"),
        "value": row.get("value"),
        "threshold": row.get("threshold"),
        "gap": row.get("gap"),
        "gap_text": row.get("gap_text"),
        "units": row.get("units"),
        "normalized": row.get("normalized"),
    }


def _summary(steps: list[dict[str, Any]], misses: list[dict[str, Any]]) -> str:
    by_id = {step["id"]: step for step in steps}
    filled = by_id.get("filled") or {"count": 0}
    signal = by_id.get("signal") or {"count": 0}
    closest = ""
    if misses:
        top = misses[0]
        who = f"{top.get('token') or top.get('symbol')} {top.get('side_label') or ''}".strip()
        distance = top.get("gap_text") or "distance not recorded"
        closest = f" Closest was {who}, {distance}."
    if int(filled.get("count") or 0) > 0:
        return f"{int(filled['count'])} filled on this scan.{closest}"
    blocker = None
    for step in steps:
        if step.get("kind") != "gate":
            continue
        if int(step.get("count") or 0) == 0 and int(step.get("drop_off") or 0) > 0:
            blocker = step
            break
    if int(signal.get("count") or 0) == 0 and blocker is not None:
        entered = int(blocker["count"]) + int(blocker["drop_off"])
        name = blocker.get("sentence") or blocker.get("label")
        return f"No entry: 0 of {entered} passed the {name} gate.{closest}"
    if int(signal.get("count") or 0) > 0:
        return f"No fill: {int(signal['count'])} signalled and none filled.{closest}"
    data = by_id.get("data_ok")
    if data is not None and int(data.get("count") or 0) == 0:
        return f"No entry: the latest scan had no usable features.{closest}"
    return f"No entry on this scan.{closest}"


def _finish(
    *,
    scan_at: str | None,
    steps: list[dict[str, Any]],
    misses: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    unavailable: list[dict[str, Any]],
) -> dict[str, Any]:
    ranked = sorted(
        [row for row in misses if _num(row.get("normalized")) is not None],
        key=lambda row: (
            float(row["normalized"]),
            float(row.get("gap") or 0),
            str(row.get("symbol") or ""),
            str(row.get("side") or ""),
        ),
    )
    shown_misses = [_miss_row(row) for row in ranked[:NEAREST_CARD]]
    shown_attempts = attempts[:_ATTEMPT_CAP]
    shown_unavailable = unavailable[:_UNAVAILABLE_CAP]
    return {
        "ok": True,
        "reason": None,
        "summary": _summary(steps, shown_misses),
        "scan_at": scan_at,
        "funnel": steps,
        "closest_misses": shown_misses,
        "attempts": shown_attempts,
        "unavailable": shown_unavailable,
        "unavailable_count": len(unavailable),
        "attempts_truncated": len(attempts) > _ATTEMPT_CAP,
        "unavailable_truncated": len(unavailable) > _UNAVAILABLE_CAP,
    }


def _candidate(
    *,
    symbol: str,
    side: str,
    drop: str,
    detail: str = "",
    reading: dict[str, Any] | None = None,
    gate_label: str = "",
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "symbol": symbol,
        "token": _token(symbol),
        "side": _side_name(side),
        "drop": drop,
        "detail": detail,
        "normalized": None,
        "gate": None,
        "gate_label": gate_label,
        "value": None,
        "threshold": None,
        "gap": None,
        "gap_text": "",
        "units": "",
    }
    if reading and reading.get("passed") is False and _num(reading.get("normalized")) is not None:
        row.update(
            {
                "normalized": reading.get("normalized"),
                "gate": reading.get("gate"),
                "value": reading.get("value"),
                "threshold": reading.get("threshold"),
                "gap": reading.get("gap"),
                "gap_text": reading.get("gap_text"),
                "units": reading.get("units"),
                "detail": reading.get("gap_text") or detail,
            }
        )
    return row


def build_bl8_why(
    contexts: list[tuple[datetime | None, dict[str, Any]]],
    *,
    entry_rejected: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    signals: list[dict[str, Any]] | None = None,
    positions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Latest BL8 hour only. Older pins in the same book stay out."""
    bounds = _scan_bounds(contexts)
    if bounds is None:
        return unavailable_why("No BL8 scan rows yet.")
    start, _end = bounds
    scan_at = datetime.fromtimestamp(start / 1000.0, tz=timezone.utc).isoformat()
    chosen = [
        (stamp, payload)
        for stamp, payload in contexts
        if _context_in_scan(stamp, payload, bounds)
    ]
    rejected_by_symbol: dict[str, str] = {}
    for row in entry_rejected or []:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else row
        if not isinstance(payload, dict):
            continue
        when = _iso_ms(row.get("t"))
        if not _in_window(when, bounds):
            continue
        symbol = _symbol_from_uid(payload.get("uid"), payload.get("symbol"))
        reason = payload.get("reason")
        if symbol and isinstance(reason, str) and reason:
            rejected_by_symbol[symbol] = reason
    signal_status: dict[str, str] = {}
    for row in signals or []:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        when = _num(payload.get("signal_ms"))
        if not _in_window(when, bounds) and when != start:
            continue
        symbol = str(row.get("symbol") or payload.get("symbol") or "")
        status = str(row.get("status") or "")
        if symbol and status:
            signal_status[symbol] = status
    filled: set[str] = set()
    for payload in positions or []:
        if not isinstance(payload, dict):
            continue
        when = _num(payload.get("entry_ms"))
        if not _in_window(when, bounds):
            continue
        symbol = str(payload.get("symbol") or "")
        if symbol:
            filled.add(symbol)
    for symbol, status in signal_status.items():
        if status == "filled":
            filled.add(symbol)

    people: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _stamp, payload in chosen:
        symbol = str(payload.get("symbol") or "")
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        status = _instrument_status(payload)
        reason = str(payload.get("reason") or "")
        unavailable = reason == "instrument_unavailable" or (
            status is not None and status != "Trading" and payload.get("eligible_signal") is not True
        )
        if unavailable:
            people.append(
                _candidate(
                    symbol=symbol,
                    side="LONG",
                    drop="data_ok",
                    detail=status or reason or "unavailable",
                )
            )
            people[-1]["unavailable_status"] = status or reason or "unavailable"
            continue
        if reason in {"missing_context", "stale_context"} or reason in _DATA_REASONS:
            people.append(_candidate(symbol=symbol, side="LONG", drop="data_ok", detail=reason))
            continue
        signalled = payload.get("eligible_signal") is True or reason == "candidate_requires_fill_gate"
        readings = None if signalled else _bl8_readings(payload)
        if signalled:
            people.append(_candidate(symbol=symbol, side="LONG", drop="signal"))
            continue
        failed = next((item for item in readings or [] if item.get("passed") is False), None)
        if failed is None:
            # The worker said no signal, and the row has no measured gate.
            # Do not promote that to a pass.
            people.append(
                _candidate(
                    symbol=symbol,
                    side="LONG",
                    drop="no_measurement",
                    detail=reason or "no_signal",
                )
            )
            continue
        label = next((name for gate, name, _sentence in _BL8_GATES if gate == failed["gate"]), failed["gate"])
        people.append(
            _candidate(
                symbol=symbol,
                side="LONG",
                drop=str(failed["gate"]),
                reading=failed,
                gate_label=label,
            )
        )

    for row in errors or []:
        when = _iso_ms(row.get("t"))
        if not _in_window(when, bounds):
            continue
        symbol = str(row.get("symbol") or "")
        if not symbol or symbol in seen:
            continue
        if str(row.get("operation") or "") not in {"", "context", "quote"}:
            continue
        seen.add(symbol)
        detail = str(row.get("error") or "error")[:180]
        people.append(_candidate(symbol=symbol, side="LONG", drop="data_ok", detail=detail))
        people[-1]["error"] = detail

    def _still(drop_ids: set[str]) -> list[dict[str, Any]]:
        return [row for row in people if row["drop"] not in drop_ids]

    steps: list[dict[str, Any]] = []
    steps.append(_step("scanned", "Symbols scanned", "scanned", people, []))
    data_failed = [row for row in people if row["drop"] == "data_ok"]
    data_ok = _still({"data_ok"})
    steps.append(_step("data_ok", "Data / feature OK", "data", data_ok, data_failed))

    blocked_gates: set[str] = set()
    for gate, label, sentence in _BL8_GATES:
        reached = [
            row
            for row in data_ok
            if row["drop"] not in blocked_gates and row["drop"] != "no_measurement"
        ]
        failed = [row for row in reached if row["drop"] == gate]
        passed = [row for row in reached if row["drop"] != gate]
        steps.append(_step(gate, label, "gate", passed, failed, sentence=sentence))
        blocked_gates.add(gate)

    signalled = [row for row in data_ok if row["drop"] == "signal" or row["symbol"] in filled]
    unscored = [row for row in data_ok if row["drop"] == "no_measurement"]
    steps.append(_step("signal", "Signal", "signal", signalled, unscored, sentence="signal"))

    risk_failed: list[dict[str, Any]] = []
    risk_passed: list[dict[str, Any]] = []
    order_failed: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for row in signalled:
        symbol = str(row["symbol"])
        if symbol in filled:
            risk_passed.append(row)
            continue
        reason = rejected_by_symbol.get(symbol) or signal_status.get(symbol) or ""
        if reason in {"pending", ""}:
            order_failed.append({**row, "detail": "pending, not sent"})
            risk_passed.append(row)
            continue
        bucket = _attempt_bucket(reason)
        detail = bucket
        risk_failed.append({**row, "detail": detail})
        attempts.append(
            {
                "symbol": symbol,
                "token": row["token"],
                "side": row["side"],
                "reason": bucket,
                "detail": reason,
            }
        )
    for row in people:
        if not row.get("error"):
            continue
        attempts.append(
            {
                "symbol": row["symbol"],
                "token": row["token"],
                "side": row["side"],
                "reason": "error",
                "detail": row["error"],
            }
        )
    steps.append(_step("risk_sizing", "Risk / sizing check", "risk", risk_passed, risk_failed, sentence="risk / sizing"))
    ordered = [row for row in risk_passed if row["symbol"] in filled]
    pending = [row for row in order_failed if row["symbol"] not in filled]
    # A pending name was also appended to risk_passed. Drop it at the order step.
    pending_symbols = {row["symbol"] for row in pending}
    ordered_pool = [row for row in risk_passed if row["symbol"] not in pending_symbols or row["symbol"] in filled]
    steps.append(
        _step(
            "order_sent",
            "Order sent",
            "order",
            [row for row in ordered_pool if row["symbol"] in filled],
            [row for row in ordered_pool if row["symbol"] not in filled] + pending,
            sentence="order",
            note="A paper fill is the order on this book. No exchange order is sent.",
        )
    )
    filled_rows = [row for row in ordered if row["symbol"] in filled]
    steps.append(_step("filled", "Filled", "filled", filled_rows, [], sentence="fill"))

    misses = [row for row in people if row.get("normalized") is not None and row["drop"] not in {"data_ok", "signal"}]
    unavailable = []
    for row in people:
        status = row.get("unavailable_status")
        if not status:
            continue
        unavailable.append(
            {
                "symbol": row["symbol"],
                "token": row["token"],
                "side": row.get("side") or "LONG",
                "status": status,
            }
        )
    unavailable.sort(key=lambda row: str(row["symbol"]))
    attempts.sort(key=lambda row: (str(row["symbol"]), str(row["reason"])))
    return _finish(
        scan_at=scan_at,
        steps=steps,
        misses=misses,
        attempts=attempts,
        unavailable=unavailable,
    )


def _f111_exit(row: dict[str, Any]) -> bool:
    if _num(row.get("realised_net_profit")) is not None:
        return True
    if "exit_fee" in row and row.get("exit_fee") is not None:
        return True
    reason = str(row.get("rejection_reason") or "")
    return reason in _EXIT_REASONS


def _f111_features(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("feature_values")
    return dict(raw) if isinstance(raw, dict) else {}


def _f111_reading(row: dict[str, Any], reason: str) -> dict[str, Any] | None:
    features = _f111_features(row)
    if not features:
        return None
    base_blocked = reason == "base_signal_blocked" or str(features.get("f111_rejection_reason") or "") == "base_signal_blocked"
    checklist = f111_checklist(features, side=row.get("side"), base_blocked=base_blocked)
    if reason and reason != "base_signal_blocked":
        match = next((item for item in checklist if item.get("gate") == reason and item.get("passed") is False), None)
        if match is not None and _num(match.get("normalized")) is not None:
            return _as_reading(match, short=_short_of(match))
    failed = [item for item in checklist if item.get("passed") is False and _num(item.get("normalized")) is not None]
    if not failed:
        return None
    failed.sort(key=lambda item: (float(item["normalized"]), str(item.get("condition") or "")))
    return _as_reading(failed[0], short=_short_of(failed[0]))


def _short_of(reading: dict[str, Any]) -> bool:
    value = _num(reading.get("value"))
    threshold = _num(reading.get("threshold"))
    if value is None or threshold is None:
        return True
    return value <= threshold


def _as_reading(reading: dict[str, Any], *, short: bool) -> dict[str, Any]:
    gate = str(reading.get("condition") or reading.get("gate") or "")
    parent = str(reading.get("gate") or gate)
    return _reading(
        gate=parent if parent == "base_signal_blocked" and gate in {"", "base_signal_blocked"} else gate or parent,
        value=_num(reading.get("value")),
        threshold=_num(reading.get("threshold")),
        gap=_num(reading.get("gap")),
        passed=False,
        units=str(reading.get("units") or ""),
        short=short,
    )


def _f111_hour(rows: list[dict[str, Any]]) -> tuple[datetime, datetime] | None:
    from core.execution.f111_paper import row_recorded_time

    stamps: list[datetime] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("record_kind") == "registry" or row.get("deploy_marker"):
            continue
        if _f111_exit(row):
            continue
        if not row.get("symbol"):
            continue
        stamp = row_recorded_time(row)
        if stamp is not None:
            stamps.append(stamp)
    if not stamps:
        return None
    latest = max(stamps)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    else:
        latest = latest.astimezone(timezone.utc)
    start = latest.replace(minute=0, second=0, microsecond=0)
    from datetime import timedelta

    return start, start + timedelta(hours=1)


def build_f111_why(
    rows: list[dict[str, Any]],
    census: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Latest F111 hour. Registry rows name unavailable markets, not gates."""
    window = _f111_hour(rows)
    if window is None and not census:
        return unavailable_why("No F111 scan rows yet.")
    from core.execution.f111_paper import row_recorded_time

    start, end = window if window is not None else (None, None)
    people: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    scan_at = start.isoformat() if start is not None else None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("record_kind") == "registry" or row.get("deploy_marker") or _f111_exit(row):
            continue
        symbol = str(row.get("symbol") or "")
        if not symbol or start is None or end is None:
            continue
        stamp = row_recorded_time(row)
        if stamp is None or not (start <= stamp < end):
            continue
        side = _side_name(row.get("side"))
        key = (symbol, side)
        # Later rows in the file replace an earlier decision for the same sleeve.
        if key in seen:
            people = [item for item in people if (item["symbol"], item["side"]) != key]
        seen.add(key)
        people.append(_f111_person(row))

    for row in census or []:
        if not isinstance(row, dict) or not row.get("instrument_unavailable"):
            continue
        symbol = str(row.get("symbol") or "")
        side = _side_name(row.get("side"))
        if not symbol or (symbol, side) in seen:
            continue
        seen.add((symbol, side))
        status = ""
        features = row.get("feature_values") if isinstance(row.get("feature_values"), dict) else {}
        if isinstance(features, dict) and features.get("exchange_status"):
            status = str(features["exchange_status"])
        else:
            status = str(row.get("rejection_reason") or "unavailable")
        person = _candidate(symbol=symbol, side=side, drop="data_ok", detail=status)
        person["unavailable_status"] = status
        people.append(person)

    if not people:
        return unavailable_why("No F111 scan rows yet.")

    data_failed = [row for row in people if row["drop"] == "data_ok"]
    data_ok = [row for row in people if row["drop"] != "data_ok"]
    steps = [
        _step("scanned", "Sleeves scanned", "scanned", people, []),
        _step("data_ok", "Data / feature OK", "data", data_ok, data_failed),
    ]
    blocked: set[str] = set()
    for gate, label, sentence in _F111_GATES:
        reached = [
            row
            for row in data_ok
            if row["drop"] not in blocked and row["drop"] != "no_measurement"
        ]
        failed = [row for row in reached if row["drop"] == gate]
        passed = [row for row in reached if row["drop"] != gate]
        steps.append(_step(gate, label, "gate", passed, failed, sentence=sentence))
        blocked.add(gate)
    signalled = [row for row in data_ok if row.get("signalled")]
    quiet = [row for row in data_ok if row["drop"] == "no_measurement"]
    steps.append(_step("signal", "Signal", "signal", signalled, quiet, sentence="signal"))
    risk_failed = [row for row in signalled if row.get("attempt")]
    risk_passed = [row for row in signalled if not row.get("attempt")]
    steps.append(
        _step("risk_sizing", "Risk / sizing check", "risk", risk_passed, risk_failed, sentence="risk / sizing")
    )
    ordered = [row for row in risk_passed if row.get("ordered") or row.get("filled")]
    not_ordered = [row for row in risk_passed if not row.get("ordered") and not row.get("filled")]
    for row in not_ordered:
        row["detail"] = row.get("detail") or "pending retest, not sent"
    steps.append(
        _step(
            "order_sent",
            "Order sent",
            "order",
            ordered,
            not_ordered,
            sentence="order",
            note="F111 paper records a simulated fill. No exchange order is sent.",
        )
    )
    filled_rows = [row for row in ordered if row.get("filled")]
    steps.append(
        _step("filled", "Filled", "filled", filled_rows, [row for row in ordered if not row.get("filled")])
    )
    attempts = []
    for row in people:
        attempt = row.get("attempt")
        if isinstance(attempt, dict):
            attempts.append(attempt)
    attempts.sort(key=lambda row: (str(row.get("symbol") or ""), str(row.get("reason") or "")))
    unavailable = [
        {"symbol": row["symbol"], "token": row["token"], "status": row["unavailable_status"], "side": row["side"]}
        for row in people
        if row.get("unavailable_status")
    ]
    unavailable.sort(key=lambda row: (str(row["symbol"]), str(row.get("side") or "")))
    misses = [row for row in people if row.get("normalized") is not None]
    return _finish(
        scan_at=scan_at,
        steps=steps,
        misses=misses,
        attempts=attempts,
        unavailable=unavailable,
    )


def _f111_person(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "")
    side = _side_name(row.get("side"))
    reason = str(row.get("rejection_reason") or "").strip()
    if reason.lower() in {"none", "null"}:
        reason = ""
    features = _f111_features(row)
    exchange = features.get("exchange_status")
    unavailable = bool(row.get("instrument_unavailable")) or (
        isinstance(reason, str) and ("unavailable" in reason.lower() or "not listed" in reason.lower() or "exchange status" in reason.lower())
    )
    if unavailable:
        status = str(exchange or reason or "unavailable")
        person = _candidate(symbol=symbol, side=side, drop="data_ok", detail=status)
        person["unavailable_status"] = status
        return person
    data_gap = bool(row.get("missing_candle_or_quote")) or reason in _DATA_REASONS or reason.startswith("hourly fetch failed")
    if data_gap:
        return _candidate(symbol=symbol, side=side, drop="data_ok", detail=reason or "missing data")
    signalled = row.get("gate_decision") is True or bool(row.get("pending_retest_created_at"))
    filled = row.get("simulated_fill") not in (None, "") and signalled and not reason
    ordered = filled or (signalled and bool(row.get("action_time")) and not reason)
    known = {gate for gate, _label, _sentence in _F111_GATES}
    if not signalled and reason in known:
        reading = _f111_reading(row, reason)
        label = next(name for gate, name, _sentence in _F111_GATES if gate == reason)
        return _candidate(
            symbol=symbol,
            side=side,
            drop=reason,
            reading=reading,
            gate_label=label,
            detail="" if reading else reason,
        )
    if not signalled:
        reading = _f111_reading(row, reason)
        drop = "no_measurement"
        if reading is not None:
            parent = next((gate for gate, _label, _sentence in _F111_GATES if gate == reading.get("gate")), None)
            drop = parent or "no_measurement"
        return _candidate(
            symbol=symbol,
            side=side,
            drop=drop,
            reading=reading,
            detail=reason or "no_signal",
        )
    person = _candidate(symbol=symbol, side=side, drop="signal")
    person["signalled"] = True
    person["filled"] = filled
    person["ordered"] = ordered
    block = row.get("occupancy_or_risk_rejection")
    block_text = str(block or reason or "").strip()
    if block_text and not filled:
        person["attempt"] = {
            "symbol": symbol,
            "token": _token(symbol),
            "side": side,
            "reason": _attempt_bucket(block_text),
            "detail": block_text,
        }
        person["detail"] = _attempt_bucket(block_text)
    return person
