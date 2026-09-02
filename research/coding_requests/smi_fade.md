# Proposal: `smi_fade`

Fade SMI extremes.

SMI double-smooths distance to the range midpoint, not %K of close.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Stochastic Momentum Index: double-smoothed close vs midpoint of HH/LL. Not Stochastic %K and not Williams %R.

## What to write

1. `core/strategy/smi_fade.py` — `Strategy` subclass, `name = "smi_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("smi_fade")`.
