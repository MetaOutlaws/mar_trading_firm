# Hourly compression: RSI exhaustion exclusion

Pre-scoring protocol, 8 October 2026 Dubai (7 October UTC). One comparison
authorized by Brian's request to proceed to the next test. Research control
remains ORIGINAL hourly compression. BTC confirmation remains the owner-approved
preferred paper variant, with cloud activation pending/unverified.

## Hypothesis and fixed rule

An original compression breakout that is already at an extreme in its direction
may have less room to continue. Test one exhaustion exclusion: retain LONG only
when its own-token completed-hour Wilder RSI14 <=70; retain SHORT only when
RSI14 >=30. Equality passes. No lower RSI floor for longs or upper ceiling for
shorts, no 50-line alignment, crossing, slope, divergence or setup-memory rule.
Arm names: baseline and rsi14_not_exhausted. Apply to BTC/ETH/SOL, both sides.
No ADX, BTC confirmation, extension cap or Connors RSI is stacked into this test.

The conventional 70/30 levels are fixed before examining treatment counts or
outcomes, not fitted to observed winners. Fidelity describes these conventional
levels and notes that extreme RSI can persist in strong trends:
https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI
This motivates a falsifiable question, not a known crypto edge. The competing
explanation is that this exclusion removes strong continuation winners.

## Exact RSI and causality

Aggregate contiguous UTC minute candles to completed hourly closes. At entry T,
use the close of [T-1h,T), whose final input is minute T-1min. No price at or
after T may enter the feature; no forward/stale fill. Recompute from raw minutes.
For hourly close C[j], j>0, gain=max(C[j]-C[j-1],0) and
loss=max(C[j-1]-C[j],0). The first hour has no change observation. Seed average
gain/loss with the first 14 changes, at zero-based hour index14. Thereafter
average[j]=(13*average[j-1]+change[j])/14. RSI=100*avgGain/(avgGain+avgLoss).
Both averages zero gives50; positive gain and zero loss gives100; reverse gives0.
Warmup remains missing and missing context at a selected entry fails validation.

Preserve entry_rsi14 from original signal features as historical context;
use independently recomputed filter_rsi14 for this predicate. Discovery imports
the arithmetic-seeded RSI from the prior trade-anatomy audit, so its definition
is the same. Verify equality with those original signal values at every entry;
its source, trigger and saved results remain unchanged.

## Fixed execution and sample

Replay ALL143 original membership-eligible 1h raw opportunities, not a subset
of the admitted ledger. Entries, raw barriers and costs remain identical for
retained opportunities: 2% SL, 2.5% TP, no timeout, quote barriers, stop-first
ties, adverse stop gaps and target quote. Fees0.055% per side; base slip0.05%
BTC/ETH and0.10% SOL per side; stress doubles slip; actual funding and original
conservative funding-boundary convention. R=net return/0.02.

Same monthly membership/rank, one position/token across sides, basket6 and
direction3 caps; exit minute remains occupied. Replay each arm independently
so skipped trades may free capacity for other raw opportunities. Historical
2022–24 and flat-reset reused2025, both costs. No2026 price feature, entry or
outcome; no additional-token score. 2025 has been repeatedly inspected and is
exploratory, not untouched validation.

## Decision and required reports

Require nonempty arms, positive stressed full-basket mean and positive stressed
mean difference against ORIGINAL baseline in BOTH periods for a point-screen
pass. A pass is not independent edge qualification, approval or deployment.
No cutoff sweep or post-result rescue. An empty sample is insufficient.

Report trades, stops and stop rate, targets, wins, net mean/PF, mean/sum R,
holding time, tokens/sides, entry years and leave-one-token-out diagnostics.
Use the unchanged one-week/four-week shared-calendar block procedures, 10,000
draws with fixed seeds and empty weeks; report absolute/difference intervals
and valid draws. Additive return sums are not funded account returns.

Separate excluded original stops from excluded target winners, shared trades,
newly admitted opportunities and eligible baseline trades displaced by changed
occupancy. Report raw and actual-admission scopes. Reconcile additive delta to
new minus removed returns; shared executions/costs must match exactly.
Save entry feature timestamp and ordinary full and excluded trade CSVs.

## Verification and continuation

Publish this protocol and duplicate audit before scoring. Freeze sources,
six raw inputs, nine features and four baseline references. Synthetic checks:
threshold equality/direction mirroring, invalid contexts, arithmetic seeds and
recurrence, flat/up/down paths, independent RSI, completed-hour alignment,
future perturbation/prefix invariance, missing/duplicate minutes and occupancy.
Independent minute-array close aggregation and scalar RSI recurrence must
match all143 entry contexts. Check all143 raw barriers, eight admissions,
286 raw and266 admitted baseline cost rows, report reconciliations and hashes.
Preserve every attempt and make a fresh-restore-verified checkpoint.

Next planned family is Connors RSI, independently against the original baseline;
its exact predicate is not yet frozen or scored. H-EXT-REGIME-01 remains a later
causal state comparison, preserving the extension cap's2022–24 improvement.
Broader-token/prospective confirmation remains pending. No runtime change or
automatic approval is part of this experiment.

Pre-scoring correction: initial protocol commit28c3da989a518dbf161c108893cbffbd2bb957d4
incorrectly described discovery's RSI seed as different. Source inspection of
entry_discovery/features.py confirmed its import of anatomy.rsi. This wording
and the added equality check were corrected before any freeze or scoring.
