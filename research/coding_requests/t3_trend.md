# Proposal: `t3_trend`

Trade in the direction of a T3 turn.

T3 is a six-pole EMA cascade, not HMA's WMA construction.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Tillson T3: six cascaded EMAs with a volume factor. Not Hull MA and not a single EMA.

## What to write

1. `core/strategy/t3_trend.py` — `Strategy` subclass, `name = "t3_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("t3_trend")`.
