"""Open-position mark and P&L are live ticker fields, not ledger columns."""

from __future__ import annotations

import pytest

from api.app import _unrealised_fields


def test_long_is_in_the_money_when_mark_is_above_entry() -> None:
    fields = _unrealised_fields("LONG", 0.4, 2472.35, 988.94, 2500.0)
    assert fields["in_the_money"] is True
    assert fields["mark_price"] == pytest.approx(2500.0)
    assert fields["unrealised_pnl"] == pytest.approx((2500.0 - 2472.35) * 0.4)
    assert fields["return_pct"] > 0


def test_short_is_in_the_money_when_mark_is_below_entry() -> None:
    fields = _unrealised_fields("SHORT", 1.0, 100.0, 100.0, 90.0)
    assert fields["in_the_money"] is True
    assert fields["unrealised_pnl"] == pytest.approx(10.0)
    assert fields["return_pct"] == pytest.approx(10.0)


def test_long_is_out_when_mark_is_below_entry() -> None:
    fields = _unrealised_fields("LONG", 0.4, 2472.35, 988.94, 2460.0)
    assert fields["in_the_money"] is False
    assert fields["unrealised_pnl"] < 0


def test_missing_mark_leaves_pnl_blank() -> None:
    fields = _unrealised_fields("LONG", 0.4, 2472.35, 988.94, None)
    assert fields["mark_price"] is None
    assert fields["unrealised_pnl"] is None
    assert fields["in_the_money"] is None
