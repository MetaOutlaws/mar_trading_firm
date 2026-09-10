# Proposal: `hvn_mean_revert`

Prior-day HVN mean-revert — tag the nearest of the top `lookback_nodes` volume nodes from the prior *completed* UTC day's volume profile, then the same-bar close reclaims through that HVN. SHORT: `high[t] >= HVN - touch_tol_atr*ATR` AND `close[t] < HVN`. LONG: `low[t] <= HVN + touch_tol_atr*ATR` AND `close[t] > HVN`. ATR is known before the signal bar (`atr.shift(1)`). Clock: `4h/4h`. Side: BOTH. Family id: `hvn_mean_revert` only (not `hvn_node_fade`). This is a FADE / reclaim-through-nearest-HVN edge — not single-POC, not prior-day H/L, not VWAP, not rolling VA.

## Coding brief (Brian Inbox-approved + Quant FINAL-locked for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved + Quant FINAL-locked for coding (do not start walk-forward). Live stays off.
- Quant lock: Profile = prior COMPLETED UTC-day volume profile only (00:00–24:00 UTC previous day). Never use a forming/incomplete day. Histogram binning LOCKED to the same definition as `prior_poc_reclaim_fade`: 20 equal-width price bins across that day's `[low, high]`; each bar's volume (else turnover) is spread uniformly across overlapping bins; node = bin midpoint; ties take the lowest-price max. HVN set = top `lookback_nodes` volume nodes; signal uses the nearest HVN to the bar extreme among that set (SHORT → high[t], LONG → low[t]). ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). SHORT = `high[t] >= HVN - touch_tol_atr*ATR` AND `close[t] < HVN`; LONG = `low[t] <= HVN + touch_tol_atr*ATR` AND `close[t] > HVN`. Free search (2 only): `lookback_nodes` `[1, 3]`, `touch_tol_atr` `[0.0, 0.15]`. Fill at `t+1` open. Family id `hvn_mean_revert` only. WITHDRAWN — do not code: `leave_atr`, bar-lookback `[20, 48]`, `hvn_node_fade` alternate family.
- Why this is novel: Prior-day HVN nearest-of-top-N mean-revert as one 4h BOTH family. Nodes are yesterday's completed UTC-day volume-profile HVNs, not raw H/L, not floor P/R1/S1, not VWAP, not a rolling value-area, and not the single-POC reclaim (Job 145).

## What to write

1. `core/strategy/hvn_mean_revert.py` — `Strategy` subclass, `name = "hvn_mean_revert"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, LONG, SHORT, kit locks (search only `lookback_nodes` `[1, 3]` and `touch_tol_atr` `[0.0, 0.15]`), no lookahead (truncation + future shock), sibling-distinction, prior-day-only profile (forming day excluded), nearest-of-top-N behavior. Document binning choice (same 20 equal-width bins as prior_poc).
4. Distinct from: `prior_poc_reclaim_fade` (Job 145 — do not recode), `prior_day_vwap_reject` / `session_vwap_band_fade`, `session_volume_profile_reversal` (skip-list), asia / inventory fades, `sma20_stretch_fade`, `keltner_channel_fade`, `prior_day_extreme_reject` (H/L), `rolling_va_extreme_reject`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not empty or revert the `PAPER_SCAN_SLEEVES` blotter fix.
