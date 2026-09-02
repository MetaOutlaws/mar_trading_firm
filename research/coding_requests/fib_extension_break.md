# Proposal: `fib_extension_break`

Break a 1.618 extension of a completed confirmed-swing impulse.

The 1.618 tag is two confirmed swings projected past the impulse end, not a rolling Donchian and not the 0.618 bounce of the same impulse. Follow-on to fib_retracement_bounce, not a clone.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs a 1.618 extension break of a completed impulse from causal confirmed_swings. Last event +1 new swing high, -1 new swing low, ffill. LONG: up-impulse ready, close>ext, close>H. SHORT symmetric. ext=end+0.618*(end-start). Optional inner 1.272 as zone start, not a second family. Invalidation is close back through impulse end. Ratios 1.272/1.618. Not Donchian, not fib_retracement_bounce. Do not implement the 0.618 retracement bounce.

## What to write

1. `core/strategy/fib_extension_break.py` — `Strategy` subclass, `name = "fib_extension_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one long and one short. Assert ext=end+0.618*(end-start) from two confirmed swings.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("fib_extension_break")`.
