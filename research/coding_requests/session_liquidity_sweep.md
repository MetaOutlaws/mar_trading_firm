# Proposal: `session_liquidity_sweep`

Identifies the high and low of the Asian session (00:00-08:00 UTC). If the London or NY session sweeps this range by less than 1.0% and immediately closes back inside the boundary on a 1h clock, it enters a reversal trade targeting the oppo

Exploits structural stop-hunting behavior and market maker inventory rebalancing at well-defined daily boundaries.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Identifies the high and low of the Asian session (00:00-08:00 UTC). If the London or NY session sweeps this range by less than 1.0% and immediately closes back inside the boundary on a 1h clock, it enters a reversal trade targeting the opposite side of the session range.

## What to write

1. `core/strategy/session_liquidity_sweep.py` — `Strategy` subclass, `name = "session_liquidity_sweep"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_liquidity_sweep")`.
