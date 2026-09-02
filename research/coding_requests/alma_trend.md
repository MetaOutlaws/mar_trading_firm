# Proposal: `alma_trend`

Trade an ALMA turn.

ALMA uses a Gaussian window, not cascaded EMAs.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Arnaud Legoux MA: Gaussian weights with offset. Not SMA, EMA, Hull, or T3.

## What to write

1. `core/strategy/alma_trend.py` — `Strategy` subclass, `name = "alma_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("alma_trend")`.
