"""Greedy beta-neutralising entry order. Paper flag, default off.

The deployed sizer (``RiskEngine._size_position``) is side-agnostic: there is
no 0.5x long factor. Long and short with the same stop distance get the same
notional. The Oct 20 replay's 0.5x long was empirical, not this code.

The gross cap is whatever ``RiskLimits.max_total_exposure_pct`` the sizer
already holds. SGP1 paper runs 0.80 since 13:22 GST on 2026-10-22
(#160, ``aa01e948``). These tests still pass 0.50 as a regression and 0.80
as the production cap. Neither value is hardcoded in the orderer.
"""

from __future__ import annotations

import hashlib
import logging
import math
from datetime import date, timedelta

import pandas as pd
import pytest

from config.settings import get_settings
from core.execution.entry_ordering import (
    BTC_SYMBOL,
    BookLeg,
    GbnCandidate,
    SubmitResult,
    book_beta_usdt,
    budgeted_daily_fetch,
    clear_daily_beta_cache,
    entry_ordering_gbn_enabled,
    execute_entry_ordering,
    legs_from_portfolio,
    load_betas,
    ols_beta_to_btc,
)
from core.risk.engine import OpenPosition, PortfolioState, RiskEngine, TradeIntent
from core.risk.killswitch import KillSwitch
from core.risk.limits import PAPER_LIMITS, RiskLimits
from core.strategy.base import SignalSide
from firm.paper_universe_sleeves import RISK_LIMITS_PATH
from core.execution.paper_bar_eval import (
    commit_deferred_paper_entry,
    cycle_paper_bar,
    sleeve_key,
)
from tests.test_paper_bar_eval import AlwaysLong, Clock, _at, _engine, _entry, poll_paper_book
from tests.test_paper_universe_sleeves import RISK_LIMITS_SHA256

EQUITY = 10_000.0
STOP = 0.0625  # 1/16, inside the stop-distance gate, exact in binary
DAY = date(2026, 10, 10)


@pytest.fixture(autouse=True)
def _isolated_daily_beta_cache() -> None:
    """One test's 1d frames must not satisfy the next test's fetch."""
    clear_daily_beta_cache()
    yield
    clear_daily_beta_cache()


