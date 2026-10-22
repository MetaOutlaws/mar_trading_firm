#!/usr/bin/env python3
"""Same-token carry simulator.

The rules and numbers come from protocol_constants.py and PROTOCOL.md.
This module does not tune them. A minute is processed in this order:

1. Pay funding that belongs to a position opened on an earlier minute.
2. Liquidate at the mark open if isolated margin is through maintenance.
3. Fill a discretionary order that was signalled `delay` minutes ago.
4. On the last minute, flatten anything still open at the close.
5. Mark equity and, from that known close, signal the later fill.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from protocol_constants import (
    BASIS_FLOOR,
    DRAWDOWN_ENTRY_STOP,
    INITIAL_MARGIN,
    LIQUIDATION_EXTRA_PENALTY,
    MAINTENANCE_MARGIN,
    MAX_GROSS_EXPOSURE,
    MAX_POSITIONS,
    POSITION_NOTIONAL_CAP,
    RISK_CEILING,
    SERIES_END_EXCLUSIVE_MS,
    STARTING_EQUITY_USDT,
    TRAILING_SETTLEMENTS,
)


@dataclass
class SymbolBook:
    name: str
    spot_o: np.ndarray
    spot_c: np.ndarray
    perp_o: np.ndarray
    perp_c: np.ndarray
    mark_o: np.ndarray
    mark_c: np.ndarray
    fund_flag: np.ndarray
    fund_rate: np.ndarray
    step: float
    min_qty: float
    # Filled by prepare(). Known at minute i, including a settlement at i.
    r3: np.ndarray = field(default=None)
    mean3: np.ndarray = field(default=None)
    known: np.ndarray = field(default=None)


@dataclass
class Cost:
    spot_fee: float
    perp_fee: float
    slippage: float
    hurdle: float


def prepare(book: SymbolBook) -> None:
    """Trailing funding already known at each minute, including a print at that minute."""
    n = len(book.spot_c)
    idx = np.flatnonzero(book.fund_flag)
    known = np.searchsorted(idx, np.arange(n), side="right").astype(np.int32)
    r3 = np.full(n, np.nan)
    mean3 = np.full(n, np.nan)
    if len(idx):
        rates = book.fund_rate[idx]
        last = known - 1
        valid = last >= 0
        r3[valid] = rates[last[valid]]
        valid3 = last >= TRAILING_SETTLEMENTS - 1
        latest = last[valid3]
        mean3[valid3] = (rates[latest] + rates[latest - 1] + rates[latest - 2]) / 3.0
    book.r3 = r3
    book.mean3 = mean3
    book.known = known


def _lots(qty: float, step: float) -> int:
    if qty <= 0 or step <= 0:
        return 0
    return int(math.floor(qty / step + 1e-9))


def _finite_bar(book: SymbolBook, i: int, use_close: bool) -> bool:
    if use_close:
        vals = (book.spot_c[i], book.perp_c[i], book.mark_c[i])
    else:
        vals = (book.spot_o[i], book.perp_o[i], book.mark_o[i])
    return all(math.isfinite(float(v)) and float(v) > 0 for v in vals)


class CarryAccount:
    def __init__(self, books: list[SymbolBook], cost: Cost, delay: int, passive: bool):
        self.books = books
        self.cost = cost
        self.delay = delay
        self.passive = passive
        self.n = len(books[0].spot_c)
        self.cash = STARTING_EQUITY_USDT
        self.peak = STARTING_EQUITY_USDT
        self.max_dd = 0.0
        self.year_max_dd: dict[int, float] = {}
        self.equity_at: dict[int, float] = {}
        self.trades: list[dict] = []
        self.blocked = {
            "in_position": 0,
            "inflight": 0,
            "drawdown": 0,
            "cash_or_size": 0,
            "risk": 0,
            "missing": 0,
            "gross_cap": 0,
            "position_cap": 0,
        }
        self.funding_total = 0.0
        self.fees_total = 0.0
        self.slippage_total = 0.0
        self.penalty_total = 0.0
        self.minutes_in_market = 0
        self.gross_sum = 0.0
        self.positions: dict[str, dict] = {}
        self._enter_at: dict[int, list] = {}
        self._exit_at: dict[int, list] = {}
        self._inflight_entry: set[str] = set()
        self._inflight_exit: set[str] = set()

    def run(self, timestamps: np.ndarray, year_ends: dict[int, int]) -> dict:
        if len(timestamps) != self.n:
            raise ValueError("timestamp length does not match the books")
        if int(timestamps[0]) < 0 or int(timestamps[-1]) >= SERIES_END_EXCLUSIVE_MS:
            raise ValueError("clock is outside 2022–2025")
        year_of = _year_index(timestamps, year_ends)
        year_peak = STARTING_EQUITY_USDT
        current_year = int(year_of[0]) if len(year_of) else 0
        self.year_max_dd[current_year] = 0.0
        for i in range(self.n):
            year = int(year_of[i])
            if year != current_year:
                current_year = year
                marked = self._equity(i, use_close=False)
                year_peak = marked
                self.year_max_dd.setdefault(year, 0.0)
            self._funding(i)
            self._liquidate(i)
            self._fill_delayed(i)
            self._remember(i)
            if i == self.n - 1:
                self._flatten_end(i)
            equity = self._equity(i, use_close=True)
            if equity > self.peak:
                self.peak = equity
            if self.peak > 0:
                dd = (self.peak - equity) / self.peak
                if dd > self.max_dd:
                    self.max_dd = dd
            if equity > year_peak:
                year_peak = equity
            if year_peak > 0:
                ydd = (year_peak - equity) / year_peak
                if ydd > self.year_max_dd.get(year, 0.0):
                    self.year_max_dd[year] = ydd
            self._exposure(i, equity)
            if year in year_ends and i == year_ends[year]:
                self.equity_at[year] = equity
            self._decide(i, equity)
        return self._pack()

    def _equity(self, i: int, use_close: bool) -> float:
        equity = self.cash
        for book in self.books:
            pos = self.positions.get(book.name)
            equity += 0.0 if pos is None else pos["isolated"]
            if pos is None:
                continue
            if use_close:
                spot = float(book.spot_c[i])
                mark = float(book.mark_c[i])
            else:
                spot = float(book.spot_o[i])
                mark = float(book.mark_o[i])
            if not (math.isfinite(spot) and math.isfinite(mark)):
                spot = pos["last_spot"]
                mark = pos["last_mark"]
            equity += pos["qty"] * spot
            equity += pos["qty"] * (pos["perp_fill"] - mark)
        return equity

    def _remember(self, i: int) -> None:
        for book in self.books:
            pos = self.positions.get(book.name)
            if pos is None:
                continue
            spot = float(book.spot_c[i])
            mark = float(book.mark_c[i])
            if math.isfinite(spot) and spot > 0:
                pos["last_spot"] = spot
            if math.isfinite(mark) and mark > 0:
                pos["last_mark"] = mark

    def _exposure(self, i: int, equity: float) -> None:
        gross = 0.0
        in_mkt = False
        for book in self.books:
            pos = self.positions.get(book.name)
            if pos is None:
                continue
            in_mkt = True
            spot = float(book.spot_c[i])
            mark = float(book.mark_c[i])
            if not math.isfinite(spot):
                spot = pos["last_spot"]
            if not math.isfinite(mark):
                mark = pos["last_mark"]
            gross += pos["qty"] * spot + pos["qty"] * mark
        if in_mkt:
            self.minutes_in_market += 1
        if equity > 0:
            self.gross_sum += gross / equity

    def _funding(self, i: int) -> None:
        for book in self.books:
            pos = self.positions.get(book.name)
            if pos is None or not book.fund_flag[i]:
                continue
            if pos["entry_i"] >= i:
                continue
            mark = float(book.mark_o[i])
            if not math.isfinite(mark) or mark <= 0:
                continue
            cashflow = float(book.fund_rate[i]) * pos["qty"] * mark
            pos["isolated"] += cashflow
            pos["funding"] += cashflow
            self.funding_total += cashflow

    def _liquidate(self, i: int) -> None:
        for book in self.books:
            pos = self.positions.get(book.name)
            if pos is None:
                continue
            if not _finite_bar(book, i, use_close=False):
                self._flatten(book, i, reason="missing_data", at_close=False, previous=True)
                continue
            mark = float(book.mark_o[i])
            margin = pos["isolated"] + pos["qty"] * (pos["perp_fill"] - mark)
            maintenance = MAINTENANCE_MARGIN * pos["qty"] * mark
            if margin <= maintenance:
                self._flatten(book, i, reason="liquidation", at_close=False, previous=False)

    def _fill_delayed(self, i: int) -> None:
        for name in list(self._exit_at.get(i, ())):
            book = self._book(name)
            self._inflight_exit.discard(name)
            if name in self.positions:
                self._flatten(book, i, reason="signal", at_close=False, previous=False)
        for item in self._enter_at.get(i, ()):
            name = item["name"]
            self._inflight_entry.discard(name)
            if name in self.positions:
                self.blocked["in_position"] += 1
                continue
            self._open(self._book(name), i, item["lots"])

    def _flatten_end(self, i: int) -> None:
        for book in self.books:
            if book.name in self.positions:
                self._flatten(book, i, reason="end_of_sample", at_close=True, previous=False)

    def _decide(self, i: int, equity: float) -> None:
        fill_i = i + self.delay
        if fill_i >= self.n:
            return
        dd_block = equity <= (1.0 - DRAWDOWN_ENTRY_STOP) * self.peak
        open_positions = len(self.positions)
        for book in self.books:
            held = book.name in self.positions
            econ_exit = self._exit_econ(book, i)
            econ_enter = self._enter_econ(book, i)
            if held and econ_exit and book.name not in self._inflight_exit:
                self._exit_at.setdefault(fill_i, []).append(book.name)
                self._inflight_exit.add(book.name)
            if not econ_enter:
                continue
            if held or book.name in self._inflight_entry:
                self.blocked["in_position" if held else "inflight"] += 1
                continue
            if dd_block:
                self.blocked["drawdown"] += 1
                continue
            if open_positions + len(self._inflight_entry) >= MAX_POSITIONS:
                self.blocked["position_cap"] += 1
                continue
            if not _finite_bar(book, i, use_close=True):
                self.blocked["missing"] += 1
                continue
            lots = self._size_lots(book, i, equity)
            if lots <= 0:
                continue
            self._enter_at.setdefault(fill_i, []).append({"name": book.name, "lots": lots})
            self._inflight_entry.add(book.name)

    def _enter_econ(self, book: SymbolBook, i: int) -> bool:
        if self.passive:
            return True
        if int(book.known[i]) < TRAILING_SETTLEMENTS:
            return False
        if not (book.mean3[i] > self.cost.hurdle and book.r3[i] > 0):
            return False
        basis = _basis(book, i)
        return basis is not None and basis > BASIS_FLOOR

    def _exit_econ(self, book: SymbolBook, i: int) -> bool:
        if self.passive:
            return False
        if int(book.known[i]) < TRAILING_SETTLEMENTS:
            return True
        if not (book.r3[i] > 0 and book.mean3[i] > self.cost.hurdle):
            return True
        basis = _basis(book, i)
        return basis is None or basis <= BASIS_FLOOR

    def _size_lots(self, book: SymbolBook, i: int, equity: float) -> int:
        slip = self.cost.slippage
        spot_q = float(book.spot_c[i]) * (1.0 + slip)
        perp_q = float(book.perp_c[i]) * (1.0 - slip)
        if spot_q <= 0 or perp_q <= 0 or equity <= 0:
            self.blocked["cash_or_size"] += 1
            return 0
        unit = spot_q * (1.0 + self.cost.spot_fee) + perp_q * self.cost.perp_fee + perp_q * INITIAL_MARGIN
        if unit <= 0:
            self.blocked["cash_or_size"] += 1
            return 0
        gross_now = self._gross_notional(i)
        room = MAX_GROSS_EXPOSURE * equity - gross_now
        leg_cap = POSITION_NOTIONAL_CAP * equity
        raw_qty = min(leg_cap / spot_q, self.cash / unit, room / (spot_q + perp_q))
        lots = _lots(raw_qty, book.step)
        if lots <= 0 or lots * book.step < book.min_qty - 1e-12:
            self.blocked["cash_or_size"] += 1
            return 0
        risk_limited = False
        while lots > 0:
            qty = lots * book.step
            if self._risk_loss(book, i, qty, equity) <= RISK_CEILING * equity + 1e-8:
                break
            risk_limited = True
            lots -= 1
        if lots <= 0 or lots * book.step < book.min_qty - 1e-12:
            self.blocked["risk" if risk_limited else "cash_or_size"] += 1
            return 0
        if risk_limited:
            # Shrinking to fit the ceiling is the rule, not a blocked entry.
            pass
        if gross_now + lots * book.step * (spot_q + perp_q) > MAX_GROSS_EXPOSURE * equity + 1e-6:
            self.blocked["gross_cap"] += 1
            return 0
        return lots

    def _gross_notional(self, i: int) -> float:
        gross = 0.0
        for book in self.books:
            pos = self.positions.get(book.name)
            if pos is None:
                continue
            gross += pos["qty"] * (float(book.spot_c[i]) + float(book.mark_c[i]))
        return gross

    def _risk_loss(self, book: SymbolBook, i: int, qty: float, equity: float) -> float:
        del equity
        slip = self.cost.slippage
        spot_c = float(book.spot_c[i])
        perp_c = float(book.perp_c[i])
        quote_spot = spot_c * (1.0 + slip)
        quote_perp = perp_c * (1.0 - slip)
        fee_entry = qty * quote_spot * self.cost.spot_fee + qty * quote_perp * self.cost.perp_fee
        fee_exit = qty * spot_c * (1.0 - slip) * self.cost.spot_fee + qty * perp_c * (1.0 + slip) * self.cost.perp_fee
        slip_entry = qty * spot_c * slip + qty * perp_c * slip
        slip_exit = slip_entry
        basis_loss = qty * spot_c * abs(BASIS_FLOOR)
        return basis_loss + fee_entry + fee_exit + slip_entry + slip_exit

    def _open(self, book: SymbolBook, i: int, lots: int) -> None:
        if not _finite_bar(book, i, use_close=False):
            self.blocked["missing"] += 1
            return
        slip = self.cost.slippage
        while lots > 0:
            qty = lots * book.step
            spot_fill = float(book.spot_o[i]) * (1.0 + slip)
            perp_fill = float(book.perp_o[i]) * (1.0 - slip)
            fee_s = qty * spot_fill * self.cost.spot_fee
            fee_p = qty * perp_fill * self.cost.perp_fee
            isolated = qty * perp_fill * INITIAL_MARGIN
            need = qty * spot_fill + fee_s + fee_p + isolated
            if need <= self.cash + 1e-6:
                break
            lots -= 1
        if lots <= 0 or lots * book.step < book.min_qty - 1e-12:
            self.blocked["cash_or_size"] += 1
            return
        qty = lots * book.step
        spot_quote = float(book.spot_o[i])
        perp_quote = float(book.perp_o[i])
        spot_fill = spot_quote * (1.0 + slip)
        perp_fill = perp_quote * (1.0 - slip)
        fee_s = qty * spot_fill * self.cost.spot_fee
        fee_p = qty * perp_fill * self.cost.perp_fee
        isolated = qty * perp_fill * INITIAL_MARGIN
        equity_before = self._equity(i, use_close=False)
        self.cash -= qty * spot_fill + fee_s + fee_p + isolated
        slip_cost = qty * (spot_fill - spot_quote) + qty * (perp_quote - perp_fill)
        self.fees_total += fee_s + fee_p
        self.slippage_total += slip_cost
        self.positions[book.name] = {
            "qty": qty,
            "entry_i": i,
            "spot_fill": spot_fill,
            "perp_fill": perp_fill,
            "spot_quote": spot_quote,
            "perp_quote": perp_quote,
            "isolated": isolated,
            "funding": 0.0,
            "fees": fee_s + fee_p,
            "slippage": slip_cost,
            "penalty": 0.0,
            "equity_at_entry": equity_before,
            "last_spot": spot_quote,
            "last_mark": float(book.mark_o[i]),
        }

    def _flatten(self, book: SymbolBook, i: int, reason: str, at_close: bool, previous: bool) -> None:
        pos = self.positions.get(book.name)
        if pos is None:
            return
        src = i - 1 if previous else i
        if src < 0:
            src = i
        # A missing bar is flattened at the previous minute's close, the last
        # price that actually printed. The missing open is not a price.
        if at_close or previous:
            spot_quote = float(book.spot_c[src])
            perp_quote = float(book.perp_c[src])
            mark_quote = float(book.mark_c[src])
        else:
            spot_quote = float(book.spot_o[src])
            perp_quote = float(book.perp_o[src])
            mark_quote = float(book.mark_o[src])
        if not all(math.isfinite(v) and v > 0 for v in (spot_quote, perp_quote, mark_quote)):
            spot_quote = pos["last_spot"]
            perp_quote = pos["last_mark"]
            mark_quote = pos["last_mark"]
        slip = self.cost.slippage
        qty = pos["qty"]
        if reason == "liquidation":
            cover_quote = mark_quote
            cover = mark_quote * (1.0 + slip + LIQUIDATION_EXTRA_PENALTY)
            penalty = qty * mark_quote * LIQUIDATION_EXTRA_PENALTY
        else:
            cover_quote = perp_quote
            cover = perp_quote * (1.0 + slip)
            penalty = 0.0
        spot_exit = spot_quote * (1.0 - slip)
        fee_s = qty * spot_exit * self.cost.spot_fee
        fee_p = qty * cover * self.cost.perp_fee
        # Release margin and realise the short. Spot sale returns the coin to cash.
        self.cash += pos["isolated"]
        self.cash += qty * (pos["perp_fill"] - cover) - fee_p
        self.cash += qty * spot_exit - fee_s
        # Model slippage only. The liquidation penalty is its own bucket.
        slip_exit = qty * (spot_quote - spot_exit) + qty * max(cover - cover_quote - (penalty / qty if qty else 0.0), 0.0)
        pos["fees"] += fee_s + fee_p
        pos["slippage"] += slip_exit
        pos["penalty"] += penalty
        self.fees_total += fee_s + fee_p
        self.slippage_total += slip_exit
        self.penalty_total += penalty
        spot_price = qty * (spot_quote - pos["spot_quote"])
        perp_price = qty * (pos["perp_quote"] - cover_quote)
        net = spot_price + perp_price + pos["funding"] - pos["fees"] - pos["slippage"] - pos["penalty"]
        self.trades.append(
            {
                "symbol": book.name,
                "entry_i": pos["entry_i"],
                "exit_i": src,
                "qty": qty,
                "pnl": net,
                "funding": pos["funding"],
                "fees": pos["fees"],
                "slippage": pos["slippage"],
                "penalty": pos["penalty"],
                "spot_price": spot_price,
                "perp_price": perp_price,
                "reason": reason,
                "equity_at_entry": pos["equity_at_entry"],
            }
        )
        del self.positions[book.name]
        self._inflight_exit.discard(book.name)

    def _book(self, name: str) -> SymbolBook:
        for book in self.books:
            if book.name == name:
                return book
        raise KeyError(name)

    def _pack(self) -> dict:
        equity = self.cash
        for pos in self.positions.values():
            equity += pos["isolated"]
        return {
            "ending_equity": equity,
            "ending_cash": self.cash,
            "open_positions": list(self.positions),
            "max_drawdown": self.max_dd,
            "year_max_drawdown": dict(self.year_max_dd),
            "equity_at_year_end": dict(self.equity_at),
            "trades": self.trades,
            "blocked": dict(self.blocked),
            "funding": self.funding_total,
            "fees": self.fees_total,
            "slippage": self.slippage_total,
            "penalty": self.penalty_total,
            "minutes_in_market": self.minutes_in_market,
            "mean_gross_exposure": self.gross_sum / self.n if self.n else 0.0,
            "minutes": self.n,
        }


def _basis(book: SymbolBook, i: int):
    spot = float(book.spot_c[i])
    perp = float(book.perp_c[i])
    if not (math.isfinite(spot) and math.isfinite(perp) and spot > 0):
        return None
    return (perp - spot) / spot


def _year_index(timestamps: np.ndarray, year_ends: dict[int, int]) -> np.ndarray:
    years = np.empty(len(timestamps), dtype=np.int16)
    # year_ends maps year -> last index. Walk forward.
    bounds = sorted(year_ends.items())
    start = 0
    for year, end in bounds:
        years[start : end + 1] = year
        start = end + 1
    if start < len(years):
        years[start:] = bounds[-1][0] if bounds else 0
    return years


def roll_funding(book: SymbolBook, minutes: int) -> SymbolBook:
    """Return a copy whose funding clock is rotated. Prices stay put."""
    rolled = SymbolBook(
        name=book.name,
        spot_o=book.spot_o,
        spot_c=book.spot_c,
        perp_o=book.perp_o,
        perp_c=book.perp_c,
        mark_o=book.mark_o,
        mark_c=book.mark_c,
        fund_flag=np.roll(book.fund_flag, minutes),
        fund_rate=np.roll(book.fund_rate, minutes),
        step=book.step,
        min_qty=book.min_qty,
    )
    prepare(rolled)
    return rolled
