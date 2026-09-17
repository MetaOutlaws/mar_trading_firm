"""
F04 research/paper execution contract.

Research (`BacktestEngine`) and paper (`PaperBroker` / `TradingEngine`) used to
encode fill timing, TP/SL origin, holding expiry, stop slippage and symbol
conflicts in two places. This module is the single written contract both
comparison paths must execute.

Canonical semantics (versioned by ``EXECUTION_CONTRACT_VERSION``):

1. **Signals.** The same ``Strategy.generate_signals`` code. A signal on bar
   ``t`` is actionable at bar ``t+1``'s open (no lookahead).
2. **Entry fill.** Quote = next-bar open. Fill = ``CostModel.entry_price``.
3. **Protection.** TP/SL percentages are applied to the *slipped fill*, not
   the signal-bar close.
4. **Intrabar path.** On each holding bar, in adverse-first order:
   gap through the stop at the open → fill at the open; both TP and SL inside
   the range → stop if ``pessimistic_intrabar`` else target; stop touched →
   fill at the stop; target touched → fill at the target.
5. **Expiry.** ``max_holding_bars`` is a hard timeout. Fill at that bar's
   close when neither level has printed. ``END_OF_DATA`` if the series ends
   first.
6. **Exit slippage.** Stop fills already sit at an adverse level, so they do
   **not** take a second ``CostModel.exit_price`` slip. TP / timeout / EOD do.
7. **Costs.** Taker fee both legs via ``CostModel.round_trip_fees``. Funding
   via ``CostModel.funding_cost`` over ``[entry_time, exit_time]`` on entry
   notional (F03).
8. **Conflicts.** One position per symbol; no pyramiding. Scanning resumes
   after the exit bar.
9. **Identity.** Every position stores contract version, strategy name, full
   params, timeframe and expiry.

Live paper still polls a sampled last price between cycles (F15). The golden
tape drives a **paper replay** broker over the same OHLC path research uses,
so the two can be compared bar-for-bar. Sampled live marks are a documented
limitation, not a second contract.

Bump ``EXECUTION_CONTRACT_VERSION`` when any numbered rule above changes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

import numpy as np
import pandas as pd

from core.data.ohlcv import TIMEFRAME_DELTAS
from core.strategy.base import SignalSide

#: Golden-tape / position stamp. Independent of ``RESEARCH_VERSION`` (F01 OOS).
EXECUTION_CONTRACT_VERSION = "exec-f04-v1"


class ExitReason(str, Enum):
    """Why a position was closed. Shared by research and paper replay."""

    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TIMEOUT = "timeout"
    END_OF_DATA = "end_of_data"


def fill_in_tradable_window(
    fill_time: datetime | pd.Timestamp,
    tradable_start: datetime | pd.Timestamp | None,
    tradable_end: datetime | pd.Timestamp | None,
) -> bool:
    """Whether an entry fill belongs in a half-open ``[start, end)`` window.

    ``None`` on a bound means that side is unbounded. Walk-forward passes the
    fold's train/test edges so warmup bars can seed indicators without
    becoming fills (F01).
    """
    stamp = pd.Timestamp(fill_time)
    if tradable_start is not None and stamp < pd.Timestamp(tradable_start):
        return False
    if tradable_end is not None and stamp >= pd.Timestamp(tradable_end):
        return False
    return True


def risk_levels(
    entry_price: float,
    side: SignalSide | str,
    take_profit_pct: float,
    stop_loss_pct: float,
) -> tuple[float, float]:
    """TP and SL prices from the *slipped fill*, not the signal close.

    Research always did this. Runtime used to derive levels from
    ``signal.price`` (the signal-bar close) and submit later at a different
    mark — the F04 mismatch this helper forbids.
    """
    direction = SignalSide(side) if not isinstance(side, SignalSide) else side
    if direction is SignalSide.LONG:
        return (
            entry_price * (1.0 + take_profit_pct),
            entry_price * (1.0 - stop_loss_pct),
        )
    return (
        entry_price * (1.0 - take_profit_pct),
        entry_price * (1.0 + stop_loss_pct),
    )


def exit_fill_price(
    costs: Any,
    quote: float,
    side: SignalSide | str,
    reason: ExitReason | str,
) -> float:
    """Apply the contract's exit-slippage rule to an OHLC-resolved quote.

    Stop fills already reflect the adverse level (or a worse gap open).
    Adding ``exit_price`` slippage on that path was a paper-only extra cost.
    """
    label = reason.value if isinstance(reason, ExitReason) else str(reason)
    side_value = side.value if isinstance(side, SignalSide) else str(side)
    if label == ExitReason.STOP_LOSS.value:
        return quote
    return costs.exit_price(quote, side_value)


def find_exit_on_path(
    *,
    entry_bar: int,
    total_bars: int,
    side: SignalSide | str,
    opens: np.ndarray,
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    take_profit: float,
    stop_loss: float,
    max_holding: int,
    pessimistic_intrabar: bool = True,
) -> tuple[int, float, ExitReason]:
    """Locate the exit bar, OHLC quote and reason on a candle path.

    Resolution order within a bar, most to least adverse:
      1. Gap through the stop at the open → fill at the open.
      2. Both TP and SL inside the bar's range → assume the stop
         (``pessimistic_intrabar``).
      3. Stop touched → fill at the stop level.
      4. Target touched → fill at the target level.

    The entry bar itself cannot gap (there is no prior open relative to the
    fill); TP/SL wicks on the fill bar still count.
    """
    direction = SignalSide(side) if not isinstance(side, SignalSide) else side
    last_bar = min(entry_bar + max_holding, total_bars - 1)

    for bar in range(entry_bar, last_bar + 1):
        bar_open = float(opens[bar])
        bar_high = float(highs[bar])
        bar_low = float(lows[bar])

        if direction is SignalSide.LONG:
            if bar > entry_bar and bar_open <= stop_loss:
                return bar, bar_open, ExitReason.STOP_LOSS

            hit_stop = bar_low <= stop_loss
            hit_target = bar_high >= take_profit

            if hit_stop and hit_target:
                if pessimistic_intrabar:
                    return bar, stop_loss, ExitReason.STOP_LOSS
                return bar, take_profit, ExitReason.TAKE_PROFIT
            if hit_stop:
                return bar, stop_loss, ExitReason.STOP_LOSS
            if hit_target:
                return bar, take_profit, ExitReason.TAKE_PROFIT
        else:
            if bar > entry_bar and bar_open >= stop_loss:
                return bar, bar_open, ExitReason.STOP_LOSS

            hit_stop = bar_high >= stop_loss
            hit_target = bar_low <= take_profit

            if hit_stop and hit_target:
                if pessimistic_intrabar:
                    return bar, stop_loss, ExitReason.STOP_LOSS
                return bar, take_profit, ExitReason.TAKE_PROFIT
            if hit_stop:
                return bar, stop_loss, ExitReason.STOP_LOSS
            if hit_target:
                return bar, take_profit, ExitReason.TAKE_PROFIT

    reason = (
        ExitReason.TIMEOUT if last_bar < total_bars - 1 else ExitReason.END_OF_DATA
    )
    return last_bar, float(closes[last_bar]), reason


def settle_round_trip(
    *,
    side: SignalSide | str,
    entry_price: float,
    exit_price: float,
    quantity: float,
    entry_time: datetime,
    exit_time: datetime,
    costs: Any,
    funding: object | None = None,
) -> tuple[float, float, float, float]:
    """Gross, fees, funding, net — the same four numbers research books."""
    direction = SignalSide(side) if not isinstance(side, SignalSide) else side
    if direction is SignalSide.LONG:
        gross = (exit_price - entry_price) * quantity
    else:
        gross = (entry_price - exit_price) * quantity
    entry_notional = entry_price * quantity
    exit_notional = exit_price * quantity
    fees = costs.round_trip_fees(entry_notional, exit_notional)
    funding_cost = costs.funding_cost(
        direction.value, entry_time, exit_time, entry_notional, funding  # type: ignore[arg-type]
    )
    net = gross - fees - funding_cost
    return gross, fees, funding_cost, net


def expiry_at(
    opened_at: datetime,
    timeframe: str,
    max_holding_bars: int,
) -> datetime | None:
    """Timeout stamp: open of the last holding bar (research ``exit_time``).

    Research labels the timeout with ``timestamps[entry_bar + max_holding]``
    and fills at that bar's close. Live paper uses this stamp as "timeout
    is due"; the replay path uses ``find_exit_on_path`` for the fill price.
    """
    if max_holding_bars <= 0:
        return None
    step = TIMEFRAME_DELTAS.get(str(timeframe or "").strip())
    if step is None:
        return None
    if opened_at.tzinfo is None:
        opened_at = opened_at.replace(tzinfo=timezone.utc)
    return opened_at + step * int(max_holding_bars)


def position_identity(
    *,
    strategy_name: str,
    params: Mapping[str, Any] | object | None,
    timeframe: str,
    max_holding_bars: int,
    opened_at: datetime | None = None,
    execution_contract: str = EXECUTION_CONTRACT_VERSION,
) -> dict[str, Any]:
    """Fields stored on every paper position so replay and the book agree."""
    blob: dict[str, Any]
    if params is None:
        blob = {}
    elif isinstance(params, Mapping):
        blob = dict(params)
    elif hasattr(params, "to_dict"):
        blob = dict(params.to_dict())
    else:
        blob = asdict(params) if dataclass_instance(params) else {}
    opened = opened_at or datetime.now(timezone.utc)
    return {
        "execution_contract": execution_contract,
        "strategy": strategy_name,
        "strategy_params": blob,
        "timeframe": timeframe,
        "max_holding_bars": int(max_holding_bars),
        "expiry_at": expiry_at(opened, timeframe, int(max_holding_bars)),
        "cost_model_version": _cost_model_version(),
    }


def dataclass_instance(value: object) -> bool:
    """True for an instance of a ``@dataclass``, not the class itself."""
    cls = type(value)
    return hasattr(cls, "__dataclass_fields__")


def tape_trade_dict(
    *,
    symbol: str,
    side: SignalSide | str,
    entry_time: datetime,
    entry_price: float,
    exit_time: datetime,
    exit_price: float,
    quantity: float,
    notional: float,
    gross_pnl: float,
    fees: float,
    funding: float,
    net_pnl: float,
    exit_reason: ExitReason | str,
    bars_held: int,
) -> dict[str, object]:
    """Canonical golden-tape row. Rounding matches ``Trade.to_dict``."""
    side_value = side.value if isinstance(side, SignalSide) else str(side)
    reason = exit_reason.value if isinstance(exit_reason, ExitReason) else str(exit_reason)
    return {
        "symbol": symbol,
        "side": side_value,
        "entry_time": _iso(entry_time),
        "entry_price": round(float(entry_price), 8),
        "exit_time": _iso(exit_time),
        "exit_price": round(float(exit_price), 8),
        "quantity": round(float(quantity), 8),
        "notional": round(float(notional), 2),
        "gross_pnl": round(float(gross_pnl), 4),
        "fees": round(float(fees), 4),
        "funding": round(float(funding), 4),
        "net_pnl": round(float(net_pnl), 4),
        "exit_reason": reason,
        "bars_held": int(bars_held),
    }


def _iso(value: datetime | pd.Timestamp) -> str:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.isoformat()


@dataclass(frozen=True)
class ContractSnapshot:
    """Version stamps a comparison run must record."""

    execution_contract: str = EXECUTION_CONTRACT_VERSION
    cost_model_version: str = ""
    pessimistic_intrabar: bool = True
    one_position_per_symbol: bool = True
    next_bar_open_entry: bool = True
    tp_sl_from_fill: bool = True
    stop_loss_extra_exit_slippage: bool = False
    max_holding_enforced: bool = True


def contract_snapshot(**overrides: Any) -> dict[str, object]:
    payload = asdict(ContractSnapshot(cost_model_version=_cost_model_version()))
    payload.update(overrides)
    return payload


def _cost_model_version() -> str:
    """Lazy import so this module does not cycle through research.__init__."""
    from research.costs import COST_MODEL_VERSION

    return COST_MODEL_VERSION
