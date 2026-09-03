# Proposal: `double_bottom_neckline_break`

Long a confirmed double-bottom neckline break; short the second-low invalidation.

Two swing lows inside lookback match within 0.15*ATR(20). LONG waits for a confirmed close through the intervening swing high. SHORT is close through the second low after that trough is in place, not a neckline break of two highs.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: In lookback (default 40) identify two swing lows whose prices differ by <= 0.15*ATR(20) and an intervening swing high (neckline). LONG when close_t crosses above that neckline. SHORT when the second low is in place and close_t crosses below it (pattern invalidation), not a neckline break of two highs. Free params: lookback, atr_tol. Not equal_high_low_restest_fade (job 110, fades a failed restest without neckline break). Not swing_failure_reversal. Not monday_range_sweep_reversal. Not failed_higher_high. Not a rename of double_top.

## What to write

1. `core/strategy/double_bottom_neckline_break.py` — `Strategy` subclass, `name = "double_bottom_neckline_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("double_bottom_neckline_break")`.
