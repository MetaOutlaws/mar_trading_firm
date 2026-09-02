# Proposal: `measured_move_break`

Break a 100% measured move (AB=CD) of a completed confirmed-swing impulse.

The measured move projects 100% of two confirmed swings past the impulse end. That is not a rolling Donchian and not the 1.618 extension of the same impulse. Follow-on to fib_extension_break, not a clone.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs an AB=CD measured-move break of a completed impulse from causal confirmed_swings. Same last-event impulse as fib_extension_break. LONG: up-impulse ready, close>mm, close>H. SHORT symmetric. mm=end+1.0*(end-start)=2*end-start. Invalidation is close back through impulse end. Ratio locked at 1.0. Not Donchian, not H+0.618*R, not fib_extension_break. Do not implement 1.618 or 0.618 in this family.

## What to write

1. `core/strategy/measured_move_break.py` — `Strategy` subclass, `name = "measured_move_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one long and one short. Assert mm=end+1.0*(end-start) from two confirmed swings, not Donchian, not equal to H+0.618*R.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("measured_move_break")`.
