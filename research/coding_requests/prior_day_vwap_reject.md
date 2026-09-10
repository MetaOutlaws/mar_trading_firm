# Proposal: `prior_day_vwap_reject`

Prior completed UTC-day VWAP stretch reject — wick-stretch the prior *completed* UTC day's session VWAP by `k*ATR`, then the same-bar close reclaims halfway toward VWAP. SHORT: `high[t] >= VWAP + k*ATR` AND `close[t] < VWAP + 0.5*k*ATR`. LONG: `low[t] <= VWAP - k*ATR` AND `close[t] > VWAP - 0.5*k*ATR`. ATR is known before the signal bar (`atr.shift(1)`). Clock: `4h/4h`. Side: BOTH. This is a FADE / halfway-reclaim-toward-prior-day-VWAP edge — not developing session VWAP, not swing AVWAP, not rolling VWAP band/spread, not POC/HVN.

## Coding brief (Brian Inbox-approved + Quant AUTHORITATIVE for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved + Quant AUTHORITATIVE for coding (do not start walk-forward). Live stays off.
- Quant lock: VWAP = prior COMPLETED UTC-day session VWAP only (00:00–24:00 UTC previous day, typical-price volume/turnover weighted). Never use a forming/incomplete day. Never use developing/live session VWAP. ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). Reject toward VWAP (halfway reclaim, frac = 0.5 locked). SHORT = `high[t] >= VWAP + k*ATR` AND `close[t] < VWAP + 0.5*k*ATR`; LONG = `low[t] <= VWAP - k*ATR` AND `close[t] > VWAP - 0.5*k*ATR`. Free search (1 only): `k` `[1.0, 1.5]`. Fill at `t+1` open.
- Why this is novel: Prior-completed-UTC-day session VWAP stretch reject as one 4h BOTH family. Magnet is yesterday's finished session VWAP, not developing UTC VWAP, not swing AVWAP, not rolling VWAP ± σ, not POC/HVN, not raw prior-day H/L.

## What to write

1. `core/strategy/prior_day_vwap_reject.py` — `Strategy` subclass, `name = "prior_day_vwap_reject"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, LONG, SHORT, kit locks (search only `k` `[1.0, 1.5]`), no lookahead (truncation + future shock), sibling-distinction, prior-day-only VWAP (forming day excluded).
4. Distinct from: `utc_session_vwap_reversion` / `swing_anchored_vwap_pullback` / `vwap_spread_exhaustion` / `vwap_volatility_band_fade` (90/94/98/99), inventory fades, `prior_poc_reclaim_fade` (Job 145 — do not recode), `hvn_mean_revert` (Job 146 — do not recode), `rolling_va_extreme_reject`, `sma20_stretch_fade`, `keltner_channel_fade` (Job 144 0/12 — do not revive), `prior_day_extreme_reject` (H/L).
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not empty or revert the `PAPER_SCAN_SLEEVES` blotter fix.
