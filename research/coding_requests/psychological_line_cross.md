# Proposal: `psychological_line_cross`

Trade PSY crossing 50.

PSY is a count of up days, not an average-gain oscillator.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Psychological Line: 100 * share of up-closes over N. Not RSI Wilder smoothing and not CMO.

## What to write

1. `core/strategy/psychological_line_cross.py` — `Strategy` subclass, `name = "psychological_line_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("psychological_line_cross")`.
