"""Frozen F111 decision math.

This is the paper implementation of the handoff rules in
``docs/mar-f111-paper-handoff/REFERENCE_RULES.md`` and the kind=2 (floor)
branch of ``references/simulator.py``. It is not a new search and it does not
read the private checkpoint.

Research samples minute opens. Callers that use a live quote must say so in
telemetry. Nothing here calls an exchange, a ledger, or a model.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

# Research primary cost. Forward paper uses the firm's CostModel for fills and
# records that difference; the floor formula still uses this fee unless the
# caller passes the configured taker fee.
RESEARCH_FEE = 0.00055
RESEARCH_SLIP = 0.002
RETEST_MINUTES = 60
STOP_ATR = 3.0
TARGET_ATR = 4.0
ACTIVATION_R = 1.25
FLOOR_R = 0.25
COMPRESSION_MIN_EXCLUSIVE = 0.5
EXTENSION_MAX_INCLUSIVE = 1.0
HIGH_VOL_MIN_INCLUSIVE = 0.01

# Exit reasons copied from the research simulator.
REASON_INITIAL_STOP = 1
REASON_TARGET = 2
REASON_END_OF_TAPE = 3
REASON_PROTECTED_STOP = 4


def _finite(value: float) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def gate_decision(
    *,
    compression: float,
    extension_atr: float,
    prior_atr: float,
    close: float,
    compression_min_exclusive: float = COMPRESSION_MIN_EXCLUSIVE,
    extension_max: float = EXTENSION_MAX_INCLUSIVE,
    high_vol_min: float = HIGH_VOL_MIN_INCLUSIVE,
) -> tuple[bool, str]:
    """F111 gates on the original hourly signal, not on the later retest.

    Equality is part of the rule: compression must be strictly greater than
    0.50, extension must be <= 1 prior ATR, and prior ATR / close must be
    >= 0.01. A missing feature is a rejection, not a pass.
    """
    if not all(_finite(v) for v in (compression, extension_atr, prior_atr, close)):
        return False, "missing_feature"
    if close <= 0 or prior_atr <= 0:
        return False, "missing_feature"
    # Collected so a row that fails two gates still names the first one, and
    # tests can probe each edge on its own.
    if prior_atr / close < high_vol_min:
        return False, "high_vol_filter"
    if not compression > compression_min_exclusive:
        return False, "compression_gate"
    if extension_atr > extension_max:
        return False, "extension_gate"
    return True, ""


def gate_mask(
    compression: np.ndarray,
    extension_atr: np.ndarray,
    prior_atr: np.ndarray,
    close: np.ndarray,
    compression_min_exclusive: float = COMPRESSION_MIN_EXCLUSIVE,
    extension_max: float = EXTENSION_MAX_INCLUSIVE,
    high_vol_min: float = HIGH_VOL_MIN_INCLUSIVE,
) -> np.ndarray:
    """Same inequalities as ``gate_decision``, for a whole signal frame."""
    compression = np.asarray(compression, dtype=float)
    extension_atr = np.asarray(extension_atr, dtype=float)
    prior_atr = np.asarray(prior_atr, dtype=float)
    close = np.asarray(close, dtype=float)
    finite = (
        np.isfinite(compression)
        & np.isfinite(extension_atr)
        & np.isfinite(prior_atr)
        & np.isfinite(close)
        & (close > 0)
        & (prior_atr > 0)
    )
    return (
        finite
        & (prior_atr / close >= high_vol_min)
        & (compression > compression_min_exclusive)
        & (extension_atr <= extension_max)
    )


def update_touch(
    side: int,
    high: float,
    low: float,
    close: float,
    boundary: float,
    touched: bool,
) -> tuple[bool, bool]:
    """Remember a touch. Reclaim is strict and may happen on the touch minute."""
    if side not in (1, -1):
        raise ValueError("side must be +1 or -1")
    if not all(math.isfinite(v) for v in (high, low, close, boundary)):
        raise ValueError("minute bar is not finite")
    now_touched = touched or (low <= boundary if side == 1 else high >= boundary)
    reclaim = bool(now_touched and side * (close - boundary) > 0)
    return now_touched, reclaim


def plan_retest(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    i: int,
    side: int,
    boundary: float,
    window: int = RETEST_MINUTES,
) -> tuple[int, str]:
    """First strict reclaim inside the window, filled on the next minute.

    The slice is ``[i, i+window)`` capped so the last index of ``close`` is
    never a confirmation: that bar would have no next open to fill. Touch and
    reclaim may be the same completed minute. A close exactly on the boundary
    is not a reclaim (``side * (close - boundary) > 0``).

    Returns ``(fill_index, status)``. ``fill_index`` is -1 when no fill is
    scheduled. Status is ``filled``, ``no_touch``, or ``no_reclaim``.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    if side not in (1, -1):
        raise ValueError("side must be +1 or -1")
    end = min(i + int(window), len(close) - 1)
    touched = False
    for k in range(i, end):
        touched, reclaim = update_touch(side, high[k], low[k], close[k], boundary, touched)
        if reclaim:
            return k + 1, "filled"
    return -1, "no_reclaim" if touched else "no_touch"


