"""
The tradable asset universe and per-asset strategy parameters.

Two distinct concepts, deliberately kept apart:

* **Universe membership** - which symbols the firm watches at all. Broad
  (~100 symbols) because breadth is cheap and feeds the research and sentiment
  employees.
* **Trading approval** - which symbols may actually have orders placed. Narrow,
  and granted *only* by `config/approved_strategies.json`, which is written by
  the research validation pipeline.

The legacy project conflated these: an `enabled=True` flag hand-edited in a
Python file was enough to trade real money. Here the legacy `enabled` flags are
read but explicitly ignored, so an unvalidated strategy cannot reach the market.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

ASSET_PARAMS_PATH = PROJECT_ROOT / "config" / "asset_params.json"
APPROVALS_PATH = PROJECT_ROOT / "config" / "approved_strategies.json"


# ---------------------------------------------------------------------------
# Monitoring universe
# ---------------------------------------------------------------------------
# Symbols watched for market intelligence and research candidate discovery,
# grouped by narrative so the Sentiment and Regime employees can reason about
# sector rotation rather than 100 unrelated tickers.
SECTORS: dict[str, list[str]] = {
    "majors": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT"],
    "layer1": [
        "ADAUSDT", "AVAXUSDT", "DOTUSDT", "NEARUSDT", "APTUSDT", "SUIUSDT",
        "TONUSDT", "TRXUSDT", "ICPUSDT", "ALGOUSDT", "HBARUSDT", "SEIUSDT",
        "TIAUSDT", "INJUSDT", "EGLDUSDT", "XTZUSDT", "MINAUSDT", "KSMUSDT",
    ],
    "layer2": [
        "ARBUSDT", "OPUSDT", "IMXUSDT", "STXUSDT", "STRKUSDT", "MNTUSDT", "CFXUSDT",
    ],
    "defi": [
        "UNIUSDT", "AAVEUSDT", "COMPUSDT", "SNXUSDT", "PENDLEUSDT", "LDOUSDT",
        "DYDXUSDT", "CRVUSDT",
    ],
    "ai": ["RENDERUSDT", "TAOUSDT", "ARKMUSDT", "FETUSDT", "GRTUSDT", "WLDUSDT"],
    "memes": [
        "DOGEUSDT", "1000PEPEUSDT", "1000SHIBUSDT", "1000BONKUSDT",
        "1000FLOKIUSDT", "WIFUSDT", "POPCATUSDT", "TRUMPUSDT",
    ],
    "gaming": ["SANDUSDT", "GALAUSDT", "AXSUSDT", "APEUSDT", "GMTUSDT", "SUPERUSDT"],
    "infra": [
        "LINKUSDT", "FILUSDT", "ARUSDT", "THETAUSDT", "VETUSDT", "IOTAUSDT",
        "RUNEUSDT", "QNTUSDT", "PYTHUSDT", "ONDOUSDT",
    ],
    "emerging": [
        "EIGENUSDT", "ENAUSDT", "JUPUSDT", "MOVEUSDT", "GRASSUSDT", "ORDIUSDT",
    ],
}

# Symbols dropped from the legacy list because they are not valid Bybit linear
# perpetuals. The legacy bot logged repeated symbol errors for these.
KNOWN_INVALID_SYMBOLS = {
    "RAYDIUMUSDT",   # Bybit lists this as RAYUSDT
    "SHIB1000USDT",  # Correct Bybit symbol is 1000SHIBUSDT
    "FLOKIUSDT",     # Correct Bybit symbol is 1000FLOKIUSDT
    "BONKUSDT",      # Correct Bybit symbol is 1000BONKUSDT
    "PEPEUSDT",      # Correct Bybit symbol is 1000PEPEUSDT
    "VirtualUSDT",   # Casing typo in legacy config
    "VIRTUALUSDT",
}

LONG = "LONG"
SHORT = "SHORT"
KNOWN_SIDES = {LONG, SHORT}


def approval_record_key(strategy: str, symbol: str, side: str, timeframe: str | None) -> str:
    """Stable id for one walk-forward: family, pair, side, and candle clock.

    Timeframe belongs in the key. A later 1h Donchian run used to overwrite the
    15m LONG rows because both wrote `donchian_breakout:BTCUSDT:LONG`.
    """
    tf = str(timeframe or "unknown").strip() or "unknown"
    return f"{strategy}:{symbol}:{side.upper()}:{tf}"


def parse_approval_key(key: str) -> tuple[str, str, str] | None:
    """Return `(strategy, symbol, side)` from an approvals-file key.

    Accepted shapes:
    - `SYMBOL:SIDE` — Phase 1 RSI rows
    - `strategy:SYMBOL:SIDE` — family namespaced, clock only in the record
    - `strategy:SYMBOL:SIDE:timeframe` — current; clocks cannot overwrite each other
    """
    if not key or key.startswith("_"):
        return None
    parts = key.split(":")
    if len(parts) == 2:
        symbol, side = parts
        if side.upper() in KNOWN_SIDES:
            return ("rsi_trend", symbol, side.upper())
        return None
    if len(parts) >= 3:
        strategy, symbol, side = parts[0], parts[1], parts[2]
        if side.upper() in KNOWN_SIDES and strategy and symbol:
            return (strategy, symbol, side.upper())
        return None
    return None


def migrate_approval_keys(payload: dict[str, Any]) -> dict[str, Any]:
    """Rewrite 2-part and 3-part keys to include the record's timeframe.

    Leaves metadata (`_generated_at`, …) and already-4-part keys alone. If a
    legacy key and a 4-part key would collide, the 4-part row wins.
    """
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if key.startswith("_") or not isinstance(value, dict):
            out[key] = value
            continue
        parts = key.split(":")
        if len(parts) >= 4:
            out[key] = value
            continue
        parsed = parse_approval_key(key)
        if parsed is None:
            out[key] = value
            continue
        strategy, symbol, side = parsed
        new_key = approval_record_key(strategy, symbol, side, value.get("timeframe"))
        if new_key in out:
            continue
        record = dict(value)
        record.setdefault("strategy", strategy)
        out[new_key] = record
    return out


@dataclass(frozen=True)
class LongParams:
    """LONG entry parameters for one asset."""

    symbol: str
    timeframe: str = "15min"
    rsi_min: float = 30.0
    rsi_max: float = 40.0
    volume_threshold: float = 1.2
    trend_filter: str = "golden_cross"
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.05


@dataclass(frozen=True)
class ShortParams:
    """SHORT entry parameters for one asset."""

    symbol: str
    timeframe: str = "4h"
    rsi_threshold: float = 65.0
    volume_threshold: float = 1.2
    trend_filter: str = "in_uptrend"
    take_profit_pct: float = 0.05
    stop_loss_pct: float = 0.05


@dataclass
class Universe:
    """Asset universe, per-asset parameters, and research trading approvals."""

    long_params: dict[str, LongParams] = field(default_factory=dict)
    short_params: dict[str, ShortParams] = field(default_factory=dict)
    legacy_claims: dict[str, dict[str, Any]] = field(default_factory=dict)
    approvals: dict[str, dict[str, Any]] = field(default_factory=dict)

    # -- membership ---------------------------------------------------------
    @property
    def monitored_symbols(self) -> list[str]:
        """Every symbol the firm watches, deduplicated and sorted."""
        symbols = {s for group in SECTORS.values() for s in group}
        symbols |= set(self.long_params) | set(self.short_params)
        symbols -= KNOWN_INVALID_SYMBOLS
        return sorted(symbols)

    def sector_of(self, symbol: str) -> str:
        """Return the narrative sector for a symbol, or 'other'."""
        for sector, members in SECTORS.items():
            if symbol in members:
                return sector
        return "other"

    # -- parameters ---------------------------------------------------------
    def params_for(self, symbol: str, side: str) -> LongParams | ShortParams | None:
        """Return the parameter set for a symbol/side, or None if absent."""
        if side.upper() == LONG:
            return self.long_params.get(symbol)
        return self.short_params.get(symbol)

    def research_candidates(self, side: str) -> list[str]:
        """Symbols that have parameters defined and are therefore worth testing."""
        source = self.long_params if side.upper() == LONG else self.short_params
        return sorted(s for s in source if s not in KNOWN_INVALID_SYMBOLS)

    # -- trading approval ---------------------------------------------------
    def is_approved(self, symbol: str, side: str) -> bool:
        """Whether research has cleared `symbol`/`side` for order placement.

        This is the only gate that grants trading rights. Legacy `enabled`
        flags have no effect here.
        """
        side_u = side.upper()
        for key, record in self.approvals.items():
            parsed = parse_approval_key(key)
            if parsed is None:
                continue
            _strategy, rec_symbol, rec_side = parsed
            if rec_symbol == symbol and rec_side == side_u and record.get("approved") is True:
                return True
        return False

    def has_paper_override(self, strategy: str, symbol: str, side: str, timeframe: str) -> bool:
        """Operator veto: this exact sleeve may paper-scan while live stays gated."""
        key = approval_record_key(strategy, symbol, side, timeframe)
        rec = self.approvals.get(key)
        return bool(isinstance(rec, dict) and rec.get("paper_override") is True)

    @property
    def paper_override_records(self) -> list[tuple[str, dict[str, Any]]]:
        """Approval rows the operator promoted to paper only."""
        out: list[tuple[str, dict[str, Any]]] = []
        for key, record in sorted(self.approvals.items()):
            if not isinstance(record, dict) or record.get("paper_override") is not True:
                continue
            if parse_approval_key(key) is None:
                continue
            out.append((key, record))
        return out

    @property
    def approved_pairs(self) -> list[tuple[str, str]]:
        """All (symbol, side) pairs cleared for trading."""
        out: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for key, record in sorted(self.approvals.items()):
            if record.get("approved") is not True:
                continue
            parsed = parse_approval_key(key)
            if parsed is None:
                continue
            _strategy, symbol, side = parsed
            pair = (symbol, side)
            if pair not in seen:
                seen.add(pair)
                out.append(pair)
        return out


def _load_approvals() -> dict[str, dict[str, Any]]:
    """Read research approvals. Absent file means nothing is approved."""
    if not APPROVALS_PATH.exists():
        logger.info("No approvals file at %s - no symbol is cleared to trade.", APPROVALS_PATH)
        return {}
    try:
        raw = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        # Fail closed: an unreadable approvals file must not grant trading rights.
        logger.error("Could not read approvals (%s) - treating as no approvals.", exc)
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


@lru_cache(maxsize=1)
def get_universe() -> Universe:
    """Load the universe from `asset_params.json` plus research approvals."""
    universe = Universe(approvals=_load_approvals())

    if not ASSET_PARAMS_PATH.exists():
        logger.warning(
            "No asset params at %s. Run scripts/port_legacy_configs.py.", ASSET_PARAMS_PATH
        )
        return universe

    raw = json.loads(ASSET_PARAMS_PATH.read_text(encoding="utf-8"))

    for symbol, entry in raw.get("long", {}).items():
        if symbol in KNOWN_INVALID_SYMBOLS:
            continue
        params = entry.get("params", {})
        universe.long_params[symbol] = LongParams(
            symbol=symbol,
            timeframe=params.get("timeframe", "15min"),
            rsi_min=float(params.get("rsi_min", 30.0)),
            rsi_max=float(params.get("rsi_max", 40.0)),
            volume_threshold=float(params.get("volume_threshold", 1.2)),
            trend_filter=params.get("trend_filter", "golden_cross"),
            take_profit_pct=float(params.get("take_profit_pct", 0.05)),
            stop_loss_pct=float(params.get("stop_loss_pct", 0.05)),
        )
        if entry.get("legacy_claims"):
            universe.legacy_claims[f"{symbol}:{LONG}"] = entry["legacy_claims"]

    for symbol, entry in raw.get("short", {}).items():
        if symbol in KNOWN_INVALID_SYMBOLS:
            continue
        params = entry.get("params", {})
        universe.short_params[symbol] = ShortParams(
            symbol=symbol,
            timeframe=params.get("timeframe", "4h"),
            rsi_threshold=float(params.get("rsi_threshold", 65.0)),
            volume_threshold=float(params.get("volume_threshold", 1.2)),
            trend_filter=params.get("trend_filter", "in_uptrend"),
            take_profit_pct=float(params.get("take_profit_pct", 0.05)),
            stop_loss_pct=float(params.get("stop_loss_pct", 0.05)),
        )
        if entry.get("legacy_claims"):
            universe.legacy_claims[f"{symbol}:{SHORT}"] = entry["legacy_claims"]

    logger.info(
        "Universe loaded: %d monitored symbols, %d LONG params, %d SHORT params, "
        "%d research-approved, %d operator paper override(s).",
        len(universe.monitored_symbols),
        len(universe.long_params),
        len(universe.short_params),
        len(universe.approved_pairs),
        len(universe.paper_override_records),
    )
    return universe
