# Proposal: `ease_of_movement_fade`

Fade extreme Ease of Movement.

EOM scales distance by box volume, not close-to-close force.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ease of Movement: midpoint change scaled by volume/range, then SMA. Not Force Index and not OBV.

## What to write

1. `core/strategy/ease_of_movement_fade.py` — `Strategy` subclass, `name = "ease_of_movement_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("ease_of_movement_fade")`.
