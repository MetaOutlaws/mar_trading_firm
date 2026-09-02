# Proposal: `williams_fractal_break`

Break a confirmed Williams fractal.

A fractal is a 5-bar pivot confirmation, not a rolling channel.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Williams 5-bar fractals: a confirmed swing high/low at t-2, then a close through that fractal. Not Donchian N-bar max and not swing-failure.

## What to write

1. `core/strategy/williams_fractal_break.py` — `Strategy` subclass, `name = "williams_fractal_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("williams_fractal_break")`.
