# Proposal: `mcginley_dynamic_cross`

Trade McGinley Dynamic crossing price.

McGinley speed-adjusts with a fourth-power ratio, not CMO.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs McGinley Dynamic: MD = MD_prev + (close-MD_prev) / (N * (close/MD_prev)^4). Not EMA and not VIDYA.

## What to write

1. `core/strategy/mcginley_dynamic_cross.py` — `Strategy` subclass, `name = "mcginley_dynamic_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("mcginley_dynamic_cross")`.