def floor_move(side: int, fee: float, funding_fraction: float, floor_g: float) -> float:
    """Favourable-move level of the cost-aware floor.

    ``candidate_price / entry = (s + f + F + g) / (s - f)`` with ``F`` the
    cumulative funding cost as a fraction of entry notional, debit positive.
    The level is ``s * (candidate_price / entry - 1)``. This is the expression
    in the research simulator's floor branch.
    """
    if side not in (1, -1):
        raise ValueError("side must be +1 or -1")
    if fee >= 1 or side - fee == 0:
        raise ValueError("fee fraction is not usable")
    ratio = (side + fee + funding_fraction + floor_g) / (side - fee)
    return side * (ratio - 1.0)


def research_exit_price(quote: float, side: int, reason: int, slip: float = RESEARCH_SLIP) -> float:
    """Stop exits keep the sampled quote. Target and terminal exits pay slip."""
    if reason in (REASON_INITIAL_STOP, REASON_PROTECTED_STOP):
        return quote
    return quote * (1.0 - side * slip)


def research_net(
    entry_price: float,
    exit_price: float,
    side: int,
    funding_fraction: float,
    fee: float = RESEARCH_FEE,
) -> dict[str, float]:
    """Both-leg fee, signed funding, and net return at the research units.

    ``fees`` is ``fee * (1 + exit/entry)``, the entry leg plus the exit leg.
    ``funding_fraction`` is debit positive as a fraction of entry notional.
    """
    gross = side * (exit_price / entry_price - 1.0)
    fees = fee * (1.0 + exit_price / entry_price)
    net = gross - fees - funding_fraction
    return {"gross_return": gross, "fees": fees, "funding": funding_fraction, "net_return": net}


def initial_brackets(entry_price: float, side: int, prior_atr: float) -> dict[str, float]:
    """3 ATR stop and 4 ATR target measured from the simulated entry, not the signal close."""
    if entry_price <= 0 or prior_atr <= 0 or side not in (1, -1):
        raise ValueError("brackets need a positive entry, a positive ATR, and a side")
    risk = STOP_ATR * prior_atr
    stop_return = risk / entry_price
    target_return = TARGET_ATR * prior_atr / entry_price
    return {
        "risk_price": risk,
        "stop_return": stop_return,
        "target_return": target_return,
        "initial_stop": entry_price - side * risk,
        "target": entry_price + side * TARGET_ATR * prior_atr,
        "activation_return": ACTIVATION_R * stop_return,
        "floor_g": FLOOR_R * stop_return,
    }


