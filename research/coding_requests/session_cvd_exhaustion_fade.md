# Proposal: `session_cvd_exhaustion_fade`

Fades price extensions outside the rolling 24-hour session range when Cumulative Volume Delta (CVD) shows a clear divergence (price makes a new high/low but CVD fails to confirm), indicating aggressive market orders are being absorbed by pa

Directly targets institutional limit order absorption at key liquidity pools, which is highly effective in choppy, non-trending regimes.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Fades price extensions outside the rolling 24-hour session range when Cumulative Volume Delta (CVD) shows a clear divergence (price makes a new high/low but CVD fails to confirm), indicating aggressive market orders are being absorbed by passive limit orders.

## What to write

1. `core/strategy/session_cvd_exhaustion_fade.py` — `Strategy` subclass, `name = "session_cvd_exhaustion_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_cvd_exhaustion_fade")`.
