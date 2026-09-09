# Proposal: `displacement_gap_follow`

Displacement gap follow — trade with an unfilled adjacent-bar gap that prints an efficient body in the gap direction. LONG when the bar gaps up and closes bullish; SHORT when it gaps down and closes bearish. Clock: `4h/4h`. Side: BOTH.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: ATR period = 20 LOCKED / not searched; ATR known before the signal bar; gap definition LOCKED (`low[t] > high[t-1]` LONG / `high[t] < low[t-1]` SHORT); follow the gap (not fade / fill). Free search (2 only): `min_gap_atr` `[0.10, 0.25]`, `min_body_eff` `[0.50, 0.70]`. LONG body `(close-open)/(high-low)`; SHORT body `(open-close)/(high-low)`; zero-range bars never fire. Fill at `t+1` open.
- Why this is novel: Displacement gap follow as one 4h BOTH family. Follow an unfilled adjacent-bar gap that prints an efficient body in the gap direction. LONG: low[t] > high[t-1] AND close[t] > open[t], gap (low[t]-high[t-1]) >= min_gap_atr * ATR20, body (close-open)/(high-low) >= min_body_eff (zero-range guarded). SHORT: high[t] < low[t-1] AND close[t] < open[t], gap (low[t-1]-high[t]) >= min_gap_atr * ATR20, body (open-close)/(high-low) >= min_body_eff. Quant-locked: ATR20 known before the signal bar, gap definition, follow not fade (not searched). Free search (2 only): min_gap_atr [0.10, 0.25], min_body_eff [0.50, 0.70]. Not weekend_gap_fill (Monday fade toward Friday). Not utc_midnight_gap_fill (first-hour fade toward prior close). Not body_efficiency_follow (two-bar |body|/TR + volume; no gap). Not open_in_prior_range_fail (gap open then close back inside prior bar). Not outside_bar_fail_reversion (142). Not sma20_stretch_fade (141). Not bb_medium_bw_upper_reject. Not three_white_soldiers (140) / three_black_crows (134). Not atr_open_flush_fade (138). Not utc_day_open_flush_fade (139). Not failed_break_reclaim (130). Not expansion_fail_fade (131). Not candle_reject_reversal. Not ib_fail_reversion (124). Not nr7_fail_reversion (123). Not engulfing_fail_reversion (126). Not asia_range_london_reject (121). Not prior_day_extreme_reject (118). Not range_compression_volume_thrust (102). Not london_close / ny_close inventory fades. Do not recode spent families 118–142. Do not modify sibling geometry.

## What to write

1. `core/strategy/displacement_gap_follow.py` — `Strategy` subclass, `name = "displacement_gap_follow"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), LONG gap-up, SHORT gap-down, kit lock asserts search only `min_gap_atr` `[0.10, 0.25]` and `min_body_eff` `[0.50, 0.70]`, ATR20 locked, distinction vs `outside_bar_fail_reversion`, `sma20_stretch_fade`, `bb_medium_bw_upper_reject`, `three_black_crows`, `three_white_soldiers`, `atr_open_flush_fade`, `utc_day_open_flush_fade`, `failed_break_reclaim`, `expansion_fail_fade`, `candle_reject_reversal`, `ib_fail_reversion`, `nr7_fail_reversion`, `engulfing_fail_reversion`, `asia_range_london_reject`, `prior_day_extreme_reject`, `body_efficiency_follow`, `open_in_prior_range_fail`, `range_compression_volume_thrust`, `weekend_gap_fill`, `utc_midnight_gap_fill`, and `london_close_inventory_fade`.
4. Do not copy a rejected family and rename it. Do not recode 118–142. Do not clone the siblings listed above. Do not code `ny_close_inventory_fade`. Do not modify sibling geometry.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
