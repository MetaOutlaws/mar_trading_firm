# Proposal: `weekend_gap_fill`

Fade or fill the weekend gap versus Friday's UTC close.

Weekend calendar math is not in the indicator library.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Friday UTC close vs the first Monday bar (or Sat–Sun range). Calendar weekend, not a rolling gap of N bars.

## What to write

1. `core/strategy/weekend_gap_fill.py` — `Strategy` subclass, `name = "weekend_gap_fill"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("weekend_gap_fill")`.
