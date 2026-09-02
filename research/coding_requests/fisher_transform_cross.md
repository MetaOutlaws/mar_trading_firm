# Proposal: `fisher_transform_cross`

Trade Fisher Transform crossing its trigger.

Fisher maps prices onto a Gaussian; it is not RSI or DPO.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Fisher Transform of a normalized median price, then a trigger of the prior Fisher value. Not a z-score fade of close.

## What to write

1. `core/strategy/fisher_transform_cross.py` — `Strategy` subclass, `name = "fisher_transform_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("fisher_transform_cross")`.
