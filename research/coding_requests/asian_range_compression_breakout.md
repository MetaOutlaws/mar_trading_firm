# Proposal: `asian_range_compression_breakout`

Measures the ratio of the Asian session range (00:00-08:00 UTC) to the 10-day average daily range. If the session is highly compressed (ratio < 0.7), it enters a breakout trade in the direction of the first 4h candle close outside the Asian

Filters out low-volatility noise and only takes breakouts when the market has stored significant energy, increasing the probability of a sustained trend.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Measures the ratio of the Asian session range (00:00-08:00 UTC) to the 10-day average daily range. If the session is highly compressed (ratio < 0.7), it enters a breakout trade in the direction of the first 4h candle close outside the Asian range during the London/NY overlap.

## What to write

1. `core/strategy/asian_range_compression_breakout.py` — `Strategy` subclass, `name = "asian_range_compression_breakout"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("asian_range_compression_breakout")`.
