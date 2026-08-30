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
        record = self.approvals.get(f"{symbol}:{side.upper()}")
        return bool(record and record.get("approved") is True)

    @property
    def approved_pairs(self) -> list[tuple[str, str]]:
        """All (symbol, side) pairs cleared for trading."""
        out: list[tuple[str, str]] = []
        for key, record in sorted(self.approvals.items()):
            if record.get("approved") is True and ":" in key:
                symbol, side = key.split(":", 1)
                out.append((symbol, side))
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
        "%d approved to trade.",
        len(universe.monitored_symbols),
        len(universe.long_params),
        len(universe.short_params),
        len(universe.approved_pairs),
    )
    return universe
