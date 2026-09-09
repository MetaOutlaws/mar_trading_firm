# Proposal: `sma20_stretch_fade`

SMA20 stretch fade — wick stretch vs SMA(20) of close by `k * ATR(20)`, then the same-bar close reclaims toward SMA (halfway line `0.5 * k * ATR`). LONG: stretch below SMA then reclaim toward SMA. SHORT: stretch above SMA then fade toward SMA. Clock: `4h/4h`. Side: BOTH.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: SMA period = 20 LOCKED / not searched; ATR period = 20 LOCKED / not searched; LONG = `(SMA - low) >= k*ATR` AND `close > SMA - 0.5*k*ATR`; SHORT = `(high - SMA) >= k*ATR` AND `close < SMA + 0.5*k*ATR`. Free search (1 only): `k` `[1.5, 2.0]`. Fill at `t+1` open.
- Why this is novel: SMA20 stretch fade as one 4h BOTH family. Wick stretch vs SMA(20) of close by k*ATR(20), then same-bar close reclaims toward SMA (halfway: 0.5*k*ATR). LONG = stretch below SMA then reclaim toward SMA. SHORT = stretch above SMA then fade toward SMA. Quant-locked: SMA20 + ATR20 (not searched). Free search (1 only): k [1.5, 2.0]. Not bb_medium_bw_upper_reject (BB tag + medium-BW close-inside). Not kairi_relative_fade (percent from SMA, no ATR wick + half-k reclaim). Not bollinger_mean_reversion (close-through BB). Not prior_close_magnet_fade (magnet is prior close). Not atr_open_flush_fade (138 — same-bar bar-open flush). Not utc_day_open_flush_fade (139 — UTC day-open flush). Not london_close_inventory_fade (100). Not three_white_soldiers (140). Not ny_close_inventory_fade (banned/parked). Do not recode spent families 118–140. Do not modify atr / three_* geometry.

## What to write

1. `core/strategy/sma20_stretch_fade.py` — `Strategy` subclass, `name = "sma20_stretch_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), LONG stretch-below reclaim, SHORT stretch-above fade, kit lock asserts search only `k` `[1.5, 2.0]`, SMA20 + ATR20 locked, distinction vs `bb_medium_bw_upper_reject`, `atr_open_flush_fade`, `utc_day_open_flush_fade`, `london_close_inventory_fade`, and `three_white_soldiers`.
4. Do not copy a rejected family and rename it. Do not recode 118–140. Do not clone `bb_medium_bw_upper_reject`, `atr_open_flush_fade`, `utc_day_open_flush_fade`, `london_close_inventory_fade`, or `three_white_soldiers`. Do not code `ny_close_inventory_fade`. Do not modify atr / three_* geometry.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
