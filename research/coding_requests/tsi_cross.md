# Proposal: `tsi_cross`

Trade TSI crossing zero.

TSI is double-smoothed momentum, not Chande's raw sum ratio.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs True Strength Index: double-smoothed momentum over double-smoothed absolute momentum. Not CMO and not RSI.

## What to write

1. `core/strategy/tsi_cross.py` — `Strategy` subclass, `name = "tsi_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("tsi_cross")`.
