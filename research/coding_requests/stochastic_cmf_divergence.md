# Proposal: `stochastic_cmf_divergence`

Applies a 14-period Stochastic oscillator formula to the Chaikin Money Flow (CMF) indicator instead of raw price. It enters a reversal trade when price makes a new 20-bar high/low but the Stochastic CMF prints a clear divergence from the ov

By smoothing volume-weighted accumulation/distribution rather than raw price, it filters out low-volume price sweeps that lack institutional backing.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Applies a 14-period Stochastic oscillator formula to the Chaikin Money Flow (CMF) indicator instead of raw price. It enters a reversal trade when price makes a new 20-bar high/low but the Stochastic CMF prints a clear divergence from the overbought (>80) or oversold (<20) thresholds.

## What to write

1. `core/strategy/stochastic_cmf_divergence.py` — `Strategy` subclass, `name = "stochastic_cmf_divergence"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("stochastic_cmf_divergence")`.
