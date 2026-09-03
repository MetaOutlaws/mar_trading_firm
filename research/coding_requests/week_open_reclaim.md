# Proposal: `week_open_reclaim`

Reclaim this week's UTC Monday 00:00 open after a wrong-side excursion.

A Monday-open reclaim after three wrong-side 4h closes is not a weekend-range fade, not a prior-week high break, and not an AVWAP pullback.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs this week's UTC Monday 00:00 open (first 4h open of the ISO week). After at least 3 4h closes on the wrong side of that open, trade the reclaim: LONG when close crosses back above with volume above the prior-20 mean; SHORT when close crosses back below. Not monday_range_sweep_reversal. Not swing_anchored_vwap_pullback. Not prior_week_high_break.

## What to write

1. `core/strategy/week_open_reclaim.py` — `Strategy` subclass, `name = "week_open_reclaim"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("week_open_reclaim")`.
