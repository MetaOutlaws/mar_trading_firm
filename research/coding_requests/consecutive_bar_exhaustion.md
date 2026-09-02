# Proposal: `consecutive_bar_exhaustion`

Fade after N consecutive closes in one direction.

Run-length of directional closes is new bar math.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs a count of consecutive up/down closes, then a fade. Not RSI and not a volume climax template.

## What to write

1. `core/strategy/consecutive_bar_exhaustion.py` — `Strategy` subclass, `name = "consecutive_bar_exhaustion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("consecutive_bar_exhaustion")`.
