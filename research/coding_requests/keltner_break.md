# Proposal: `keltner_break`

Break a Keltner Channel band.

Keltner is ATR around EMA, not a stdev envelope.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Keltner Channel: EMA mid with ATR bands, then a close through the band. Not Bollinger stdev bands and not SuperTrend.

## What to write

1. `core/strategy/keltner_break.py` — `Strategy` subclass, `name = "keltner_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("keltner_break")`.
