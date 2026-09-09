# Proposal: `three_white_soldiers`

Classic three white soldiers — three consecutive bullish candles with ascending closes; each opens within the prior candle's range; substantial bodies; limited lower wicks. LONG entry after the third soldier confirms. Clock: `4h/4h`. Side: LONG (LONG-bias — not BOTH). Mirror of `three_black_crows` SHORT.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `LONG`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `n_bars = 3` LOCKED / not searched; exactly 3 consecutive bullish ascending closes (`close[t] > close[t-1] > close[t-2]`, each bullish); each soldier opens in the prior candle's range (open inside prior high-low) LOCKED; LONG side only LOCKED. Free search (2 only): `min_body_frac` `[0.40, 0.50]`, `max_lower_wick_frac` `[0.15, 0.25]` (not `max_lower_wick`).
- Why this is novel: Classic three white soldiers as a LONG-only family. Three consecutive bullish candles with ascending closes; each opens within the prior candle's high-low; substantial bodies; limited lower wicks. LONG entry after the third soldier confirms. Quant-locked: n_bars=3 (not searched), open-in-prior-range locked, LONG only (not BOTH / not three black crows). Free search (2 only): min_body_frac [0.40, 0.50], max_lower_wick_frac [0.15, 0.25]. Not three_black_crows (job 134 — SHORT-only descending bearish crows). Not three_bar_play (trend + narrow rest + break of rest leftover). Not engulfing_fail_reversion (job 126 — two-bar body engulf then fail through engulf open). Not atr_open_flush_fade (138 — same-bar bar-open flush fade). Not utc_day_open_flush_fade (139 — UTC day-open flush fade). Not ny_close_inventory_fade (banned/parked). Do not recode spent families 118–139. Do not modify three_black_crows geometry.

## What to write

1. `core/strategy/three_white_soldiers.py` — `Strategy` subclass, `name = "three_white_soldiers"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), LONG three-soldier entry, kit lock asserts search only `min_body_frac` `[0.40, 0.50]` plus `max_lower_wick_frac` `[0.15, 0.25]`, `n_bars` locked at 3, open-in-prior-range locked, ascending-closes lock, distinction vs `three_black_crows`, `three_bar_play`, `engulfing_fail_reversion`, `atr_open_flush_fade`, and `utc_day_open_flush_fade`.
4. Do not copy a rejected family and rename it. Do not recode 118–139. Do not code SHORT three black crows / BOTH in this file. Do not modify `three_black_crows` geometry. Do not clone `three_bar_play` leftover or `engulfing_fail_reversion`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
