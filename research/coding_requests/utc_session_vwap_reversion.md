# Proposal: `utc_session_vwap_reversion`

Fade stretch away from the UTC-day VWAP.

Session VWAP is untested here; requires cumulative volume math.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs VWAP reset at each UTC midnight from typical-price * volume. Not a rolling SMA and not a Bollinger fade.

## What to write

1. `core/strategy/utc_session_vwap_reversion.py` — `Strategy` subclass, `name = "utc_session_vwap_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("utc_session_vwap_reversion")`.
