# Proposal: `stochastic_velocity_reversal`

Calculates a 14-period Stochastic oscillator on the 3-period rate of change (velocity) of price. It enters a mean-reversion trade on a 4h clock when the stochastic of velocity reaches extreme overbought (>80) or oversold (<20) levels and cr

Directly measures the exhaustion of momentum rather than price levels, preventing premature entries in strong trends.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates a 14-period Stochastic oscillator on the 3-period rate of change (velocity) of price. It enters a mean-reversion trade on a 4h clock when the stochastic of velocity reaches extreme overbought (>80) or oversold (<20) levels and crosses back, signaling that the momentum of the move is decelerating rapidly.

## What to write

1. `core/strategy/stochastic_velocity_reversal.py` — `Strategy` subclass, `name = "stochastic_velocity_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("stochastic_velocity_reversal")`.
