# Hourly compression: Connors RSI exhaustion exclusion

Pre-scoring protocol, 8 October 2026 Dubai (7 October UTC). Brian authorized the
next test. His RSI regime-use hypothesis is saved separately as H-RSI-REGIME-01.
This experiment does not test a regime switch and changes no runtime settings.

## Hypothesis and single fixed predicate

Connors RSI includes recent price momentum, consecutive up/down streaks and the
relative size of the latest return. An extreme in the breakout direction may
identify exhaustion more specifically than RSI14. Counter-hypothesis: extremes
identify continuation winners and excluding them lowers expectancy.

Use own-token completed-hour ConnorsRSI(3,2,100). Retain LONG only when CRSI<=90;
retain SHORT only when CRSI>=10. Equality passes. No opposite bound, slope,
crossing, setup-memory, 50-line direction condition or threshold/lookback grid.
Apply identically to BTC/ETH/SOL, both directions. Arms: baseline and
crsi_not_exhausted. Neither arm includes BTC24 confirmation, RSI14 exclusion,
ADX, extension cap or an exit change. Original hourly compression is the control.

This is a standalone entry filter, not the existing connors_rsi_fade family.
The 10/90 levels and 3/2/100 definition are fixed before examining this test's
feature distribution, counts or outcomes. Source motivation only:
- TradingMarkets original indicator specification, including strict-less-than
  rank against prior returns: https://www.tradingmarkets.com/media/2012/CRHS.pdf
- Discussion of 10/90 extremes: https://tradingmarkets.com/analytics/how-does-connorsrsi-compare-to-rsi2-1583255
- Their original focus was daily prices; our hourly crypto application needs
  testing: https://tradingmarkets.com/connorsrsi/the-most-popular-technical-indicators-1583330
These sources establish definition/context, not profitability on these entries.

## Exact definition and clock

Aggregate contiguous UTC minute candles into completed hourly closes. At entry T
use bar [T-1h,T), last input minute T-1min. No price at/after T affects context.
No forward/stale filling or silent missing-context exclusions.

1. Price RSI3: hourly close differences, positive gains/negative losses. Seed
   averages with the first3 differences, at hour index3; thereafter
   avg=(2*previousAvg+newChange)/3.
2. Signed streak: first observed hour0; same-direction rise/fall extends +1/-1,
   reversal starts +1/-1, unchanged close resets0. Apply RSI2 to the CHANGES in
   this signed streak. Seed first2 changes at hour index2, then average with
   Wilder recurrence (previousAvg+newChange)/2.
3. Return r[j]=close[j]/close[j-1]-1. Rank100 is the percentage of the PREVIOUS100
   returns strictly LESS than r[j], excluding current. Ties contribute zero.
   First valid rank at hour index101 (102 observed closes). Warmup remains NaN.

For both RSI components use100*avgGain/(avgGain+avgLoss); both zero gives50,
only loss zero gives100, only gain zero gives0. CRSI is the equal-weight mean
of these three components; unavailable until all are valid. A completely flat
history gives (50+50+0)/3=33.3333, not50. This rank/tie/seed definition matches
the prior trade_anatomy_20261006 research convention; production fade code is
not modified or assumed numerically identical without verification.

Require finite CRSI in[0,100] at every selected signal; fail on invalid/missing
minutes or timestamp misalignment. Save each component, streak, last return and
input timestamp. Original RSI14 feature remains available but does not gate.

## Unchanged sample, execution and primary screen

ALL143 original membership-eligible hourly compression raw opportunities,
BTC/ETH/SOL, both directions. Historical2022–24 and flat-reset reused2025;
no2026 price feature, entry or outcome, no additional-token results. These
periods have already been inspected; this is exploratory, not independent OOS.

Same2% SL/2.5% TP, no timeout, entry times/prices and raw barriers. Quote barriers,
stop-first ties, adverse stop gaps, target quote; fees0.055% per side; base
slip0.05% BTC/ETH and0.10% SOL per side; stress doubles slip; actual funding and
original conservative funding-boundary rule. R=net return/0.02.

Same monthly membership/rank, one position/token across sides, six basket slots,
three per direction, no reentry in an exit minute. Independently replay ALL
eligible raw opportunities in each arm so exclusions can change later admissions.
Do not merely filter the old admitted ledger.

Primary exploratory screen: nonempty arms, positive stressed full-basket mean
AND positive stressed difference versus ORIGINAL baseline in BOTH periods.
An empty arm is insufficient. A point pass is not proof, independent research
qualification, automatic owner approval or deployment. No post-result retuning.

## Reports and verification

Report counts/stops/stop rates, targets, win rate, net mean/PF, mean/sum R,
holding times, tokens/sides, annual and leave-one-token-out diagnostics.
Same one-week/four-week shared-calendar intervals,10,000 draws and fixed seeds,
empty weeks included; report valid draws and absolute/difference intervals.
Additive return sums are not account returns.

Separate direct exclusions (stops versus target winners), shared admissions,
newly admitted trades and eligible baseline trades lost through changed occupancy.
Report raw-opportunity and actual-admission scopes; reconcile total additive
delta and require identical shared costs/paths. Preserve ordinary full/excluded
trade CSVs and per-entry CRSI components, alongside hashes and all attempts.

Publish protocol and novelty audit before scoring; freeze source,6 raw inputs,
9 features and4 baseline references. Synthetic checks cover seed/recurrence,
flat warmup, streak reset/reversal, rank window/ties/current exclusion, threshold
equality/direction, invalid context, exact timestamp, future perturbation/prefix
invariance, independent calculation and occupancy changes. Independently
reconstruct hourly closes from minute arrays and use a scalar implementation
for all143 components/contexts; also compare to the saved anatomy formula.
Independently check143 barriers and8 admission runs, reproduce286 raw/266 admitted
baseline cost rows, reconcile reports and verify a fresh restored checkpoint.

## Next decision

Close this single fixed indicator comparison after reporting it, without stacking
or a cutoff rescue. Next research stage: jointly PLAN a common causal-state
analysis for H-EXT-REGIME-01 and H-RSI-REGIME-01, retaining each filter separately.
Exact state definitions remain unfrozen/unscored; no calendar label becomes a
trade rule. Broader-token/prospective evidence remains pending. BTC confirmation
remains owner-approved paper preference with activation PENDING / NOT VERIFIED.
