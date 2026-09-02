# Proposal: `bar_vwap_inflow_surge`

Follow a per-bar VWAP inflow surge from unused turnover.

Turnover/volume is a bar VWAP the other volume ledgers never use. A one-bar pulse versus its own prior |pulse| is not a cumulative force and not a fade of a price extreme.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs per-bar VWAP from unused turnover/volume, then pulse = volume*(close-bar_vwap)/ATR versus the prior-20 |pulse| baseline (current bar excluded). LONG surge>2, SHORT<-2. Optional same-direction body. Not OBV/VPT/Force/volume_force_divergence/ADL/CMF/Klinger/climax fade. Do not cumsum. Do not fade. Do not invent taker/CVD/netflow/on-chain/funding columns.

## What to write

1. `core/strategy/bar_vwap_inflow_surge.py` — `Strategy` subclass, `name = "bar_vwap_inflow_surge"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one long and one short. Assert tests read turnover.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("bar_vwap_inflow_surge")`.
