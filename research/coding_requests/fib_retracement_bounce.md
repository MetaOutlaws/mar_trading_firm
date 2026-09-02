# Proposal: `fib_retracement_bounce`

Bounce the 0.618 retracement of a completed confirmed-swing impulse.

The 0.618 tag is two confirmed swings, not a rolling Donchian, not a daily floor pivot, and not a failed swing break. Extensions are a different family.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs a 0.618 bounce of a completed confirmed impulse from causal confirmed_swings. LONG: last event is swing high after a distinct low, tag 0.618, close back above it, origin intact. SHORT symmetric. Ratios 0.500/0.618/0.786. Optional 0.15*ATR buffer. Not Donchian, not floor pivots, not round_number_fade, not swing_failure_reversal. Do not implement 1.272/1.618 extensions.

## What to write

1. `core/strategy/fib_retracement_bounce.py` — `Strategy` subclass, `name = "fib_retracement_bounce"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one long and one short. Assert 0.618 comes from two confirmed swings not Donchian.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("fib_retracement_bounce")`.
