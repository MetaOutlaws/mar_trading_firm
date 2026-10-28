"""A cipher-forward retest already evaluated at this as-of minute is a no-op.

Re-running it must not emit a second signal or add a signal, decision, or
position row. The as-of minute is an argument. The worker clock is frozen and
Bybit is a feed stub, so these tests do not open a socket.
"""

from __future__ import annotations

import copy

import pytest

import scripts.run_cipher_forward_paper as paper
from research.cipher_forward.config import frozen_config
from research.cipher_forward.feed import MINUTE, advance_retest
from research.cipher_forward.ledger import PaperTrial
from scripts.run_cipher_forward_paper import retests
from tests import test_cipher_forward_runtime as runtime

# Signal builder and cycle helper from the runtime tests. The temp ledger
# fixture below matches that module's `book` fixture.
cycle = runtime.cycle
signal = runtime.signal
T = runtime.T

# One closed minute after the pending row's next_minute.
ASOF = T + MINUTE
BOUNDARY = 100.0


@pytest.fixture
def book(tmp_path):
    """Temporary ledger, same construction as tests/test_cipher_forward_runtime.py."""
    trial = PaperTrial(tmp_path / "trial.db", frozen_config(), create=True)
    yield trial
    trial.db.close()


@pytest.fixture(autouse=True)
def frozen_clock_and_no_bybit(monkeypatch):
    """Injected as-of minutes only. The worker clock and the Bybit opener cannot run."""
    monkeypatch.setattr(paper, "now_ms", lambda: ASOF)

    def refuse_network(*_args, **_kwargs):
        raise AssertionError("retest idempotency tests must not call Bybit")

    # PublicClient binds this name when a Market is constructed. These tests
    # never construct one; the patch fails the run if a future path does.
    monkeypatch.setattr("urllib.request.urlopen", refuse_network)
    monkeypatch.setattr("research.cipher_forward.public.urlopen", refuse_network)


def _bar(open_ms, *, low, high, close, open_):
    """Minute bar as advance_retest sees it: t is the close, one minute after the open."""
    return dict(t=open_ms + MINUTE, o=open_, h=high, l=low, c=close, v=1.0)


def _quiet_bar(open_ms):
    """Long bar that stays above the boundary, so the retest remains pending."""
    return _bar(
        open_ms,
        low=BOUNDARY + 1,
        high=BOUNDARY + 2,
        close=BOUNDARY + 1.5,
        open_=BOUNDARY + 1.2,
    )


def _reclaim_bar(open_ms):
    """Long bar that touches the boundary and closes back above it."""
    return _bar(
        open_ms,
        low=BOUNDARY - 1,
        high=BOUNDARY + 3,
        close=BOUNDARY + 1,
        open_=BOUNDARY + 0.5,
    )


def _pending(uid, symbol, open_ms=T):
    """Hourly retest row in the shape hourly_candidates stores."""
    return dict(
        uid=uid,
        symbol=symbol,
        source="H",
        side=1,
        sector="majors",
        signal_ms=open_ms,
        boundary=BOUNDARY,
        prior_atr=3.0,
        next_minute=open_ms,
        touched=False,
        eligible_signal=True,
    )


class _FixedBars:
    """Feed stub. retest_bars returns the same closed bars for a symbol every time."""

    def __init__(self, bars_by_symbol):
        self.bars_by_symbol = bars_by_symbol

    def retest_bars(self, symbol, minute):
        if minute != ASOF:
            raise AssertionError(f"unexpected as-of {minute}")
        return list(self.bars_by_symbol[symbol])


def _counts(db):
    """SQLite row counts a repeated signal must leave unchanged."""
    tables = ("signals", "decisions", "positions")
    return {name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0] for name in tables}


