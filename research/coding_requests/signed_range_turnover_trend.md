# Proposal: `signed_range_turnover_trend`

Follow signed range times turnover (direction plus participation).

The product of (close-open) and unused quote turnover is not an EMA of close and not ADX. Qstick ignores participation; Force Index uses Δclose × base volume. This is a rolling trend of signed-range × turnover.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs pulse = (close-open)*turnover, then trend = sum_N pulse / (prior-N mean|pulse| * N) with the current bar excluded from the baseline. LONG trend>k, SHORT trend<-k. Direction plus participation. Not an EMA/ADX clone. Not Qstick, not Force Index, not bar_vwap_inflow_surge, not BOP. Do not invent taker/CVD/netflow/on-chain/funding columns.

## What to write

1. `core/strategy/signed_range_turnover_trend.py` — `Strategy` subclass, `name = "signed_range_turnover_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one long and one short. Assert tests read turnover. Flipping bodies on a rising close tape must flip the side (not an EMA clone).
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("signed_range_turnover_trend")`.
