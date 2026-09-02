# Proposal: `utc_midnight_gap_fill`

Fade the UTC-midnight gap back toward the prior day's close.

Daily gap vs prior close is calendar math, not a channel.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs the gap from prior UTC day close to today's first hour open, then a fade toward the prior close. Not VWAP and not opening-range break.

## What to write

1. `core/strategy/utc_midnight_gap_fill.py` — `Strategy` subclass, `name = "utc_midnight_gap_fill"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("utc_midnight_gap_fill")`.
