# Proposal: `session_liquidity_sweep_fade`

Identifies the high and low boundaries established during the Asian session (00:00-08:00 UTC). If the subsequent London or NY session sweeps outside this range by less than a threshold percentage (e.g., 1.0%) and immediately closes back ins

Exploits highly reliable daily liquidity-seeking behavior of market maker algorithms in range-bound regimes.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Identifies the high and low boundaries established during the Asian session (00:00-08:00 UTC). If the subsequent London or NY session sweeps outside this range by less than a threshold percentage (e.g., 1.0%) and immediately closes back inside the boundary on a 1h clock, it enters a reversal trade targeting the opposite side of the session range.

## What to write

1. `core/strategy/session_liquidity_sweep_fade.py` — `Strategy` subclass, `name = "session_liquidity_sweep_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_liquidity_sweep_fade")`.
