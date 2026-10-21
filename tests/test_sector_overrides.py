"""Sector labels for paper-plan symbols that are not in SECTORS.

SECTORS is the engine watch list. The 32 names live in SECTOR_OVERRIDES so
``sector_of`` can name them without enlarging ``monitored_symbols``. The
per-sector cap stays 2. The SHIB denylist is intentionally untouched.
"""

from __future__ import annotations

import json

from config.universe import (
    APPROVALS_PATH,
    SECTORS,
    SECTOR_OVERRIDES,
    get_universe,
    parse_approval_key,
)
from core.execution.f111_paper import _sector
from core.risk.engine import OpenPosition, PortfolioState, RiskEngine, RiskVerdict, TradeIntent
from core.risk.killswitch import KillSwitch
from core.risk.limits import INITIAL_LIVE_LIMITS, PAPER_LIMITS, RiskLimits

# Mukanya 2026-10-21 (brief sha a021945a). Existing labels only.
EXPECTED_SECTOR: dict[str, str] = {
    "1000RATSUSDT": "memes",
    "ARPAUSDT": "infra",
    "ATOMUSDT": "layer1",
    "AUCTIONUSDT": "defi",
    "BCHUSDT": "layer1",
    "BLURUSDT": "gaming",
    "CHZUSDT": "gaming",
    "ETCUSDT": "layer1",
    "FARTCOINUSDT": "memes",
    "HYPEUSDT": "defi",
    "JASMYUSDT": "infra",
    "KNCUSDT": "defi",
    "LPTUSDT": "infra",
    "LTCUSDT": "layer1",
    "LUNA2USDT": "layer1",
    "MASKUSDT": "infra",
    "MOODENGUSDT": "memes",
    "NOTUSDT": "gaming",
    "PENGUUSDT": "memes",
    "PEOPLEUSDT": "memes",
    "PUMPFUNUSDT": "emerging",
    "RAREUSDT": "gaming",
    "SHIB1000USDT": "memes",
    "SPXUSDT": "memes",
    "SUSHIUSDT": "defi",
    "TRBUSDT": "infra",
    "VIRTUALUSDT": "ai",
    "WAVESUSDT": "layer1",
    "XLMUSDT": "layer1",
    "YGGUSDT": "gaming",
    "ZECUSDT": "layer1",
    "ZILUSDT": "layer1",
}

# The 29 are not in the monitored 84. These three already are, via asset params.
ALREADY_MONITORED = frozenset({"BCHUSDT", "LPTUSDT", "XLMUSDT"})

# Watched via asset params, not in the 81-symbol plan, and still unmapped.
ENGINE_ONLY_OTHER = frozenset(
    {
        "DEXEUSDT",
        "FLRUSDT",
        "GLMUSDT",
        "HNTUSDT",
        "KASUSDT",
        "RSRUSDT",
        "XCNUSDT",
    }
)

# Counts across the 81 approval-book symbols after the 32 move.
EXPECTED_PLAN_COUNTS = {
    "ai": 2,
    "defi": 10,
    "emerging": 4,
    "gaming": 10,
    "infra": 9,
    "layer1": 21,
    "layer2": 6,
    "majors": 5,
    "memes": 14,
    "other": 0,
}

# Engine watch list at feat tip a510f1a, before this lookup split. Same set
# and the same 84 names must come back after the overrides are added.
EXPECTED_MONITORED = (
    "1000BONKUSDT",
    "1000FLOKIUSDT",
    "1000PEPEUSDT",
    "1000SHIBUSDT",
    "AAVEUSDT",
    "ADAUSDT",
    "ALGOUSDT",
    "APEUSDT",
    "APTUSDT",
    "ARBUSDT",
    "ARKMUSDT",
    "ARUSDT",
    "AVAXUSDT",
    "AXSUSDT",
    "BCHUSDT",
    "BNBUSDT",
    "BTCUSDT",
    "CFXUSDT",
    "COMPUSDT",
    "CRVUSDT",
    "DEXEUSDT",
    "DOGEUSDT",
    "DOTUSDT",
    "DYDXUSDT",
    "EGLDUSDT",
    "EIGENUSDT",
    "ENAUSDT",
    "ETHUSDT",
    "FETUSDT",
    "FILUSDT",
    "FLRUSDT",
    "GALAUSDT",
    "GLMUSDT",
    "GMTUSDT",
    "GRASSUSDT",
    "GRTUSDT",
    "HBARUSDT",
    "HNTUSDT",
    "ICPUSDT",
    "IMXUSDT",
    "INJUSDT",
    "IOTAUSDT",
    "JUPUSDT",
    "KASUSDT",
    "KSMUSDT",
    "LDOUSDT",
    "LINKUSDT",
    "LPTUSDT",
    "MINAUSDT",
    "MNTUSDT",
    "MOVEUSDT",
    "NEARUSDT",
    "ONDOUSDT",
    "OPUSDT",
    "ORDIUSDT",
    "PENDLEUSDT",
    "POPCATUSDT",
    "PYTHUSDT",
    "QNTUSDT",
    "RENDERUSDT",
    "RSRUSDT",
    "RUNEUSDT",
    "SANDUSDT",
    "SEIUSDT",
    "SNXUSDT",
    "SOLUSDT",
    "STRKUSDT",
    "STXUSDT",
    "SUIUSDT",
    "SUPERUSDT",
    "TAOUSDT",
    "THETAUSDT",
    "TIAUSDT",
    "TONUSDT",
    "TRUMPUSDT",
    "TRXUSDT",
    "UNIUSDT",
    "VETUSDT",
    "WIFUSDT",
    "WLDUSDT",
    "XCNUSDT",
    "XLMUSDT",
    "XRPUSDT",
    "XTZUSDT",
)


