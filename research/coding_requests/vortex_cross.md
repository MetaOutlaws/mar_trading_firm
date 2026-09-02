# Proposal: `vortex_cross`

Trade +VI crossing -VI.

Vortex is a directional movement ratio, not ADX.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Vortex +VI/-VI from true-range-normalized VM+ / VM-. Not ADX and not SuperTrend.

## What to write

1. `core/strategy/vortex_cross.py` — `Strategy` subclass, `name = "vortex_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("vortex_cross")`.
