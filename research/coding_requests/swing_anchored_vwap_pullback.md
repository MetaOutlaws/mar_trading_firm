# Proposal: `swing_anchored_vwap_pullback`

Pullback to VWAP anchored on confirmed_swings.

Same swing engine as fib_extension_break, different path: volume-weighted continuation. AVWAP is Σturnover/Σvolume from the impulse origin, not a 0.618 fib tag and not a 1.618 extension break.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs a pullback to VWAP anchored on causal confirmed_swings. Same last-event impulse as fib_extension_break (+1 new swing high, -1 new swing low, ffill). LONG: up-impulse ready, end>avwap, low<=avwap, close>avwap, origin intact. SHORT symmetric. avwap=Σturnover/Σvolume from origin publish. Invalidation is close back through origin. Not fib_retracement_bounce (dead 0.618). Not fib_extension_break (already in the book). Do not implement 0.618 or 1.618 in this family.

## What to write

1. `core/strategy/swing_anchored_vwap_pullback.py` — `Strategy` subclass, `name = "swing_anchored_vwap_pullback"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one long and one short. Assert avwap=Σturnover/Σvolume from two confirmed swings, not equal to the 0.618 fib tag, not equal to H+0.618*R.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("swing_anchored_vwap_pullback")`.