def test_advance_retest_same_and_older_asof_are_noop():
    """The first closed minute stays pending. The same as-of, and an older one, do not move it."""
    row = _pending("BTCUSDT|H|1|retest", "BTCUSDT")
    # The later bar would reclaim. A second pass that keeps walking would emit a signal.
    bars = [_quiet_bar(T), _reclaim_bar(T + MINUTE)]
    state, emitted, status = advance_retest(row, bars, ASOF)
    assert emitted is None and status == "pending"
    assert state["next_minute"] == row["next_minute"] + MINUTE
    assert state["touched"] is False

    snapshot = copy.deepcopy(state)
    again, emitted_again, status_again = advance_retest(state, bars, ASOF)
    assert again == snapshot
    assert again["next_minute"] == snapshot["next_minute"]
    assert state == snapshot
    assert emitted_again is None and status_again == "pending"

    # A clock that steps backward must not reopen a minute already evaluated.
    older, emitted_older, status_older = advance_retest(state, bars, ASOF - MINUTE)
    assert older == snapshot
    assert older["next_minute"] == snapshot["next_minute"]
    assert state == snapshot
    assert emitted_older is None and status_older == "pending"


def test_reclaim_removes_uid_so_second_retests_emits_nothing():
    """A reclaim returns no pending row, so the next retests() call cannot emit that uid."""
    reclaimed = _pending("BTCUSDT|H|1|reclaim", "BTCUSDT")
    still_open = _pending("ETHUSDT|H|1|still", "ETHUSDT")
    btc_bars = [_reclaim_bar(T)]
    eth_bars = [_quiet_bar(T), _reclaim_bar(T + MINUTE)]

    state, emitted, status = advance_retest(reclaimed, btc_bars, ASOF)
    assert state is None and status == "candidate"
    assert emitted["uid"] == reclaimed["uid"]
    assert emitted["action_ms"] == ASOF
    assert "next_minute" not in emitted and "touched" not in emitted

    feed = _FixedBars({"BTCUSDT": btc_bars, "ETHUSDT": eth_bars})
    first = retests(feed, {reclaimed["uid"]: reclaimed, still_open["uid"]: still_open}, ASOF)
    # advance_retest returned no pending state, so retests drops the uid.
    assert reclaimed["uid"] not in first["pending"]
    assert reclaimed["uid"] in first["ready"]
    assert still_open["uid"] in first["pending"]

    second = retests(feed, first["pending"], ASOF)
    assert reclaimed["uid"] not in second["ready"]
    assert reclaimed["uid"] not in second["pending"]
    assert all(item.get("uid") != reclaimed["uid"] for item in second["observations"])


def test_retests_same_minute_on_same_pending_dict_is_noop():
    """Two retests() calls at one minute leave pending, ready, and observations unchanged."""
    row = _pending("BTCUSDT|H|1|retest", "BTCUSDT")
    feed = _FixedBars({"BTCUSDT": [_quiet_bar(T), _reclaim_bar(T + MINUTE)]})
    pending = {row["uid"]: row}
    first = retests(feed, pending, ASOF)
    assert first["ready"] == {}
    assert first["observations"] == []
    assert first["pending"][row["uid"]]["next_minute"] == row["next_minute"] + MINUTE
    # The worker keeps one pending dict and replaces it with the evaluated rows.
    evaluated = copy.deepcopy(first["pending"])
    pending.clear()
    pending.update(copy.deepcopy(evaluated))
    second = retests(feed, pending, ASOF)
    assert second["pending"] == evaluated
    assert second["ready"] == {}
    assert second["observations"] == []
    assert pending == evaluated


def test_ledger_cycle_identical_signal_body_adds_no_rows(book):
    """The same uid and body on a later cycle does not insert signal, decision, or position rows.

    The later minute is a new event id, so this is the signal-uid path. An exact
    event replay returns earlier and would not reach that check.
    """
    candidate = signal()
    cycle(book, signals=[candidate])
    before = _counts(book.db)
    assert before["signals"] == 1
    assert before["decisions"] > 0 and before["positions"] > 0
    again = cycle(book, T + MINUTE, signals=[copy.deepcopy(candidate)])
    assert again.get("duplicate") is not True
    assert _counts(book.db) == before


def test_ledger_cycle_conflicting_signal_uid_adds_no_rows(book):
    """A second body for an existing uid raises and commits nothing."""
    candidate = signal()
    cycle(book, signals=[candidate])
    before = _counts(book.db)
    changed = copy.deepcopy(candidate)
    changed["target"] = candidate["target"] + 1
    with pytest.raises(ValueError) as caught:
        cycle(book, T + MINUTE, signals=[changed])
    assert str(caught.value) == "conflicting signal UID"
    assert _counts(book.db) == before
