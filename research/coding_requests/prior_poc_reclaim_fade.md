# Proposal: `prior_poc_reclaim_fade`

Prior-day volume-profile POC reclaim fade — tag the prior *completed* UTC day's volume-profile point of control, then the same-bar close reclaims toward value through POC. SHORT: `high[t] >= POC - touch_tol_atr*ATR` AND `close[t] < POC`. LONG: `low[t] <= POC + touch_tol_atr*ATR` AND `close[t] > POC`. ATR is known before the signal bar (`atr.shift(1)`). Clock: `4h/4h`. Side: BOTH. No k-stretch. This is a FADE / reclaim-through-POC edge — not prior-day H/L, not SMA stretch, not Keltner.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward). Live stays off.
- Quant lock: POC = volume-profile point of control from the prior COMPLETED UTC day only (00:00–24:00 UTC previous day). Never use a forming/incomplete day. Histogram binning LOCKED: 20 equal-width price bins across that day's `[low, high]`; each bar's volume (else turnover) is spread uniformly across overlapping bins; POC = highest-volume bin midpoint; ties take the lowest-price max. ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). No k-stretch geometry. SHORT = `high[t] >= POC - touch_tol_atr*ATR` AND `close[t] < POC`; LONG = `low[t] <= POC + touch_tol_atr*ATR` AND `close[t] > POC`. Free search (1 only): `touch_tol_atr` `[0.0, 0.10]`. Fill at `t+1` open.
- Why this is novel: Prior-day volume-profile POC reclaim fade as one 4h BOTH family. POC is yesterday's completed UTC-day volume-profile node, not raw H/L, not floor P/R1/S1, not VWAP, not a rolling value-area. Tag then reclaim through POC with searched touch slack only.

## What to write

1. `core/strategy/prior_poc_reclaim_fade.py` — `Strategy` subclass, `name = "prior_poc_reclaim_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, LONG, SHORT, kit locks (search only `touch_tol_atr` `[0.0, 0.10]`), no lookahead (truncation + future shock), sibling-distinction, prior-day-only POC (forming day excluded). Document binning choice (20 equal-width bins, volume histogram, bin midpoint).
4. Distinct from: `prior_day_extreme_reject` (H/L), `sma20_stretch_fade`, `keltner_channel_fade` (Job 144 0/12 — do not revive), `keltner_break`, `bb_medium_bw_upper_reject`, `outside_bar_fail_reversion`, `asia_range_london_reject`, inventory fades, `hvn_mean_revert`, `prior_day_vwap_reject` / `session_vwap_band_fade`, `rolling_va_extreme_reject`, `displacement_gap_follow`, `week_open_reclaim`, `orb_fail_reversion`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not empty or revert the `PAPER_SCAN_SLEEVES` blotter fix.
