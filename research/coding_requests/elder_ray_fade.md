# Proposal: `elder_ray_fade`

Fade extreme Elder Ray Bear/Bull Power.

Elder Ray measures bar extremes vs EMA, not signed volume.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Elder Ray Bull/Bear Power: high-EMA and low-EMA, fade extreme Bear Power turning up. Not ATR channel and not Force Index.

## What to write

1. `core/strategy/elder_ray_fade.py` — `Strategy` subclass, `name = "elder_ray_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("elder_ray_fade")`.
