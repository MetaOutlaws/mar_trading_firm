# Proposal: `london_session_breakout`

Break the completed London (08:00–16:00 UTC) range.

London cash hours are a different session box than Asia or ORB.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs the high/low of 08:00–16:00 UTC, published only after 16:00. Not Asian 00–08 and not the 1-hour opening range.

## What to write

1. `core/strategy/london_session_breakout.py` — `Strategy` subclass, `name = "london_session_breakout"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("london_session_breakout")`.
