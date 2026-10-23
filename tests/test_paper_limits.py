"""Paper concurrent-position cap matches the in-effect SGP1 edit.

At b00c4f73, PAPER_LIMITS was `RiskLimits()` and therefore inherited
max_concurrent_positions=5 and the original gross default of 0.50
(e0127da). The SGP1 paper host runs with the concurrent cap set to 15.
Gross exposure is a later paper-only override: PAPER_LIMITS passes 0.80
explicitly. The dataclass default stays 0.50, so a bare RiskLimits() and
testnet do not pick up the paper cap. INITIAL_LIVE_LIMITS still overrides
that field to 0.20. Every other default stays at its b00c4f73 value.
"""

from __future__ import annotations

import core.risk.limits as limits_module
from config.settings import get_settings
from core.risk.limits import INITIAL_LIVE_LIMITS, PAPER_LIMITS, RiskLimits

# Original dataclass snapshot. Gross exposure is 0.50, the value in the
# first version of limits.py (e0127da), restored after a977119 had raised
# the shared default to 0.80.
_BARE_DEFAULTS = {
    "max_concurrent_positions": 5,
    "max_daily_trades": 20,
    "max_positions_per_sector": 2,
    "max_positions_per_symbol": 1,
    "max_position_pct": 0.10,
    "max_total_exposure_pct": 0.50,
    "max_risk_per_trade_pct": 0.01,
    "min_notional_usdt": 5.0,
    "max_leverage": 1.0,
    "daily_loss_limit_pct": 0.03,
    "max_drawdown_pct": 0.15,
    "max_consecutive_losses": 6,
    "require_stop_loss": True,
    "min_stop_distance_pct": 0.005,
    "max_stop_distance_pct": 0.15,
}

# Name kept so the live snapshot below still reads as the b00c4f73 book.
_PAPER_AT_B00C4F73 = _BARE_DEFAULTS

# INITIAL_LIVE_LIMITS at b00c4f73. Only the fields passed to that constructor
# differ from the dataclass defaults; the rest are the same snapshot.
_LIVE_AT_B00C4F73 = {
    **_PAPER_AT_B00C4F73,
    "max_concurrent_positions": 3,
    "max_daily_trades": 10,
    "max_position_pct": 0.05,
    "max_total_exposure_pct": 0.20,
    "max_risk_per_trade_pct": 0.005,
    "daily_loss_limit_pct": 0.02,
    "max_drawdown_pct": 0.10,
}


def test_paper_max_concurrent_positions_matches_sgp1():
    assert PAPER_LIMITS.max_concurrent_positions == 15


def test_risklimits_default_max_concurrent_positions_is_unchanged():
    """The dataclass default stays 5. Gross exposure is the original 0.50."""
    assert RiskLimits().max_concurrent_positions == 5
    assert RiskLimits().to_dict() == _BARE_DEFAULTS


def test_bare_risk_limits_use_the_conservative_gross_cap():
    """Bare RiskLimits() is the e0127da default, not the paper 0.80 cap."""
    assert RiskLimits().max_total_exposure_pct == 0.50


def test_paper_factory_gross_cap_is_explicitly_0_80():
    """PAPER_LIMITS is the only factory that sets the wider gross cap."""
    assert PAPER_LIMITS.max_total_exposure_pct == 0.80
    assert PAPER_LIMITS.max_concurrent_positions == 15


def test_live_gross_cap_stays_0_20():
    assert INITIAL_LIVE_LIMITS.max_total_exposure_pct == 0.20


def test_live_build_engine_keeps_the_live_gross_cap(monkeypatch, firm_db) -> None:
    """Live keeps INITIAL_LIVE_LIMITS, including the 0.20 gross cap."""
    from core.execution import bybit as bybit_mod
    from core.execution import engine as engine_mod

    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("GO_LIVE_CONFIRMED", "I_ACCEPT_THE_RISK")
    monkeypatch.setenv("BYBIT_LIVE_API_KEY", "test-key")
    monkeypatch.setenv("BYBIT_LIVE_API_SECRET", "test-secret")
    get_settings.cache_clear()
    monkeypatch.setattr(
        engine_mod,
        "build_plan",
        lambda require_approval=False, candidates=None: engine_mod.TradingPlan(),
    )

    class SpyBroker:
        def __init__(self, mode=None) -> None:
            self.mode = mode

        def bind_book_guard(self, guard) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(bybit_mod, "BybitBroker", SpyBroker)
    engine = engine_mod.build_engine(starting_equity=10_000.0)
    try:
        assert engine.risk.limits is INITIAL_LIVE_LIMITS
        assert engine.risk.limits.max_total_exposure_pct == 0.20
    finally:
        engine.close()


