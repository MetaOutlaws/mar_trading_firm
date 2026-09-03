# Proposal: `equal_high_low_restest_fade`

Fade a failed restest of a rolling equal high or equal low.

If a 4h high (low) matches a prior high (low) within a small tick/ATR tolerance inside a lookback, then this bar trades through that level and closes back inside. Family id is `restest` as spelled, not `retest`.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Rolling equal high/low restest fail. If a 4h high (low) matches a prior high (low) within a small tick/ATR tolerance inside a lookback, then this bar trades through that level and closes back inside, fade the failed restest. Not monday_range_sweep_reversal (weekend box). Not session_liquidity_sweep (dead, do not recode).

## What to write

1. `core/strategy/equal_high_low_restest_fade.py` — `Strategy` subclass, `name = "equal_high_low_restest_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("equal_high_low_restest_fade")`.
