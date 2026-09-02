# Proposal: `session_volume_profile_reversal`

Identifies the Value Area High (VAH) and Value Area Low (VAL) of the preceding UTC session. When price sweeps outside these boundaries on below-average volume and immediately closes back inside the value area on a 1h clock, it enters a reve

Exploits institutional limit order absorption at key structural boundaries where retail stop-losses are clustered.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Identifies the Value Area High (VAH) and Value Area Low (VAL) of the preceding UTC session. When price sweeps outside these boundaries on below-average volume and immediately closes back inside the value area on a 1h clock, it enters a reversion trade targeting the Point of Control (POC).

## What to write

1. `core/strategy/session_volume_profile_reversal.py` — `Strategy` subclass, `name = "session_volume_profile_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_volume_profile_reversal")`.
