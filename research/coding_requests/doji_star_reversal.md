# Proposal: `doji_star_reversal`

Fade after a doji that prints following a directional run.

Doji body/range ratio plus run context is new candle math.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs a doji (small body vs range) after a directional run, then the next close. Not wick-rejection and not engulfing.

## What to write

1. `core/strategy/doji_star_reversal.py` — `Strategy` subclass, `name = "doji_star_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("doji_star_reversal")`.
