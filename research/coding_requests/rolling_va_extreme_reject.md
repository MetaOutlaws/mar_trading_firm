# Proposal: `rolling_va_extreme_reject`

Rolling volume-profile value-area extreme reject — tag VAH or VAL of the rolling walk-clock value area, then the same-bar close rejects back inside the VA. SHORT: `high[t] >= VAH - touch_tol_atr*ATR` AND `VAL < close[t] < VAH`. LONG: `low[t] <= VAL + touch_tol_atr*ATR` AND `VAL < close[t] < VAH`. ATR is known before the signal bar (`atr.shift(1)`). Clock: `4h/4h`. Side: BOTH. Family id: `rolling_va_extreme_reject` only. This is a FADE / chop mean-reversion edge — not a breakout, not prior-day POC/HVN, not VWAP.

## Coding brief (Garwe AUTHORITATIVE stamp for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Garwe AUTHORITATIVE stamp + CEO YES for coding (do not start walk-forward). Live stays off.
- Quant lock: Profile = rolling volume-profile value area on the walk clock from the prior `lookback` bars (signal bar excluded). Never a prior-completed-UTC-day profile. Histogram binning LOCKED to the same definition as `prior_poc_reclaim_fade` / `hvn_mean_revert`: 20 equal-width price bins across that window's `[low, high]`; each bar's volume (else turnover) is spread uniformly across overlapping bins; VA grows one bin at a time from POC until `va_frac` of volume; VAH/VAL = outer bin edges; ties take the lowest-price neighbor. ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). `require_close_inside_va` = True LOCKED. SHORT = `high[t] >= VAH - touch_tol_atr*ATR` AND `VAL < close[t] < VAH`; LONG = `low[t] <= VAL + touch_tol_atr*ATR` AND `VAL < close[t] < VAH`. Free search (3 only): `lookback` `[20, 48]`, `touch_tol_atr` `[0.0, 0.10]`, `va_frac` `[0.68, 0.70]`. Fill at `t+1` open. Family id `rolling_va_extreme_reject` only. Do not widen the grid. Do not rename free params.
- Why this is novel: Rolling walk-clock value-area extreme fade as one 4h BOTH family. Extremes are VAH/VAL of a rolling volume profile, not raw H/L, not floor P/R1/S1, not VWAP, not the single-POC reclaim (Job 145), and not nearest-of-top-N HVN (Job 146).

## What to write

1. `core/strategy/rolling_va_extreme_reject.py` — `Strategy` subclass, `name = "rolling_va_extreme_reject"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, LONG, SHORT, kit locks (search only `lookback` `[20, 48]`, `touch_tol_atr` `[0.0, 0.10]`, `va_frac` `[0.68, 0.70]`), no lookahead (truncation + future shock), sibling-distinction, rolling window excludes the signal bar, `require_close_inside_va` locked True. Document binning choice (same 20 equal-width bins as prior_poc).
4. Distinct from: `prior_poc_reclaim_fade` (Job 145 — do not recode), `hvn_mean_revert` (Job 146 — do not recode), `prior_day_vwap_reject` / `session_vwap_band_fade`, `session_volume_profile_reversal` (skip-list), asia / inventory fades, `sma20_stretch_fade`, `keltner_channel_fade`, `prior_day_extreme_reject` (H/L).
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not empty or revert the `PAPER_SCAN_SLEEVES` blotter fix.
