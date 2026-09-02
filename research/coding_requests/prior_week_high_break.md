# Proposal: `prior_week_high_break`

Break the prior UTC week's high or low after that week has closed.

Weekly calendar aggregation is not in the indicator library.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs last completed UTC week's high/low, published only after Sunday closes. Not prior-day pivots and not a rolling Donchian.

## What to write

1. `core/strategy/prior_week_high_break.py` — `Strategy` subclass, `name = "prior_week_high_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("prior_week_high_break")`.