class NamedLong(AlwaysLong):
    """Always-long sleeve with its own name so two rows are different sleeves."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name


def _limits(gross_cap: float, **overrides: object) -> RiskLimits:
    """A paper-shaped limit set whose only moving part in most tests is the cap."""
    values: dict[str, object] = dict(
        max_concurrent_positions=15,
        max_daily_trades=20,
        max_positions_per_sector=10,
        max_position_pct=0.10,
        max_total_exposure_pct=gross_cap,
        max_risk_per_trade_pct=0.01,
        max_leverage=1.0,
        min_notional_usdt=5.0,
        max_consecutive_losses=100,
        daily_loss_limit_pct=1.0,
        max_drawdown_pct=1.0,
    )
    values.update(overrides)
    return RiskLimits(**values)  # type: ignore[arg-type]


def _intent(
    symbol: str,
    side: str,
    sector: str,
    *,
    price: float = 100.0,
    stop_pct: float = STOP,
) -> TradeIntent:
    if side == "LONG":
        stop = price * (1.0 - stop_pct)
        target = price * (1.0 + stop_pct)
    else:
        stop = price * (1.0 + stop_pct)
        target = price * (1.0 - stop_pct)
    return TradeIntent(
        symbol=symbol,
        side=side,
        entry_price=price,
        stop_price=stop,
        take_profit_price=target,
        strategy="gbn_test",
        score=1.0,
        sector=sector,
    )


def _candidate(
    intent: TradeIntent,
    plan_index: int,
    *,
    score: float | None,
) -> GbnCandidate:
    return GbnCandidate(
        symbol=intent.symbol,
        side=intent.side,
        score=score,
        plan_index=plan_index,
        payload=intent,
    )


def _position(
    symbol: str,
    side: str,
    notional: float,
    sector: str,
    *,
    price: float = 100.0,
) -> OpenPosition:
    quantity = 0.0 if price == 0 else notional / price
    return OpenPosition(
        symbol=symbol,
        side=side,
        quantity=quantity,
        entry_price=price,
        notional=notional,
        sector=sector,
    )


def _drive(
    tmp_path,
    limits: RiskLimits,
    candidates: list[GbnCandidate],
    positions: list[OpenPosition],
    betas: dict[str, float],
    *,
    enabled: bool,
    failures: dict[str, str] | None = None,
    size_raises: bool = False,
):
    """Run the orderer against the real sizer and the real risk checks."""
    risk = RiskEngine(limits=limits, kill_switch=KillSwitch(tmp_path / "kill.json"))
    state = PortfolioState(
        equity=EQUITY, peak_equity=EQUITY, open_positions=list(positions)
    )
    attempts: list[tuple[str, bool, float, str]] = []

    def book():
        return legs_from_portfolio(state)

    def size(candidate: GbnCandidate) -> float:
        if size_raises:
            raise AssertionError("sizer preview must not run on this path")
        return float(risk._size_position(candidate.payload, state)[1])

    def submit(candidate: GbnCandidate) -> SubmitResult:
        decision = risk.evaluate(candidate.payload, state)
        attempts.append(
            (
                candidate.symbol,
                bool(decision.is_approved),
                float(decision.notional),
                "; ".join(decision.reasons),
            )
        )
        if decision.is_approved:
            state.open_positions.append(
                _position(
                    candidate.symbol,
                    candidate.side,
                    decision.notional,
                    candidate.payload.sector,
                    price=candidate.payload.entry_price,
                )
            )
        return SubmitResult(
            approved=bool(decision.is_approved), reasons="; ".join(decision.reasons)
        )

    mode = execute_entry_ordering(
        candidates,
        enabled=enabled,
        betas=betas,
        beta_failures=failures or {},
        book_legs=book,
        size_notional=size,
        submit=submit,
        cycle_day=DAY,
        gross_cap=limits.max_total_exposure_pct,
    )
    return mode, attempts, state


def _returns(n: int) -> list[float]:
    """Non-zero market variance. Alternating so the OLS denominator is positive."""
    return [0.01 if i % 2 == 0 else -0.02 for i in range(n)]


def _closes(beta: float, n_returns: int, last_day: date) -> pd.Series:
    """``n_returns + 1`` daily closes ending on ``last_day``, exact beta to a beta=1 path."""
    prices = [100.0]
    for step in _returns(n_returns):
        prices.append(prices[-1] * math.exp(beta * step))
    start = last_day - timedelta(days=n_returns)
    index = pd.date_range(start, periods=len(prices), freq="D", tz="UTC")
    series = pd.Series(prices, index=index, dtype="float64")
    series.index.name = "timestamp"
    return series


def _daily_frame(beta: float) -> pd.DataFrame:
    """31 closes, 2026-09-09 through 2026-10-09, strictly before the 10 Oct cycle."""
    closes = _closes(beta, 30, date(2026, 10, 9))
    frame = pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": 1.0,
            "turnover": 1.0,
        },
        index=closes.index,
    )
    frame.index.name = "timestamp"
    return frame


class BetaFeed:
    """1h bars from the paper-bar fixture feed; 1d bars with a known beta."""

    def __init__(self, clock: Clock, betas: dict[str, float]) -> None:
        from tests.test_paper_bar_eval import CandleFeed

        self._hourly = CandleFeed(clock)
        self.betas = betas
        self.calls: list[tuple[str, str]] = []

    def fetch_latest(self, symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        self.calls.append((symbol, timeframe))
        self._hourly.calls.append((symbol, timeframe))
        if timeframe == "1d":
            return _daily_frame(self.betas.get(symbol, 1.0))
        return self._hourly.fetch_latest(symbol, timeframe, bars)

    def close(self) -> None:
        return None


def _arm(monkeypatch, flag: str | None) -> None:
    if flag is None:
        monkeypatch.delenv("ENTRY_ORDERING_GBN", raising=False)
    else:
        monkeypatch.setenv("ENTRY_ORDERING_GBN", flag)
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Flag and the pinned limits file
# ---------------------------------------------------------------------------
def test_flag_defaults_off(monkeypatch) -> None:
    _arm(monkeypatch, None)
    try:
        assert get_settings().entry_ordering_gbn is False
        assert entry_ordering_gbn_enabled() is False
    finally:
        get_settings.cache_clear()


def test_non_paper_ignores_the_flag(monkeypatch) -> None:
    monkeypatch.setenv("ENTRY_ORDERING_GBN", "true")
    monkeypatch.setenv("TRADING_MODE", "testnet")
    get_settings.cache_clear()
    try:
        assert get_settings().entry_ordering_gbn is True
        assert entry_ordering_gbn_enabled() is False
    finally:
        get_settings.cache_clear()


def test_risk_limits_sha_is_unchanged() -> None:
    digest = hashlib.sha256(RISK_LIMITS_PATH.read_bytes()).hexdigest()
    assert digest == RISK_LIMITS_SHA256
    assert RiskLimits().max_total_exposure_pct == 0.80
    assert PAPER_LIMITS.max_total_exposure_pct == 0.80


@pytest.mark.parametrize("gross_cap", [0.50, 0.80])
def test_deployed_sizer_is_side_agnostic(tmp_path, gross_cap: float) -> None:
    """The replay's LONG = 0.5x is not in this sizer. Same stop, same notional."""
    risk = RiskEngine(
        limits=_limits(gross_cap), kill_switch=KillSwitch(tmp_path / "kill.json")
    )
    state = PortfolioState(equity=EQUITY, peak_equity=EQUITY)
    long_n = risk._size_position(_intent("ETHUSDT", "LONG", "majors"), state)[1]
    short_n = risk._size_position(_intent("ETHUSDT", "SHORT", "majors"), state)[1]
    assert long_n == pytest.approx(short_n)
    assert long_n == pytest.approx(EQUITY * 0.10)


# ---------------------------------------------------------------------------
# Ordering against the real sizer, both caps
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("gross_cap", [0.50, 0.80])
def test_flag_off_keeps_plan_order_under_both_caps(tmp_path, gross_cap: float) -> None:
    """GBN would fill the hedge first. Flag off still walks plan order.

    The fill notional changes with the cap (the sizer read it). The order does not.
    """
    limits = _limits(
        gross_cap,
        max_position_pct=1.0,
        max_risk_per_trade_pct=0.5,
        max_leverage=1.0,
    )
    # Room = cap * equity - 1000. Position cap and leverage sit at equity, so
    # the exposure room is the binding cap: 4000 at 0.50, 7000 at 0.80.
    book = [_position("BTCUSDT", "SHORT", 1000.0, "majors")]
    low = _candidate(_intent("L1USDT", "LONG", "defi"), 0, score=1.0)
    high = _candidate(_intent("L2USDT", "LONG", "defi"), 1, score=9.0)
    betas = {"BTCUSDT": 1.0, "L1USDT": 0.25, "L2USDT": 0.125}
    mode, attempts, state = _drive(
        tmp_path,
        limits,
        [high, low],  # shuffled input; plan_index restores plan order
        book,
        betas,
        enabled=False,
        size_raises=True,
    )
    assert mode == "plan"
    assert [row[0] for row in attempts] == ["L1USDT", "L2USDT"]
    assert attempts[0][1] is True
    assert attempts[0][2] == pytest.approx(EQUITY * gross_cap - 1000.0)
    # The first fill used the whole room, so the second is rejected. That is
    # the sizer's cap, reached in plan order.
    assert attempts[1][1] is False
    assert "exposure" in attempts[1][3]
    opened = [position.symbol for position in state.open_positions]
    assert opened == ["BTCUSDT", "L1USDT"]


