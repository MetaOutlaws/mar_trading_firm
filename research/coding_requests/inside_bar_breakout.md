# Proposal: `inside_bar_breakout`

Break the mother bar after an inside bar.

Pattern is two-bar structure, not a channel lookback.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs a mother-bar high/low: current bar range fully inside the prior bar, then a later close through that mother range. Not N-bar Donchian.

## What to write

1. `core/strategy/inside_bar_breakout.py` — `Strategy` subclass, `name = "inside_bar_breakout"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("inside_bar_breakout")`.
