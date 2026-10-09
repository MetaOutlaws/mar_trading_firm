# Secondary timing diagnostic: specification before scoring

6 October 2026. Continue the already registered one-hour and 24-hour diagnostic
horizons. The completed primary four-hour gate remains failed (0/18 groups).
Secondary outcomes are descriptive and cannot rescue that gate.

Reuse the reconstructed original zone candidates and matching features from
run_prediction.py. For each horizon independently, discard potential signal
and control times whose full minute window crosses the period boundary, then
match with the same seed, strata, minimum five controls and maximum twenty
draws. Different horizons may therefore have slightly different cohorts.

Measure signed open-to-final-close return, maximum favourable excursion and
maximum adverse excursion from the minute entry quote over the full observation
window. Long MFE=max(0,max(high)/entry-1), MAE=max(0,1-min(low)/entry); shorts
mirror these formulas. Include every minute in the horizon. These are bar-based
path bounds, not attainable fills or a live exit policy. No trading time limit
is introduced; no fees/funding are applied to these prediction diagnostics.

For each token, clock, direction and historical period export signal/control
means, paired differences, coverage and exclusions. Report ordinary 95% paired
calendar-bootstrap intervals with one- and four-week blocks for all three
metrics. These are explicitly unadjusted secondary intervals across many
comparisons. Do not select an entry or exit from their endpoints. Preserve all
draws, repeated controls and paired observations; no 2026 scoring.

The separate costed control-entry exit diagnostic remains pending; it is not
represented by these quoted movement observations.