@pytest.mark.parametrize("gross_cap", [0.50, 0.80])
def test_flag_on_picks_the_smaller_abs_b_and_reads_the_cap(
    tmp_path, gross_cap: float, caplog
) -> None:
    """Same book as the flag-off test. The winner flips with the cap.

    0.50 sizes 4000. Beta 0.25 lands on B=0 and beats beta 0.125.
    0.80 sizes 7000. Beta 0.125 lands closer to flat and wins.
    The second name is rejected only because the first fill updated the book.
    """
    limits = _limits(
        gross_cap,
        max_position_pct=1.0,
        max_risk_per_trade_pct=0.5,
        max_leverage=1.0,
    )
    book = [_position("BTCUSDT", "SHORT", 1000.0, "majors")]
    first = _candidate(_intent("L1USDT", "LONG", "defi"), 0, score=1.0)
    second = _candidate(_intent("L2USDT", "LONG", "defi"), 1, score=1.0)
    betas = {"BTCUSDT": 1.0, "L1USDT": 0.25, "L2USDT": 0.125}
    caplog.set_level(logging.INFO, logger="core.execution.entry_ordering")
    mode, attempts, state = _drive(
        tmp_path, limits, [first, second], book, betas, enabled=True
    )
    assert mode == "gbn"
    winner = "L1USDT" if gross_cap == 0.50 else "L2USDT"
    assert [row[0] for row in attempts] == [winner, "L2USDT" if winner == "L1USDT" else "L1USDT"]
    assert attempts[0][1] is True
    assert attempts[0][2] == pytest.approx(EQUITY * gross_cap - 1000.0)
    assert attempts[1][1] is False
    assert "exposure" in attempts[1][3]
    assert [position.symbol for position in state.open_positions] == ["BTCUSDT", winner]
    text = caplog.text
    assert "candidate_set=" in text
    assert "shadow_plan_order=" in text
    assert f"gross_cap={gross_cap:.2f}" in text
    assert "abs_B_before=" in text
    assert "abs_B_after=" in text
    assert "reasons=" in text


@pytest.mark.parametrize("gross_cap", [0.50, 0.80])
def test_flag_on_updates_the_book_before_the_next_choice(tmp_path, gross_cap: float) -> None:
    """A one-shot sort of the original book would pick A, B, C.

    After A fills, C reduces |B| more than B does, so C is next. N is the
    10% position cap under both gross caps, so the order does not depend on
    which cap is installed — and both caps must still produce it.
    """
    limits = _limits(gross_cap)
    names = [
        ("AUSDT", "LONG", 0.125, 0, 1.0, "defi"),
        ("BUSDT", "LONG", 0.25, 1, 1.0, "layer1"),
        ("CUSDT", "SHORT", 0.25, 2, 1.0, "memes"),
    ]
    candidates = [
        _candidate(_intent(symbol, side, sector), index, score=score)
        for symbol, side, _beta, index, score, sector in names
    ]
    betas = {symbol: beta for symbol, _side, beta, _index, _score, _sector in names}
    mode, attempts, state = _drive(
        tmp_path, limits, candidates, [], betas, enabled=True
    )
    assert mode == "gbn"
    assert [row[0] for row in attempts] == ["AUSDT", "CUSDT", "BUSDT"]
    assert all(row[1] for row in attempts)
    assert attempts[0][2] == pytest.approx(1000.0)
    assert [position.symbol for position in state.open_positions] == [
        "AUSDT",
        "CUSDT",
        "BUSDT",
    ]
    # A +125, C -250, B +250. Final B is +125. A one-shot rank would have
    # filled B before C and landed on the same notionals in a different order.
    assert book_beta_usdt(legs_from_portfolio(state), betas) == pytest.approx(125.0)


@pytest.mark.parametrize("gross_cap", [0.50, 0.80])
def test_rejected_candidate_is_removed_and_does_not_update_the_book(
    tmp_path, gross_cap: float
) -> None:
    """The best |B_after| is sector-capped. It is attempted, rejected, dropped.

    The book is unchanged, so the next choice is the same one the flat book
    would have made. Later, an approval does change the next choice (C before B).
    """
    limits = _limits(gross_cap, max_positions_per_sector=1)
    held = _position("HOLDUSDT", "LONG", 0.0, "majors")
    rows = [
        ("DUSDT", "LONG", 0.0625, 0, 1.0, "majors"),
        ("AUSDT", "LONG", 0.125, 1, 1.0, "defi"),
        ("BUSDT", "LONG", 0.25, 2, 1.0, "layer1"),
        ("CUSDT", "SHORT", 0.25, 3, 1.0, "memes"),
    ]
    candidates = [
        _candidate(_intent(symbol, side, sector), index, score=score)
        for symbol, side, _beta, index, score, sector in rows
    ]
    betas = {symbol: beta for symbol, _side, beta, _i, _s, _sec in rows}
    mode, attempts, state = _drive(
        tmp_path, limits, candidates, [held], betas, enabled=True
    )
    assert mode == "gbn"
    assert [row[0] for row in attempts] == ["DUSDT", "AUSDT", "CUSDT", "BUSDT"]
    assert attempts[0][1] is False
    assert "sector" in attempts[0][3]
    assert all(row[1] for row in attempts[1:])
    assert [position.symbol for position in state.open_positions] == [
        "HOLDUSDT",
        "AUSDT",
        "CUSDT",
        "BUSDT",
    ]