def test_other_paper_limit_fields_match_b00c4f73():
    """Paper overrides only the concurrent cap and the gross cap."""
    expected = dict(_BARE_DEFAULTS)
    expected["max_concurrent_positions"] = 15
    expected["max_total_exposure_pct"] = 0.80
    assert PAPER_LIMITS.to_dict() == expected


def test_live_limits_are_unchanged():
    """Every live limits object on the module still matches b00c4f73."""
    live_names = sorted(
        name
        for name in vars(limits_module)
        if name.isupper() and "LIVE" in name and not name.startswith("_")
    )
    assert live_names == ["INITIAL_LIVE_LIMITS"]
    assert INITIAL_LIVE_LIMITS.to_dict() == _LIVE_AT_B00C4F73
    assert INITIAL_LIVE_LIMITS.max_concurrent_positions == 3


def test_paper_build_engine_uses_the_paper_factory(tmp_path, monkeypatch, firm_db) -> None:
    """The paper engine takes PAPER_LIMITS, which carries the explicit 0.80."""
    from core.execution import engine as engine_mod

    monkeypatch.setenv("TRADING_MODE", "paper")
    get_settings.cache_clear()
    monkeypatch.setattr(engine_mod, "PAPER_CASH_PATH", tmp_path / "paper_cash.json")
    monkeypatch.setattr(
        engine_mod,
        "build_plan",
        lambda require_approval=False, candidates=None: engine_mod.TradingPlan(),
    )

    class SpyBroker:
        def __init__(self, starting_equity=10_000.0, costs=None, data_source=None, cash_store=None):
            self.mode = "paper"

        def hydrate(self, positions) -> None:
            return None

        def bind_book_guard(self, guard) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(engine_mod, "PaperBroker", SpyBroker)
    engine = engine_mod.build_engine(starting_equity=10_000.0)
    try:
        assert engine.risk.limits is PAPER_LIMITS
        assert engine.risk.limits.max_total_exposure_pct == 0.80
    finally:
        engine.close()


def test_testnet_build_engine_uses_the_conservative_gross_cap(
    tmp_path, monkeypatch, firm_db
) -> None:
    """Testnet takes the dataclass gross default, not PAPER_LIMITS' 0.80.

    The concurrent cap stays at the value testnet already shared with paper.
    Every other field is the bare default.
    """
    from core.execution import bybit as bybit_mod
    from core.execution import engine as engine_mod

    monkeypatch.setenv("TRADING_MODE", "testnet")
    monkeypatch.setenv("BYBIT_TESTNET_API_KEY", "test-key")
    monkeypatch.setenv("BYBIT_TESTNET_API_SECRET", "test-secret")
    get_settings.cache_clear()
    monkeypatch.setattr(
        engine_mod,
        "build_plan",
        lambda require_approval=False, candidates=None: engine_mod.TradingPlan(),
    )

    class SpyBroker:
        def __init__(self, mode=None) -> None:
            self.mode = mode

        def bind_book_guard(self, guard) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr(bybit_mod, "BybitBroker", SpyBroker)
    engine = engine_mod.build_engine(starting_equity=10_000.0)
    try:
        assert engine.risk.limits.max_total_exposure_pct == RiskLimits().max_total_exposure_pct
        assert engine.risk.limits.max_total_exposure_pct == 0.50
        expected = RiskLimits(
            max_concurrent_positions=PAPER_LIMITS.max_concurrent_positions,
        ).to_dict()
        assert engine.risk.limits.to_dict() == expected
        assert engine.risk.limits.max_concurrent_positions == 15
    finally:
        engine.close()
