# Proposal: `dema_cross`

Trade DEMA crossing a slow DEMA.

Two DEMAs, not ZLEMA versus a single EMA.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs double EMA (DEMA) crossing a slow DEMA. Distinct from zero-lag 2*EMA-EMA(EMA) used as a fast line versus a raw EMA.

## What to write

1. `core/strategy/dema_cross.py` — `Strategy` subclass, `name = "dema_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("dema_cross")`.
