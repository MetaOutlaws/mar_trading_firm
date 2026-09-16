# Proposal: `lvn_fill_reject`

Prior-day LVN fill-reject — tag the low-volume node from the prior *completed* UTC day's volume profile, then the same-bar close rejects back on the fade side of LVN. SHORT: `high[t] >= LVN - touch_tol_atr*ATR` AND `close[t] < LVN`. LONG: `low[t] <= LVN + touch_tol_atr*ATR` AND `close[t] > LVN`. ATR is known before the signal bar (`atr.shift(1)`). Clock: `4h/4h`. Side: BOTH. Family id: `lvn_fill_reject` only. This is a FADE / fill-then-reject-from-LVN edge — not single-POC, not nearest-of-top-N HVN, not VWAP, not rolling VA.

## Coding brief (Garwe AUTHORITATIVE stamp for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Garwe AUTHORITATIVE stamp for coding (do not start walk-forward). Live stays off.
- Quant lock: Level = prior COMPLETED UTC-day LVN only (00:00–24:00 UTC previous day). Never use a forming/incomplete day. Histogram binning LOCKED to the same definition as `prior_poc_reclaim_fade` / `hvn_mean_revert`: 20 equal-width price bins across that day's `[low, high]`; each bar's volume (else turnover) is spread uniformly across overlapping bins; LVN = lowest-positive-volume bin midpoint; zero-weight bins skipped; ties take the lowest-price min. ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). SHORT = `high[t] >= LVN - touch_tol_atr*ATR` AND `close[t] < LVN`; LONG = `low[t] <= LVN + touch_tol_atr*ATR` AND `close[t] > LVN`. Free search (1 only): `touch_tol_atr` `[0.0, 0.05, 0.10, 0.15]` (endpoints 0.0 and 0.15 plus 0.05-step interiors). Fill at `t+1` open. Family id `lvn_fill_reject` only. Do not rename free params. Do not implement `inside_bar_break_fail`.
- Why this is novel: Prior-day LVN fill-then-reject as one 4h BOTH family. The level is yesterday's completed UTC-day volume-profile low-volume node, not raw H/L, not floor P/R1/S1, not VWAP, not the single-POC reclaim (Job 145), not nearest-of-top-N HVN (Job 146), and not a rolling value-area extreme.

## What to write

1. `core/strategy/lvn_fill_reject.py` — `Strategy` subclass, `name = "lvn_fill_reject"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, LONG, SHORT, kit locks (search only `touch_tol_atr` `[0.0, 0.05, 0.10, 0.15]`), no lookahead (truncation + future shock), sibling-distinction, prior-day-only LVN (forming day excluded). Document binning choice (same 20 equal-width bins as prior_poc).
4. Distinct from: `prior_poc_reclaim_fade` (Job 145 — do not recode), `hvn_mean_revert` (Job 146 — do not recode), `prior_day_vwap_reject` / `session_vwap_band_fade`, `rolling_va_extreme_reject`, `session_volume_profile_reversal` (skip-list), asia / inventory fades, `sma20_stretch_fade`, `keltner_channel_fade`, `prior_day_extreme_reject` (H/L). Do not implement F `inside_bar_break_fail`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not empty or revert the `PAPER_SCAN_SLEEVES` blotter fix.
