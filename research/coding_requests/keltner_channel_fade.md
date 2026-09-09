# Proposal: `keltner_channel_fade`

Keltner channel fade — wick tags EMA(20) of close ± `k * ATR(20)`, then the same-bar close rejects back inside that tagged band. SHORT: `high[t] > upper[t]` AND `close[t] < upper[t]`. LONG: `low[t] < lower[t]` AND `close[t] > lower[t]`. ATR is known before the signal bar (`atr.shift(1)`). Clock: `4h/4h`. Side: BOTH. This is a FADE / reject-inside edge — not `keltner_break`.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: EMA period = 20 of close LOCKED / not searched; ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`); require close back inside the tagged band LOCKED; SHORT = `high[t] > upper[t]` AND `close[t] < upper[t]`; LONG = `low[t] < lower[t]` AND `close[t] > lower[t]` (strict tag, not `>=`). Free search (1 only): `k` `[1.5, 2.0]`. Fill at `t+1` open.
- Why this is novel: Keltner channel fade as one 4h BOTH family. Same-bar wick tag of EMA(20) of close ± k*ATR(20), then close rejects back inside that tagged band. ATR known before the signal bar (atr.shift(1)). Quant-locked: EMA20 of close (not typical), ATR20, require close-inside, SHORT=high>upper AND close<upper / LONG=low<lower AND close>lower (strict tag, not >=). Free search (1 only): k [1.5, 2.0]. Not keltner_break (close-through typical-price Keltner / ATR10). Not sma20_stretch_fade (141 — SMA wick stretch + halfway reclaim). Not bb_medium_bw_upper_reject (BB + medium-BW). Not outside_bar_fail_reversion (142). Not three_black_crows / three_white_soldiers. Not atr_open_flush_fade / utc_day_open_flush_fade. Not failed_break_reclaim / expansion_fail_fade / candle_reject_reversal. Not ib_fail / nr7_fail / engulfing_fail. Not asia_range_london_reject / prior_day_extreme_reject. Not displacement_gap_follow (PARKED). Not range_compression_volume_thrust / inventory fades. Do not recode spent families 118–142. Do not modify sibling geometry.

## What to write

1. `core/strategy/keltner_channel_fade.py` — `Strategy` subclass, `name = "keltner_channel_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), LONG lower-band reject, SHORT upper-band reject, kit lock asserts search only `k` `[1.5, 2.0]`, EMA20 + ATR20 + close-inside locked, strict tag (not `>=`), distinction vs `keltner_break`, `sma20_stretch_fade`, `bb_medium_bw_upper_reject`, `outside_bar_fail_reversion`, `three_black_crows`, `three_white_soldiers`, `atr_open_flush_fade`, `utc_day_open_flush_fade`, `failed_break_reclaim`, `expansion_fail_fade`, `candle_reject_reversal`, `ib_fail_reversion`, `nr7_fail_reversion`, `engulfing_fail_reversion`, `asia_range_london_reject`, `prior_day_extreme_reject`, `range_compression_volume_thrust`, and inventory fades.
4. Do not copy a rejected family and rename it. Do not recode 118–142. Do not clone `keltner_break` or any keltner breakout class. Do not revive `displacement_gap_follow`. Do not modify sibling geometry.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
