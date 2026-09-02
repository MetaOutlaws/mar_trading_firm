# Proposal: `session_liquidity_sweep_fade`

Captures high-probability mean-reversion flows when breakout traders are trapped outside key structural ranges during low-volatility regimes.

Exploits highly reliable daily liquidity-seeking behavior of market maker algorithms in range-bound regimes.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Captures high-probability mean-reversion flows when breakout traders are trapped outside key structural ranges during low-volatility regimes.

## What to write

1. `core/strategy/session_liquidity_sweep_fade.py` — `Strategy` subclass, `name = "session_liquidity_sweep_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("session_liquidity_sweep_fade")`.
