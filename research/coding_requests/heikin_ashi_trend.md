# Proposal: `heikin_ashi_trend`

Trade in the direction of a Heikin-Ashi run.

HA averaging is new bar math, not EMA trend.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Heikin-Ashi open/close (HA close = OHLC/4, HA open = prior HA midpoint). Not raw candle direction.

## What to write

1. `core/strategy/heikin_ashi_trend.py` — `Strategy` subclass, `name = "heikin_ashi_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("heikin_ashi_trend")`.
