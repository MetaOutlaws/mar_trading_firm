# Proposal: `prior_session_mid_reclaim`

Reclaim the prior completed UTC 8h session midpoint.

An 8h session-mid reclaim after the session closes through one side is not a UTC-day box fade, not a session-VWAP stretch, and not a first-4h opening-box fail.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs UTC 8h sessions 00-08 / 08-16 / 16-24. After the session closes through one side of its (high+low)/2 midpoint, a later 4h bar that closes back through that mid on volume above the prior-20 mean trades the reclaim. Not session_boundary_volume_fade. Not utc_session_vwap_reversion. Not utc_open_fail_reversion.

## What to write

1. `core/strategy/prior_session_mid_reclaim.py` — `Strategy` subclass, `name = "prior_session_mid_reclaim"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("prior_session_mid_reclaim")`.