@pytest.mark.parametrize("gross_cap", [0.50, 0.80])
def test_ties_break_on_score_then_plan_order_unscored_last(
    tmp_path, gross_cap: float
) -> None:
    """Equal |B_after| (same beta, same size). Higher score, then plan order.

    A missing score ranks under every finite score, including after the book
    has moved and every remaining long is still tied.
    """
    limits = _limits(gross_cap)
    specs = [
        ("S0USDT", 0, 1.0),
        ("S1USDT", 1, 3.0),
        ("S2USDT", 2, None),
        ("S3USDT", 3, 3.0),
    ]
    candidates = [
        _candidate(_intent(symbol, "LONG", "defi"), index, score=score)
        for symbol, index, score in specs
    ]
    betas = {symbol: 1.0 for symbol, _index, _score in specs}
    mode, attempts, _state = _drive(
        tmp_path, limits, list(reversed(candidates)), [], betas, enabled=True
    )
    assert mode == "gbn"
    assert [row[0] for row in attempts] == ["S1USDT", "S3USDT", "S0USDT", "S2USDT"]
    assert all(row[1] for row in attempts)


def test_values_inside_one_cent_tie(tmp_path) -> None:
    """|B_after| is compared after rounding to the cent, then score, then plan."""
    limits = _limits(0.50, max_position_pct=1.0, max_risk_per_trade_pct=1.0)
    # The fake notional is what the orderer ranks on. 100.004 and 100.001
    # are the same cent. The higher score wins that tie.
    notionals = {"HIUSDT": 100.004, "LOUSDT": 100.001, "PLANUSDT": 100.004}

    def size(candidate: GbnCandidate) -> float:
        return notionals[candidate.symbol]

    seen: list[str] = []

    def submit(candidate: GbnCandidate) -> SubmitResult:
        seen.append(candidate.symbol)
        return SubmitResult(approved=False, reasons="rejected for the test")

    candidates = [
        GbnCandidate("PLANUSDT", "LONG", 1.0, 0),
        GbnCandidate("LOUSDT", "LONG", 5.0, 1),
        GbnCandidate("HIUSDT", "SHORT", 1.0, 2),
    ]
    # Flat book. |beta * s * N| is just N, so the two 100.00x values tie
    # and the score-5 name wins. PLANUSDT and HIUSDT then tie on score 1
    # and plan order keeps PLANUSDT ahead of HIUSDT.
    mode = execute_entry_ordering(
        candidates,
        enabled=True,
        betas={name: 1.0 for name in notionals},
        beta_failures={},
        book_legs=lambda: [],
        size_notional=size,
        submit=submit,
        cycle_day=DAY,
        gross_cap=limits.max_total_exposure_pct,
    )
    assert mode == "gbn"
    assert seen == ["LOUSDT", "PLANUSDT", "HIUSDT"]


# ---------------------------------------------------------------------------
# Beta
# ---------------------------------------------------------------------------
def test_ols_beta_uses_thirty_returns_and_ignores_the_cycle_day() -> None:
    cycle = date(2026, 10, 20)
    last = date(2026, 10, 19)
    btc = _closes(1.0, 30, last)
    symbol = _closes(2.0, 30, last)
    # A close ON the cycle day would wreck the beta if it were included.
    extra = pd.Series(
        [float(symbol.iloc[-1]) * 10.0],
        index=pd.DatetimeIndex([pd.Timestamp(cycle, tz="UTC")]),
    )
    symbol = pd.concat([symbol, extra])
    beta, reason = ols_beta_to_btc(symbol, btc, cycle)
    assert reason == ""
    assert beta == pytest.approx(2.0)


def test_ols_beta_accepts_twenty_returns_and_rejects_nineteen() -> None:
    cycle = date(2026, 10, 20)
    last = date(2026, 10, 19)
    btc_ok = _closes(1.0, 20, last)
    symbol_ok = _closes(1.5, 20, last)
    beta, reason = ols_beta_to_btc(symbol_ok, btc_ok, cycle)
    assert reason == ""
    assert beta == pytest.approx(1.5)

    btc_short = _closes(1.0, 19, last)
    symbol_short = _closes(1.5, 19, last)
    missing, why = ols_beta_to_btc(symbol_short, btc_short, cycle)
    assert missing is None
    assert "20" in why


def test_ols_beta_rejects_a_flat_btc_path() -> None:
    cycle = date(2026, 10, 20)
    index = pd.date_range("2026-09-20", periods=25, freq="D", tz="UTC")
    flat = pd.Series([100.0] * len(index), index=index)
    moving = pd.Series(
        [100.0 * (1.01 ** i) for i in range(len(index))], index=index
    )
    beta, why = ols_beta_to_btc(moving, flat, cycle)
    assert beta is None
    assert "variance" in why


def test_btc_beta_is_one_without_a_fetch() -> None:
    def fetch(_symbol: str) -> pd.DataFrame:
        raise AssertionError("BTC beta is defined, not fetched when it is the only name")

    betas, failures = load_betas(fetch, {BTC_SYMBOL}, DAY)
    assert betas == {BTC_SYMBOL: 1.0}
    assert failures == {}


def test_missing_daily_data_is_a_named_failure() -> None:
    def fetch(symbol: str):
        if symbol == BTC_SYMBOL:
            return _closes(1.0, 30, date(2026, 10, 9))
        raise RuntimeError("feed down")

    betas, failures = load_betas(fetch, {"ETHUSDT"}, DAY)
    assert "ETHUSDT" not in betas
    assert "unavailable" in failures["ETHUSDT"]


