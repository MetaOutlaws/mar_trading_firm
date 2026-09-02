# Proposal: `round_number_fade`

Fade a rejection of a round psychological price.

Round-number grid is not a pivot and not a channel.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs psychological round levels (100/1000 steps of price) and a rejection. Not floor pivots from H+L+C.

## What to write

1. `core/strategy/round_number_fade.py` — `Strategy` subclass, `name = "round_number_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("round_number_fade")`.
