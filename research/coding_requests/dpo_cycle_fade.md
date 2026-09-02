# Proposal: `dpo_cycle_fade`

Fade causal DPO extremes.

DPO removes trend; not a Bollinger mean-reversion.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Detrended Price Oscillator with a causal lag (shift SMA by N/2+1 of PAST bars only). Fade DPO extremes.

## What to write

1. `core/strategy/dpo_cycle_fade.py` — `Strategy` subclass, `name = "dpo_cycle_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("dpo_cycle_fade")`.
