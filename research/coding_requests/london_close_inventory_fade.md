# Proposal: `london_close_inventory_fade`

Fade an extreme London-close 4h bar on high volume, back to London VWAP.

The London cash-close 4h bar faded to London VWAP is not a London-range breakout and not a UTC-day box fade.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs the 4h bar covering 15:00–16:00 UTC and London-session VWAP (08:00–16:00), not UTC-midnight VWAP. Fade when that close is in the extreme 20% of the bar on volume above the prior-20 mean. Calendar London-close inventory. Not london_session_breakout. Not session_boundary_volume_fade. Not monday_range_sweep_reversal.

## What to write

1. `core/strategy/london_close_inventory_fade.py` — `Strategy` subclass, `name = "london_close_inventory_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("london_close_inventory_fade")`.
