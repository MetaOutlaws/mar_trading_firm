# Proposal: `ny_cash_open_drive`

Trade in the direction of the US cash-open hour after it closes.

US cash open is a calendar hour the library does not isolate.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs the 13:00–14:00 UTC (08:00–09:00 ET) cash-open hour as a drive bar. Not ORB and not a Donchian.

## What to write

1. `core/strategy/ny_cash_open_drive.py` — `Strategy` subclass, `name = "ny_cash_open_drive"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("ny_cash_open_drive")`.
