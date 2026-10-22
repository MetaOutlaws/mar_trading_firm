"""Frozen same-token carry protocol. Numbers live here so the backtest cannot
quietly redefine them. Hypothesis count is 1. No constant was chosen by
scanning historical strategy profit.

Quantity is sized off the decision minute's close. The delayed open is the
fill only. See PROTOCOL.md.
"""
from __future__ import annotations

# One primary hypothesis: long paid-for spot, short the same linear perpetual.
HYPOTHESIS_COUNT = 1
HYPOTHESIS_ID = "long_spot_short_perp_same_token"

STARTING_EQUITY_USDT = 20_000.0
# Handoff sizing. limits.py still says 5 concurrent positions and was not edited.
MAX_POSITIONS = 15
MAX_LEVERAGE = 1.0
POSITION_NOTIONAL_CAP = 0.10
MAX_GROSS_EXPOSURE = 0.80
RISK_CEILING = 0.01
DRAWDOWN_ENTRY_STOP = 0.70
MAINTENANCE_MARGIN = 0.05
# Isolated initial margin at 1x. Spot coins are not perp collateral.
INITIAL_MARGIN = 1.0 / MAX_LEVERAGE

# Adverse basis in (perp - spot) / spot. Entry requires basis above this.
# Exit when basis is at or below it. Not a searched threshold.
BASIS_FLOOR = -0.01
AMORTIZATION_DAYS = 30
SETTLEMENTS_PER_DAY = 3
AMORTIZATION_SETTLEMENTS = AMORTIZATION_DAYS * SETTLEMENTS_PER_DAY  # 90
TRAILING_SETTLEMENTS = 3

PRIMARY_DELAY_MINUTES = 1
SENSITIVITY_DELAY_MINUTES = 5
LIQUIDATION_EXTRA_PENALTY = 0.0025

# Published non-VIP schedule, labeled because the archive has no fee history.
# Spot taker 10 bp, linear taker 5.5 bp. Slippage is labeled, not measured.
SPOT_TAKER = 0.001
PERP_TAKER = 0.00055

# Desk round trip is 2 * (5.5 bp + 10 bp) = 31 bp per leg, from research/costs.py.
DESK_ROUND_TRIP = 2.0 * (PERP_TAKER + 0.001)

QTY_STEP = {"BTCUSDT": 0.001, "ETHUSDT": 0.01}
MIN_QTY = {"BTCUSDT": 0.001, "ETHUSDT": 0.01}
SYMBOLS = ("BTCUSDT", "ETHUSDT")

# Pair round trip = both legs, entry and exit, fee plus slippage.
# Hurdle = that fraction divided by 90. It is not the sample mean funding rate.
COST_MODELS = {
    "baseline": {"spot_fee": SPOT_TAKER, "perp_fee": PERP_TAKER, "slippage": 0.0001, "role": "primary"},
    "moderate": {"spot_fee": SPOT_TAKER, "perp_fee": PERP_TAKER, "slippage": 0.0005, "role": "primary"},
    "desk_031": {
        "spot_fee": DESK_ROUND_TRIP / 2.0,
        "perp_fee": DESK_ROUND_TRIP / 2.0,
        "slippage": 0.0,
        "role": "primary_desk",
    },
    "severe": {"spot_fee": SPOT_TAKER, "perp_fee": PERP_TAKER, "slippage": 0.001, "role": "stress"},
}

# Research gates copied from research/validate.py ApprovalCriteria. Not loosened.
MIN_CLOSED_TRADES = 30
MIN_PROFIT_FACTOR = 1.15
MIN_EXPECTANCY = 0.0
MAX_DRAWDOWN = 0.25
MIN_PROFITABLE_YEAR_RATIO = 0.50
BOOTSTRAP_DRAWS = 2000
BOOTSTRAP_SEED = 20261022
NULL_SHIFTS = 200
NULL_SHIFT_MIN_DAYS = 7
NULL_SHIFT_MAX_DAYS = 1454
CONCENTRATION_TOKEN = 0.80
CONCENTRATION_YEAR = 0.70

ARCHIVE_SHA256 = "2157ec16fdacc8d27da2c0f81e644b8887d0e395d455453851755a07c79129c4"
SHA256SUMS_SHA256 = "560485b8a73b5dae304329a4d082373e248b9cd687b1e1366d613d7f2b312135"
SERIES_END_EXCLUSIVE_MS = 1767225600000
SERIES_BEGIN_MS = 1640995200000


def pair_round_trip(model: str) -> float:
    """Fraction of one-leg notional paid to enter and exit both legs."""
    spec = COST_MODELS[model]
    return 2.0 * (spec["spot_fee"] + spec["slippage"]) + 2.0 * (spec["perp_fee"] + spec["slippage"])


def funding_hurdle(model: str) -> float:
    return pair_round_trip(model) / AMORTIZATION_SETTLEMENTS
