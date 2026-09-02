# Proposal: `momentum_velocity_acceleration`

Measures the rate of change of a 14-period momentum indicator (velocity of velocity). It enters trend-following positions on a 4h clock when momentum acceleration crosses zero, indicating that the trend is not just moving, but actively spee

Filters out slow, grinding trends that are prone to sudden mean-reverting collapses, focusing only on high-velocity moves.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Measures the rate of change of a 14-period momentum indicator (velocity of velocity). It enters trend-following positions on a 4h clock when momentum acceleration crosses zero, indicating that the trend is not just moving, but actively speeding up.

## What to write

1. `core/strategy/momentum_velocity_acceleration.py` — `Strategy` subclass, `name = "momentum_velocity_acceleration"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("momentum_velocity_acceleration")`.
