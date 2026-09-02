# Proposal: `session_volume_imbalance_reversal`

Calculates the volume imbalance ratio between buying and selling volume at the boundaries of the preceding UTC session. When price sweeps the session high or low on a 4h clock but volume imbalance shows a clear exhaustion signature (less th

Passive limit orders at session extremes act as strong absorption barriers in range-bound regimes, trapping breakout traders.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates the volume imbalance ratio between buying and selling volume at the boundaries of the preceding UTC session. When price sweeps the session high or low on a 4h clock but volume imbalance shows a clear exhaustion signature (less than 30% of the average session boundary volume), it enters a mean-reversion trade targeting the session mid-point.

## What to write

1. `core/strategy/session_volume_imbalance_reversal.py` — `Strategy` subclass, `name = "session_volume_imbalance_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_volume_imbalance_reversal")`.
