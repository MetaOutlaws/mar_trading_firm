# Proposal: `body_efficiency_follow`

Follow two consecutive high body-efficiency 4h bars in the same direction.

Two efficient same-direction bodies with non-decreasing volume is a follow, not a 3-bar rest break, not an engulfing reverse, and not a consecutive-close fade.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs two consecutive 4h bars with body efficiency |close-open|/true_range >= 0.7, the same close direction, and the second bar's volume >= the first. Follow that direction. Not three_bar_play. Not engulfing_reversal. Not consecutive_bar_exhaustion.

## What to write

1. `core/strategy/body_efficiency_follow.py` — `Strategy` subclass, `name = "body_efficiency_follow"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("body_efficiency_follow")`.
