# Proposal: `swing_failure_reversal`

Fade a failed break of the last swing high or low.

Market-structure pivots are not in the indicator library.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs swing highs/lows (N-bar pivots) and a failed break of the last swing. Not ATR/Donchian channel break.

## What to write

1. `core/strategy/swing_failure_reversal.py` — `Strategy` subclass, `name = "swing_failure_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("swing_failure_reversal")`.
