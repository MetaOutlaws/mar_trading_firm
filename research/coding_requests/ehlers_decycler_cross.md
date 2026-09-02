# Proposal: `ehlers_decycler_cross`

Trade the Ehlers decycler crossing zero.

Decycler is a high-pass FIR, not detrended price vs SMA.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ehlers high-pass decycler of close vs a slow decycler. Not DPO with a causal SMA lag.

## What to write

1. `core/strategy/ehlers_decycler_cross.py` — `Strategy` subclass, `name = "ehlers_decycler_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("ehlers_decycler_cross")`.
