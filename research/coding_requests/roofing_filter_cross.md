# Proposal: `roofing_filter_cross`

Trade the roofing filter crossing zero.

Roofing is HP then SuperSmoother; decycler is HP minus slow HP.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ehlers roofing filter: high-pass then SuperSmoother of close. Not a single high-pass decycler.

## What to write

1. `core/strategy/roofing_filter_cross.py` — `Strategy` subclass, `name = "roofing_filter_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("roofing_filter_cross")`.
