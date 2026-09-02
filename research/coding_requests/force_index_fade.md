# Proposal: `force_index_fade`

Fade an extreme Force Index print.

Force Index is signed volume, not RSI.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Elder Force Index = (close-prior close)*volume, then EMA. Not volume climax RSI.

## What to write

1. `core/strategy/force_index_fade.py` — `Strategy` subclass, `name = "force_index_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("force_index_fade")`.
