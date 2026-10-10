"""F111 paper lifecycle: retests, protection, registry scan, and telemetry.

The trading engine fills hourly signals immediately. F111 does not use that
path. This module is called from the existing paper loop's exit poll so the
decision itself does not wait on an agent or an LLM. It never starts a second
worker and it never resets cash.

Forward quotes can exit earlier than the research minute-open tape because the
existing 15-second paper poll still enforces the stop that is already
effective. The minute-open simulator in ``f111_semantics`` remains the fixture
for gap and stop/target order. See the versioned config field
``execution_differences_vs_research_tape``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from core.data.bybit_linear_instruments import (
    AVAILABLE,
    UNAVAILABLE,
    InstrumentStatus,
    fetch_registry,
)
from core.execution.broker import Instrument
from core.strategy.f111_config import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    TELEMETRY_FIELDS,
    assert_f111_paper_only,
    assert_not_a_second_worker,
    cohort_of,
    load_f111_config,
    scan_enabled,
)
from core.strategy.f111_semantics import (
    RESEARCH_FEE,
    RESEARCH_SLIP,
    REASON_INITIAL_STOP,
    REASON_PROTECTED_STOP,
    REASON_TARGET,
    floor_move,
    gate_decision,
    new_protection_state,
    research_exit_price,
    signed_extension,
    step_protection,
    update_touch,
)

logger = logging.getLogger(__name__)

# A registry census row is not an hourly signal, so it has no source_signal_id.
# gate=False still needs a string. None used to be logged as False because the
# line did `rejection_reason or gate_decision`.
NO_SIGNAL_REASON = "no_signal"
# Parent names that must survive a null extension. missing_feature is not one
# of them: it means the feature was actually absent.
_KEPT_PARENT_REASONS = frozenset(
    {
        "high_vol_filter",
        "compression_gate",
        "extension_gate",
        "base_signal_blocked",
    }
)

_REASON_NAME = {
    REASON_INITIAL_STOP: "initial_stop",
    REASON_PROTECTED_STOP: "protected_stop",
    REASON_TARGET: "target",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bar_open_utc(stamp: Any) -> datetime:
    """Hourly index label as a UTC bar open. Naive stamps are UTC."""
    if getattr(stamp, "tzinfo", None) is None:
        opened = stamp.to_pydatetime().replace(tzinfo=timezone.utc)
    else:
        opened = stamp.to_pydatetime().astimezone(timezone.utc)
    return opened


def _drop_unclosed_hourly(frame: Any, now: datetime) -> Any:
    """Drop every trailing hourly bar that is still forming.

    A bar is closed only when its open plus one hour is at or before ``now``.
    ``closed_candles`` removes a single trailing bar. Two unclosed bars, or a
    last bar whose close is still ahead of ``now``, must not become the signal.
    """
    if frame is None or len(frame) == 0:
        return frame
    moment = _as_utc(now)
    end = len(frame)
    while end > 0:
        if _bar_open_utc(frame.index[end - 1]) + timedelta(hours=1) <= moment:
            break
        end -= 1
    return frame.iloc[:end]


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    return _as_utc(parsed)


def _signal_id(symbol: str, side: str, t0: datetime) -> str:
    raw = f"{STRATEGY_ID}|{symbol}|{side}|{_iso(t0)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def retire_hourly_entry_records(book: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Turn superseded hourly ENTRY sleeves off.

    The returned book is the scan book. Open positions are not in it, so
    removing a row does not close or convert a position. Exit supervision is
    the paper broker poll, which keys off the open position rather than the
    scan plan.
    """
    from core.strategy.f111_config import RETIRED_ENTRY_SLEEVES

    if not isinstance(book, dict):
        raise ValueError("approval book must be an object")
    kept: dict[str, Any] = {}
    removed: list[str] = []
    for key, value in book.items():
        if not isinstance(value, dict):
            kept[key] = value
            continue
        strategy = str(value.get("strategy") or str(key).split(":")[0])
        active = bool(value.get("paper_override") or value.get("approved"))
        if strategy in RETIRED_ENTRY_SLEEVES and active:
            removed.append(str(key))
            continue
        if strategy == STRATEGY_ID:
            # F111 is not an engine-plan sleeve. A hand-added approval would
            # immediate-fill the hourly close.
            removed.append(str(key))
            continue
        kept[key] = value
    return kept, removed


def _blank_event(config_sha: str, run_id: str) -> dict[str, Any]:
    row = {field: None for field in TELEMETRY_FIELDS}
    row["strategy_version"] = STRATEGY_VERSION
    row["configuration_sha256"] = config_sha
    row["run_id"] = run_id
    row["gate_decision"] = False
    row["missing_candle_or_quote"] = False
    row["instrument_unavailable"] = False
    return row


