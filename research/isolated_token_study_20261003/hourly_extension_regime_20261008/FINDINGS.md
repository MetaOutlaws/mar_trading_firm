# Extension cap conditional on pre-breakout market state

BTC + Connors remains the owner-approved PAPER deployment. This next isolated experiment found a promising additional candidate: apply the fixed one-ATR extension cap only in a low-efficiency state. Average net return improves in both periods at both cost levels. The originally hypothesized directional-state-only cap reduces historical mean. No new filter has been approved or deployed automatically.

## Frozen definitions and scope

ER24 is the absolute price displacement divided by the total absolute hourly movement across24 hours, ending BEFORE the signal hour. ER>=0.30 is directional; below0.30 is low-efficiency. These are price-path measures, not blanket labels for entire years. The extension cap requires breakout close distance from the prior20-hour boundary <=1 priorATR. Equality passes. Entries, SL2%/TP2.5%, funding and execution assumptions otherwise stay fixed.

Protocol-before-scoring commit `94ee97be88aacf0dca4dc9f927274c718027dced`. Both conditional policies were declared before scoring; there was no threshold search. Main comparator is the approved BTC+Connors rule. Original baseline policies are diagnostic controls. No2026 price outcome scored. Cached validated minute paths are reused and admissions replayed, not old ledgers simply filtered.

## Main comparison

| Period | Extension policy on BTC + Connors | Trades | Stops | Targets | Win rate | Base mean net | Stressed mean net |
|---|---|---:|---:|---:|---:|---:|---:|
| 2022–24 | No cap: approved benchmark | 56 | 22 | 34 | 60.71% | +0.5051% | +0.3849% |
| 2022–24 | Cap always | 38 | 14 | 24 | 63.16% | +0.6133% | +0.4914% |
| 2022–24 | Cap only in directional state | 53 | 21 | 32 | 60.38% | +0.4914% | +0.3720% |
| 2022–24 | Cap only in low-efficiency state | 41 | 15 | 26 | 63.41% | +0.6229% | +0.5003% |
| 2025 | No cap: approved benchmark | 19 | 5 | 14 | 73.68% | +1.0580% | +0.9205% |
| 2025 | Cap always | 15 | 3 | 12 | 80.00% | +1.3400% | +1.1993% |
| 2025 | Cap only in directional state | 19 | 5 | 14 | 73.68% | +1.0580% | +0.9205% |
| 2025 | Cap only in low-efficiency state | 15 | 3 | 12 | 80.00% | +1.3400% | +1.1993% |

Stress doubles slippage only; fees and funding remain included. Mean return is per trade notional. Eight arms and two cost scenarios overlap and are not independent trades.

## What changed

- Low-efficiency-only cap,2022–24: removes7 stopped trades and8 target winners.56 trades become41, stops22 to15, targets34 to26. No new or occupancy-displaced trades. Mean improves +0.3849% to +0.5003% stressed.
- Low-efficiency-only cap,2025: removes2 stops and2 target winners.19 trades become15, stops5 to3, targets14 to12. Win rate73.68% to80.00%; stressed mean +0.9205% to +1.1993%. No new or occupancy-displaced trades.
- The historical removed bundle was still net-positive overall: stressed additive return sum falls0.215525 to0.205117. Average quality improves while total historical opportunity falls. In2025 the additive sum rises0.174895 to0.179897. These sums are NOT account or compounded portfolio returns.
- Always-on cap also improves both pooled means on BTC+Connors. Low-efficiency-only retains three directional-state historical trades (one stop,two targets) that the always-on cap removes. It has slightly higher historical mean (+0.5003% versus +0.4914%) and the identical15-trade2025 set.
- Directional-state-only cap removes one historical stop and two winners, lowering mean to+0.3720%. It changes no2025 trades. This contradicts the directional-only benefit hypothesis; the preregistered low-efficiency alternative supplies the positive finding.

## Uncertainty and concentration

Paired10,000-draw bootstrap, including empty weeks; differences below are percentage points of stressed mean net return versus approved BTC+Connors. Both intervals cross zero, so the incremental improvement is not statistically established.2025 has already been repeatedly inspected.

| Period | Difference | 1-week 95% interval | 4-week 95% interval |
|---|---:|---:|---:|
| 2025 | +0.2788 pp | [-0.1956, +0.9435] | [-0.2045, +0.8772] |
| 2022–24 | +0.1154 pp | [-0.2165, +0.4743] | [-0.2587, +0.4750] |

All three token means and all leave-one-token-out means are positive under the candidate in both periods. Historical ETH improves from negative to +0.0759%, but historical SOL mean falls from+1.1594% to+0.9738%.2025 ETH is only two target winners. Annual means remain positive, but2023 is slightly below the approved benchmark. Positive pooled means do not mean every subgroup improves.

| Token | 2022–24 trades / stops / stressed mean | 2025 trades / stops / stressed mean |
|---|---|---|
| BTCUSDT | 15 / 5 / +0.6972% | 7 / 2 / +0.8953% |
| ETHUSDT | 17 / 8 / +0.0759% | 2 / 0 / +2.1637% |
| SOLUSDT | 9 / 2 / +0.9738% | 6 / 1 / +1.2325% |

## Does this support the calendar-year explanation?

Under this fixed measure, low-efficiency hours account for 73.31% of valid2022–24 token-hours and 73.98% of2025 token-hours. That modest difference does not support calling the whole historical period trending and the whole2025 period choppy. Token-hours are descriptive exposure, not independent observations.
Among approved-combination admissions,48/56 historical and18/19 evaluation trades occur in low-efficiency states. The2025 directional cell contains just one trade. The cap does not remove it. Consequently the2025 evidence cannot establish that the conditional policy is superior to always-on activation. Compression entries preferentially occur after quieter paths; this state is measured before the breakout, not a market-wide forecast.

## Original-baseline diagnostic

On the original baseline, the directional-only cap changes historical97 trades/44 stops/+0.1037% stressed to89/40/+0.1229%, while2025 remains36/14/+0.3685%. Low-efficiency-only changes historical to68/30/+0.1490%, but2025 falls to22/10/+0.0635%. Thus the cap behaves differently after BTC+Connors screening; standalone-filter results cannot be assumed additive. All original-control results are saved separately from the main comparison.

## Decision and next step

LOW-EFFICIENCY-ONLY passes the predeclared point-estimate screen: positive means both periods, no mean deterioration in either period at either cost, and improvement in at least one period. Here it improves both. DIRECTIONAL-ONLY fails. Equality in one period is allowed in this protocol; this corrects the earlier overly rigid deployment-selection treatment without rewriting old experimental results.

This is a promising candidate for further paper consideration, not proven statistical non-inferiority, certainty or automatic activation. Brian’s current approved deployment is BTC+Connors without an extension cap. Grok handover and runtime source explicitly implement that approval. Next isolated test: RSI14 exhaustion filter with this exact pre-breakout ER24 state definition on the approved BTC+Connors benchmark; do not silently stack it with this cap. Wider-token/prospective confirmation remains pending.

## Verification and recovery

2 focused state tests;143 independent minute-endpoint/path-efficiency checks;286 cached raw cost rows; exact original/always-cap/BTC+Connors prior ledger reproduction;32 independent admissions;24 attribution checks. Report values reconciled to the individual ledger. New runtime support:37 targeted tests pass,143 full and143 rolling-window entry checks match. One unrelated API count test could not import FastAPI locally and is recorded as unverified. No cloud activation claim.
