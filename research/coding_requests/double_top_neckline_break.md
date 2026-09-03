# Proposal: `double_top_neckline_break`

Short a confirmed double-top neckline break; long the second-high invalidation.

Two swing highs inside lookback match within 0.15*ATR(20). SHORT waits for a confirmed close through the intervening swing low. LONG is close through the second high after that peak is in place, not a neckline break of two lows. Implement the high-high-neckline geometry; do not copy double_bottom and flip signs as a file rename.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: In lookback (default 40) identify two swing highs whose prices differ by <= 0.15*ATR(20) and an intervening swing low (neckline). SHORT when close_t crosses below that neckline. LONG when the second high is in place and close_t crosses above it (invalidation), not a neckline break of two lows. Free params: lookback, atr_tol. High-high-neckline geometry, not a sign-flipped double_bottom file. Distinct from 110: 110 fades a failed restest; this trades the confirmed neckline break.

## What to write

1. `core/strategy/double_top_neckline_break.py` — `Strategy` subclass, `name = "double_top_neckline_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("double_top_neckline_break")`.
