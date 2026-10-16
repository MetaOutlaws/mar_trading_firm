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
from core.strategy.range_compression_volume_thrust import (
    RangeCompressionVolumeThrustParams,
    RangeCompressionVolumeThrustStrategy,
)
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

# Bybit instruments-info from this environment returned HTTP 403 (CloudFront
# country block) on 2026-10-16. The operator note that 79 of 96 symbols were
# Trading is not stored as a per-symbol census in the repo. Leaving this empty
# refuses to invent a Closed list. Pass a real status map to ``closed_exclusions``
# when one exists; only the exact status ``Closed`` is an exclusion.
EXCHANGE_STATUS_BY_SYMBOL: dict[str, str] = {}


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
            reasons[symbol] = "exchange status Closed"
    return reasons


def exclusion_reasons(symbols: list[str]) -> dict[str, str]:
    """Feature gaps plus a Closed census, when one was supplied."""
    reasons = feature_exclusions(symbols)
    for symbol, reason in closed_exclusions(symbols, EXCHANGE_STATUS_BY_SYMBOL).items():
        reasons.setdefault(symbol, reason)
    return reasons


def existing_combinations(book: Mapping[str, Any]) -> set[tuple[str, str, str]]:
    """``(strategy, symbol, side)`` already present, any clock."""
    found: set[tuple[str, str, str]] = set()
    for key in book:
        parsed = parse_approval_key(key)
        if parsed is None:
            continue
        found.add(parsed)
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

    A token+rule+side that already exists is skipped even when the stored
    clock differs. Excluded symbols are not added on either side.
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
            for side in SIDES:
                if (family, symbol, side) in present:
                    skipped.append(
                        {
                            "strategy": family,
                            "symbol": symbol,
                            "side": side,
                            "reason": "token+rule+side already in the book",
                        }
                    )
                    continue
                key = approval_record_key(family, symbol, side, record["timeframe"])
                if key in book:
                    skipped.append(
                        {
                            "strategy": family,
                            "symbol": symbol,
                            "side": side,
                            "reason": "book key already exists",
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

    ``raw`` must be a JSON object ending in ``\\n}`` with no trailing newline
    after the root brace (the shape of ``config/approved_strategies.json``).
    Every byte before that final newline stays, then a comma, then the new
    keys. An empty ``records`` returns ``raw`` unchanged.
    """
    if not records:
        return raw
    if not raw.endswith(b"\n}"):
        raise ValueError(
            "approval book must end with a newline and a root brace so rows "
            "can be appended without rewriting existing rows"
        )
    blob = json.dumps(records, indent=2)
    if not (blob.startswith("{\n") and blob.endswith("\n}")):
        raise ValueError("json.dumps did not produce an object we can splice")
    inner = blob[2:-2].encode("utf-8")
    return raw[:-2] + b",\n" + inner + b"\n}"


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
