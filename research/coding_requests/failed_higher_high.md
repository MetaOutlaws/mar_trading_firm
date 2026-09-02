# Proposal: `failed_higher_high`

Fade a failed higher-high against the prior swing high.

Two-swing structure is not one wick through one pivot.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs two consecutive swing highs where the second makes a higher high then closes back below the first. Not a single swing-failure.

## What to write

1. `core/strategy/failed_higher_high.py` — `Strategy` subclass, `name = "failed_higher_high"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("failed_higher_high")`.