class F111Runtime:
    """Persistent pending retests and monotone protection for one paper process."""

    def __init__(
        self,
        *,
        config: dict[str, Any] | None = None,
        config_sha: str | None = None,
        state_path: Path | None = None,
        telemetry_path: Path | None = None,
        disable_flag: Path | None = None,
        broker: Any = None,
        risk: Any = None,
        ledger: Any = None,
        engine: Any = None,
        clock: Callable[[], datetime] | None = None,
        run_id: str | None = None,
    ) -> None:
        loaded, digest = load_f111_config()
        self.config = config or loaded
        self.config_sha = config_sha or digest
        self.state_path = state_path
        self.telemetry_path = telemetry_path
        self.disable_flag = disable_flag
        self.broker = broker
        self.risk = risk
        self.ledger = ledger
        self.engine = engine
        self.clock = clock or _utcnow
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self.registry: dict[str, InstrumentStatus] = {}
        self.pending: list[dict[str, Any]] = []
        self.protection: dict[str, dict[str, Any]] = {}
        self.last_exit: dict[str, str] = {}
        self.seen_signals: list[str] = []
        self.events: list[dict[str, Any]] = []
        self.last_registry_at: datetime | None = None
        self.last_signal_hour: datetime | None = None
        stale = self.config.get("stale_action") or {}
        self.actionable_window = timedelta(seconds=int(stale.get("actionable_window_seconds") or 60))
        self.fee = float((self.config.get("paper_cost_reference") or {}).get("fee_each_notional_side") or RESEARCH_FEE)

    # -----------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------
    def restore(self) -> None:
        """Load pending retests and protection. A missing file is an empty book."""
        if self.state_path is None or not self.state_path.exists():
            return
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if int(payload.get("version") or 0) != 1:
            raise RuntimeError("F111 state version is not 1")
        self.pending = list(payload.get("pending") or [])
        self.protection = dict(payload.get("protection") or {})
        self.last_exit = dict(payload.get("last_exit") or {})
        self.seen_signals = list(payload.get("seen_signals") or [])

    def persist(self) -> None:
        """Atomic replace so a crash mid-write cannot drop a pending retest."""
        if self.state_path is None:
            return
        payload = {
            "version": 1,
            "config_sha256": self.config_sha,
            "strategy_version": STRATEGY_VERSION,
            "pending": self.pending,
            "protection": self.protection,
            "last_exit": self.last_exit,
            "seen_signals": self.seen_signals[-5000:],
        }
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_path)

    def _emit(self, row: dict[str, Any]) -> dict[str, Any]:
        # Repair before the log and the JSONL write so both carry the string.
        if row.get("gate_decision") is False and not _reason_text(row.get("rejection_reason")):
            row["rejection_reason"] = NO_SIGNAL_REASON
        self.events.append(row)
        if row.get("record_kind") == "registry":
            # Census rows are not gate decisions. The old line used
            # `rejection_reason or gate_decision`, so None or False printed
            # reason=False for every available sleeve.
            availability = "unavailable" if row.get("instrument_unavailable") else "available"
            logger.info(
                "F111 registry %s %s status=%s",
                row.get("symbol"),
                row.get("side"),
                availability,
            )
        elif row.get("deploy_marker"):
            logger.info(
                "F111 deploy_marker=%s configuration_sha256=%s strategy_version=%s run_id=%s",
                row.get("deploy_marker"),
                row.get("configuration_sha256"),
                row.get("strategy_version"),
                row.get("run_id"),
            )
        else:
            # Gate rows print the rejection string. Never substitute the bool.
            logger.info(
                "F111 %s %s %s gate=%s reason=%s",
                row.get("symbol"),
                row.get("side"),
                row.get("source_signal_id"),
                row.get("gate_decision"),
                row.get("rejection_reason"),
            )
        if self.telemetry_path is not None:
            self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
            with self.telemetry_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, default=str) + "\n")
        return row

    def note_restart(self) -> dict[str, Any]:
        """Write a restart boundary into telemetry.

        The verify script uses this row, or a new ``run_id``, as the start of
        the current deploy when it scopes the missing_feature share.
        """
        row = _blank_event(self.config_sha, self.run_id)
        row["deploy_marker"] = "restart"
        row["gate_decision"] = None
        row["rejection_reason"] = "restart"
        return self._emit(row)

    def entries_allowed(self) -> bool:
        return scan_enabled(self.config, self.disable_flag)

    # -----------------------------------------------------------------
    # Registry scan
    # -----------------------------------------------------------------
    def sleeve_rows(self, registry: list[InstrumentStatus]) -> list[dict[str, Any]]:
        """One explicit row for every supplied symbol and both sides.

        Unavailable instruments stay in the list. Nothing here substitutes a
        different ticker, and nothing here places an order.
        """
        by_symbol = {item.symbol: item for item in registry}
        rows: list[dict[str, Any]] = []
        for symbol in self.config["universe"]:
            status = by_symbol.get(symbol)
            if status is None:
                status = InstrumentStatus(
                    symbol=symbol,
                    availability=UNAVAILABLE,
                    reason="missing from registry",
                )
            self.registry[symbol] = status
            unavailable = status.availability != AVAILABLE
            for side in self.config["sides"]:
                row = _blank_event(self.config_sha, self.run_id)
                row.update(
                    {
                        "symbol": symbol,
                        "side": side,
                        "cohort": cohort_of(symbol, self.config),
                        "sector": _sector(symbol),
                        "record_kind": "registry",
                        "gate_decision": False,
                        # Available sleeves have no hourly signal on this census
                        # row. The JSONL still stores a string. source_signal_id
                        # stays unset: this is not a signal.
                        "rejection_reason": NO_SIGNAL_REASON if not unavailable else status.reason,
                        "instrument_unavailable": unavailable,
                        "feature_values": {
                            "availability": status.availability,
                            "reason": status.reason,
                            "exchange_status": status.exchange_status,
                            "tick_size": status.tick_size,
                            "qty_step": status.qty_step,
                            "min_qty": status.min_qty,
                            "min_notional": status.min_notional,
                            "returned_symbol": status.returned_symbol,
                            "evaluated": True,
                        },
                    }
                )
                rows.append(self._emit(row))
        expected = int(self.config["expected_scan_sleeves"])
        if len(rows) != expected:
            raise RuntimeError(f"F111 scan produced {len(rows)} sleeves, expected {expected}")
        return rows

    # -----------------------------------------------------------------
    # Signals and retests
    # -----------------------------------------------------------------
    def observe_signal(
        self,
        *,
        symbol: str,
        side: str,
        t0: datetime,
        boundary: float,
        prior_atr: float,
        close: float,
        compression: float,
        extension_atr: float,
        base_passed: bool,
        observed_at: datetime | None = None,
        features: dict[str, Any] | None = None,
        feature_asof: dict[str, Any] | None = None,
        sector: str | None = None,
    ) -> dict[str, Any]:
        """Record the original hourly decision. A pass opens one pending retest.

        Minutes that already closed before ``observed_at`` are not replayed.
        If this process is already late for t0, the signal is rejected.
        """
        assert_f111_paper_only()
        t0 = _as_utc(t0)
        observed = _as_utc(observed_at or self.clock())
        features = dict(features or {})
        sign = 1 if side == "LONG" else -1 if side == "SHORT" else 0
        if _finite_number(extension_atr) is None:
            filled = signed_extension(sign, close, boundary, prior_atr)
            if _finite_number(filled) is not None:
                extension_atr = float(filled)
        if _finite_number(extension_atr) is not None:
            features["extension_atr"] = float(extension_atr)
        passed, gate_reason = gate_decision(
            compression=compression,
            extension_atr=extension_atr,
            prior_atr=prior_atr,
            close=close,
        )
        if not base_passed and not gate_reason:
            gate_reason = "base_signal_blocked"
            passed = False
        elif not base_passed:
            passed = False
        # A null extension is optional once an earlier gate, or the parent
        # signal, already named the rejection. Do not replace that name.
        parent_reason = str(features.get("f111_rejection_reason") or "")
        if gate_reason == "missing_feature" and parent_reason in _KEPT_PARENT_REASONS:
            gate_reason = parent_reason
            passed = False
        row = self._signal_row(
            symbol=symbol,
            side=side,
            t0=t0,
            boundary=boundary,
            prior_atr=prior_atr,
            close=close,
            compression=compression,
            extension_atr=extension_atr,
            features=features,
            feature_asof=feature_asof,
            sector=sector,
        )
        signal_id = row["source_signal_id"]
        if not passed:
            row["gate_decision"] = False
            row["rejection_reason"] = gate_reason
            return self._emit(row)
        row["gate_decision"] = True
        if not self.entries_allowed():
            row["rejection_reason"] = "f111_scan_disabled"
            row["gate_decision"] = True
            return self._emit(row)
        status = self.registry.get(symbol)
        if status is not None and status.availability != AVAILABLE:
            row["instrument_unavailable"] = True
            row["rejection_reason"] = status.reason
            return self._emit(row)
        if signal_id in self.seen_signals:
            row["rejection_reason"] = "duplicate_signal"
            return self._emit(row)
        if observed > t0 + self.actionable_window:
            row["rejection_reason"] = "stale_signal_not_backfilled"
            row["poll_latency"] = (observed - t0).total_seconds()
            self.seen_signals.append(signal_id)
            return self._emit(row)
        # No opposite-signal cancellation: the other side's pending stays.
        self.seen_signals.append(signal_id)
        pending = {
            "symbol": symbol,
            "side": side,
            "sign": 1 if side == "LONG" else -1,
            "source_signal_id": signal_id,
            "source_signal_time": _iso(t0),
            "t0": _iso(t0),
            "expiry": _iso(t0 + timedelta(minutes=59)),
            "boundary": float(boundary),
            "prior_atr": float(prior_atr),
            "signal_close": float(close),
            "compression": float(compression),
            "extension_atr": float(extension_atr),
            "cohort": cohort_of(symbol, self.config),
            "sector": sector or _sector(symbol),
            "features": features or {},
            "feature_asof": feature_asof or {},
            "created_at": _iso(observed),
            "touched": False,
            "touch_time": None,
            "reclaim_time": None,
            "action_time": None,
            "next_minute": _iso(t0),
            "status": "watching",
        }
        self.pending.append(pending)
        row["pending_retest_created_at"] = pending["created_at"]
        row["pending_expiry"] = pending["expiry"]
        row["rejection_reason"] = None
        return self._emit(row)

    def observe_minute(
        self,
        *,
        symbol: str,
        minute: datetime,
        high: float | None,
        low: float | None,
        close: float | None,
        quote: float | None,
        quote_time: datetime | None,
        observed_at: datetime | None = None,
        funding_fraction: float | None = None,
        funding_source: str | None = None,
        funding_asof: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Advance one completed minute for pendings and any open F111 position.

        A missing bar rejects the pending. It is not filled from a neighbour.
        """
        assert_f111_paper_only()
        minute = _as_utc(minute)
        observed = _as_utc(observed_at or self.clock())
        events: list[dict[str, Any]] = []
        if symbol in self.protection:
            if not self._position_still_open(symbol):
                # The existing 15-second poll already closed this row.
                self.protection.pop(symbol, None)
                self.last_exit.setdefault(symbol, _iso(observed) or "")
            else:
                events.extend(
                    self._advance_protection(
                        symbol,
                        minute,
                        quote,
                        quote_time,
                        observed,
                        funding_fraction,
                        funding_source,
                        funding_asof,
                    )
                )
        for pending in list(self.pending):
            if pending["symbol"] != symbol or pending["status"] not in {"watching", "scheduled"}:
                continue
            events.extend(
                self._advance_pending(
                    pending,
                    minute,
                    high,
                    low,
                    close,
                    quote,
                    quote_time,
                    observed,
                    funding_fraction,
                    funding_source,
                )
            )
        return events

    def _advance_pending(
        self,
        pending: dict[str, Any],
        minute: datetime,
        high: float | None,
        low: float | None,
        close: float | None,
        quote: float | None,
        quote_time: datetime | None,
        observed: datetime,
        funding_fraction: float | None,
        funding_source: str | None,
    ) -> list[dict[str, Any]]:
        expected = _parse_time(pending["next_minute"])
        assert expected is not None
        if minute < expected:
            return []
        if minute > expected:
            return [self._reject_pending(pending, "missing_candle_or_quote", missing=True, observed=observed)]
        if pending["status"] == "scheduled":
            action = _parse_time(pending["action_time"])
            if action is not None and minute == action:
                return [
                    self._try_fill(
                        pending,
                        quote,
                        quote_time,
                        observed,
                        funding_fraction,
                        funding_source,
                    )
                ]
            if action is not None and minute > action:
                return [self._reject_pending(pending, "stale_action", observed=observed, action=action)]
            return []
        # Watching a confirmation minute. The bar's own OHLC is required.
        if high is None or low is None or close is None:
            return [self._reject_pending(pending, "missing_candle_or_quote", missing=True, observed=observed)]
        try:
            touched, reclaim = update_touch(
                int(pending["sign"]), float(high), float(low), float(close), float(pending["boundary"]), bool(pending["touched"])
            )
        except ValueError:
            return [self._reject_pending(pending, "missing_candle_or_quote", missing=True, observed=observed)]
        pending["touched"] = touched
        if touched and pending["touch_time"] is None:
            pending["touch_time"] = _iso(minute)
        row = self._row_from_pending(pending)
        row["touch_time"] = pending["touch_time"]
        row["quote_time"] = _iso(quote_time)
        row["reference_price"] = close
        if reclaim:
            pending["reclaim_time"] = _iso(minute)
            pending["action_time"] = _iso(minute + timedelta(minutes=1))
            pending["status"] = "scheduled"
            pending["next_minute"] = pending["action_time"]
            row["reclaim_time"] = pending["reclaim_time"]
            row["action_time"] = pending["action_time"]
            row["gate_decision"] = True
            row["rejection_reason"] = None
            return [self._emit(row)]
        expiry = _parse_time(pending["expiry"])
        pending["next_minute"] = _iso(minute + timedelta(minutes=1))
        if expiry is not None and minute >= expiry:
            reason = "no_reclaim" if pending["touched"] else "no_touch"
            return [self._reject_pending(pending, reason, observed=observed)]
        row["gate_decision"] = True
        row["rejection_reason"] = None
        row["pending_expiry"] = pending["expiry"]
        return [self._emit(row)]

    def _try_fill(
        self,
        pending: dict[str, Any],
        quote: float | None,
        quote_time: datetime | None,
        observed: datetime,
        funding_fraction: float | None,
        funding_source: str | None,
    ) -> dict[str, Any]:
        action = _parse_time(pending["action_time"])
        assert action is not None
        latency = (observed - action).total_seconds()
        opposite = [
            other
            for other in self.pending
            if other is not pending
            and other["symbol"] == pending["symbol"]
            and other["status"] == "scheduled"
            and other["action_time"] == pending["action_time"]
        ]
        if opposite:
            self._reject_pending(opposite[0], "simultaneous_opposite_entries", observed=observed, action=action)
            return self._reject_pending(pending, "simultaneous_opposite_entries", observed=observed, action=action)
        if quote is None or quote_time is None or not _finite_price(quote):
            return self._reject_pending(pending, "missing_candle_or_quote", missing=True, observed=observed, action=action)
        quote_time = _as_utc(quote_time)
        if quote_time < action or observed > action + self.actionable_window:
            return self._reject_pending(pending, "stale_action", observed=observed, action=action)
        symbol = pending["symbol"]
        exit_at = _parse_time(self.last_exit.get(symbol))
        if exit_at is not None and action <= exit_at:
            return self._reject_pending(
                pending, "same_timestamp_reentry", observed=observed, action=action, risk=True
            )
        if self._symbol_occupied(symbol):
            return self._reject_pending(pending, "position_already_open", observed=observed, action=action, risk=True)
        veto = self._agent_veto(symbol)
        if veto:
            return self._reject_pending(pending, veto, observed=observed, action=action, risk=True)
        status = self.registry.get(symbol)
        if status is None or status.availability != AVAILABLE:
            reason = status.reason if status is not None else "instrument metadata not verified"
            row = self._reject_pending(pending, reason, observed=observed, action=action)
            row["instrument_unavailable"] = True
            return row
        if self.broker is None or self.risk is None:
            return self._reject_pending(
                pending, "paper broker or risk engine not attached", observed=observed, action=action, risk=True
            )
        side = pending["side"]
        sign = int(pending["sign"])
        atr = float(pending["prior_atr"])
        stop_price = quote - sign * 3.0 * atr
        target_price = quote + sign * 4.0 * atr
        from core.risk.engine import TradeIntent

        intent = TradeIntent(
            symbol=symbol,
            side=side,
            entry_price=float(quote),
            stop_price=float(stop_price),
            take_profit_price=float(target_price),
            strategy=STRATEGY_ID,
            score=1.0,
            sector=pending.get("sector") or _sector(symbol),
        )
        equity = float(self.broker.get_balance())
        decision = self.risk.evaluate(intent, self._portfolio(equity, {symbol: float(quote)}))
        multiplier = getattr(self.engine, "agent_size_multipliers", {}) if self.engine is not None else {}
        if decision.is_approved and symbol in multiplier:
            decision = self.risk.apply_agent_adjustment(decision, multiplier[symbol], agent="portfolio_manager")
        if not decision.is_approved:
            return self._reject_pending(
                pending,
                "; ".join(decision.reasons) or decision.verdict.value,
                observed=observed,
                action=action,
                risk=True,
            )
        self._install_instrument(status)
        result = self.broker.place_market_order(
            symbol=symbol,
            side=side,
            quantity=decision.quantity,
            expected_price=float(quote),
        )
        if not result.success:
            return self._reject_pending(
                pending,
                result.error or "order rejected",
                observed=observed,
                action=action,
                risk=True,
            )
        fill = float(result.fill_price or quote)
        brackets = new_protection_state(
            entry_price=fill,
            side=sign,
            prior_atr=atr,
            quantity=float(result.filled_quantity or decision.quantity),
            entry_fee=float(result.fee or 0.0),
        )
        stops_ok = self.broker.set_stops(symbol, brackets["target"], brackets["initial_stop"])
        if not stops_ok:
            self.broker.close_position(symbol)
            return self._reject_pending(pending, "stops_failed", observed=observed, action=action, risk=True)
        position_id = None
        if self.ledger is not None:
            position_id = self.ledger.open_position(
                symbol=symbol,
                side=side,
                quantity=brackets["quantity"],
                entry_price=fill,
                expected_entry_price=float(quote),
                take_profit=brackets["target"],
                stop_loss=brackets["initial_stop"],
                strategy=STRATEGY_ID,
                sector=pending.get("sector") or _sector(symbol),
                signal_score=1.0,
                signal_reason="F111 retest reclaim",
                broker_order_id=result.order_id or "",
                entry_fee=brackets["entry_fee"],
                execution_contract=self.config.get("execution_model_version") or "",
                strategy_params={"strategy_version": STRATEGY_VERSION, "configuration_sha256": self.config_sha},
                timeframe="1m",
                max_holding_bars=0,
            )
        brackets.update(
            {
                "position_id": position_id,
                "symbol": symbol,
                "side_name": side,
                "source_signal_id": pending["source_signal_id"],
                "source_signal_time": pending["source_signal_time"],
                "configured_stop": brackets["initial_stop"],
                "funding_source": funding_source,
                "funding_events": [] if funding_fraction is None else [
                    {"fraction": funding_fraction, "source": funding_source, "asof": _iso(observed)}
                ],
                "opened_at": _iso(observed),
            }
        )
        self.protection[symbol] = brackets
        pending["status"] = "filled"
        row = self._row_from_pending(pending)
        row.update(
            {
                "gate_decision": True,
                "rejection_reason": None,
                "action_time": pending["action_time"],
                "quote_time": _iso(quote_time),
                "reference_price": float(quote),
                "simulated_fill": fill,
                "fill_assumptions": {
                    "research_slip": RESEARCH_SLIP,
                    "research_fill": float(quote) * (1.0 + sign * RESEARCH_SLIP),
                    "forward_model": self.config.get("execution_model_version"),
                    "paper_slippage_is_modelled_not_measured_execution": True,
                    "funding_known_at_entry": funding_fraction is not None,
                    "funding_source": funding_source,
                },
                "original_ATR": atr,
                "original_risk_R_units": brackets["stop_return"],
                "initial_stop": brackets["initial_stop"],
                "target": brackets["target"],
                "configured_stop": brackets["initial_stop"],
                "entry_fee": brackets["entry_fee"],
                "poll_latency": latency,
                "occupancy_or_risk_rejection": None,
            }
        )
        return self._emit(row)

    def _advance_protection(
        self,
        symbol: str,
        minute: datetime,
        quote: float | None,
        quote_time: datetime | None,
        observed: datetime,
        funding_fraction: float | None,
        funding_source: str | None,
        funding_asof: datetime | None,
    ) -> list[dict[str, Any]]:
        state = self.protection.get(symbol)
        if state is None:
            return []
        row = self._row_from_protection(state)
        row["poll_latency"] = (observed - minute).total_seconds()
        row["quote_time"] = _iso(quote_time)
        if quote is None or not _finite_price(quote):
            row["missing_candle_or_quote"] = True
            row["rejection_reason"] = "missing_candle_or_quote"
            row["funding_events"] = state.get("funding_events")
            return [self._emit(row)]
        if funding_fraction is None:
            # Do not arm or tighten a floor on a substituted zero.
            row["missing_candle_or_quote"] = False
        else:
            events = list(state.get("funding_events") or [])
            events.append(
                {
                    "fraction": float(funding_fraction),
                    "source": funding_source,
                    "asof": _iso(funding_asof or observed),
                }
            )
            state["funding_events"] = events
            state["funding_source"] = funding_source
        updated, exit_row = step_protection(
            state,
            float(quote),
            funding_fraction=funding_fraction,
            fee=self.fee,
            sample_id=_iso(minute),
        )
        updated["funding_events"] = state.get("funding_events")
        updated["funding_source"] = state.get("funding_source")
        updated["position_id"] = state.get("position_id")
        updated["symbol"] = symbol
        updated["side_name"] = state.get("side_name")
        updated["source_signal_id"] = state.get("source_signal_id")
        updated["source_signal_time"] = state.get("source_signal_time")
        self.protection[symbol] = updated
        configured = float(updated["entry_price"]) * (1.0 + int(updated["side"]) * float(updated["effective_level"]))
        updated["configured_stop"] = configured
        self._publish_stop(symbol, updated, configured)
        row = self._row_from_protection(updated)
        row["reference_price"] = float(quote)
        row["quote_time"] = _iso(quote_time)
        row["poll_latency"] = (observed - minute).total_seconds()
        row["configured_stop"] = configured
        row["estimated_cost_aware_exit_value"] = _estimated_floor_price(updated, self.fee)
        row["funding_events"] = updated.get("funding_events")
        if exit_row is None:
            row["gate_decision"] = True
            row["rejection_reason"] = None if updated.get("funding_known") else "funding_missing"
            return [self._emit(row)]
        return [self._exit_position(symbol, updated, exit_row, quote_time, observed, minute)]

    def _exit_position(
        self,
        symbol: str,
        state: dict[str, Any],
        exit_row: dict[str, Any],
        quote_time: datetime | None,
        observed: datetime,
        minute: datetime,
    ) -> dict[str, Any]:
        reason = int(exit_row["reason"])
        quote = float(exit_row["quote"])
        sign = int(state["side"])
        # Research stop fills keep the sampled quote. Target fills pay exit slip
        # through the broker's market-close path (the forward CostModel, not a
        # second copy of the 20bps research slip on top of a stop).
        at_stop = reason in (REASON_INITIAL_STOP, REASON_PROTECTED_STOP)
        entry_fee = float(state.get("entry_fee") or 0.0)
        exit_fee = 0.0
        funding = 0.0
        realised = None
        fill_price = quote
        closed = None
        if self.broker is not None and symbol in getattr(self.broker, "_positions", {}):
            if at_stop:
                closed = self.broker.close_at_fill(symbol, quote, float(exit_row.get("configured_stop") or quote))
            else:
                # The market-close path reads the broker mark. Pin it to this
                # sample so a later tick cannot reorder the exit.
                prices = getattr(getattr(self.broker, "_data", None), "prices", None)
                if isinstance(prices, dict):
                    prices[symbol] = quote
                closed = self.broker.close_position(symbol)
            if not closed.success:
                row = self._row_from_protection(state)
                row["rejection_reason"] = closed.error or "close failed"
                row["occupancy_or_risk_rejection"] = row["rejection_reason"]
                return self._emit(row)
            fill_price = float(closed.fill_price or quote)
            exit_fee = float(closed.fee or 0.0)
            funding = float(closed.funding or 0.0)
        if self.ledger is not None and closed is not None and closed.success:
            position = self.ledger.find_open_position(symbol)
            if position is not None:
                self._settle_ledger_close(position, closed, at_stop, quote)
        if closed is not None and closed.success:
            # close_at_fill already moved cash by gross - exit fee. Entry fee
            # left cash at the open. Funding was accrued into cash earlier.
            direction = 1.0 if sign == 1 else -1.0
            gross = (fill_price - float(state["entry_price"])) * float(state["quantity"]) * direction
            realised = gross - entry_fee - exit_fee - funding
        self.protection.pop(symbol, None)
        self.last_exit[symbol] = _iso(observed) or ""
        research_price = research_exit_price(quote, sign, reason, RESEARCH_SLIP)
        row = self._row_from_protection(state)
        stop_return = float(state["stop_return"])
        net_return = None
        if realised is not None and state["entry_price"] and state["quantity"]:
            net_return = realised / (float(state["entry_price"]) * float(state["quantity"]))
        row.update(
            {
                "gate_decision": True,
                "rejection_reason": _REASON_NAME.get(reason, str(reason)),
                "quote_time": _iso(quote_time),
                "reference_price": quote,
                "simulated_fill": fill_price,
                "configured_stop": state.get("configured_stop"),
                "estimated_cost_aware_exit_value": _estimated_floor_price(state, self.fee),
                "realised_net_profit": realised,
                "entry_fee": entry_fee,
                "exit_fee": exit_fee,
                "funding_events": state.get("funding_events"),
                "net_R": (net_return / stop_return) if net_return is not None and stop_return else None,
                "poll_latency": (observed - minute).total_seconds(),
                "fill_assumptions": {
                    "reason": _REASON_NAME.get(reason, str(reason)),
                    "research_exit_price_at_20bps": research_price,
                    "forward_model": self.config.get("execution_model_version"),
                    "stop_uses_sampled_quote": at_stop,
                    "paper_slippage_is_modelled_not_measured_execution": True,
                },
            }
        )
        return self._emit(row)

    def _settle_ledger_close(self, position: Any, closed: Any, at_stop: bool, quote: float) -> None:
        """Write the ledger trade after the broker has already moved cash.

        ``close_at_fill`` journals cash. Calling the paper settler as well
        would apply that cash a second time, so this path only closes the
        SQLite row.
        """
        self.ledger.close_position(
            position_id=int(position.id),
            exit_price=float(closed.fill_price or quote),
            expected_exit_price=float(quote if at_stop else (closed.fill_price or quote)),
            exit_reason="stop_loss" if at_stop else "take_profit",
            entry_fees=float(getattr(position, "entry_fee", 0.0) or 0.0),
            exit_fees=float(closed.fee or 0.0),
            funding=float(closed.funding or 0.0),
        )

    def _position_still_open(self, symbol: str) -> bool:
        """True when the broker or the ledger still has the row.

        Protection state on its own is not a position. A pure in-memory test
        with no broker keeps stepping the state machine.
        """
        if self.broker is not None:
            return symbol in self.broker._positions
        if self.ledger is not None:
            return self.ledger.find_open_position(symbol) is not None
        return True

    def _publish_stop(self, symbol: str, state: dict[str, Any], configured: float) -> None:
        """Push only the effective stop. The just-decided floor waits a minute."""
        if self.broker is None:
            return
        position = self.broker._positions.get(symbol) if hasattr(self.broker, "_positions") else None
        if position is None:
            return
        current = position.stop_loss
        sign = int(state["side"])
        if current is not None:
            tighter = configured > float(current) + 1e-12 if sign == 1 else configured < float(current) - 1e-12
            if not tighter and abs(configured - float(current)) > 1e-12:
                # A looser price is ignored. Equality is left as-is.
                if (sign == 1 and configured < float(current)) or (sign == -1 and configured > float(current)):
                    return
        target = float(state["target"])
        self.broker.set_stops(symbol, target, configured)
        position_id = state.get("position_id")
        if self.ledger is not None and position_id is not None:
            self.ledger.update_open_stop(int(position_id), configured)

    def _reject_pending(
        self,
        pending: dict[str, Any],
        reason: str,
        *,
        missing: bool = False,
        observed: datetime | None = None,
        action: datetime | None = None,
        risk: bool = False,
    ) -> dict[str, Any]:
        pending["status"] = "rejected"
        pending["rejection_reason"] = reason
        row = self._row_from_pending(pending)
        row["gate_decision"] = True
        row["rejection_reason"] = reason
        row["missing_candle_or_quote"] = missing
        row["occupancy_or_risk_rejection"] = reason if risk else None
        if action is not None and observed is not None:
            row["poll_latency"] = (_as_utc(observed) - _as_utc(action)).total_seconds()
            row["action_time"] = _iso(action)
        return self._emit(row)

    def _symbol_occupied(self, symbol: str) -> bool:
        if self.broker is not None and symbol in getattr(self.broker, "_positions", {}):
            return True
        if self.ledger is not None and self.ledger.find_open_position(symbol) is not None:
            return True
        return symbol in self.protection

    def _agent_veto(self, symbol: str) -> str | None:
        vetoes = getattr(self.engine, "agent_vetoes", None) if self.engine is not None else None
        if not vetoes:
            return None
        reason = vetoes.get(symbol)
        return str(reason) if reason else None

    def _portfolio(self, equity: float, marks: dict[str, float]):
        if self.ledger is not None:
            return self.ledger.portfolio_state(equity, marks)
        from core.risk.engine import OpenPosition, PortfolioState

        positions = []
        for snap in self.broker.get_positions() if self.broker is not None else []:
            positions.append(
                OpenPosition(
                    symbol=snap.symbol,
                    side=snap.side,
                    quantity=snap.quantity,
                    entry_price=snap.entry_price,
                    notional=abs(snap.quantity * snap.entry_price),
                    sector=_sector(snap.symbol),
                )
            )
        return PortfolioState(equity=equity, peak_equity=max(equity, 0.0), open_positions=positions)

    def _install_instrument(self, status: InstrumentStatus) -> None:
        if self.broker is None or status.tick_size is None or status.qty_step is None or status.min_qty is None:
            return
        self.broker._instruments[status.symbol] = Instrument(
            symbol=status.symbol,
            tick_size=float(status.tick_size),
            qty_step=float(status.qty_step),
            min_qty=float(status.min_qty),
            min_notional=float(status.min_notional or 0.0),
        )

    def _signal_row(self, **kwargs: Any) -> dict[str, Any]:
        symbol = kwargs["symbol"]
        side = kwargs["side"]
        t0 = kwargs["t0"]
        row = _blank_event(self.config_sha, self.run_id)
        row.update(
            {
                "source_signal_id": _signal_id(symbol, side, t0),
                "source_signal_time": _iso(t0),
                "symbol": symbol,
                "cohort": cohort_of(symbol, self.config),
                "sector": kwargs.get("sector") or _sector(symbol),
                "side": side,
                "feature_values": {
                    "compression": kwargs["compression"],
                    "extension_atr": kwargs["extension_atr"],
                    "prior_atr": kwargs["prior_atr"],
                    "close": kwargs["close"],
                    "boundary": kwargs["boundary"],
                    **(kwargs.get("features") or {}),
                },
                "feature_asof_times": kwargs.get("feature_asof") or {"signal_close": _iso(t0)},
                "original_ATR": kwargs["prior_atr"],
                "reference_price": kwargs["close"],
            }
        )
        return row

    def _row_from_pending(self, pending: dict[str, Any]) -> dict[str, Any]:
        row = _blank_event(self.config_sha, self.run_id)
        row.update(
            {
                "source_signal_id": pending["source_signal_id"],
                "source_signal_time": pending["source_signal_time"],
                "symbol": pending["symbol"],
                "cohort": pending["cohort"],
                "sector": pending["sector"],
                "side": pending["side"],
                "feature_values": pending.get("features") or {},
                "feature_asof_times": pending.get("feature_asof") or {},
                "pending_retest_created_at": pending.get("created_at"),
                "touch_time": pending.get("touch_time"),
                "reclaim_time": pending.get("reclaim_time"),
                "pending_expiry": pending.get("expiry"),
                "action_time": pending.get("action_time"),
                "original_ATR": pending.get("prior_atr"),
                "gate_decision": True,
            }
        )
        return row

    def _row_from_protection(self, state: dict[str, Any]) -> dict[str, Any]:
        row = _blank_event(self.config_sha, self.run_id)
        sign = int(state["side"])
        row.update(
            {
                "source_signal_id": state.get("source_signal_id"),
                "source_signal_time": state.get("source_signal_time"),
                "symbol": state.get("symbol"),
                "cohort": cohort_of(str(state.get("symbol")), self.config),
                "sector": _sector(str(state.get("symbol"))),
                "side": state.get("side_name") or ("LONG" if sign == 1 else "SHORT"),
                "original_ATR": state.get("prior_atr"),
                "original_risk_R_units": state.get("stop_return"),
                "initial_stop": state.get("initial_stop"),
                "target": state.get("target"),
                "activation_time": state.get("activation_time"),
                "floor_decided_at": state.get("floor_decided_at"),
                "floor_effective_at": state.get("floor_effective_at"),
                "configured_stop": state.get("configured_stop") or state.get("initial_stop"),
                "entry_fee": state.get("entry_fee"),
                "funding_events": state.get("funding_events"),
                "gate_decision": True,
            }
        )
        return row

    def step_market(self, now: datetime, *, data: Any = None, registry_fetcher: Callable[[], list[InstrumentStatus]] | None = None) -> None:
        """Hourly signals once per closed hour, minute bars only for active symbols.

        No model call. A failed instrument query stays UNAVAILABLE. A failed
        candle fetch is a missing input, not a backfilled price.
        """
        now = _as_utc(now)
        if data is None:
            data = getattr(self, "_market_data", None)
            if data is None:
                from core.data.ohlcv import BybitOHLCV

                data = BybitOHLCV()
                self._market_data = data
        if self.last_registry_at is None or now - self.last_registry_at >= timedelta(hours=1):
            try:
                if registry_fetcher is None:
                    registry = fetch_registry(list(self.config["universe"]))
                else:
                    registry = registry_fetcher()
                self.sleeve_rows(registry)
            except Exception:
                logger.exception("F111 registry refresh failed")
            self.last_registry_at = now
        hour = now.replace(minute=0, second=0, microsecond=0)
        if self.last_signal_hour != hour:
            self._consume_hourly(data, now)
            self.last_signal_hour = hour
        for symbol in self._active_symbols():
            try:
                frame = data.fetch_latest(symbol, "1m", bars=90)
            except Exception as exc:
                logger.warning("F111 minute fetch failed for %s: %s", symbol, exc)
                continue
            self._consume_minutes(symbol, frame, now)

    def _active_symbols(self) -> list[str]:
        names = {pending["symbol"] for pending in self.pending if pending["status"] in {"watching", "scheduled"}}
        names.update(self.protection)
        return sorted(names)

    def _earliest_minute(self, symbol: str) -> datetime | None:
        stamps = [
            _parse_time(pending.get("next_minute"))
            for pending in self.pending
            if pending["symbol"] == symbol and pending["status"] in {"watching", "scheduled"}
        ]
        if symbol in self.protection:
            opened = _parse_time(self.protection[symbol].get("opened_at"))
            if opened is not None:
                stamps.append(opened)
        stamps = [stamp for stamp in stamps if stamp is not None]
        return min(stamps) if stamps else None

    def _consume_hourly(self, data: Any, now: datetime) -> None:
        from core.data.ohlcv import closed_candles
        from core.strategy.base import SignalSide
        from core.strategy.mar_f111_r12_extension_latefloor_v1 import (
            MarF111R12ExtensionLatefloorV1Strategy,
        )
        from dataclasses import replace

        # Rows emitted by this pass only. The Inbox summary is a diary of
        # these rows; it is written after the pass and cannot change it.
        start = len(self.events)
        available = [
            symbol
            for symbol, status in self.registry.items()
            if status.availability == AVAILABLE
        ]
        if not available:
            _publish_hourly_summary(self, [], now)
            return
        try:
            btc = closed_candles(data.fetch_latest("BTCUSDT", "1h", bars=860), "1h", now=now)
            if btc is not None and len(btc):
                btc = _drop_unclosed_hourly(btc, now)
        except Exception as exc:
            logger.warning("F111 BTC hourly fetch failed: %s", exc)
            btc = None
        for symbol in available:
            try:
                frame = btc if symbol == "BTCUSDT" else closed_candles(
                    data.fetch_latest(symbol, "1h", bars=860), "1h", now=now
                )
            except Exception as exc:
                self._emit_data_gap(symbol, f"hourly fetch failed: {exc}")
                continue
            if frame is None or len(frame) == 0:
                self._emit_data_gap(symbol, "no_history")
                continue
            # closed_candles drops only the final in-progress bar. Drop every
            # hourly bar that has not closed: bar open + 1h <= now.
            frame = _drop_unclosed_hourly(frame, now)
            if frame is None or len(frame) == 0:
                self._emit_data_gap(symbol, "hourly bar still forming")
                continue
            if len(frame) < MarF111R12ExtensionLatefloorV1Strategy.min_bars:
                self._emit_data_gap(symbol, "insufficient_history")
                continue
            bar_open = _bar_open_utc(frame.index[-1])
            t0 = bar_open + timedelta(hours=1)
            if t0 > _as_utc(now):
                self._emit_data_gap(symbol, "hourly bar still forming")
                continue
            for side in (SignalSide.LONG, SignalSide.SHORT):
                rule = MarF111R12ExtensionLatefloorV1Strategy(replace(MarF111R12ExtensionLatefloorV1Strategy().params, side=side))
                try:
                    contextual = rule.prepare_market_context(
                        symbol, frame, None if symbol == "BTCUSDT" else btc
                    )
                    signals = rule.generate_signals(contextual)
                except Exception as exc:
                    self._emit_data_gap(symbol, str(exc), side=side.value)
                    continue
                last = signals.iloc[-1]
                parent_reason = str(last.get("f111_rejection_reason") or "")
                close_px = float(frame["close"].iloc[-1])
                boundary_px = (
                    float(last["entry_boundary"])
                    if _finite_price(last.get("entry_boundary"))
                    else float("nan")
                )
                atr_px = float(last["prior_atr"]) if _finite_price(last.get("prior_atr")) else float("nan")
                # Sign and zero stay. _finite_price would drop a non-positive
                # extension or compression and the gate would say missing_feature.
                extension = _finite_or_nan(last.get("extension_atr"))
                if _finite_number(extension) is None:
                    extension = signed_extension(int(side.sign), close_px, boundary_px, atr_px)
                extension_feature = _finite_or_none(last.get("extension_atr"))
                if extension_feature is None and _finite_number(extension) is not None:
                    extension_feature = float(extension)
                try:
                    distance_features = _distance_features(last, frame, symbol)
                except Exception:
                    logger.exception(
                        "F111 distance snapshot failed for %s; the signal is unchanged", symbol
                    )
                    distance_features = {}
                self.observe_signal(
                    symbol=symbol,
                    side=side.value,
                    t0=t0,
                    boundary=boundary_px,
                    prior_atr=atr_px,
                    close=close_px,
                    compression=_finite_or_nan(last.get("compression")),
                    extension_atr=float(extension) if _finite_number(extension) is not None else float("nan"),
                    base_passed=parent_reason != "base_signal_blocked",
                    observed_at=now,
                    features={
                        "compression": _finite_or_none(last.get("compression")),
                        "extension_atr": extension_feature,
                        "f111_rejection_reason": parent_reason,
                        **distance_features,
                    },
                    feature_asof={"hourly_bar_open": str(bar_open), "signal_close": _iso(t0)},
                )
        _publish_hourly_summary(self, self.events[start:], now)

    def _consume_minutes(self, symbol: str, frame: Any, now: datetime) -> None:
        from core.data.ohlcv import closed_candles

        if frame is None or len(frame) == 0:
            return
        closed = closed_candles(frame, "1m", now=now)
        earliest = self._earliest_minute(symbol)
        for stamp, bar in closed.iterrows():
            moment = stamp.to_pydatetime()
            moment = moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)
            if earliest is not None and moment < earliest:
                continue
            fraction, source = _funding_for_open(self, symbol, moment)
            self.observe_minute(
                symbol=symbol,
                minute=moment,
                high=float(bar["high"]),
                low=float(bar["low"]),
                close=float(bar["close"]),
                quote=float(bar["open"]),
                quote_time=moment,
                observed_at=now,
                funding_fraction=fraction,
                funding_source=source,
                funding_asof=moment,
            )

    def _emit_data_gap(self, symbol: str, reason: str, side: str | None = None) -> None:
        sides = [side] if side else list(self.config["sides"])
        for item in sides:
            row = _blank_event(self.config_sha, self.run_id)
            row.update(
                {
                    "symbol": symbol,
                    "side": item,
                    "cohort": cohort_of(symbol, self.config),
                    "sector": _sector(symbol),
                    "rejection_reason": reason,
                    "missing_candle_or_quote": True,
                }
            )
            self._emit(row)


def _funding_for_open(runtime: F111Runtime, symbol: str, now: datetime) -> tuple[float | None, str | None]:
    """Observed funding fraction, or (None, reason) when the feed did not answer.

    An empty successful window is an observed zero. A failed request is not
    rewritten as zero.
    """
    state = runtime.protection.get(symbol)
    if state is None:
        return None, None
    opened = _parse_time(state.get("opened_at"))
    if opened is None:
        return None, "funding opened_at missing"
    try:
        import httpx

        response = httpx.get(
            "https://api.bybit.com/v5/market/funding/history",
            params={
                "category": "linear",
                "symbol": symbol,
                "startTime": int(opened.timestamp() * 1000),
                "endTime": int(now.timestamp() * 1000),
                "limit": 200,
            },
            timeout=20.0,
            headers={"User-Agent": "mar-trading-firm/0.1"},
        )
    except Exception as exc:
        return None, f"funding unreachable: {exc}"
    if response.status_code != 200:
        return None, f"funding unreachable: HTTP {response.status_code}"
    try:
        payload = response.json()
    except Exception as exc:
        return None, f"funding unreachable: {exc}"
    if int(payload.get("retCode") or 0) != 0:
        return None, f"funding unreachable: {payload.get('retMsg')}"
    rows = (payload.get("result") or {}).get("list") or []
    sign = int(state["side"])
    total = 0.0
    counted = 0
    for record in rows:
        try:
            stamp = datetime.fromtimestamp(int(record["fundingRateTimestamp"]) / 1000, tz=timezone.utc)
            rate = float(record["fundingRate"])
        except (KeyError, TypeError, ValueError):
            continue
        if opened < stamp <= now:
            total += rate
            counted += 1
    # Debit positive: a long pays a positive rate, a short receives it.
    return sign * total, f"bybit v5 funding history ({counted} settlements)"


def _finite_price(value: float | None) -> bool:
    """A usable price. Zero and negatives are not prices."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return number > 0 and math.isfinite(number)


def _finite_number(value: float | None) -> float | None:
    """Finite feature value. Zero and negatives are kept. Prices use ``_finite_price``."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _finite_or_nan(value: float | None) -> float:
    """Finite feature, or NaN when it is missing. Sign is allowed."""
    number = _finite_number(value)
    return float("nan") if number is None else number


def _finite_or_none(value: float | None) -> float | None:
    """Finite feature for telemetry, or None when it is missing. Sign is allowed."""
    return _finite_number(value)


# Share of rows that already have prior ATR and boundary. Above this, a
# missing_feature stamp means the scan wrapper dropped a real feature.
MISSING_FEATURE_SHARE_LIMIT = 0.05


def _reason_text(value: Any) -> str | None:
    """A non-empty rejection string. Bools and None are not reasons."""
    if isinstance(value, str) and value:
        return value
    return None


def _marker_matches_deploy(row: dict[str, Any], *, configuration_sha256: str, strategy_version: str) -> bool:
    """True when a deploy marker belongs to this config or this code version."""
    marker = row.get("deploy_marker")
    if not isinstance(marker, str) or not marker:
        return False
    sha = row.get("configuration_sha256")
    version = row.get("strategy_version")
    if sha == configuration_sha256 or version == strategy_version:
        return True
    # A boundary that names neither still splits history from the rows after it.
    return sha is None and version is None


def row_recorded_time(row: dict[str, Any]) -> datetime | None:
    """Instant used by ``--since``.

    The first parseable value wins: ``emitted_at``, ``source_signal_time``,
    ``observed_at``, then ``feature_asof_times.signal_close``. A row with
    none of those has no recorded time.
    """
    for field in ("emitted_at", "source_signal_time", "observed_at"):
        raw = row.get(field)
        if isinstance(raw, str):
            parsed = _parse_time(raw)
            if parsed is not None:
                return parsed
    asof = row.get("feature_asof_times")
    if not isinstance(asof, dict):
        asof = row.get("feature_asof")
    if isinstance(asof, dict):
        raw = asof.get("signal_close")
        if isinstance(raw, str):
            return _parse_time(raw)
    return None


def rows_since_timestamp(rows: list[dict[str, Any]], since: datetime) -> list[dict[str, Any]]:
    """Rows whose recorded time is at or after ``since``.

    Rows with no recorded time are outside this window. A naive ``since`` is UTC.
    """
    cutoff = _as_utc(since)
    return [
        row
        for row in rows
        if (recorded := row_recorded_time(row)) is not None and recorded >= cutoff
    ]


def rows_since_latest_deploy(
    rows: list[dict[str, Any]],
    *,
    configuration_sha256: str,
    strategy_version: str,
) -> list[dict[str, Any]]:
    """Rows since the latest activation or restart of the current deploy.

    The cut is the later of the last matching deploy marker and the first row
    of the latest ``run_id``. A marker matches the current
    ``configuration_sha256`` or the current code version. Rows before the cut
    stay in the all-history share only.
    """
    marker_at: int | None = None
    for index, row in enumerate(rows):
        if _marker_matches_deploy(
            row,
            configuration_sha256=configuration_sha256,
            strategy_version=strategy_version,
        ):
            marker_at = index
    run_at: int | None = None
    last_run: str | None = None
    for index, row in enumerate(rows):
        run_id = row.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            continue
        if run_id != last_run:
            last_run = run_id
            run_at = index
    cuts = [index for index in (marker_at, run_at) if index is not None]
    if not cuts:
        return list(rows)
    return list(rows[max(cuts) :])


def missing_feature_share(rows: list[dict[str, Any]]) -> float | None:
    """Fraction of input-complete rows rejected as ``missing_feature``.

    A row counts only when prior ATR and boundary are present. Instrument-only
    scan rows, which have neither, are ignored. ``None`` means there were no
    such rows.
    """
    eligible = 0
    missing = 0
    for row in rows:
        features = row.get("feature_values") or {}
        prior = features.get("prior_atr")
        if prior is None:
            prior = row.get("original_ATR")
        boundary = features.get("boundary")
        if not _finite_price(prior) or not _finite_price(boundary):
            continue
        eligible += 1
        if row.get("rejection_reason") == "missing_feature":
            missing += 1
    if eligible == 0:
        return None
    return missing / eligible


def _sector(symbol: str) -> str:
    from config.universe import get_universe

    return get_universe().sector_of(symbol)


def _estimated_floor_price(state: dict[str, Any], fee: float) -> float | None:
    """Cost-aware candidate. Distinct from the configured stop and from realised P&L."""
    if not state.get("funding_known") or state.get("funding_fraction") is None:
        return None
    level = floor_move(
        int(state["side"]),
        fee,
        float(state["funding_fraction"]),
        float(state["floor_g"]),
    )
    return float(state["entry_price"]) * (1.0 + int(state["side"]) * level)


def fresh_scan(
    *,
    registry: list[InstrumentStatus] | None = None,
    client: Any = None,
    telemetry_path: Path | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Evaluate all 192 sleeves. Does not start a worker and does not place orders."""
    assert_not_a_second_worker(False)
    assert_f111_paper_only()
    config, digest = load_f111_config()
    if registry is None:
        registry = fetch_registry(list(config["universe"]), client=client)
    runtime = F111Runtime(config=config, config_sha=digest, telemetry_path=telemetry_path, run_id=run_id)
    rows = runtime.sleeve_rows(registry)
    available = sorted({row["symbol"] for row in rows if not row["instrument_unavailable"]})
    unavailable = []
    seen: set[str] = set()
    for row in rows:
        symbol = str(row["symbol"])
        if symbol in seen or not row["instrument_unavailable"]:
            continue
        seen.add(symbol)
        unavailable.append({"symbol": symbol, "reason": row["rejection_reason"]})
    transport = [item for item in unavailable if str(item["reason"]).startswith("instruments-info unreachable")]
    return {
        "strategy_id": STRATEGY_ID,
        "strategy_version": STRATEGY_VERSION,
        "configuration_sha256": digest,
        "sleeves_expected": 192,
        "sleeves_evaluated": len(rows),
        "symbols": len(config["universe"]),
        "available_symbols": len(available),
        "unavailable_symbols": len(unavailable),
        "unavailable": unavailable,
        "transport_failures": len(transport),
        "orders_placed": 0,
        "saved_path_parity": config.get("saved_path_parity"),
        "rows": rows,
    }


_ATTACHED: F111Runtime | None = None


def attached_runtime(engine: Any) -> F111Runtime:
    """One runtime for the paper process. A second worker is not created."""
    global _ATTACHED
    from core.strategy.f111_config import STATE_PATH, TELEMETRY_PATH

    if _ATTACHED is None:
        runtime = F111Runtime(
            broker=engine.broker,
            risk=engine.risk,
            ledger=engine.ledger,
            engine=engine,
            state_path=STATE_PATH,
            telemetry_path=TELEMETRY_PATH,
        )
        runtime.restore()
        runtime.note_restart()
        _ATTACHED = runtime
        return runtime
    _ATTACHED.broker = engine.broker
    _ATTACHED.risk = engine.risk
    _ATTACHED.ledger = engine.ledger
    _ATTACHED.engine = engine
    return _ATTACHED


def _distance_features(last: Any, frame: Any, symbol: str) -> dict[str, Any]:
    """Copy inputs the distance card reads. Does not decide the signal.

    Keys already passed to ``observe_signal`` (compression, extension, ATR,
    close, boundary) are left for that call to set. This only adds the base
    signal's other inputs, and only when they are finite.
    """
    extra: dict[str, Any] = {"is_btc": symbol == "BTCUSDT"}
    for key in ("volume_ratio", "close_location", "r24", "filter_crsi", "btc24"):
        number = _finite_or_none(last.get(key))
        if number is not None:
            extra[key] = number
    efficiency = _finite_or_none(last.get("efficiency24_before_signal"))
    if efficiency is not None:
        extra["efficiency24"] = efficiency
    for flag in ("passes_crsi", "passes_btc", "passes_loweff_cap"):
        value = last.get(flag)
        if isinstance(value, bool) or type(value).__name__ == "bool_":
            extra[flag] = bool(value)
    try:
        opened = float(frame["open"].iloc[-1])
    except (TypeError, ValueError, KeyError, IndexError):
        opened = float("nan")
    if math.isfinite(opened):
        extra["open"] = opened
    if frame is not None and len(frame) >= 2:
        try:
            high = float(frame["high"].iloc[-1])
            low = float(frame["low"].iloc[-1])
            prev = float(frame["close"].iloc[-2])
        except (TypeError, ValueError, KeyError, IndexError):
            high = low = prev = float("nan")
        if all(math.isfinite(item) for item in (high, low, prev)):
            extra["true_range"] = max(high - low, abs(high - prev), abs(low - prev))
    return extra


def _publish_hourly_summary(runtime: F111Runtime, rows: list[dict[str, Any]], now: datetime) -> None:
    """Write the hourly Inbox diary. Never raises into the F111 pass."""
    try:
        from firm.scan_inbox import publish_f111_hourly

        watching = sum(
            1
            for pending in runtime.pending
            if pending.get("status") in {"watching", "scheduled"}
        )
        publish_f111_hourly(list(rows), now=now, pending_retests=watching)
    except Exception:
        logger.exception("F111 scan summary was not written; trading is unchanged")


def run_attached_minute_step(engine: Any, *, data: Any = None, now: datetime | None = None) -> None:
    """One F111 pass inside the existing paper loop.

    Failures are logged by the caller. This function does not acquire the
    paper pid file and does not call an LLM. ``data`` defaults to the public
    Bybit kline client; tests inject a fake.
    """
    assert_not_a_second_worker(False)
    try:
        assert_f111_paper_only()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return
    config, _digest = load_f111_config()
    if not scan_enabled(config):
        logger.info("F111 scan disabled; existing exit supervision is unchanged")
        return
    runtime = attached_runtime(engine)
    when = _as_utc(now or runtime.clock())
    try:
        runtime.step_market(when, data=data)
    except Exception:
        logger.exception("F111 minute step failed")
        return
    runtime.persist()
