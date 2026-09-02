# Proposal: `prior_day_pivot_breakout`

Break prior UTC-day pivot / R1 / S1 after that day has closed.

Daily floor pivots require calendar-day aggregation.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs classic floor-trader pivots from the prior UTC day (H+L+C)/3 plus R1/S1. Not a rolling Donchian.

## What to write

1. `core/strategy/prior_day_pivot_breakout.py` — `Strategy` subclass, `name = "prior_day_pivot_breakout"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("prior_day_pivot_breakout")`.
