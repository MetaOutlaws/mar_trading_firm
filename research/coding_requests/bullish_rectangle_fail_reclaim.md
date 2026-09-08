# Proposal: `bullish_rectangle_fail_reclaim`

Flat dual-rail rectangle (support + resistance). Price closes outside a rail then closes back inside the box (fail-reclaim / fade). NOT a breakout continuation. LONG: close below support, then close back inside. SHORT: close above resistance, then close back inside. Clock: `4h/4h`. Side: BOTH.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `max_bars_outside = 2` LOCKED / not searched (not a `[1, 2]` grid); `require_close_inside = True` LOCKED; ATR period `20` LOCKED; `min_touches_per_rail = 2` LOCKED; `PIVOT_LEFT = 3` LOCKED. Free search (2 only): `lookback` `[24, 32]`, `atr_tol` `[0.10, 0.15]`. Fail-reclaim only — close outside then back inside within `max_bars_outside`. Do not implement breakout entries.
- Why this is novel: Classic flat dual-rail rectangle (multi-touch support + resistance). LONG = close below the flat lower rail, then close back inside the box. SHORT = close above the flat upper rail, then close back inside. Rails are published swing clusters whose span is `<= atr_tol · ATR(20)`, at least two touches per rail. Quant-locked: max_bars_outside=2 (not searched; clearer of job 119), require_close_inside=True, ATR period 20, min_touches_per_rail=2, PIVOT_LEFT=3. Free search (2 only): lookback [24, 32], atr_tol [0.10, 0.15]. Not failed_range_break_reversion (119 — Donchian close-through, no dual-rail multi-touch flat rectangle). Not failed_break_reclaim (130 — Donchian wick-probe, no flat rectangle rails / multi-touch box). Not a triangle / wedge / H&S / cup / pennant / three_black_crows / displacement recode. Do not recode spent families 118–132.

## What to write

1. `core/strategy/bullish_rectangle_fail_reclaim.py` — `Strategy` subclass, `name = "bullish_rectangle_fail_reclaim"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG fail-reclaim below support and one SHORT fail-reclaim above resistance, kit lock asserts search only `lookback` `[24, 32]` plus `atr_tol` `[0.10, 0.15]`, `max_bars_outside` locked at 2, multi-touch rails, `require_close_inside`, distinction vs breakout and vs `failed_break_reclaim` / `failed_range_break_reversion`.
4. Do not copy a rejected family and rename it. Do not recode 118–132. Do not code `three_black_crows` or `displacement_gap_follow`. Do not implement breakout entries.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
