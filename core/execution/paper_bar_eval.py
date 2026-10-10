"""Evaluate paper-book sleeves once, on the first poll after the bar closes.

On SGP1 a cycle runs for about 0.5-1 minute and the next cycle starts about
15.5 minutes later. ``MAX_CANDLE_LATENCY`` is 15 minutes, so a 15m close that
lands while the cycle body has the poll paused is already outside the window
by the next cycle, and the order never happens. The same window drops a 1h
or 4h close the cycle walks past. The 15s paper poll already runs exit
supervision and F111. Every paper sleeve whose clock ``normalise_timeframe``
accepts joins that poll: 15m, 1h, 4h, and any other timeframe in the
``family:SYMBOL:SIDE:TF`` key.

Rules this module is not allowed to break:

- One evaluation per closed bar per sleeve (symbol, timeframe, side, strategy).
- The cursor is on disk, so a restart does not evaluate that bar again.
- A restart may catch up only the current closed bar, and only while it is
  still inside the latency window. Older bars are never replayed.
- The 900s cycle still runs the pipeline, seats, and walk-forward refills.
  It must not evaluate a bar this poll already handled.
- Signals, sit-out gates, risk, sizing, and the approval book are unchanged.
- No employee seat and no model call. This is the hot path.
- Paper only. Live and a set go-live phrase do not enter here.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from config.settings import PROJECT_ROOT, TradingMode, get_settings
from core.data.ohlcv import TIMEFRAME_DELTAS, closed_candles, normalise_timeframe
from core.execution.paper import PaperBroker
from core.strategy.base import Signal

logger = logging.getLogger(__name__)

#: Next to the other paper runtime files (cash, kill switch, F111 state).
#: On SGP1 this is whatever directory ``data/`` is mounted to.
PAPER_BAR_STATE_PATH = PROJECT_ROOT / "data" / "paper_bar_eval_state.json"

#: The exit poll is 15s and also runs F111. Leave the rest of the slice for
#: stop supervision. Sleeves that do not fit are taken by the next poll,
#: still inside the 15-minute latency window.
PAPER_POLL_BUDGET_SECONDS = 8.0

_STATE_VERSION = 1


def _engine_mod():
    """Late import so the engine can call back into this module."""
    from core.execution import engine as engine_mod

    return engine_mod


def _clock() -> datetime:
    """Same clock ``_evaluate`` uses. Tests freeze ``engine._now``."""
    return _engine_mod()._now()


def _as_utc(value: datetime | object) -> datetime:
    return _engine_mod()._as_utc(value)


def _latency() -> timedelta:
    return _engine_mod().MAX_CANDLE_LATENCY


def sleeve_key(entry: Any) -> str:
    """Identity of one paper sleeve: symbol, timeframe, side, sleeve id."""
    side = entry.side.value if hasattr(entry.side, "value") else str(entry.side)
    return f"{entry.symbol}|{entry.timeframe}|{side}|{entry.strategy.name}"


def is_known_timeframe(timeframe: str) -> bool:
    """True when this sleeve clock is a bar size we can align to a close.

    The approval key is ``family:SYMBOL:SIDE:TF``. 15m, 1h, and 4h are on
    the book; every other label ``normalise_timeframe`` accepts (including
    legacy spellings such as ``15min``) uses the same once-per-close path.
    An unknown label returns False and the cycle scan keeps it.
    """
    try:
        normalise_timeframe(timeframe)
    except (TypeError, ValueError):
        return False
    return True


def last_closed_bar_open(now: datetime, timeframe: str) -> datetime:
    """Open time of the most recent fully closed bar.

    A 15m bar that closes at 12:15 opened at 12:00. A 1h bar that closes at
    12:00 opened at 11:00. A 4h bar that closes at 12:00 opened at 08:00.
    One second before the boundary, that bar is still forming and the
    previous close is the one we mean.
    """
    now = _as_utc(now)
    step = TIMEFRAME_DELTAS[normalise_timeframe(timeframe)]
    step_s = int(step.total_seconds())
    epoch = int(now.timestamp())
    boundary = (epoch // step_s) * step_s
    return datetime.fromtimestamp(boundary - step_s, tz=timezone.utc)


def bar_is_actionable(now: datetime, timeframe: str, bar_open: datetime) -> bool:
    """Same window ``_evaluate`` uses: closed, and not older than 15 minutes.

    ``now == close + 15min`` is still inside. One second later is not.
    """
    now = _as_utc(now)
    bar_open = _as_utc(bar_open)
    step = TIMEFRAME_DELTAS[normalise_timeframe(timeframe)]
    close_at = bar_open + step
    if now < close_at:
        return False
    if now > close_at + _latency():
        return False
    return True


def _same_instant(left: datetime, right: datetime) -> bool:
    return int(_as_utc(left).timestamp()) == int(_as_utc(right).timestamp())


def paper_bar_eval_enabled(engine: Any) -> bool:
    """Paper broker, paper mode, go-live phrase unset.

    Live and testnet keep the cycle path. A paper broker with the live
    phrase set is treated as armed and does not take this shortcut.
    """
    if not isinstance(getattr(engine, "broker", None), PaperBroker):
        return False
    settings = get_settings()
    if settings.trading_mode is not TradingMode.PAPER:
        return False
    if str(getattr(settings, "go_live_confirmed", "") or ""):
        return False
    return True


def _entries_blocked(engine: Any) -> bool:
    """Kill switch is an entry gate. Do not burn the bar while it is tripped.

    A MagicMock ``is_tripped`` is not ``True``. Only a real tripped switch
    blocks, so test doubles that are not a kill switch stay out of the way.
    """
    risk = getattr(engine, "risk", None)
    switch = getattr(risk, "kill_switch", None)
    if switch is None:
        return False
    return getattr(switch, "is_tripped", False) is True


class ClosedBarCandleCache:
    """One fetch per symbol and timeframe for the bar that just closed.

    A poll in the middle of the hour does not call this: nothing is due.
    A second sleeve on the same symbol and clock reuses the frame. A frame
    that does not yet contain the closed bar is not stored, so the next
    poll can refetch once the exchange has published it.
    """

    def __init__(self) -> None:
        self._frames: dict[tuple[str, str], tuple[str, Any]] = {}
        self.fetches = 0

    def fetch(self, inner: Any, symbol: str, timeframe: str, bars: int, now: datetime) -> Any:
        timeframe = normalise_timeframe(timeframe)
        expected = last_closed_bar_open(now, timeframe)
        key = (symbol, timeframe)
        iso = expected.isoformat()
        hit = self._frames.get(key)
        if hit is not None and hit[0] == iso and len(hit[1]) >= bars:
            return hit[1]
        self.fetches += 1
        frame = inner.fetch_latest(symbol, timeframe, bars=bars)
        closed = closed_candles(frame, timeframe, now=now)
        if (
            not closed.empty
            and _same_instant(_as_utc(closed.index[-1]), expected)
            and len(frame) >= bars
        ):
            self._frames[key] = (iso, frame)
        return frame


class _CachingFeed:
    """Route ``_evaluate``'s fetches through the closed-bar cache."""

    def __init__(self, inner: Any, cache: ClosedBarCandleCache, now: datetime) -> None:
        self._inner = inner
        self._cache = cache
        self._now = now

    def fetch_latest(self, symbol: str, timeframe: str, bars: int = 300) -> Any:
        return self._cache.fetch(self._inner, symbol, timeframe, bars, self._now)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class BarEvalState:
    """Last evaluated bar open per sleeve. Atomic replace, version 1.

    A missing file is an empty cursor. A corrupt file or a future version
    refuses to evaluate: guessing would either double-order or skip a live bar.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.sleeves: dict[str, dict[str, Any]] = {}
        self._loaded = False
        self._broken = False
        self._waiting_logged: set[str] = set()
        self._sitout_logged: set[str] = set()

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._broken = True
            logger.error(
                "paper bar state at %s is unreadable (%s); not evaluating until it is fixed",
                self.path,
                exc,
            )
            return
        if int(payload.get("version") or 0) != _STATE_VERSION:
            self._broken = True
            logger.error(
                "paper bar state version at %s is not %s; not evaluating",
                self.path,
                _STATE_VERSION,
            )
            return
        sleeves = payload.get("sleeves") or {}
        self.sleeves = dict(sleeves) if isinstance(sleeves, dict) else {}

    @property
    def broken(self) -> bool:
        self.load()
        return self._broken

    def seen(self, key: str, bar_open: datetime) -> bool:
        self.load()
        row = self.sleeves.get(key)
        if not isinstance(row, dict):
            return False
        recorded = row.get("bar_open")
        return recorded == _as_utc(bar_open).isoformat()

    def mark(self, key: str, bar_open: datetime, *, signal: str, reason: str) -> None:
        """Persist before the caller returns so a crash cannot repeat the bar."""
        self.load()
        self.sleeves[key] = {
            "bar_open": _as_utc(bar_open).isoformat(),
            "evaluated_at": _as_utc(_clock()).isoformat(),
            "signal": signal,
            "reason": reason,
        }
        self._persist()

    def _persist(self) -> None:
        payload = {"version": _STATE_VERSION, "sleeves": self.sleeves}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, self.path)


def _state(engine: Any) -> BarEvalState:
    path = getattr(engine, "paper_bar_state_path", None) or PAPER_BAR_STATE_PATH
    current = getattr(engine, "_paper_bar_state", None)
    if current is None or current.path != Path(path):
        current = BarEvalState(Path(path))
        engine._paper_bar_state = current
    return current


def _cache(engine: Any) -> ClosedBarCandleCache:
    cache = getattr(engine, "_paper_bar_candles", None)
    if cache is None:
        cache = ClosedBarCandleCache()
        engine._paper_bar_candles = cache
    return cache


def _order_symbol(order: Any) -> str:
    if isinstance(order, dict):
        return str(order.get("symbol") or "")
    return str(getattr(order, "symbol", "") or "")


def _reduce_only(order: Any) -> bool:
    if isinstance(order, dict):
        return bool(order.get("reduce_only") or order.get("reduceOnly"))
    return bool(getattr(order, "reduce_only", False) or getattr(order, "reduceOnly", False))


def duplicate_order_block(engine: Any, entry: Any) -> GuardResult:
    """Refuse a second entry while this symbol already has a position or order.

    Risk already blocks a second position. This runs first so a retry after
    a crash (cursor not saved, position already open) cannot call the broker
    again. An unreadable book fails closed and does not mark the bar, so the
    next poll can try while the window is still open.
    """
    symbol = entry.symbol
    try:
        positions = engine.broker.get_positions() or []
    except Exception:
        logger.exception("paper bar eval could not read broker positions for %s", symbol)
        return GuardResult(uncertain=True)
    for position in positions:
        if getattr(position, "symbol", None) == symbol:
            return GuardResult(reason=f"duplicate open position {symbol}")
    try:
        row = engine.ledger.find_open_position(symbol)
    except Exception:
        logger.exception("paper bar eval could not read the ledger for %s", symbol)
        return GuardResult(uncertain=True)
    if row is not None:
        return GuardResult(reason=f"duplicate open position {symbol}")
    getter = getattr(engine.broker, "get_open_orders", None)
    if not callable(getter):
        return GuardResult()
    try:
        orders = getter(symbol) or []
    except TypeError:
        try:
            orders = getter() or []
        except Exception:
            logger.exception("paper bar eval could not read open orders for %s", symbol)
            return GuardResult(uncertain=True)
    except Exception:
        logger.exception("paper bar eval could not read open orders for %s", symbol)
        return GuardResult(uncertain=True)
    for order in orders:
        if _reduce_only(order):
            continue
        if _order_symbol(order) == symbol:
            return GuardResult(reason=f"duplicate open order {symbol}")
    return GuardResult()


@dataclass
class GuardResult:
    """``uncertain`` means the book could not be read. Do not order and do not mark."""

    reason: str | None = None
    uncertain: bool = False


@dataclass
class PaperBarOutcome:
    """What the cycle should do with one sleeve after the fast path looked."""

    handled: bool
    signal: Signal | None = None
    price: float | None = None
    ordered: bool = False
    rejection: str | None = None
    error: str | None = None
    #: True only after the cursor for this bar was written.
    evaluated: bool = False
    #: Closed-bar open and the flat/reject reason. The Inbox diary reads
    #: these. They do not change whether the bar was traded.
    bar_open: datetime | None = None
    reason: str = ""


def _flat_reason(strategy: Any, signal: Signal | None) -> str:
    raw = getattr(strategy, "_last_eval_reason", None)
    if isinstance(raw, str) and raw.strip():
        if signal is None:
            return raw.strip()
        return (signal.reason or raw).strip() or "signal"
    if signal is None:
        return "no_signal"
    return (signal.reason or "signal").strip() or "signal"


def _log_eval(
    entry: Any, bar_open: datetime, signal: Signal | None, reason: str, source: str
) -> None:
    logger.info(
        "paper bar eval sleeve=%s bar=%s signal=%s reason=%s source=%s",
        sleeve_key(entry),
        _as_utc(bar_open).isoformat(),
        "none" if signal is None else signal.side.value,
        reason,
        source,
    )


def _published_bar(frame: Any, timeframe: str, now: datetime) -> datetime | None:
    closed = closed_candles(frame, timeframe, now=now)
    if closed.empty:
        return None
    return _as_utc(closed.index[-1])


def _evaluate_published(
    engine: Any,
    entry: Any,
    *,
    equity: float,
    marks: dict[str, float],
    source: str,
    expected: datetime,
) -> PaperBarOutcome:
    """Run the existing evaluator on the just-closed bar, then remember it.

    The strategy, sit-out gate, risk engine, and sizer are the ones
    ``run_cycle`` already uses. This function only decides whether this bar
    still needs that work.
    """
    state = _state(engine)
    cache = _cache(engine)
    now = _clock()
    bars = int(entry.strategy.min_bars) + 50
    original = engine._data
    try:
        frame = cache.fetch(original, entry.symbol, entry.timeframe, bars, now)
        published = _published_bar(frame, entry.timeframe, now)
        if published is None or not _same_instant(published, expected):
            token = f"{sleeve_key(entry)}|{expected.isoformat()}"
            if token not in state._waiting_logged:
                state._waiting_logged.add(token)
                logger.info(
                    "paper bar waiting sleeve=%s bar=%s reason=candle_not_published",
                    sleeve_key(entry),
                    expected.isoformat(),
                )
            # Not marked. The next poll retries until the window closes.
            return PaperBarOutcome(handled=True, rejection=None)
        engine._data = _CachingFeed(original, cache, now)
        signal, price, reason, bar_open = engine._evaluate_detail(entry)
    except Exception as exc:
        logger.warning("paper bar eval failed for %s: %s", sleeve_key(entry), exc)
        return PaperBarOutcome(handled=True, error=f"{entry.key}: {exc}")
    finally:
        engine._data = original

    if bar_open is None or not _same_instant(bar_open, expected):
        return PaperBarOutcome(handled=True)
    if not bar_is_actionable(now, entry.timeframe, bar_open):
        return PaperBarOutcome(handled=True)

    ordered = False
    rejection: str | None = None
    if signal is not None:
        block = duplicate_order_block(engine, entry)
        if block.uncertain:
            # Do not mark. The next poll can still take the bar. Do not
            # hand the signal back to the cycle or it would count an order
            # that was not attempted.
            return PaperBarOutcome(
                handled=True,
                error=f"{entry.key}: open book unreadable",
            )
        if block.reason:
            reason = block.reason
            rejection = block.reason
        else:
            decision = engine._attempt_entry(signal, equity, marks)
            if decision.is_approved:
                ordered = True
                reason = signal.reason or reason or "signal"
            else:
                rejection = "; ".join(decision.reasons) or "rejected"
                reason = rejection
    else:
        reason = reason or _flat_reason(entry.strategy, None)

    if price is not None:
        marks[entry.symbol] = price
    state.mark(
        sleeve_key(entry),
        bar_open,
        signal="none" if signal is None else signal.side.value,
        reason=reason,
    )
    _log_eval(entry, bar_open, signal, reason, source)
    return PaperBarOutcome(
        handled=True,
        signal=signal,
        price=price,
        ordered=ordered,
        rejection=rejection,
        evaluated=True,
        bar_open=bar_open,
        reason=reason,
    )


def cycle_paper_bar(
    engine: Any,
    entry: Any,
    *,
    equity: float,
    marks: dict[str, float],
) -> PaperBarOutcome:
    """Cycle hook. ``handled=False`` means the existing scan path should run.

    A bar the poll already stored is handled and skipped. A bar that is not
    inside the latency window is left to ``_evaluate``, which still refuses
    to trade it and still reports a dead feed. A due bar is evaluated here
    so a cycle that lands inside the window does the work exactly once.
    """
    if not paper_bar_eval_enabled(engine) or not is_known_timeframe(entry.timeframe):
        return PaperBarOutcome(handled=False)
    if _entries_blocked(engine):
        return PaperBarOutcome(handled=False)
    state = _state(engine)
    if state.broken:
        return PaperBarOutcome(handled=True, error=f"{entry.key}: paper bar state unreadable")
    now = _clock()
    expected = last_closed_bar_open(now, entry.timeframe)
    # Seen wins over the window. After the 15 minutes the old scan would
    # still load candles and no-op; that is a second look at a bar the poll
    # already finished.
    if state.seen(sleeve_key(entry), expected):
        return PaperBarOutcome(handled=True)
    if not bar_is_actionable(now, entry.timeframe, expected):
        return PaperBarOutcome(handled=False)
    sitout = _engine_mod().paper_regime_sitout_reason(entry)
    if sitout:
        # Same gate as the cycle. Do not mark: if the feed clears before the
        # window ends, a later poll may still take the bar.
        return PaperBarOutcome(handled=False)
    return _evaluate_published(
        engine, entry, equity=equity, marks=marks, source="cycle", expected=expected
    )


def poll_paper_book(
    engine: Any,
    *,
    budget_seconds: float = PAPER_POLL_BUDGET_SECONDS,
    monotonic: Callable[[], float] | None = None,
) -> int:
    """Evaluate each due paper sleeve once for its latest closed bar.

    The clock comes from the sleeve (15m, 1h, 4h, or any other known
    timeframe). Returns how many bars were newly evaluated. No-op unless
    this process is an unarmed paper broker. Stops when the budget is spent;
    the next 15s poll continues. Does not call a seat or a model.
    """
    if not paper_bar_eval_enabled(engine):
        return 0
    if _entries_blocked(engine):
        return 0
    state = _state(engine)
    if state.broken:
        return 0
    clock = monotonic or time.monotonic
    deadline = clock() + max(0.0, float(budget_seconds))
    notes: list[dict[str, Any]] = []
    try:
        equity = float(engine.broker.get_balance())
    except Exception:
        logger.exception("paper bar poll could not read equity; skipping this poll")
        return 0
    marks: dict[str, float] = {}
    try:
        evaluated = _poll_due_sleeves(
            engine,
            state=state,
            clock=clock,
            deadline=deadline,
            budget_seconds=budget_seconds,
            equity=equity,
            marks=marks,
            notes=notes,
        )
    finally:
        # The diary is written even when a later sleeve raises. The flush
        # itself cannot raise, so it does not hide that sleeve's error.
        _flush_book_notes(notes)
    return evaluated


def _poll_due_sleeves(
    engine: Any,
    *,
    state: BarEvalState,
    clock: Callable[[], float],
    deadline: float,
    budget_seconds: float,
    equity: float,
    marks: dict[str, float],
    notes: list[dict[str, Any]],
) -> int:
    """The poll body. Split out so the Inbox flush runs in a finally."""
    evaluated = 0
    refreshed = False
    for entry in list(engine.plan.entries):
        if clock() >= deadline:
            logger.info(
                "paper bar poll budget %.1fs exhausted; remaining sleeves wait for the next poll",
                budget_seconds,
            )
            break
        # Who is eligible is already decided: ``plan.entries`` is the approved
        # book plus the paper-override path. Regime sit-out is applied below.
        # This loop only decides which closed bar is due.
        if not is_known_timeframe(entry.timeframe):
            continue
        now = _clock()
        expected = last_closed_bar_open(now, entry.timeframe)
        if not bar_is_actionable(now, entry.timeframe, expected):
            continue
        if state.seen(sleeve_key(entry), expected):
            continue
        sitout = _engine_mod().paper_regime_sitout_reason(entry)
        if sitout:
            token = f"{sleeve_key(entry)}|{expected.isoformat()}"
            if token not in state._sitout_logged:
                state._sitout_logged.add(token)
                logger.info(
                    "paper bar eval sleeve=%s bar=%s signal=none reason=%s source=poll",
                    sleeve_key(entry),
                    expected.isoformat(),
                    sitout,
                )
            _remember_book_note(notes, entry, expected, signal=False, ordered=False, rejection=sitout)
            continue
        if not refreshed:
            # Same overlay the cycle applies. The positioning module caches it.
            engine._refresh_crowding()
            refreshed = True
            if clock() >= deadline:
                logger.info(
                    "paper bar poll budget %.1fs exhausted; remaining sleeves wait",
                    budget_seconds,
                )
                break
        outcome = _evaluate_published(
            engine, entry, equity=equity, marks=marks, source="poll", expected=expected
        )
        if outcome.evaluated:
            evaluated += 1
            _remember_book_note(
                notes,
                entry,
                outcome.bar_open or expected,
                signal=outcome.signal is not None,
                ordered=outcome.ordered,
                rejection=_note_rejection(outcome),
            )
    return evaluated


def _bar_close_iso(entry: Any, bar_open: datetime) -> str:
    step = TIMEFRAME_DELTAS[normalise_timeframe(entry.timeframe)]
    return _as_utc(bar_open + step).isoformat()


def _note_rejection(outcome: PaperBarOutcome) -> str:
    """Rejection text for the diary. An order is not a rejection."""
    if outcome.ordered:
        return ""
    if outcome.rejection:
        return outcome.rejection
    if outcome.signal is not None:
        return ""
    return outcome.reason or "no_signal"


def _remember_book_note(
    notes: list[dict[str, Any]],
    entry: Any,
    bar_open: datetime,
    *,
    signal: bool,
    ordered: bool,
    rejection: str,
) -> None:
    try:
        from firm.scan_inbox import remember_scan_note

        remember_scan_note(
            notes,
            sleeve_id=sleeve_key(entry),
            bar_time=_bar_close_iso(entry, bar_open),
            signal=signal,
            ordered=ordered,
            rejection=rejection,
        )
    except Exception:
        logger.exception("Book scan note failed; the evaluation stands")


def _flush_book_notes(notes: list[dict[str, Any]]) -> None:
    if not notes:
        return
    try:
        from firm.scan_inbox import publish_book_notes

        publish_book_notes(notes)
    except Exception:
        logger.exception("Book scan summary was not written; trading is unchanged")