def test_beta_failure_falls_back_to_plan_order_for_the_cycle(tmp_path) -> None:
    """One missing beta keeps the whole cycle in plan order. No beta=1 substitute."""
    limits = _limits(0.50)
    good = _candidate(_intent("GOODUSDT", "LONG", "defi"), 1, score=99.0)
    bad = _candidate(_intent("BADUSDT", "SHORT", "defi"), 0, score=0.0)
    # If GBN ran, GOOD (plan 1) would be first: it hedges a flat book and
    # outscores BAD. Fallback must still send BAD first.
    mode, attempts, _state = _drive(
        tmp_path,
        limits,
        [good, bad],
        [],
        betas={"GOODUSDT": 0.1},
        enabled=True,
        failures={"BADUSDT": "fewer than 20 paired daily returns (4 before 2026-10-10)"},
    )
    assert mode == "plan_fallback"
    assert [row[0] for row in attempts] == ["BADUSDT", "GOODUSDT"]


def test_open_position_missing_beta_falls_back_even_when_candidates_are_fine() -> None:
    seen: list[str] = []

    def submit(candidate: GbnCandidate) -> SubmitResult:
        seen.append(candidate.symbol)
        return SubmitResult(approved=False, reasons="no")

    def size(_candidate: GbnCandidate) -> float:
        raise AssertionError("incomplete book beta must not rank")

    mode = execute_entry_ordering(
        [GbnCandidate("SOLUSDT", "LONG", 1.0, 0)],
        enabled=True,
        betas={"SOLUSDT": 0.4},
        beta_failures={},
        book_legs=lambda: [BookLeg("ZECUSDT", "SHORT", 500.0)],
        size_notional=size,
        submit=submit,
        cycle_day=DAY,
        gross_cap=0.50,
    )
    assert mode == "plan_fallback"
    assert seen == ["SOLUSDT"]


def test_zero_notional_position_does_not_force_fallback() -> None:
    seen: list[str] = []

    def submit(candidate: GbnCandidate) -> SubmitResult:
        seen.append(candidate.symbol)
        return SubmitResult(approved=True, reasons="")

    mode = execute_entry_ordering(
        [GbnCandidate("SOLUSDT", "LONG", 1.0, 0)],
        enabled=True,
        betas={"SOLUSDT": 0.4},
        beta_failures={},
        book_legs=lambda: [BookLeg("ZECUSDT", "LONG", 0.0)],
        size_notional=lambda _candidate: 100.0,
        submit=submit,
        cycle_day=DAY,
        gross_cap=0.80,
    )
    assert mode == "gbn"
    assert seen == ["SOLUSDT"]


def test_zero_notional_missing_beta_does_not_force_fallback() -> None:
    """A dust candidate and a flat open leg do not need a beta.

    Plan order would send SOL first. GBN sends the zero-size name first,
    because it leaves ``|B|`` at 0 and the short does not. That reorder is
    the proof the missing betas were ignored.
    """
    seen: list[str] = []

    def size(candidate: GbnCandidate) -> float:
        if candidate.symbol == "DUSTUSDT":
            return 0.0
        return 250.0

    def submit(candidate: GbnCandidate) -> SubmitResult:
        seen.append(candidate.symbol)
        return SubmitResult(approved=False, reasons="no")

    mode = execute_entry_ordering(
        [
            GbnCandidate("SOLUSDT", "SHORT", 1.0, 0),
            GbnCandidate("DUSTUSDT", "LONG", 1.0, 1),
        ],
        enabled=True,
        betas={"SOLUSDT": 0.4},
        beta_failures={
            "DUSTUSDT": "fewer than 20 paired daily returns (4 before 2026-10-10)",
            "ZECUSDT": "daily closes unavailable (feed down)",
        },
        book_legs=lambda: [BookLeg("ZECUSDT", "LONG", 0.0)],
        size_notional=size,
        submit=submit,
        cycle_day=DAY,
        gross_cap=0.80,
    )
    assert mode == "gbn"
    assert seen == ["DUSTUSDT", "SOLUSDT"]


def test_mid_cycle_exception_submits_each_candidate_once(caplog) -> None:
    """A sizing error after the first fill must not drop or repeat a name.

    Equal ``|B|`` on a flat book, so the higher score (MID) is sent first.
    The next preview raises. MID stays sent; the other two follow plan order.
    """
    submitted: list[str] = []

    def size(candidate: GbnCandidate) -> float:
        if submitted:
            raise RuntimeError(f"sizer failed on {candidate.symbol}")
        return 800.0

    def submit(candidate: GbnCandidate) -> SubmitResult:
        submitted.append(candidate.symbol)
        return SubmitResult(approved=True, reasons="")

    caplog.set_level(logging.ERROR, logger="core.execution.entry_ordering")
    mode = execute_entry_ordering(
        [
            GbnCandidate("EARLYUSDT", "LONG", 1.0, 0),
            GbnCandidate("MIDUSDT", "SHORT", 5.0, 1),
            GbnCandidate("LATEUSDT", "LONG", 3.0, 2),
        ],
        enabled=True,
        betas={"EARLYUSDT": 1.0, "MIDUSDT": 1.0, "LATEUSDT": 1.0},
        beta_failures={},
        book_legs=lambda: [],
        size_notional=size,
        submit=submit,
        cycle_day=DAY,
        gross_cap=0.80,
    )
    assert mode == "plan_fallback"
    assert submitted == ["MIDUSDT", "EARLYUSDT", "LATEUSDT"]
    assert len(submitted) == len(set(submitted))
    assert "plan order" in caplog.text


def test_daily_fetch_is_cached_for_the_utc_day() -> None:
    """A second cycle on the same UTC day does not fetch. The next day does.

    Scan and poll both load betas through this function, so one cache covers
    both. The key is (symbol, cycle date).
    """
    calls: list[str] = []

    def fetch(symbol: str) -> pd.Series:
        calls.append(symbol)
        beta = 1.0 if symbol == BTC_SYMBOL else 1.5
        return _closes(beta, 30, date(2026, 10, 9))

    day = date(2026, 10, 10)
    first, failures = load_betas(fetch, {"ETHUSDT", "SOLUSDT"}, day)
    assert failures == {}
    assert first["ETHUSDT"] == pytest.approx(1.5)
    assert calls == [BTC_SYMBOL, "ETHUSDT", "SOLUSDT"]

    calls.clear()
    second, again = load_betas(fetch, {"SOLUSDT", "ETHUSDT"}, day)
    assert again == {}
    assert calls == []
    assert second["ETHUSDT"] == pytest.approx(first["ETHUSDT"])
    assert second["SOLUSDT"] == pytest.approx(first["SOLUSDT"])

    next_day = day + timedelta(days=1)
    load_betas(fetch, {"ETHUSDT"}, next_day)
    assert calls == [BTC_SYMBOL, "ETHUSDT"]


