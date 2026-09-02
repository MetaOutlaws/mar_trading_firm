# Proposal: `session_boundary_volume_fade`

Identifies the high and low of the previous UTC day. When price sweeps outside this boundary on the 4h clock but the volume of the sweeping bar is below the 20-period volume moving average, it enters a mean-reversion trade targeting the dai

Captures trapped breakout traders at key daily liquidity pools when there is no institutional volume to support the expansion.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Identifies the high and low of the previous UTC day. When price sweeps outside this boundary on the 4h clock but the volume of the sweeping bar is below the 20-period volume moving average, it enters a mean-reversion trade targeting the daily VWAP.

## What to write

1. `core/strategy/session_boundary_volume_fade.py` — `Strategy` subclass, `name = "session_boundary_volume_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_boundary_volume_fade")`.
