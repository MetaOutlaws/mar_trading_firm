# Proposal: `rainbow_oscillator_cross`

Trade Rainbow Oscillator crossing zero.

Rainbow is a multi-SMA ribbon oscillator, not MACD.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Rainbow Oscillator: stacked SMAs of close, oscillator of the ribbon width. Not a dual-EMA MACD.

## What to write

1. `core/strategy/rainbow_oscillator_cross.py` — `Strategy` subclass, `name = "rainbow_oscillator_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("rainbow_oscillator_cross")`.