def test_empty_daily_frame_is_not_cached() -> None:
    """An empty frame must not be pinned. The next call fetches it again."""
    calls: list[str] = []

    def fetch(symbol: str):
        calls.append(symbol)
        if symbol == BTC_SYMBOL:
            return _closes(1.0, 30, date(2026, 10, 9))
        return pd.DataFrame()

    day = date(2026, 10, 10)
    load_betas(fetch, {"ETHUSDT"}, day)
    assert calls == [BTC_SYMBOL, "ETHUSDT"]
    calls.clear()
    load_betas(fetch, {"ETHUSDT"}, day)
    assert calls == ["ETHUSDT"]


def test_daily_frame_missing_previous_utc_day_is_not_cached() -> None:
    """Bars that stop the day before yesterday are not pinned past 00:00 UTC."""
    calls: list[str] = []

    def fetch(symbol: str) -> pd.Series:
        calls.append(symbol)
        # Cycle day 10 Oct needs the 9 Oct bar. ETH stops on 8 Oct.
        last = date(2026, 10, 9) if symbol == BTC_SYMBOL else date(2026, 10, 8)
        beta = 1.0 if symbol == BTC_SYMBOL else 1.5
        return _closes(beta, 30, last)

    day = date(2026, 10, 10)
    load_betas(fetch, {"ETHUSDT"}, day)
    assert calls == [BTC_SYMBOL, "ETHUSDT"]
    calls.clear()
    load_betas(fetch, {"ETHUSDT"}, day)
    assert calls == ["ETHUSDT"]


def test_daily_cache_evicts_other_utc_days_on_write() -> None:
    """A write for a new UTC day drops every key from any other day."""
    calls: list[str] = []
    last_close = {"day": date(2026, 10, 9)}

    def fetch(symbol: str) -> pd.Series:
        calls.append(symbol)
        beta = 1.0 if symbol == BTC_SYMBOL else 1.25
        return _closes(beta, 30, last_close["day"])

    day = date(2026, 10, 10)
    load_betas(fetch, {"ETHUSDT", "SOLUSDT"}, day)
    calls.clear()
    load_betas(fetch, {"ETHUSDT", "SOLUSDT"}, day)
    assert calls == []

    last_close["day"] = date(2026, 10, 10)
    calls.clear()
    nxt = date(2026, 10, 11)
    load_betas(fetch, {"ETHUSDT"}, nxt)
    assert calls == [BTC_SYMBOL, "ETHUSDT"]
    calls.clear()
    load_betas(fetch, {"ETHUSDT"}, nxt)
    assert calls == []

    # SOL was cached for 10 Oct and this write did not replace it. The date
    # is gone anyway, so the old day fetches again.
    last_close["day"] = date(2026, 10, 9)
    calls.clear()
    load_betas(fetch, {"SOLUSDT"}, day)
    assert calls == [BTC_SYMBOL, "SOLUSDT"]


# ---------------------------------------------------------------------------
# Engine hook: poll and cycle. Flag off does not fetch daily bars.
# ---------------------------------------------------------------------------
def _two_sleeves():
    return [
        _entry("ETHUSDT", SignalSide.LONG, NamedLong("eth_long"), "1h"),
        _entry("SOLUSDT", SignalSide.LONG, NamedLong("sol_long"), "1h"),
    ]


def _record(engine):
    seen: list[str] = []
    real = engine._attempt_entry

    def wrap(signal, equity, marks):
        seen.append(signal.symbol)
        return real(signal, equity, marks)

    engine._attempt_entry = wrap
    return seen


@pytest.mark.parametrize("gross_cap", [0.50, 0.80])
@pytest.mark.parametrize("path", ["poll", "cycle"])
def test_engine_flag_off_is_plan_order_and_does_not_fetch_daily(
    tmp_path, monkeypatch, firm_db, gross_cap: float, path: str
) -> None:
    _arm(monkeypatch, None)
    clock = Clock(_at(12, 5))
    engine = _engine(tmp_path, monkeypatch, clock, _two_sleeves())
    engine.risk.limits = _limits(gross_cap)
    # Candles in this fixture print 100_000. The paper quote has to match or
    # the sized quantity fills below the exchange minimum and never opens.
    engine.broker._data.prices.update({"ETHUSDT": 100_000.0, "SOLUSDT": 100_000.0})
    seen = _record(engine)
    try:
        if path == "poll":
            assert poll_paper_book(engine) == 2
        else:
            report = engine.run_cycle()
            assert report.orders_placed == 2
        assert seen == ["ETHUSDT", "SOLUSDT"]
        assert all(timeframe != "1d" for _symbol, timeframe in engine._data.calls)
        assert [row.symbol for row in engine.ledger.open_positions()] == [
            "ETHUSDT",
            "SOLUSDT",
        ]
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("gross_cap", [0.50, 0.80])
@pytest.mark.parametrize("path", ["poll", "cycle"])
def test_engine_flag_on_reorders_and_logs_the_deployed_cap(
    tmp_path, monkeypatch, firm_db, caplog, gross_cap: float, path: str
) -> None:
    """Flat book, equal scores. Lower beta (SOL 0.25) is sent before ETH (beta 2)."""
    _arm(monkeypatch, "true")
    clock = Clock(_at(12, 5))
    engine = _engine(tmp_path, monkeypatch, clock, _two_sleeves())
    engine.risk.limits = _limits(gross_cap)
    engine.broker._data.prices.update({"ETHUSDT": 100_000.0, "SOLUSDT": 100_000.0})
    engine._data = BetaFeed(clock, {"BTCUSDT": 1.0, "ETHUSDT": 2.0, "SOLUSDT": 0.25})
    seen = _record(engine)
    caplog.set_level(logging.INFO, logger="core.execution.entry_ordering")
    try:
        if path == "poll":
            assert poll_paper_book(engine) == 2
        else:
            report = engine.run_cycle()
            assert report.signals_found == 2
            assert report.orders_placed == 2
        assert seen == ["SOLUSDT", "ETHUSDT"]
        assert ("BTCUSDT", "1d") in engine._data.calls
        assert [row.symbol for row in engine.ledger.open_positions()] == [
            "SOLUSDT",
            "ETHUSDT",
        ]
        assert f"gross_cap={gross_cap:.2f}" in caplog.text
        assert "shadow_plan_order=" in caplog.text
        assert "0:ETHUSDT:LONG" in caplog.text
    finally:
        get_settings.cache_clear()


