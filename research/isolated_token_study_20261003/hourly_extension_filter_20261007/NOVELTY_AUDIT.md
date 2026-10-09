# Duplicate audit: hourly breakout extension cap

7 October 2026, before scoring. Scope: entry filter on the owner-approved hourly
compression rule, not a claim of a new strategy family.

## Evidence inspected
- Current research branch head c7b8786db84f8e004a6dbc163bd7876d0dd92b21, recovered
  from fresh GitHub branch inventory. PR metadata reads timed out; no success
  was inferred from those errors.
- Hourly runtime source at d56eac5cf82c403089d5a2bab20f13bc931de654:
  core/strategy/hourly_compression_v1.py, blob
  ab289144f561d1978e265fc844a624fd3006dd90. Its conditions are6/60 compression,
  >=1.5 prior ATR expansion, >=1.5 relative volume, body/close-location,
  prior20-hour breakout and24-hour token direction. No cap on distance from
  the broken20-hour boundary.
- Frozen entry discovery, broader replication, three-token replay, family
  follow-ups, stop-width, price-break-even, failed-breakout-exit and sweep-
  confirmation protocols and code. No same hourly admission cap found.
  The failed-breakout EXIT uses the same20-hour boundary after entry; it is
  a different intervention, already completed and rejected.
- Recorded Grokbot execution addendum at
  d79735916aab139ced1d827d601404484cb30003, retained from the previous verified
  audit. A fresh refetch timed out, so the pinned saved text was used.
  Grokbot compression has range_compression<=0.40, relative volume>=2.0,
  trend agreement and a break of96 prior15m bars; no maximum extension.
  Its fade uses a1% overshoot and is a reversal, not this compression filter.
  Its18-config CLOSED_NULL remains closed.
- Existing range_compression_volume_thrust uses ATR percentile compression
  and a minimum thrust. It is a different4h strategy with no matching upper
  boundary-distance cap. Stretch fades and Fibonacci extensions are different
  entry families, not evidence this exact comparison already ran.
- GitHub commit search 'compression extension' returned no hits. PR search
  returned related development/research PRs; inspected rules, not search
  absence alone, support the scoped decision. Local Git/source searches did
  not identify a matching cap. External Grokbot runtime ledgers remain outside
  accessible evidence.

## Decision
No equivalent one-prior-ATR admission cap on these exact hourly signals was
found in the inspected record. Proceed as one separately registered filter
comparison; do not claim universal novelty or overwrite prior budgets.

References:
https://github.com/MetaOutlaws/mar_trading_firm/pull/100
https://github.com/MetaOutlaws/mar_trading_firm/pull/99
https://github.com/MetaOutlaws/mar_trading_firm/blob/d56eac5cf82c403089d5a2bab20f13bc931de654/core/strategy/hourly_compression_v1.py
https://github.com/MetaOutlaws/mar_trading_firm/blob/d79735916aab139ced1d827d601404484cb30003/research/isolated_token_study_20261003/entry_trailing_20261004/EXECUTION_ADDENDUM.md