def _plan_symbols() -> set[str]:
    """Unique symbols in the approval book. That book is the 81-symbol plan."""
    book = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    symbols: set[str] = set()
    for key in book:
        parsed = parse_approval_key(key)
        if parsed is None:
            continue
        symbols.add(parsed[1])
    return symbols


def _long(symbol: str, sector: str) -> TradeIntent:
    entry = 100.0
    return TradeIntent(
        symbol=symbol,
        side="LONG",
        entry_price=entry,
        stop_price=entry * 0.97,
        take_profit_price=entry * 1.06,
        strategy="rsi_trend",
        score=2.0,
        sector=sector,
    )


def test_each_mapped_symbol_resolves_to_its_sector() -> None:
    universe = get_universe()
    assert SECTOR_OVERRIDES == EXPECTED_SECTOR
    assert len(EXPECTED_SECTOR) == 32
    resolved = {symbol: universe.sector_of(symbol) for symbol in EXPECTED_SECTOR}
    assert resolved == EXPECTED_SECTOR
    # The 1h path calls the same function. A stored pending row is a separate
    # question; a fresh lookup must see the map.
    assert {symbol: _sector(symbol) for symbol in EXPECTED_SECTOR} == EXPECTED_SECTOR
    members = {symbol for group in SECTORS.values() for symbol in group}
    assert set(EXPECTED_SECTOR).isdisjoint(members)
    assert set(EXPECTED_SECTOR.values()) <= set(SECTORS)


def test_no_plan_symbol_resolves_to_other() -> None:
    universe = get_universe()
    plan = _plan_symbols()
    assert len(plan) == 81
    assert set(EXPECTED_SECTOR) <= plan
    still_other = sorted(symbol for symbol in plan if universe.sector_of(symbol) == "other")
    assert still_other == []
    counts: dict[str, int] = {}
    for symbol in plan:
        sector = universe.sector_of(symbol)
        counts[sector] = counts.get(sector, 0) + 1
    assert counts == EXPECTED_PLAN_COUNTS
    assert sum(counts.values()) == 81


def test_max_positions_per_sector_stays_2() -> None:
    assert RiskLimits().max_positions_per_sector == 2
    assert PAPER_LIMITS.max_positions_per_sector == 2
    assert INITIAL_LIVE_LIMITS.max_positions_per_sector == 2


def test_engine_monitored_universe_is_unchanged() -> None:
    universe = get_universe()
    monitored = universe.monitored_symbols
    assert len(monitored) == 84
    assert tuple(monitored) == EXPECTED_MONITORED
    outside = set(EXPECTED_SECTOR) - ALREADY_MONITORED
    assert len(outside) == 29
    assert outside.isdisjoint(monitored)
    assert ALREADY_MONITORED <= set(monitored)
    # The seven engine-only names stay in the watch list and stay unmapped.
    assert ENGINE_ONLY_OTHER <= set(monitored)
    assert all(universe.sector_of(symbol) == "other" for symbol in ENGINE_ONLY_OTHER)
    assert ENGINE_ONLY_OTHER.isdisjoint(_plan_symbols())
    sector_members = {symbol for group in SECTORS.values() for symbol in group}
    assert len(sector_members) == 74


def test_zec_long_is_not_capped_by_a_full_other_bucket(tmp_path) -> None:
    """Oct 20: ZEC long was rejected because 'other' was already 2/2.

    The paper engine stamps ``intent.sector`` from ``sector_of`` and then
    ``RiskEngine`` counts positions in that label. With the map, ZEC is
    layer1, so a full 'other' book does not cap it. A full layer1 book still
    does: the cap itself did not move.
    """
    universe = get_universe()
    assert universe.sector_of("ZECUSDT") == "layer1"
    engine = RiskEngine(
        limits=PAPER_LIMITS,
        kill_switch=KillSwitch(path=tmp_path / "killswitch.json"),
    )
    other_full = PortfolioState(
        equity=10_000.0,
        peak_equity=10_000.0,
        open_positions=[
            OpenPosition("DEXEUSDT", "LONG", 5.0, 100.0, 500.0, sector="other"),
            OpenPosition("FLRUSDT", "LONG", 5.0, 100.0, 500.0, sector="other"),
        ],
    )
    # Same composition as TradingEngine._attempt_entry: sector comes from the lookup.
    zec = _long("ZECUSDT", universe.sector_of("ZECUSDT"))
    decision = engine.evaluate(zec, other_full)
    assert decision.is_approved
    assert not any("sector 'other'" in reason for reason in decision.reasons)

    # The pre-map label is still what the cap rejects. This is the Oct 20 path.
    blocked = engine.evaluate(_long("ZECUSDT", "other"), other_full)
    assert blocked.verdict is RiskVerdict.REJECTED
    assert any("sector 'other'" in reason for reason in blocked.reasons)

    layer1_full = PortfolioState(
        equity=10_000.0,
        peak_equity=10_000.0,
        open_positions=[
            OpenPosition("ADAUSDT", "LONG", 5.0, 100.0, 500.0, sector="layer1"),
            OpenPosition("AVAXUSDT", "LONG", 5.0, 100.0, 500.0, sector="layer1"),
        ],
    )
    crowded = engine.evaluate(zec, layer1_full)
    assert crowded.verdict is RiskVerdict.REJECTED
    assert any("sector 'layer1'" in reason for reason in crowded.reasons)
    assert not any("sector 'other'" in reason for reason in crowded.reasons)