def test_engine_flag_on_falls_back_to_plan_order_when_beta_cannot_be_computed(
    tmp_path, monkeypatch, firm_db, caplog
) -> None:
    """Flat daily closes have no BTC variance. The cycle must not reorder."""
    _arm(monkeypatch, "true")
    clock = Clock(_at(12, 5))
    engine = _engine(tmp_path, monkeypatch, clock, _two_sleeves())
    seen = _record(engine)
    caplog.set_level(logging.INFO, logger="core.execution.entry_ordering")
    try:
        assert poll_paper_book(engine) == 2
        assert seen == ["ETHUSDT", "SOLUSDT"]
        assert "plan_fallback" in caplog.text
        assert "variance" in caplog.text
    finally:
        get_settings.cache_clear()


def test_gbn_poll_submits_the_batch_once_when_the_due_set_is_complete(
    tmp_path, monkeypatch, firm_db
) -> None:
    """A slow walk holds candidates. The next poll finishes the set and sends it once, in GBN order."""
    _arm(monkeypatch, "true")
    clock = Clock(_at(12, 5))
    engine = _engine(tmp_path, monkeypatch, clock, _two_sleeves())
    engine.risk.limits = _limits(0.80)
    engine.broker._data.prices.update({"ETHUSDT": 100_000.0, "SOLUSDT": 100_000.0})
    engine._data = BetaFeed(clock, {"BTCUSDT": 1.0, "ETHUSDT": 2.0, "SOLUSDT": 0.25})
    seen = _record(engine)

    class Mono:
        def __init__(self) -> None:
            self.t = 0.0

        def __call__(self) -> float:
            return self.t

    mono = Mono()
    real = engine._data.fetch_latest

    def slow(symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        if timeframe != "1d":
            mono.t += 5.0
        return real(symbol, timeframe, bars)

    engine._data.fetch_latest = slow  # type: ignore[method-assign]
    try:
        assert poll_paper_book(engine, budget_seconds=4, monotonic=mono) == 0
        assert seen == []
        assert engine.ledger.open_positions() == []
        assert poll_paper_book(engine, budget_seconds=4, monotonic=mono) == 2
        assert seen == ["SOLUSDT", "ETHUSDT"]
        assert [row.symbol for row in engine.ledger.open_positions()] == [
            "SOLUSDT",
            "ETHUSDT",
        ]
    finally:
        get_settings.cache_clear()


def test_gbn_poll_discards_a_held_batch_when_the_bar_rolls(
    tmp_path, monkeypatch, firm_db, caplog
) -> None:
    _arm(monkeypatch, "true")
    clock = Clock(_at(12, 5))
    engine = _engine(tmp_path, monkeypatch, clock, _two_sleeves())
    engine.risk.limits = _limits(0.80)
    engine.broker._data.prices.update({"ETHUSDT": 100_000.0, "SOLUSDT": 100_000.0})
    engine._data = BetaFeed(clock, {"BTCUSDT": 1.0, "ETHUSDT": 2.0, "SOLUSDT": 0.25})
    seen = _record(engine)

    class Mono:
        def __init__(self) -> None:
            self.t = 0.0

        def __call__(self) -> float:
            return self.t

    mono = Mono()
    real = engine._data.fetch_latest

    def slow(symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        if timeframe != "1d":
            mono.t += 5.0
        return real(symbol, timeframe, bars)

    engine._data.fetch_latest = slow  # type: ignore[method-assign]
    caplog.set_level(logging.INFO, logger="core.execution.paper_bar_eval")
    try:
        assert poll_paper_book(engine, budget_seconds=4, monotonic=mono) == 0
        assert seen == []
        clock.when = _at(13, 5)
        assert poll_paper_book(engine, budget_seconds=4, monotonic=mono) == 0
        assert seen == []
        assert engine.ledger.open_positions() == []
        assert "discarded held batch" in caplog.text
    finally:
        get_settings.cache_clear()


def _hold_one_sleeve(engine, monkeypatch):
    """Stop the GBN poll after the first due sleeve is held, before any submit."""

    class Mono:
        def __init__(self) -> None:
            self.t = 0.0

        def __call__(self) -> float:
            return self.t

    mono = Mono()
    real = engine._data.fetch_latest

    def slow(symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        if timeframe != "1d":
            mono.t += 5.0
        return real(symbol, timeframe, bars)

    engine._data.fetch_latest = slow  # type: ignore[method-assign]
    assert poll_paper_book(engine, budget_seconds=4, monotonic=mono) == 0
    hold = engine._paper_bar_state.gbn_hold
    assert hold is not None and hold.pending and hold.visited
    return hold


def test_gbn_cycle_does_not_submit_a_sleeve_the_poll_is_holding(
    tmp_path, monkeypatch, firm_db
) -> None:
    """The cycle skips sleeves in gbn_hold.visited. The poll still submits once."""
    _arm(monkeypatch, "true")
    clock = Clock(_at(12, 5))
    engine = _engine(tmp_path, monkeypatch, clock, _two_sleeves())
    engine.risk.limits = _limits(0.80)
    engine.broker._data.prices.update({"ETHUSDT": 100_000.0, "SOLUSDT": 100_000.0})
    engine._data = BetaFeed(clock, {"BTCUSDT": 1.0, "ETHUSDT": 2.0, "SOLUSDT": 0.25})
    try:
        hold = _hold_one_sleeve(engine, monkeypatch)
        saved = [
            (entry, outcome.signal, outcome.price, outcome.bar_open)
            for _index, entry, outcome in hold.pending
        ]
        for entry in engine.plan.entries:
            if sleeve_key(entry) not in hold.visited:
                continue
            outcome = cycle_paper_bar(engine, entry, equity=EQUITY, marks={})
            assert outcome.handled is True
            assert outcome.ordered is False
        assert engine.ledger.open_positions() == []
        # Resume. The held sleeve is still unseen, so the batch submits once.
        engine._data.fetch_latest = engine._data.fetch_latest  # keep the slow walk
        assert poll_paper_book(engine, budget_seconds=30, monotonic=lambda: 0.0) == 2
        assert [row.symbol for row in engine.ledger.open_positions()] == [
            "SOLUSDT",
            "ETHUSDT",
        ]
        entry, signal, price, bar_open = saved[0]
        again = commit_deferred_paper_entry(
            engine,
            entry,
            signal,
            equity=EQUITY,
            marks={},
            source="poll",
            price=price,
            bar_open=bar_open,
        )
        assert again.ordered is False
        assert again.reason == "already submitted"
        assert len(engine.ledger.open_positions()) == 2
    finally:
        get_settings.cache_clear()


def test_gbn_commit_does_not_resubmit_after_a_reject_or_an_exit(
    tmp_path, monkeypatch, firm_db
) -> None:
    """duplicate_order_block passes after a reject or an exit. seen does not."""
    _arm(monkeypatch, "true")
    clock = Clock(_at(12, 5))
    engine = _engine(tmp_path, monkeypatch, clock, _two_sleeves())
    engine.risk.limits = _limits(0.80)
    engine.broker._data.prices.update({"ETHUSDT": 100_000.0, "SOLUSDT": 100_000.0})
    engine._data = BetaFeed(clock, {"BTCUSDT": 1.0, "ETHUSDT": 2.0, "SOLUSDT": 0.25})
    attempts: list[str] = []
    real = engine._attempt_entry

    def counted(signal, equity, marks):  # noqa: ANN001
        attempts.append(signal.symbol)
        return real(signal, equity, marks)

    engine._attempt_entry = counted  # type: ignore[method-assign]
    try:
        hold = _hold_one_sleeve(engine, monkeypatch)
        _index, entry, outcome = hold.pending[0]
        engine.risk.limits = _limits(0.80, max_concurrent_positions=0)
        rejected = commit_deferred_paper_entry(
            engine,
            entry,
            outcome.signal,
            equity=EQUITY,
            marks={},
            source="poll",
            price=outcome.price,
            bar_open=outcome.bar_open,
        )
        assert rejected.ordered is False
        assert engine.ledger.open_positions() == []
        engine.risk.limits = _limits(0.80)
        retried = commit_deferred_paper_entry(
            engine,
            entry,
            outcome.signal,
            equity=EQUITY,
            marks={},
            source="poll",
            price=outcome.price,
            bar_open=outcome.bar_open,
        )
        assert retried.ordered is False
        assert retried.reason == "already submitted"
        assert attempts == [entry.symbol]

        # A fresh bar that fills, then exits, must not be submitted again.
        engine._paper_bar_state.sleeves.pop(sleeve_key(entry), None)
        filled = commit_deferred_paper_entry(
            engine,
            entry,
            outcome.signal,
            equity=EQUITY,
            marks={},
            source="poll",
            price=outcome.price,
            bar_open=outcome.bar_open,
        )
        assert filled.ordered is True
        engine.broker._data.prices[entry.symbol] = 1.0
        assert engine.supervise_exits() >= 1
        assert engine.ledger.find_open_position(entry.symbol) is None
        after_exit = commit_deferred_paper_entry(
            engine,
            entry,
            outcome.signal,
            equity=EQUITY,
            marks={},
            source="cycle",
            price=outcome.price,
            bar_open=outcome.bar_open,
        )
        assert after_exit.ordered is False
        assert after_exit.reason == "already submitted"
        assert engine.ledger.find_open_position(entry.symbol) is None
        assert attempts.count(entry.symbol) == 2
    finally:
        get_settings.cache_clear()


def test_beta_fetch_budget_skips_names_past_the_cap() -> None:
    """A throttled 1d pull does not start another symbol after the 5s budget."""
    clock = {"t": 0.0}
    calls: list[str] = []

    class Data:
        def fetch_latest(self, symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
            calls.append(symbol)
            clock["t"] += 3.0
            beta = 1.0 if symbol == BTC_SYMBOL else 1.2
            return _daily_frame(beta)

    fetch = budgeted_daily_fetch(Data(), 45, budget=5, monotonic=lambda: clock["t"])
    _betas, failures = load_betas(fetch, {"ETHUSDT", "SOLUSDT"}, DAY)
    assert calls == [BTC_SYMBOL, "ETHUSDT"]
    assert "budget" in failures["SOLUSDT"]
