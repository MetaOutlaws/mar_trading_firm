"""Synthetic checks for the frozen carry rules. No historical sample is read."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carry_sim import CarryAccount, Cost, SymbolBook, prepare
from protocol_constants import (
    BASIS_FLOOR,
    LIQUIDATION_EXTRA_PENALTY,
    SERIES_END_EXCLUSIVE_MS,
    STARTING_EQUITY_USDT,
)


def book(n, price=100.0, step=0.001, rate=0.001, flags=None, spot=None, perp=None, mark=None):
    spot_c = np.full(n, price) if spot is None else np.array(spot, dtype=float)
    perp_c = np.full(n, price) if perp is None else np.array(perp, dtype=float)
    mark_c = np.full(n, price) if mark is None else np.array(mark, dtype=float)
    # Opens equal closes unless a test overwrites them after construction.
    flag = np.zeros(n, dtype=bool) if flags is None else np.array(flags, dtype=bool)
    rates = np.zeros(n)
    rates[flag] = rate
    out = SymbolBook(
        name="BTCUSDT",
        spot_o=spot_c.copy(),
        spot_c=spot_c,
        perp_o=perp_c.copy(),
        perp_c=perp_c,
        mark_o=mark_c.copy(),
        mark_c=mark_c,
        fund_flag=flag,
        fund_rate=rates,
        step=step,
        min_qty=step,
    )
    prepare(out)
    return out


def run(books, fee=0.0, slip=0.0, hurdle=0.0, delay=1, passive=False, start=0):
    for item in books:
        if item.r3 is None:
            prepare(item)
    acct = CarryAccount(books, Cost(fee, fee, slip, hurdle), delay, passive)
    n = books[0].spot_c.shape[0]
    ts = (start + np.arange(n) * 60_000).astype(np.int64)
    if np.any(ts >= SERIES_END_EXCLUSIVE_MS):
        raise AssertionError("test built a 2026 timestamp")
    return acct.run(ts, {2022: n - 1}), acct


class CarryTests(unittest.TestCase):
    def test_flat_round_trip_conserves_cash(self):
        flags = np.zeros(12, dtype=bool)
        flags[:3] = True
        data = book(12, flags=flags, rate=0.01)
        result, _acct = run([data], hurdle=0.0)
        self.assertEqual(result["open_positions"], [])
        self.assertEqual(len(result["trades"]), 1)
        self.assertAlmostEqual(result["ending_equity"], STARTING_EQUITY_USDT, places=6)
        self.assertAlmostEqual(result["trades"][0]["pnl"], 0.0, places=6)

    def test_both_leg_fees_leave_cash(self):
        flags = np.zeros(8, dtype=bool)
        flags[:3] = True
        data = book(8, flags=flags, rate=0.01)
        result, _acct = run([data], fee=0.001, hurdle=0.0)
        trade = result["trades"][0]
        self.assertGreater(trade["fees"], 0)
        self.assertAlmostEqual(result["ending_equity"], STARTING_EQUITY_USDT + trade["pnl"], places=6)
        self.assertLess(result["ending_equity"], STARTING_EQUITY_USDT)

    def test_positive_funding_pays_the_short_and_respects_the_boundary(self):
        flags = np.zeros(8, dtype=bool)
        flags[0] = flags[1] = flags[2] = flags[4] = True
        data = book(8, flags=flags, rate=0.01)
        result, _acct = run([data], hurdle=0.0)
        trade = result["trades"][0]
        # Decision at minute 2, fill at minute 3. The print at minute 4 is the
        # first one strictly after entry. Prints at 0, 1 and 2 are not held.
        self.assertEqual(trade["entry_i"], 3)
        self.assertAlmostEqual(trade["funding"], 0.01 * trade["qty"] * 100.0, places=6)
        self.assertGreater(result["ending_equity"], STARTING_EQUITY_USDT)

    def test_future_settlement_cannot_create_the_entry(self):
        flags = np.zeros(8, dtype=bool)
        flags[4] = True
        data = book(8, flags=flags, rate=0.05)
        result, _acct = run([data], hurdle=0.0)
        self.assertEqual(result["trades"], [])
        self.assertAlmostEqual(result["ending_equity"], STARTING_EQUITY_USDT, places=6)

    def test_quantity_is_a_whole_step(self):
        flags = np.zeros(6, dtype=bool)
        flags[:3] = True
        data = book(6, price=50_000.0, step=0.001, flags=flags, rate=0.01)
        result, _acct = run([data], hurdle=0.0)
        qty = result["trades"][0]["qty"]
        self.assertGreater(qty, 0)
        self.assertAlmostEqual(qty / 0.001, round(qty / 0.001), places=6)

    def test_delay_fills_the_later_open(self):
        flags = np.zeros(12, dtype=bool)
        flags[:3] = True
        data = book(12, flags=flags, rate=0.01)
        data.spot_o[7] = 110.0
        data.perp_o[7] = 110.0
        data.mark_o[7] = 110.0
        result, _acct = run([data], hurdle=0.0, delay=5)
        self.assertEqual(result["trades"][0]["entry_i"], 7)
        self.assertAlmostEqual(result["trades"][0]["spot_price"] + result["trades"][0]["perp_price"], 0.0, places=6)
        self.assertNotAlmostEqual(result["trades"][0]["spot_price"], 0.0, places=6)

    def test_basis_dislocation_blocks_entry(self):
        flags = np.zeros(6, dtype=bool)
        flags[:3] = True
        # Perp is 2% cheap versus spot, through the -1% floor.
        data = book(6, flags=flags, rate=0.01, spot=np.full(6, 100.0), perp=np.full(6, 98.0), mark=np.full(6, 98.0))
        result, _acct = run([data], hurdle=0.0)
        self.assertEqual(result["trades"], [])

    def test_gap_flattens_without_inventing_the_missing_open(self):
        flags = np.zeros(8, dtype=bool)
        flags[:3] = True
        data = book(8, flags=flags, rate=0.01)
        data.spot_o[5] = np.nan
        data.spot_c[5] = np.nan
        data.perp_o[5] = np.nan
        data.perp_c[5] = np.nan
        data.mark_o[5] = np.nan
        data.mark_c[5] = np.nan
        # A later print that must not be used as the gap fill.
        data.spot_c[6] = 50.0
        data.perp_c[6] = 50.0
        result, _acct = run([data], hurdle=0.0)
        trade = result["trades"][0]
        self.assertEqual(trade["reason"], "missing_data")
        self.assertEqual(trade["exit_i"], 4)
        self.assertAlmostEqual(trade["spot_price"], 0.0, places=6)

    def test_mark_spike_liquidates_the_isolated_short(self):
        flags = np.zeros(8, dtype=bool)
        flags[:3] = True
        data = book(8, flags=flags, rate=0.0001)
        # Entry fills at minute 3. Minute 4's mark is a triple. That wipes 1x margin.
        for arr in (data.mark_o, data.mark_c):
            arr[4] = 400.0
        result, _acct = run([data], hurdle=0.0)
        trade = result["trades"][0]
        self.assertEqual(trade["reason"], "liquidation")
        self.assertGreater(trade["penalty"], 0)
        self.assertAlmostEqual(
            trade["penalty"],
            trade["qty"] * 400.0 * LIQUIDATION_EXTRA_PENALTY,
            places=6,
        )
        self.assertEqual(result["open_positions"], [])

    def test_negative_latest_funding_exits(self):
        flags = np.zeros(10, dtype=bool)
        flags[0] = flags[1] = flags[2] = flags[6] = True
        data = book(10, flags=flags, rate=0.01)
        data.fund_rate[6] = -0.01
        prepare(data)
        result, _acct = run([data], hurdle=0.0)
        self.assertEqual(len(result["trades"]), 1)
        self.assertLess(result["trades"][0]["exit_i"], 9)

    def test_cash_account_does_nothing(self):
        # No settlements and a hurdle above zero: selective mode stays in cash.
        data = book(5, flags=np.zeros(5, dtype=bool))
        result, _acct = run([data], hurdle=1.0)
        self.assertEqual(result["trades"], [])
        self.assertAlmostEqual(result["ending_equity"], STARTING_EQUITY_USDT, places=8)

    def test_refuses_a_2026_clock(self):
        data = book(2, flags=np.array([True, True]))
        acct = CarryAccount([data], Cost(0, 0, 0, 0), 1, True)
        ts = np.array([SERIES_END_EXCLUSIVE_MS - 60_000, SERIES_END_EXCLUSIVE_MS], dtype=np.int64)
        with self.assertRaises(ValueError):
            acct.run(ts, {2026: 1})


if __name__ == "__main__":
    unittest.main(verbosity=2)
