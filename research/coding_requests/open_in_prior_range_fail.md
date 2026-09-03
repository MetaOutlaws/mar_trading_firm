# Proposal: `open_in_prior_range_fail`

Fade a same-bar fail of an open that started outside the prior bar's high-low, toward the prior-bar mid.

This-bar open vs prior-bar range, then same-bar fail. Adjacent 4h bar math, not a UTC first-4h box and not a NY cash-open drive.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: If this 4h opens outside the prior 4h high-low, then the close fails back inside that prior range, fade toward the prior-bar mid (SHORT if opened above prior high and closed back inside; LONG if opened below prior low and closed back inside). Not utc_open_fail_reversion (UTC first-4h box, 0/12). Not ny_cash_open_drive.

## What to write

1. `core/strategy/open_in_prior_range_fail.py` — `Strategy` subclass, `name = "open_in_prior_range_fail"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("open_in_prior_range_fail")`.
