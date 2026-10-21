# Approved for Cursor: `session_relative_variance_fade`

The operator approved this brief in Inbox. Implement it now.

# Proposal: `session_relative_variance_fade`

Fade price moves that exceed a rolling session-relative variance threshold. It calculates the rolling standard deviation of the typical price over a 24-bar lookback, normalized by the ATR, and enters a reversion trade when price stretches b

Captures exhaustion at the outer boundaries of established intraday value areas when momentum is not supported by institutional volume.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `SHORT`
- Why this is novel: Fade price moves that exceed a rolling session-relative variance threshold. It calculates the rolling standard deviation of the typical price over a 24-bar lookback, normalized by the ATR, and enters a reversion trade when price stretches beyond 2.5 standard deviations from the session VWAP, closing back inside.

## What to write

1. `core/strategy/session_relative_variance_fade.py` — `Strategy` subclass, `name = "session_relative_variance_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_relative_variance_fade")`.


Source: `/app/research/coding_requests/session_relative_variance_fade.md`
