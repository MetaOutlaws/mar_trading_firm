"""Paper concurrent-position cap matches the in-effect SGP1 edit.

At b00c4f73, PAPER_LIMITS was `RiskLimits()` and therefore inherited
max_concurrent_positions=5. The SGP1 paper host runs with that cap set to 15.
Gross exposure is the one later move: the RiskLimits default, which paper
inherits, is 0.80. INITIAL_LIVE_LIMITS still overrides that field to 0.20.
Every other default stays at its b00c4f73 value.
"""

from __future__ import annotations

import core.risk.limits as limits_module
from core.risk.limits import INITIAL_LIVE_LIMITS, PAPER_LIMITS, RiskLimits

# PAPER_LIMITS at b00c4f73, where the object was an un-overridden RiskLimits().
_PAPER_AT_B00C4F73 = {
    "max_concurrent_positions": 5,
    "max_daily_trades": 20,
    "max_positions_per_sector": 2,
    "max_positions_per_symbol": 1,
    "max_position_pct": 0.10,
    "max_total_exposure_pct": 0.80,
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
    """The dataclass default stays 5. Gross exposure is 0.80; nothing else moved."""
    assert RiskLimits().max_concurrent_positions == 5
    assert RiskLimits().to_dict() == _PAPER_AT_B00C4F73


def test_other_paper_limit_fields_match_b00c4f73():
    expected = dict(_PAPER_AT_B00C4F73)
    expected["max_concurrent_positions"] = 15
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
