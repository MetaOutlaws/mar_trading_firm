"""Read-only distance from a sleeve to the gate that rejected it.

Nothing here writes a signal frame, calls ``gate_decision``, or changes a
threshold. Limits are read from the modules that already enforce them:

* F111 extension, compression, and high-vol live in ``f111_semantics``
* the hourly base signal lives in the hourly-compression modules

A book strategy that does not expose a number falls back to its reason.
``Strategy.gate_diagnostics`` is the optional hook for that number.
"""

from __future__ import annotations

import math
from typing import Any

from core.strategy import f111_semantics
from core.strategy import hourly_compression_btc_connors_loweff_v1 as loweff
from core.strategy import hourly_compression_btc_connors_v1 as btc_gate
from core.strategy import hourly_compression_connors_v1 as connors
from core.strategy import hourly_compression_v1 as hourly

# How many of the closest misses the Inbox card shows. The operator asked
# for the 5–10 nearest; 10 is the top of that range, fewer when fewer exist.
NEAREST_CARD = 10

# Top-level F111 gates. "All but one" counts these, not every base sub-check.
F111_GATES = (
    "high_vol_filter",
    "compression_gate",
    "extension_gate",
    "base_signal_blocked",
)


def _num(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _side_sign(side: Any) -> int:
    text = str(side or "").strip().upper()
    if text in {"LONG", "BUY", "1", "+1"}:
        return 1
    if text in {"SHORT", "SELL", "-1"}:
        return -1
    try:
        sign = int(side)
    except (TypeError, ValueError):
        return 0
    return sign if sign in (1, -1) else 0


def _scale(threshold: float | None, fallback: float | None = None) -> float:
    """Denominator for gap / threshold. A zero bound uses a fallback or 1."""
    if threshold is not None and abs(threshold) > 0:
        return abs(threshold)
    if fallback is not None and abs(fallback) > 0:
        return abs(fallback)
    return 1.0


def _reading(
    *,
    gate: str,
    condition: str,
    value: float | None,
    threshold: float | None,
    gap: float | None,
    passed: bool | None,
    units: str,
    scale: float | None = None,
) -> dict[str, Any]:
    """One condition. ``gap`` is in ``units``. ``normalized`` is gap / scale."""
    norm = None
    if gap is not None:
        denom = scale if scale is not None and scale > 0 else _scale(threshold)
        norm = gap / denom
    return {
        "gate": gate,
        "condition": condition,
        "metric": condition,
        "value": None if value is None else round(value, 6),
        "threshold": None if threshold is None else threshold,
        "gap": None if gap is None else round(gap, 6),
        "normalized": None if norm is None else round(norm, 6),
        "passed": passed,
        "units": units,
    }


def _above(value: float, limit: float, *, exclusive: bool) -> tuple[bool, float]:
    """Pass when value clears ``limit``. Gap is how far short, in the same units."""
    passed = value > limit if exclusive else value >= limit
    gap = 0.0 if passed else limit - value
    return passed, gap


def _below(value: float, limit: float, *, exclusive: bool) -> tuple[bool, float]:
    """Pass when value is under ``limit``. Gap is how far over."""
    passed = value < limit if exclusive else value <= limit
    gap = 0.0 if passed else value - limit
    return passed, gap


def _flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if type(value).__name__ == "bool_":
        return bool(value)
    return None


def f111_numeric_gates(features: dict[str, Any]) -> list[dict[str, Any]]:
    """Extension, compression, and high-vol, each scored on its own.

    ``gate_decision`` stops at the first failure. This scores all three so a
    sleeve that missed only one can be told apart from a sleeve that missed
    two. Missing inputs are left unscored; they are not invented failures.
    """
    features = features or {}
    readings: list[dict[str, Any]] = []
    extension_limit = float(f111_semantics.EXTENSION_MAX_INCLUSIVE)
    compression_limit = float(f111_semantics.COMPRESSION_MIN_EXCLUSIVE)
    high_vol_limit = float(f111_semantics.HIGH_VOL_MIN_INCLUSIVE)

    extension = _num(features.get("extension_atr"))
    if extension is not None:
        passed, gap = _below(extension, extension_limit, exclusive=False)
        readings.append(
            _reading(
                gate="extension_gate",
                condition="extension_atr",
                value=extension,
                threshold=extension_limit,
                gap=gap,
                passed=passed,
                units="ATR",
            )
        )

    compression = _num(features.get("compression"))
    if compression is not None:
        # Strict: compression must be greater than the floor. Equality fails
        # with a gap of zero, which ranks as the closest possible miss.
        passed, gap = _above(compression, compression_limit, exclusive=True)
        readings.append(
            _reading(
                gate="compression_gate",
                condition="compression",
                value=compression,
                threshold=compression_limit,
                gap=gap,
                passed=passed,
                units="compression",
            )
        )

    prior = _num(features.get("prior_atr"))
    close = _num(features.get("close"))
    if prior is not None and close is not None and close > 0 and prior > 0:
        ratio = prior / close
        passed, gap = _above(ratio, high_vol_limit, exclusive=False)
        readings.append(
            _reading(
                gate="high_vol_filter",
                condition="prior_atr/close",
                value=ratio,
                threshold=high_vol_limit,
                gap=gap,
                passed=passed,
                units="prior ATR / close",
            )
        )
    return readings


def _sub(
    *,
    condition: str,
    value: float | None,
    threshold: float | None,
    gap: float | None,
    passed: bool | None,
    units: str,
    scale: float | None = None,
) -> dict[str, Any]:
    row = _reading(
        gate="base_signal_blocked",
        condition=condition,
        value=value,
        threshold=threshold,
        gap=gap,
        passed=passed,
        units=units,
        scale=scale,
    )
    return row


def base_signal_subs(features: dict[str, Any], *, side: Any) -> list[dict[str, Any]]:
    """Which base-signal sub-condition failed, and by how much.

    A sub-condition is included only when its inputs are on the row. The
    parent signal is an AND of these checks, plus the low-efficiency OR.
    """
    features = features or {}
    sign = _side_sign(side if side is not None else features.get("side"))
    if sign == 0:
        return []
    subs: list[dict[str, Any]] = []
    prior = _num(features.get("prior_atr"))
    price_scale = prior if prior is not None and prior > 0 else None

    compression = _num(features.get("compression"))
    if compression is not None:
        limit = float(hourly.COMPRESSION_MAX_INCLUSIVE)
        passed, gap = _below(compression, limit, exclusive=False)
        subs.append(
            _sub(
                condition="base_compression",
                value=compression,
                threshold=limit,
                gap=gap,
                passed=passed,
                units="compression",
            )
        )

    tr = _num(features.get("true_range"))
    if tr is not None and prior is not None and prior > 0:
        limit = float(hourly.RANGE_EXPANSION_MIN_INCLUSIVE)
        ratio = tr / prior
        passed, gap = _above(ratio, limit, exclusive=False)
        subs.append(
            _sub(
                condition="base_range_expansion",
                value=ratio,
                threshold=limit,
                gap=gap,
                passed=passed,
                units="true range / prior ATR",
            )
        )

    volume = _num(features.get("volume_ratio"))
    if volume is not None:
        limit = float(hourly.VOLUME_RATIO_MIN_INCLUSIVE)
        passed, gap = _above(volume, limit, exclusive=False)
        subs.append(
            _sub(
                condition="base_volume",
                value=volume,
                threshold=limit,
                gap=gap,
                passed=passed,
                units="volume / 20-bar median",
            )
        )

    close = _num(features.get("close"))
    opened = _num(features.get("open"))
    if close is not None and opened is not None:
        # The bar must close in the trade's direction. Threshold is zero,
        # so the ranking scale is prior ATR when we have one.
        signed = sign * (close - opened)
        passed = signed > 0
        gap = 0.0 if passed else -signed
        subs.append(
            _sub(
                condition="base_bar_direction",
                value=signed,
                threshold=0.0,
                gap=gap,
                passed=passed,
                units="price",
                scale=price_scale,
            )
        )

    r24 = _num(features.get("r24"))
    if r24 is not None:
        signed = sign * r24
        passed = signed >= 0
        gap = 0.0 if passed else -signed
        subs.append(
            _sub(
                condition="base_r24",
                value=signed,
                threshold=0.0,
                gap=gap,
                passed=passed,
                units="24h return",
                scale=1.0,
            )
        )

    boundary = _num(features.get("boundary"))
    if boundary is None:
        boundary = _num(features.get("entry_boundary"))
    if close is not None and boundary is not None:
        signed = sign * (close - boundary)
        passed = signed > 0
        gap = 0.0 if passed else -signed
        subs.append(
            _sub(
                condition="base_breakout",
                value=signed,
                threshold=0.0,
                gap=gap,
                passed=passed,
                units="price beyond the prior-20 boundary",
                scale=price_scale,
            )
        )

    location = _num(features.get("close_location"))
    if location is not None:
        if sign == 1:
            limit = float(hourly.CLOSE_LOCATION_LONG_MIN_INCLUSIVE)
            passed, gap = _above(location, limit, exclusive=False)
        else:
            limit = float(hourly.CLOSE_LOCATION_SHORT_MAX_INCLUSIVE)
            passed, gap = _below(location, limit, exclusive=False)
        subs.append(
            _sub(
                condition="base_close_location",
                value=location,
                threshold=limit,
                gap=gap,
                passed=passed,
                units="close location in the bar",
            )
        )

    crsi = _num(features.get("filter_crsi"))
    crsi_flag = _flag(features.get("passes_crsi"))
    if crsi is not None or crsi_flag is not None:
        if sign == 1:
            limit = float(connors.CRSI_LONG_MAX_INCLUSIVE)
            if crsi is None:
                passed, gap, value = crsi_flag, None, None
            else:
                passed, gap = _below(crsi, limit, exclusive=False)
                value = crsi
                if crsi_flag is not None:
                    passed = crsi_flag
        else:
            limit = float(connors.CRSI_SHORT_MIN_INCLUSIVE)
            if crsi is None:
                passed, gap, value = crsi_flag, None, None
            else:
                passed, gap = _above(crsi, limit, exclusive=False)
                value = crsi
                if crsi_flag is not None:
                    passed = crsi_flag
        subs.append(
            _sub(
                condition="base_crsi",
                value=value,
                threshold=limit,
                gap=gap,
                passed=passed,
                units="Connors RSI",
            )
        )

    is_btc = features.get("is_btc")
    btc = _num(features.get("btc24"))
    btc_flag = _flag(features.get("passes_btc"))
    if is_btc is True:
        subs.append(
            _sub(
                condition="base_btc24",
                value=btc,
                threshold=float(btc_gate.BTC24_DIRECTION_MIN_EXCLUSIVE),
                gap=0.0,
                passed=True,
                units="BTC 24h return",
                scale=1.0,
            )
        )
    elif btc is not None or btc_flag is not None:
        limit = float(btc_gate.BTC24_DIRECTION_MIN_EXCLUSIVE)
        if btc is None:
            passed, gap, value = btc_flag, None, None
        else:
            signed = sign * btc
            passed = signed > limit
            gap = 0.0 if passed else limit - signed
            value = signed
            if btc_flag is not None:
                passed = btc_flag
        subs.append(
            _sub(
                condition="base_btc24",
                value=value,
                threshold=limit,
                gap=gap,
                passed=passed,
                units="BTC 24h return",
                scale=1.0,
            )
        )

    efficiency = _num(features.get("efficiency24"))
    if efficiency is None:
        efficiency = _num(features.get("efficiency24_before_signal"))
    extension = _num(features.get("extension_atr"))
    low_flag = _flag(features.get("passes_loweff_cap"))
    if efficiency is not None or extension is not None or low_flag is not None:
        eff_limit = float(loweff.EFFICIENCY_FLOOR_INCLUSIVE)
        ext_limit = float(loweff.LOW_EFFICIENCY_EXTENSION_MAX_INCLUSIVE)
        eff_passed = eff_gap = None
        ext_passed = ext_gap = None
        if efficiency is not None:
            eff_passed, eff_gap = _above(efficiency, eff_limit, exclusive=False)
        if extension is not None:
            ext_passed, ext_gap = _below(extension, ext_limit, exclusive=False)
        if eff_passed is True or ext_passed is True:
            passed = True
            gap = 0.0
            # Report the side that already clears the OR.
            if eff_passed is True:
                value, threshold, units = efficiency, eff_limit, "prior efficiency"
            else:
                value, threshold, units = extension, ext_limit, "ATR"
        elif eff_gap is not None or ext_gap is not None:
            # Distance to an OR is the closer of the two failing sides.
            candidates = []
            if eff_gap is not None and efficiency is not None:
                candidates.append(
                    (eff_gap / _scale(eff_limit), eff_gap, efficiency, eff_limit, "prior efficiency")
                )
            if ext_gap is not None and extension is not None:
                candidates.append(
                    (ext_gap / _scale(ext_limit), ext_gap, extension, ext_limit, "ATR")
                )
            _norm, gap, value, threshold, units = min(candidates, key=lambda item: item[0])
            passed = False
        else:
            passed, gap, value, threshold, units = low_flag, None, None, None, "low-efficiency cap"
        if low_flag is not None:
            passed = low_flag
            if passed:
                gap = 0.0
        subs.append(
            _sub(
                condition="base_low_efficiency",
                value=value,
                threshold=threshold,
                gap=gap,
                passed=passed,
                units=units,
            )
        )
    return subs


def base_gate_reading(features: dict[str, Any], *, side: Any, forced_fail: bool = False) -> dict[str, Any] | None:
    """Collapse the base sub-conditions into one gate.

    The displayed value is the closest failed sub-condition. ``forced_fail``
    covers a row the parent already marked ``base_signal_blocked`` when the
    sub-condition numbers were not on the telemetry.
    """
    subs = base_signal_subs(features, side=side)
    failed = [row for row in subs if row.get("passed") is False]
    if not subs and not forced_fail:
        return None
    if not failed and not forced_fail:
        return _reading(
            gate="base_signal_blocked",
            condition="base_signal",
            value=None,
            threshold=None,
            gap=0.0,
            passed=True,
            units="",
        )
    if not failed:
        return _reading(
            gate="base_signal_blocked",
            condition="base_signal_blocked",
            value=None,
            threshold=None,
            gap=None,
            passed=False,
            units="",
        )
    closest = min(failed, key=_sort_reading)
    chosen = dict(closest)
    chosen["gate"] = "base_signal_blocked"
    chosen["passed"] = False
    return chosen


def readings_from_signal_row(row: dict[str, Any], *, side: Any = None) -> list[dict[str, Any]]:
    """Hook helper: F111 numeric gates plus base sub-conditions that are present.

    Returned for ``Strategy.gate_diagnostics``. Callers must not write these
    back onto the signal frame.
    """
    features = dict(row or {})
    chosen_side = side if side is not None else features.get("side")
    readings = f111_numeric_gates(features)
    readings.extend(base_signal_subs(features, side=chosen_side))
    return readings


def f111_checklist(features: dict[str, Any], *, side: Any, base_blocked: bool = False) -> list[dict[str, Any]]:
    """The four F111 gates, scored independently of ``gate_decision``."""
    checklist = list(f111_numeric_gates(features))
    subs = base_signal_subs(features, side=side)
    base = base_gate_reading(features, side=side, forced_fail=base_blocked and not subs)
    # The parent already rejected the bar, but every measured sub-condition
    # cleared. Keep the failure for the all-but-one count and do not invent
    # a zero gap, which would look like a perfect near miss.
    if base_blocked and base is not None and base.get("passed") is True:
        base = dict(base)
        base["passed"] = False
        base["gap"] = None
        base["normalized"] = None
        base["condition"] = "base_signal_blocked"
        base["metric"] = "base_signal_blocked"
    if base_blocked and base is None:
        base = base_gate_reading(features, side=side, forced_fail=True)
    if base is not None:
        checklist.append(base)
    return checklist


def normalize_hook(items: Any) -> tuple[list[dict[str, Any]], bool]:
    """Turn a strategy hook into readings.

    A full checklist is a list where every item says whether it passed.
    A single ``(condition, value, threshold)`` is the failing condition
    only, and is not treated as "all but one".
    """
    if not isinstance(items, (list, tuple)) or isinstance(items, (str, bytes)):
        return [], False
    # One triple, not a list of triples.
    if len(items) >= 3 and not isinstance(items[0], (dict, list, tuple)):
        items = [items]
    readings: list[dict[str, Any]] = []
    explicit = True
    for item in items:
        row = _hook_item(item)
        if row is None:
            continue
        if row.get("passed") is None:
            explicit = False
            row["passed"] = False
        readings.append(row)
    checklist = bool(readings) and explicit and len(readings) >= 2
    return readings, checklist


def _hook_item(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        condition = str(item.get("condition") or item.get("gate") or item.get("metric") or "").strip()
        if not condition:
            return None
        value = _num(item.get("value"))
        threshold = _num(item.get("threshold"))
        gap = _num(item.get("gap"))
        passed = item.get("passed")
        if not isinstance(passed, bool) and type(passed).__name__ != "bool_":
            passed = None
        else:
            passed = bool(passed)
        if gap is None and value is not None and threshold is not None and passed is False:
            gap = abs(value - threshold)
        if gap is None and passed is True:
            gap = 0.0
        gate = str(item.get("gate") or condition)
        return _reading(
            gate=gate,
            condition=condition,
            value=value,
            threshold=threshold,
            gap=gap if passed is not None or gap is not None else None,
            passed=passed,
            units=str(item.get("units") or ""),
            scale=_num(item.get("scale")),
        )
    if isinstance(item, (list, tuple)) and len(item) >= 3:
        condition = str(item[0] or "").strip()
        if not condition:
            return None
        value = _num(item[1])
        threshold = _num(item[2])
        passed = item[3] if len(item) >= 4 and isinstance(item[3], bool) else None
        gap = None
        if value is not None and threshold is not None and passed is False:
            gap = abs(value - threshold)
        if passed is True:
            gap = 0.0
        if passed is None and value is not None and threshold is not None:
            gap = abs(value - threshold)
        return _reading(
            gate=condition,
            condition=condition,
            value=value,
            threshold=threshold,
            gap=gap,
            passed=passed,
            units="",
        )
    return None


def _sort_reading(row: dict[str, Any]) -> tuple:
    norm = _num(row.get("normalized"))
    gap = _num(row.get("gap"))
    return (
        norm if norm is not None else float("inf"),
        gap if gap is not None else float("inf"),
        str(row.get("condition") or ""),
    )


def closest_failure(readings: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The failed reading with the smallest normalized gap, if any number exists."""
    failed = [row for row in readings if row.get("passed") is False and _num(row.get("normalized")) is not None]
    if not failed:
        return None
    return min(failed, key=_sort_reading)


def rank_misses(misses: list[dict[str, Any]], limit: int = NEAREST_CARD) -> list[dict[str, Any]]:
    """Nearest first. A missing distance sorts last and is dropped."""
    ranked = [row for row in misses if _num(row.get("normalized")) is not None]
    ranked.sort(
        key=lambda row: (
            float(row["normalized"]),
            float(row.get("gap") or 0),
            str(row.get("symbol") or ""),
            str(row.get("side") or ""),
            str(row.get("condition") or ""),
        )
    )
    return ranked[: max(0, int(limit))]
