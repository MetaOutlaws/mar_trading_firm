# Proposal: `session_cvd_exhaustion_fade`

Calculates a rolling Cumulative Volume Delta (CVD) over the current UTC session. When price sweeps the session high or low on a 1h clock but CVD fails to confirm (printing a lower high or higher low), it triggers a mean-reversion trade targ

Directly targets institutional limit order absorption at key liquidity pools, which is highly effective in choppy, non-trending regimes.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Calculates a rolling Cumulative Volume Delta (CVD) over the current UTC session. When price sweeps the session high or low on a 1h clock but CVD fails to confirm (printing a lower high or higher low), it triggers a mean-reversion trade targeting the session VWAP, filtered by a low ADX to ensure a range-bound regime.

## What to write

1. `core/strategy/session_cvd_exhaustion_fade.py` — `Strategy` subclass, `name = "session_cvd_exhaustion_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_cvd_exhaustion_fade")`.
