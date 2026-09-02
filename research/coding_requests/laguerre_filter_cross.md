# Proposal: `laguerre_filter_cross`

Trade the Laguerre filter crossing its trigger.

The Laguerre filter is a gamma FIR of price, not RSI-mapped poles.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ehlers Laguerre filter of close (four-pole gamma FIR), then a cross of filter vs its prior-bar trigger. Not Laguerre RSI and not EMA.

## What to write

1. `core/strategy/laguerre_filter_cross.py` — `Strategy` subclass, `name = "laguerre_filter_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("laguerre_filter_cross")`.
