"""Paper sleeves for two frozen rules on the SGP1 96-token universe.

Brian YES 2026-10-16: append ``ema_adx_trend`` and
``range_compression_volume_thrust``, LONG and SHORT, as operator paper
overrides. ``approved`` stays false, so the live plan cannot select them.

Params and clocks are the ones already frozen in the repo. Nothing here
searches a grid or invents a new number.

The approval book is appended. Existing rows stay the bytes they already
were. A comma is inserted after the last old row so the new keys can follow.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Mapping

from config.settings import PROJECT_ROOT
from config.universe import approval_record_key, parse_approval_key
from core.strategy.ema_adx_trend import EmaAdxParams, EmaAdxTrendStrategy
from core.strategy.double_top_neckline_break import DoubleTopNecklineBreakParams
from core.strategy.fib_extension_break import FibExtensionBreakParams
from core.strategy.monday_range_sweep_reversal import MondayRangeSweepReversalParams
from core.strategy.range_compression_volume_thrust import (
    RangeCompressionVolumeThrustParams,
    RangeCompressionVolumeThrustStrategy,
)
from core.strategy.week_open_reclaim import WeekOpenReclaimParams
from firm.research_catalog import RESEARCH_HYPOTHESES
from firm.research_jobs import CLOCK_BY_FAMILY

# Same digest ``research.revalidation.fingerprint_approval_book`` uses:
# SHA-256 of the raw file bytes, not a re-serialised JSON object.
BOOK_PATH = PROJECT_ROOT / "config" / "approved_strategies.json"
F111_UNIVERSE_PATH = (
    PROJECT_ROOT / "config" / "sleeves" / "mar_f111_r12_extension_latefloor_v1.json"
)
L01_UNIVERSE_PATH = (
    PROJECT_ROOT / "config" / "sleeves" / "mar_l01_long_f111_short_v1.json"
)
SEED_PATH = PROJECT_ROOT / "config" / "l01_4h_research_seed.json"
RISK_LIMITS_PATH = PROJECT_ROOT / "core" / "risk" / "limits.py"

RULES: tuple[str, ...] = ("ema_adx_trend", "range_compression_volume_thrust")
SIDES: tuple[str, ...] = ("LONG", "SHORT")

# Fixed stamp so a second append of the same rows cannot drift the digest.
PAPER_OVERRIDE_AT = "2026-10-16T05:00:00+00:00"
PAPER_OVERRIDE_BY = "operator"
PAPER_OVERRIDE_REASON = (
    "Brian YES 2026-10-16: paper sleeve only. Live stays off. "
    "Frozen dataclass params and the catalog 4h/4h clock. No re-optimisation."
)

# SGP1 f111/bl8 census plus a Bybit cross-check, captured 2026-10-16 09:27 GST.
# 17 of the 96 paper symbols were Closed. Only the exact status ``Closed`` drops
# a symbol. The other 79 stay eligible.
CLOSED_REASON = "exchange status Closed (SGP1 and Bybit 09:27 GST)"
EXCHANGE_STATUS_BY_SYMBOL: dict[str, str] = {
    symbol: "Closed"
    for symbol in (
        "AERGOUSDT",
        "AKROUSDT",
        "BLZUSDT",
        "EOSUSDT",
        "FETUSDT",
        "FLMUSDT",
        "FTMUSDT",
        "LINAUSDT",
        "LUNAUSDT",
        "MATICUSDT",
        "REEFUSDT",
        "RNDRUSDT",
        "SXPUSDT",
        "TOMOUSDT",
        "TONUSDT",
        "UNFIUSDT",
        "UXLINKUSDT",
    )
}


def book_sha256(raw: bytes) -> str:
    """SHA-256 hex of approval-book bytes. Same method as the 8-char prefixes."""
    return hashlib.sha256(raw).hexdigest()


def sgp1_paper_universe() -> list[str]:
    """The 96 symbols the SGP1 paper worker already scans for F111 and L01.

    Both sleeve configs carry the same list. A drift between them is a stop,
    not a reason to pick one quietly.
    """
    f111 = json.loads(F111_UNIVERSE_PATH.read_text(encoding="utf-8"))["universe"]
    l01 = json.loads(L01_UNIVERSE_PATH.read_text(encoding="utf-8"))["universe"]
    if f111 != l01:
        raise ValueError("F111 and L01 paper universes differ; refusing to pick one")
    if len(f111) != 96 or len(set(f111)) != 96:
        raise ValueError("SGP1 paper universe must be 96 unique symbols")
    return list(f111)


def frozen_clock(family: str) -> str:
    """Catalog clock ``signal/trend``. Both of these rules are ``4h/4h``.

    ``ema_adx_trend`` is also pinned to 4h for both sides in
    ``scripts/validate_strategy.py`` ``STRATEGY_TIMEFRAME_BY_SIDE``.
    ``range_compression_volume_thrust`` is the hypothesis
    ``range_compression_volume_thrust@4h/4h`` in ``firm/research_catalog.py``.
    """
    clock = CLOCK_BY_FAMILY[family]
    if clock != "4h/4h":
        raise ValueError(f"{family} clock drifted from 4h/4h to {clock}")
    return clock


def frozen_timeframe(family: str) -> str:
    """The approval-book clock is the signal leg of ``4h/4h``."""
    signal, trend = frozen_clock(family).split("/")
    if signal != trend or signal != "4h":
        raise ValueError(f"{family} is not a square 4h clock")
    return signal


def frozen_params(family: str) -> dict[str, Any]:
    """Dataclass defaults. ``side`` stays in the book key, not in params.

    ``ema_adx_trend`` defaults live on ``EmaAdxParams`` (``min_adx`` 20 matches
    the catalog freeze ``ema_adx_trend@4h/4h@frozen_adx``). The per-symbol
    walk-forward rows in the book are rejected optimisations and are not reused.

    ``range_compression_volume_thrust`` defaults live on
    ``RangeCompressionVolumeThrustParams``. ``research/validate.py`` searches
    only ``compress_pct: [0.30]`` and ``thrust_mult: [1.5]``, which are those
    defaults.
    """
    if family == "ema_adx_trend":
        params = EmaAdxParams()
        strategy_min = EmaAdxTrendStrategy().min_bars
    elif family == "range_compression_volume_thrust":
        params = RangeCompressionVolumeThrustParams()
        strategy_min = RangeCompressionVolumeThrustStrategy().min_bars
    else:
        raise KeyError(family)
    out: dict[str, Any] = {}
    for item in fields(params):
        if item.name == "side":
            continue
        out[item.name] = getattr(params, item.name)
    # Touch the strategy so a default-param drift that changes warmup is visible
    # to the feature check below. The number is not written into the book.
    if strategy_min < 1:
        raise ValueError(f"{family} min_bars must be positive")
    return out


def required_complete_bars() -> int:
    """4h bars both rules need before a signal is possible.

    EMA+ADX warmup is ``max(ema_slow + 10, adx_period + 40)`` (60 at the
    defaults). Compression thrust needs ``compress_lookback + 2`` (102).
    """
    ema = EmaAdxTrendStrategy().min_bars
    thrust = RangeCompressionVolumeThrustStrategy().min_bars
    return max(ema, thrust)


def feature_exclusions(symbols: list[str]) -> dict[str, str]:
    """Symbols whose stored 4h tape cannot feed these rules.

    ``config/l01_4h_research_seed.json`` is the checked-in 4h history for this
    universe (complete bar counts, not a new download). A symbol missing from
    that seed, or shorter than ``required_complete_bars``, is excluded.
    """
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))["records"]
    need = required_complete_bars()
    reasons: dict[str, str] = {}
    for symbol in symbols:
        record = seed.get(symbol)
        if not isinstance(record, dict):
            reasons[symbol] = (
                "missing data: no 4h history in config/l01_4h_research_seed.json"
            )
            continue
        bars = record.get("complete_bars")
        if not isinstance(bars, int) or bars < need:
            reasons[symbol] = (
                f"missing features: 4h complete_bars {bars} < {need} "
                "required by ema_adx_trend and range_compression_volume_thrust"
            )
    return reasons


def closed_exclusions(symbols: list[str], statuses: Mapping[str, str]) -> dict[str, str]:
    """Drop a symbol only when its exchange status is exactly ``Closed``.

    Other statuses (not listed, mismatch, PreLaunch) are not relabelled as
    Closed. An empty map adds no exclusions.
    """
    reasons: dict[str, str] = {}
    for symbol in symbols:
        status = statuses.get(symbol)
        if status == "Closed":
            reasons[symbol] = CLOSED_REASON
    return reasons


def exclusion_reasons(symbols: list[str]) -> dict[str, str]:
    """Closed census first, then 4h history gaps on the symbols that remain."""
    closed = closed_exclusions(symbols, EXCHANGE_STATUS_BY_SYMBOL)
    reasons = feature_exclusions([symbol for symbol in symbols if symbol not in closed])
    reasons.update(closed)
    return reasons


def existing_combinations(book: Mapping[str, Any]) -> set[tuple[str, str, str, str]]:
    """``(strategy, symbol, side, timeframe)`` already present.

    A 1h row does not occupy the 4h key. The original ema walks stored both
    clocks, and only the matching clock is skipped.
    """
    found: set[tuple[str, str, str, str]] = set()
    for key, record in book.items():
        parsed = parse_approval_key(key)
        if parsed is None:
            continue
        strategy, symbol, side = parsed
        parts = str(key).split(":")
        timeframe = parts[3] if len(parts) >= 4 else ""
        if not timeframe and isinstance(record, dict):
            timeframe = str(record.get("timeframe") or "")
        found.add((strategy, symbol, side, timeframe))
    return found


def sleeve_record(family: str) -> dict[str, Any]:
    """One paper-only row. ``approved`` is false. Live ``build_plan`` skips it."""
    return {
        "approved": False,
        "paper_override": True,
        "paper_override_at": PAPER_OVERRIDE_AT,
        "paper_override_by": PAPER_OVERRIDE_BY,
        "paper_override_reason": PAPER_OVERRIDE_REASON,
        "timeframe": frozen_timeframe(family),
        "strategy": family,
        "params": frozen_params(family),
        "activation_mode": "unrestricted",
        "blocked_regimes": [],
        "regime_activation_filter": [],
        "live_authorized": False,
    }


def plan_sleeves(
    book: Mapping[str, Any],
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Decide adds, skips, and exclusions. Does not write.

    Skip a row only when that rule+symbol+side+timeframe is already in the
    book. A 1h ema row does not block the 4h paper sleeve. Excluded symbols
    are not added on either side.
    """
    universe = symbols if symbols is not None else sgp1_paper_universe()
    present = existing_combinations(book)
    excluded = exclusion_reasons(universe)
    added: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    for symbol in universe:
        if symbol in excluded:
            excluded_rows.append({"symbol": symbol, "reason": excluded[symbol]})
            continue
        for family in RULES:
            record = sleeve_record(family)
            timeframe = str(record["timeframe"])
            for side in SIDES:
                key = approval_record_key(family, symbol, side, timeframe)
                if (family, symbol, side, timeframe) in present or key in book:
                    skipped.append(
                        {
                            "strategy": family,
                            "symbol": symbol,
                            "side": side,
                            "timeframe": timeframe,
                            "reason": "rule+symbol+side+timeframe already in the book",
                        }
                    )
                    continue
                added[key] = record
    return {
        "added": added,
        "skipped": skipped,
        "excluded": excluded_rows,
        "universe": len(universe),
    }


