# Proposal: `super_smoother_cross`

Trade SuperSmoother crossing its trigger.

SuperSmoother is a 2-pole Butterworth, not Laguerre poles.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ehlers SuperSmoother 2-pole IIR of close, then a cross of filter vs trigger. Not Laguerre gamma FIR and not EMA.

## What to write

1. `core/strategy/super_smoother_cross.py` — `Strategy` subclass, `name = "super_smoother_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("super_smoother_cross")`.
