# Proposal: `utc_session_twap_reversion`

Fade stretch away from the UTC-day TWAP.

TWAP is equal-time, VWAP is volume — different math.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs time-weighted average price resetting at UTC midnight (equal weight per bar, not volume). Not session VWAP.

## What to write

1. `core/strategy/utc_session_twap_reversion.py` — `Strategy` subclass, `name = "utc_session_twap_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("utc_session_twap_reversion")`.
