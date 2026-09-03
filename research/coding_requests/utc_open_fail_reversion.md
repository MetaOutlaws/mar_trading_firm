# Proposal: `utc_open_fail_reversion`

Fade a failed break of the UTC day's first 4h box on the second 4h bar.

A failed second-4h break of the first-4h UTC box is not a midnight gap fill and not an Asian-range breakout.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs the UTC day's first 4h (00:00–04:00) as a box, then a failed break on the second 4h (04:00–08:00) that closes back inside, fading toward the first-4h mid. Not utc_midnight_gap_fill. Not asian_range_breakout. Not session_liquidity_sweep.

## What to write

1. `core/strategy/utc_open_fail_reversion.py` — `Strategy` subclass, `name = "utc_open_fail_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("utc_open_fail_reversion")`.