def new_protection_state(
    *,
    entry_price: float,
    side: int,
    prior_atr: float,
    quantity: float,
    entry_fee: float,
) -> dict[str, Any]:
    """State at the fill. The first sample is the next minute, not this fill."""
    brackets = initial_brackets(entry_price, side, prior_atr)
    stop_return = brackets["stop_return"]
    return {
        "entry_price": float(entry_price),
        "side": int(side),
        "prior_atr": float(prior_atr),
        "quantity": float(quantity),
        "entry_fee": float(entry_fee),
        "stop_return": stop_return,
        "target_return": brackets["target_return"],
        "initial_stop": brackets["initial_stop"],
        "target": brackets["target"],
        "activation_return": brackets["activation_return"],
        "floor_g": brackets["floor_g"],
        "best_move": 0.0,
        "armed": False,
        "effective_level": -stop_return,
        "decided_level": -stop_return,
        "activation_time": None,
        "floor_decided_at": None,
        "floor_effective_at": None,
        "funding_fraction": None,
        "funding_known": False,
    }


def step_protection(
    state: dict[str, Any],
    quote: float,
    *,
    funding_fraction: float | None,
    fee: float = RESEARCH_FEE,
    sample_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """One forward sample. Stop, then target, then a protection decision.

    The level decided on this sample becomes effective on the next call. A
    funding print that would lower the floor is ignored (monotone). Unknown
    funding does not pretend to be zero: the initial stop stays in force and
    the cost-aware floor is not armed.
    """
    if not _finite(quote) or quote <= 0:
        raise ValueError("protection sample needs a positive quote")
    out = dict(state)
    side = int(out["side"])
    entry = float(out["entry_price"])
    # Decisions from the previous sample apply now, before this quote can exit.
    out["effective_level"] = max(float(out["effective_level"]), float(out["decided_level"]))
    if out["armed"] and out["floor_effective_at"] is None and sample_id is not None:
        out["floor_effective_at"] = sample_id
    level = float(out["effective_level"])
    stop_price = entry * (1.0 + side * level)
    move = side * (quote / entry - 1.0)
    stop_hit = side * (quote - stop_price) <= 0
    target_price = entry * (1.0 + side * float(out["target_return"]))
    target_hit = side * (quote - target_price) >= 0
    if stop_hit or target_hit:
        # Stop wins when both are true on the same quote. The fill is the
        # quote, not the stop price, so a gap through the stop is kept.
        if stop_hit:
            reason = (
                REASON_PROTECTED_STOP
                if level > -float(out["stop_return"]) + 1e-12
                else REASON_INITIAL_STOP
            )
        else:
            reason = REASON_TARGET
        exit_row = {
            "reason": reason,
            "quote": float(quote),
            "configured_stop": float(stop_price),
            "target": float(target_price),
            "move": float(move),
        }
        return out, exit_row

    out["best_move"] = max(float(out["best_move"]), move)
    if funding_fraction is None or not _finite(funding_fraction):
        out["funding_known"] = False
        out["funding_fraction"] = None
        return out, None
    out["funding_known"] = True
    out["funding_fraction"] = float(funding_fraction)
    candidate = floor_move(side, fee, float(funding_fraction), float(out["floor_g"]))
    if (
        not out["armed"]
        and out["best_move"] >= float(out["activation_return"])
        and move > candidate
    ):
        out["armed"] = True
        out["activation_time"] = sample_id
        out["floor_decided_at"] = sample_id
    if out["armed"]:
        # Never loosen. A funding credit that lowers the candidate stays behind
        # the previous decided level.
        tightened = max(float(out["decided_level"]), candidate)
        if tightened > float(out["decided_level"]) + 1e-15:
            out["floor_decided_at"] = sample_id
        out["decided_level"] = tightened
    return out, None


def simulate_policy331(
    opens: np.ndarray,
    entry_i: int,
    side: int,
    prior_atr: float,
    funding_fraction: np.ndarray | None = None,
    *,
    slip: float = RESEARCH_SLIP,
    fee: float = RESEARCH_FEE,
    closes: np.ndarray | None = None,
) -> dict[str, Any]:
    """Walk minute opens the way policy331 does, for fixture tests.

    ``funding_fraction[j]`` is debit-positive cumulative funding at open ``j``.
    A missing series is treated as unknown and the floor never arms. That is
    the forward missing-funding policy, not a claim that the research tape had
    zero funding. Pass an explicit numeric series to match the simulator.
    """
    opens = np.asarray(opens, dtype=float)
    if closes is None:
        closes = opens
    else:
        closes = np.asarray(closes, dtype=float)
    entry = opens[entry_i] * (1.0 + side * slip)
    state = new_protection_state(
        entry_price=entry,
        side=side,
        prior_atr=prior_atr,
        quantity=1.0,
        entry_fee=fee * entry,
    )
    last_quote = float(closes[-1])
    exit_row = None
    exit_i = len(opens) - 1
    for j in range(entry_i + 1, len(opens)):
        fraction = None if funding_fraction is None else float(funding_fraction[j])
        state, exit_row = step_protection(
            state, float(opens[j]), funding_fraction=fraction, fee=fee, sample_id=str(j)
        )
        if exit_row is not None:
            exit_i = j
            last_quote = float(exit_row["quote"])
            break
    else:
        exit_row = {
            "reason": REASON_END_OF_TAPE,
            "quote": float(closes[-1]),
            "configured_stop": None,
            "target": state["target"],
            "move": side * (float(closes[-1]) / entry - 1.0),
        }
        last_quote = float(closes[-1])
    reason = int(exit_row["reason"])
    exit_price = research_exit_price(last_quote, side, reason, slip)
    # Funding at the exit sample. Unknown stays unknown and is not booked as zero.
    if funding_fraction is None:
        booked_funding = None
    else:
        booked_funding = float(funding_fraction[exit_i])
    net = None
    if booked_funding is not None:
        net = research_net(entry, exit_price, side, booked_funding, fee)
    return {
        "entry_i": entry_i,
        "exit_i": exit_i,
        "entry_price": entry,
        "quote": last_quote,
        "exit_price": exit_price,
        "reason": reason,
        "armed": bool(state["armed"]),
        "state": state,
        "net": net,
    }


def simulate_reference_floor(
    opens: np.ndarray,
    f0: np.ndarray,
    entry_i: int,
    side: int,
    stop: float,
    target: float,
    trigger: float,
    floor: float,
    *,
    slip: float = RESEARCH_SLIP,
    fee: float = RESEARCH_FEE,
) -> tuple[int, float, int, int, int]:
    """Line-by-line port of the research ``simulate`` floor branch (kind 2).

    ``f0`` is the cumulative funding-price series. Accrued funding as a
    fraction of entry notional is ``side * (f0[j] - f0[i]) / entry_price``.
    ``stop``, ``target``, ``trigger`` and ``floor`` are returns, matching the
    call site that passes ``3 * atr / entry`` and ``0.25 * stop``.
    """
    opens = np.asarray(opens, dtype=float)
    f0 = np.asarray(f0, dtype=float)
    entry = opens[entry_i] * (1.0 + side * slip)
    level = -stop
    best = 0.0
    armed = False
    trigger_i = -1
    for j in range(entry_i + 1, len(opens)):
        move = side * (opens[j] / entry - 1.0)
        if side * (opens[j] - entry * (1.0 + side * level)) <= 0:
            reason = 4 if level > -stop + 1e-12 else 1
            return j, float(opens[j]), reason, int(armed), trigger_i
        if side * (opens[j] - entry * (1.0 + side * target)) >= 0:
            return j, float(opens[j]), 2, int(armed), trigger_i
        best = max(best, move)
        accrued = side * (f0[j] - f0[entry_i]) / entry
        candidate = side * ((side + fee + accrued + floor) / (side - fee) - 1.0)
        if (not armed) and best >= trigger and move > candidate:
            armed = True
            trigger_i = j
        if armed:
            level = max(level, candidate)
    return len(opens) - 1, float(opens[-1]), 3, int(armed), trigger_i
