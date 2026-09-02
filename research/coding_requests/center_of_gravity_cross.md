# Proposal: `center_of_gravity_cross`

Trade CG oscillator crossing its trigger.

CG is a finite FIR oscillator, not a z-score of close.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ehlers Center of Gravity: weighted sum of closes / sum of weights, then a trigger. Not SMA and not Fisher.

## What to write

1. `core/strategy/center_of_gravity_cross.py` — `Strategy` subclass, `name = "center_of_gravity_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("center_of_gravity_cross")`.
