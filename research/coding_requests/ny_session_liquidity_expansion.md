# Proposal: `ny_session_liquidity_expansion`

Identifies the high and low of the New York session (13:00 to 21:00 UTC). If the preceding London session had low volatility (ATR ratio < 1.0), it enters a breakout trade in the direction of the first 4h candle close outside the NY range, u

It capitalizes on the structural expansion of volatility that occurs when New York market participants break out of compressed ranges established during quieter sessions.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Identifies the high and low of the New York session (13:00 to 21:00 UTC). If the preceding London session had low volatility (ATR ratio < 1.0), it enters a breakout trade in the direction of the first 4h candle close outside the NY range, using a trailing ATR stop.

## What to write

1. `core/strategy/ny_session_liquidity_expansion.py` — `Strategy` subclass, `name = "ny_session_liquidity_expansion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("ny_session_liquidity_expansion")`.
