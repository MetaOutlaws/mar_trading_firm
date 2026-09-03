# Proposal: `turnover_climax_rejection_fade`

Fade a quote-turnover climax whose close rejects the 20-bar extreme.

A 20-bar turnover climax with a rejected close is not an RSI volume-climax fade and not a follow-the-money imbalance.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs unused quote turnover as a 20-bar high, then a fade when that climax bar breaks the 20-bar price high and closes in the lower 20% (SHORT) or breaks the 20-bar low and closes in the upper 20% (LONG). Climax + rejection. Not volume_climax_fade. Not bar_vwap_inflow_surge. Not up_down_turnover_imbalance.

## What to write

1. `core/strategy/turnover_climax_rejection_fade.py` — `Strategy` subclass, `name = "turnover_climax_rejection_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("turnover_climax_rejection_fade")`.
