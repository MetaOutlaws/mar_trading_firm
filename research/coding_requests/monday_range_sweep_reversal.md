# Proposal: `monday_range_sweep_reversal`

Identifies the high and low boundaries established during the UTC weekend (Saturday 00:00 to Sunday 23:59). When the Monday London or NY session sweeps outside this range by less than 1.5% and closes back inside on a 4h clock, it enters a r

Weekend ranges represent low-volume retail positioning that institutional algorithms frequently target for liquidity sweeps before establishing the true weekly direction.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Identifies the high and low boundaries established during the UTC weekend (Saturday 00:00 to Sunday 23:59). When the Monday London or NY session sweeps outside this range by less than 1.5% and closes back inside on a 4h clock, it enters a reversion trade targeting the weekend mid-point.

## What to write

1. `core/strategy/monday_range_sweep_reversal.py` — `Strategy` subclass, `name = "monday_range_sweep_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("monday_range_sweep_reversal")`.