def splice_records(raw: bytes, records: dict[str, dict[str, Any]]) -> bytes:
    """Append ``records`` after the last existing row.

    Two endings are valid. The deployed SGP1 book ends in ``}\\n}\\n`` (root
    brace plus a trailing newline). The older catalog ended in ``\\n}`` with
    no byte after the root brace. In both cases every byte through the last
    record's closing brace stays, a comma is inserted, and the new keys
    follow. An empty ``records`` returns ``raw`` unchanged.
    """
    if not records:
        return raw
    if raw.endswith(b"}\n}\n"):
        prefix, closer = raw[:-3], b"\n}\n"
    elif raw.endswith(b"\n}"):
        prefix, closer = raw[:-2], b"\n}"
    else:
        raise ValueError(
            "approval book must end with a root brace so rows can be appended "
            "without rewriting existing rows"
        )
    blob = json.dumps(records, indent=2)
    if not (blob.startswith("{\n") and blob.endswith("\n}")):
        raise ValueError("json.dumps did not produce an object we can splice")
    inner = blob[2:-2].encode("utf-8")
    return prefix + b",\n" + inner + closer


def append_sleeves(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    """Plan against ``raw`` and splice the adds. Idempotent once applied."""
    book = json.loads(raw)
    if not isinstance(book, dict):
        raise ValueError("approval book must be a JSON object")
    decision = plan_sleeves(book)
    updated = splice_records(raw, decision["added"])
    parsed = json.loads(updated)
    # Old keys keep their parsed values. A splice that corrupted one fails here
    # before anything is written.
    for key, value in book.items():
        if parsed.get(key) != value:
            raise ValueError(f"append changed existing row {key}")
    for key, value in decision["added"].items():
        if parsed.get(key) != value:
            raise ValueError(f"appended row {key} did not round-trip")
        if value.get("approved") is True:
            raise ValueError(f"{key} must not be approved")
    return updated, decision


# Approved survivor. Its timeframe is the 1h leg of a square 1h/1h clock.
# CLOCK_BY_FAMILY still says 4h/4h for this family; that is not the row Brian
# named. Params are copied from this record, not from DojiStarParams defaults.
DOJI_FAMILY = "doji_star_reversal"
DOJI_SOURCE_KEY = "doji_star_reversal:SOLUSDT:SHORT:1h"
DOJI_TIMEFRAME = "1h"
DOJI_PAPER_OVERRIDE_AT = "2026-10-16T05:39:00+00:00"
DOJI_PAPER_OVERRIDE_REASON = (
    "Brian YES 2026-10-16 09:39 GST: paper sleeve only. Live stays off. "
    "Clock and params copied from doji_star_reversal:SOLUSDT:SHORT:1h. "
    "No re-optimisation."
)


def approved_doji_source(book: Mapping[str, Any]) -> dict[str, Any]:
    """The approved SOLUSDT SHORT 1h row. Callers must not rewrite it."""
    record = book.get(DOJI_SOURCE_KEY)
    if not isinstance(record, dict):
        raise ValueError(f"{DOJI_SOURCE_KEY} is missing from the approval book")
    if record.get("approved") is not True:
        raise ValueError(f"{DOJI_SOURCE_KEY} is no longer approved")
    if str(record.get("timeframe") or "") != DOJI_TIMEFRAME:
        raise ValueError(f"{DOJI_SOURCE_KEY} timeframe drifted from {DOJI_TIMEFRAME}")
    params = record.get("params")
    if not isinstance(params, dict) or not params:
        raise ValueError(f"{DOJI_SOURCE_KEY} has no params to freeze")
    return record


def approved_doji_params(book: Mapping[str, Any]) -> dict[str, Any]:
    """Param dict from the approved row, key order preserved.

    ``DojiStarParams`` defaults are take-profit 0.04 and stop 0.02.
    The approved row is take-profit 0.05 and stop 0.03, with ``run_bars`` 3.
    ``max_body_frac`` is absent on the row, so it is not added here.
    """
    params = approved_doji_source(book)["params"]
    return dict(params)


def doji_sleeve_record(params: Mapping[str, Any]) -> dict[str, Any]:
    """One paper-only doji row. ``approved`` is false. Live plan skips it."""
    return {
        "approved": False,
        "paper_override": True,
        "paper_override_at": DOJI_PAPER_OVERRIDE_AT,
        "paper_override_by": PAPER_OVERRIDE_BY,
        "paper_override_reason": DOJI_PAPER_OVERRIDE_REASON,
        "timeframe": DOJI_TIMEFRAME,
        "strategy": DOJI_FAMILY,
        "params": dict(params),
        "activation_mode": "unrestricted",
        "blocked_regimes": [],
        "regime_activation_filter": [],
        "live_authorized": False,
    }


def plan_doji_sleeves(
    book: Mapping[str, Any],
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """1h doji paper sleeves for the 79 tradable symbols.

    Skip a symbol+side when ``doji_star_reversal`` at 1h is already in the
    book. The approved SOLUSDT SHORT row is one of those skips. Closed symbols
    are not added. A 4h doji row does not block the 1h sleeve.
    """
    universe = symbols if symbols is not None else sgp1_paper_universe()
    present = existing_combinations(book)
    excluded = exclusion_reasons(universe)
    params = approved_doji_params(book)
    record = doji_sleeve_record(params)
    added: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    for symbol in universe:
        if symbol in excluded:
            excluded_rows.append({"symbol": symbol, "reason": excluded[symbol]})
            continue
        for side in SIDES:
            key = approval_record_key(DOJI_FAMILY, symbol, side, DOJI_TIMEFRAME)
            if (DOJI_FAMILY, symbol, side, DOJI_TIMEFRAME) in present or key in book:
                skipped.append(
                    {
                        "strategy": DOJI_FAMILY,
                        "symbol": symbol,
                        "side": side,
                        "timeframe": DOJI_TIMEFRAME,
                        "reason": "rule+symbol+side+timeframe already in the book",
                    }
                )
                continue
            added[key] = record
    return {
        "added": added,
        "skipped": skipped,
        "excluded": excluded_rows,
        "universe": len(universe),
        "params": params,
    }


def append_doji_sleeves(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    """Splice doji paper rows. Idempotent once applied. Does not touch ema rows."""
    book = json.loads(raw)
    if not isinstance(book, dict):
        raise ValueError("approval book must be a JSON object")
    source = approved_doji_source(book)
    decision = plan_doji_sleeves(book)
    updated = splice_records(raw, decision["added"])
    parsed = json.loads(updated)
    for key, value in book.items():
        if parsed.get(key) != value:
            raise ValueError(f"append changed existing row {key}")
    if parsed.get(DOJI_SOURCE_KEY) != source:
        raise ValueError(f"{DOJI_SOURCE_KEY} must stay byte-identical")
    for key, value in decision["added"].items():
        if parsed.get(key) != value:
            raise ValueError(f"appended row {key} did not round-trip")
        if value.get("approved") is True or value.get("live_authorized") is True:
            raise ValueError(f"{key} must not be approved or live")
    return updated, decision


def apply_doji_to_path(path: Path = BOOK_PATH) -> dict[str, Any]:
    """Splice doji paper sleeves onto ``path``. Returns a summary."""
    before = path.read_bytes()
    after, decision = append_doji_sleeves(before)
    if after != before:
        path.write_bytes(after)
    added = decision["added"]
    parsed_after = json.loads(path.read_bytes())
    summary = {
        "path": str(path),
        "old_sha256": book_sha256(before),
        "new_sha256": book_sha256(path.read_bytes()),
        "sleeves_added": len(added),
        "rows_before": sum(1 for key in json.loads(before) if parse_approval_key(key) is not None),
        "rows_after": sum(1 for key in parsed_after if parse_approval_key(key) is not None),
        "approved_after": sum(
            1
            for key, value in parsed_after.items()
            if parse_approval_key(key) is not None
            and isinstance(value, dict)
            and value.get("approved") is True
        ),
        "skipped": decision["skipped"],
        "excluded": decision["excluded"],
        "params": decision["params"],
        "unchanged": after == before,
    }
    summary["risk_limits_sha256"] = book_sha256(RISK_LIMITS_PATH.read_bytes())
    return summary


def catalog_clock_ok() -> None:
    """Fail if the hypothesis card for the thrust rule is no longer 4h/4h."""
    thrust = [
        row
        for row in RESEARCH_HYPOTHESES
        if row.get("family") == "range_compression_volume_thrust"
        and row.get("id") == "range_compression_volume_thrust@4h/4h"
    ]
    if len(thrust) != 1 or thrust[0].get("clock") != "4h/4h":
        raise ValueError("range_compression_volume_thrust@4h/4h card drifted")
    frozen_clock("ema_adx_trend")
    frozen_clock("range_compression_volume_thrust")


def apply_to_path(path: Path = BOOK_PATH) -> dict[str, Any]:
    """Splice ``path`` in place when there is something to add. Returns a summary."""
    catalog_clock_ok()
    before = path.read_bytes()
    after, decision = append_sleeves(before)
    if after != before:
        path.write_bytes(after)
    added = decision["added"]
    summary = {
        "path": str(path),
        "old_sha256": book_sha256(before),
        "new_sha256": book_sha256(path.read_bytes()),
        "sleeves_added": len(added),
        "rows_before": sum(
            1 for key in json.loads(before) if parse_approval_key(key) is not None
        ),
        "rows_after": sum(
            1
            for key in json.loads(path.read_bytes())
            if parse_approval_key(key) is not None
        ),
        "skipped": decision["skipped"],
        "excluded": decision["excluded"],
        "unchanged": after == before,
    }
    summary["risk_limits_sha256"] = book_sha256(RISK_LIMITS_PATH.read_bytes())
    return summary


# Brian YES 2026-10-16 09:48 GST. Fourteen C1/C2 paper rows, append-only.
# The results artifact's row keys are batch, rule, side, clock, token, and
# the sealed metrics. There is no params field (the schema sets
# additionalProperties false). Clocks below are those result rows.
# Params are the HEAD dataclass defaults — the same freeze already written
# on the C1 thrust paper rows — not a per-symbol walk-forward pick.
C1C2_PAPER_OVERRIDE_AT = "2026-10-16T05:48:00+00:00"
C1C2_PAPER_OVERRIDE_REASON = (
    "Brian YES 2026-10-16 09:48 GST: paper sleeve only. Live stays off. "
    "Clock is the C1/C2 results row. Params are the HEAD dataclass defaults; "
    "the results JSON has no params field. No re-optimisation."
)
# (strategy, symbol, side, timeframe). Timeframe is the JSON clock.
C1C2_ROWS: tuple[tuple[str, str, str, str], ...] = (
    ("monday_range_sweep_reversal", "XLMUSDT", "SHORT", "4h"),
    ("monday_range_sweep_reversal", "DYDXUSDT", "SHORT", "4h"),
    ("monday_range_sweep_reversal", "ICPUSDT", "SHORT", "4h"),
    ("monday_range_sweep_reversal", "DOGEUSDT", "SHORT", "4h"),
    ("monday_range_sweep_reversal", "ATOMUSDT", "SHORT", "4h"),
    ("week_open_reclaim", "XLMUSDT", "SHORT", "4h"),
    ("week_open_reclaim", "ATOMUSDT", "SHORT", "4h"),
    ("week_open_reclaim", "LINKUSDT", "SHORT", "4h"),
    ("double_top_neckline_break", "ADAUSDT", "SHORT", "1h"),
    ("double_top_neckline_break", "CHZUSDT", "SHORT", "1h"),
    ("double_top_neckline_break", "XLMUSDT", "SHORT", "1h"),
    ("double_top_neckline_break", "LINKUSDT", "SHORT", "1h"),
    ("fib_extension_break", "UNIUSDT", "SHORT", "4h"),
    ("range_compression_volume_thrust", "FILUSDT", "SHORT", "4h"),
)
_C1C2_PARAM_CLASS = {
    "monday_range_sweep_reversal": MondayRangeSweepReversalParams,
    "week_open_reclaim": WeekOpenReclaimParams,
    "double_top_neckline_break": DoubleTopNecklineBreakParams,
    "fib_extension_break": FibExtensionBreakParams,
    "range_compression_volume_thrust": RangeCompressionVolumeThrustParams,
}
# Outside the 96-symbol SGP1 list. Included only when the engine can plan them.
C1C2_OUTSIDE_UNIVERSE = frozenset({"UNIUSDT", "FILUSDT"})


def c1c2_default_params(family: str) -> dict[str, Any]:
    """Dataclass defaults except ``side``. Thrust matches ``frozen_params``.

    The C1/C2 results file does not carry a params object. Omitted fields
    would stay at these defaults inside ``_named_strategy`` anyway.
    """
    if family == "range_compression_volume_thrust":
        return frozen_params(family)
    params_cls = _C1C2_PARAM_CLASS.get(family)
    if params_cls is None:
        raise KeyError(family)
    params = params_cls()
    out: dict[str, Any] = {}
    for item in fields(params):
        if item.name == "side":
            continue
        out[item.name] = getattr(params, item.name)
    return out


def outside_universe_block(symbol: str) -> str | None:
    """Why ``build_plan`` would drop this symbol, or None when it can plan it.

    Paper ``build_plan`` walks ``paper_override_records``. It does not consult
    the SGP1 96-list. ``_entry_from_record`` emits a row when the family is
    registered and the record has a timeframe. ``KNOWN_INVALID_SYMBOLS`` is
    not applied on that path; a symbol on that denylist is still refused here
    so a bad ticker is not appended.
    """
    from config.universe import KNOWN_INVALID_SYMBOLS

    if symbol in KNOWN_INVALID_SYMBOLS:
        return f"{symbol} is in KNOWN_INVALID_SYMBOLS"
    return None


def c1c2_sleeve_record(family: str, timeframe: str, params: Mapping[str, Any]) -> dict[str, Any]:
    """One paper-only C1/C2 row. ``approved`` is false. Live plan skips it."""
    return {
        "approved": False,
        "paper_override": True,
        "paper_override_at": C1C2_PAPER_OVERRIDE_AT,
        "paper_override_by": PAPER_OVERRIDE_BY,
        "paper_override_reason": C1C2_PAPER_OVERRIDE_REASON,
        "timeframe": timeframe,
        "strategy": family,
        "params": dict(params),
        "activation_mode": "unrestricted",
        "blocked_regimes": [],
        "regime_activation_filter": [],
        "live_authorized": False,
    }


def plan_c1c2_sleeves(book: Mapping[str, Any]) -> dict[str, Any]:
    """The fourteen named rows. Skip a key that already exists.

    A family with no registered module is skipped, not coded. UNIUSDT and
    FILUSDT are outside the 96-list and are added only when
    ``outside_universe_block`` is empty.
    """
    from core.strategy.registry import get_strategy

    present = existing_combinations(book)
    universe = set(sgp1_paper_universe())
    added: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, str]] = []
    params_by_family: dict[str, dict[str, Any]] = {}
    for family, symbol, side, timeframe in C1C2_ROWS:
        identity = {
            "strategy": family,
            "symbol": symbol,
            "side": side,
            "timeframe": timeframe,
        }
        try:
            get_strategy(family)
        except KeyError:
            skipped.append({**identity, "reason": f"no strategy module registered for {family}"})
            continue
        if symbol not in universe:
            block = outside_universe_block(symbol)
            if block:
                skipped.append({**identity, "reason": block})
                continue
        key = approval_record_key(family, symbol, side, timeframe)
        if (family, symbol, side, timeframe) in present or key in book:
            skipped.append(
                {**identity, "reason": "rule+symbol+side+timeframe already in the book"}
            )
            continue
        if family not in params_by_family:
            params_by_family[family] = c1c2_default_params(family)
        added[key] = c1c2_sleeve_record(family, timeframe, params_by_family[family])
    return {
        "added": added,
        "skipped": skipped,
        "params": params_by_family,
    }


def append_c1c2_sleeves(raw: bytes) -> tuple[bytes, dict[str, Any]]:
    """Splice the C1/C2 paper rows. Idempotent once applied."""
    book = json.loads(raw)
    if not isinstance(book, dict):
        raise ValueError("approval book must be a JSON object")
    decision = plan_c1c2_sleeves(book)
    updated = splice_records(raw, decision["added"])
    parsed = json.loads(updated)
    for key, value in book.items():
        if parsed.get(key) != value:
            raise ValueError(f"append changed existing row {key}")
    for key, value in decision["added"].items():
        if parsed.get(key) != value:
            raise ValueError(f"appended row {key} did not round-trip")
        if value.get("approved") is True or value.get("live_authorized") is True:
            raise ValueError(f"{key} must not be approved or live")
    return updated, decision


def apply_c1c2_to_path(path: Path = BOOK_PATH) -> dict[str, Any]:
    """Splice the C1/C2 paper sleeves onto ``path``. Returns a summary."""
    before = path.read_bytes()
    after, decision = append_c1c2_sleeves(before)
    if after != before:
        path.write_bytes(after)
    parsed_after = json.loads(path.read_bytes())
    summary = {
        "path": str(path),
        "old_sha256": book_sha256(before),
        "new_sha256": book_sha256(path.read_bytes()),
        "sleeves_added": len(decision["added"]),
        "rows_before": sum(1 for key in json.loads(before) if parse_approval_key(key) is not None),
        "rows_after": sum(1 for key in parsed_after if parse_approval_key(key) is not None),
        "approved_after": sum(
            1
            for key, value in parsed_after.items()
            if parse_approval_key(key) is not None
            and isinstance(value, dict)
            and value.get("approved") is True
        ),
        "added": sorted(decision["added"]),
        "skipped": decision["skipped"],
        "params": decision["params"],
        "unchanged": after == before,
    }
    summary["risk_limits_sha256"] = book_sha256(RISK_LIMITS_PATH.read_bytes())
    return summary
