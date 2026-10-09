# Previous-day sweep confirmation: rejected

Completed 7 October 2026. BTC/ETH/SOL, both directions, 15m, fixed SL2%/TP2.5%,
no timeout. The frozen comparison fails: both entry arms lose after costs in
2022–24 and reused 2025. Confirmation improves the older aggregate but worsens
2025 mean return and win rate. Close this bounded experiment; do not deploy it
or search indicator/stop/target thresholds to rescue it.

## Novelty correction
The family already existed as prior_day_extreme_reject (family 118, PR16).
The distinct comparison was immediate-next-15m-candle confirmation. See
NOVELTY_AUDIT.md for GitHub/Grokbot predecessors, pinned sources and access limits.
No exact duplicate was found in inspected records; this does not certify an
unrecorded external Grokbot ledger. The old 4h family's detailed results were
unavailable; later briefs call it spent. This study is not a job118 rerun.

Protocol and audit were published BEFORE scoring at
7403b72ef1a8c99e920ddcd39dfa3c0597547781. Historical settings/results, the Grokbot
18-config CLOSED_NULL, and the approved hourly pilot remain separate.

## Chronological results
| Period | Entry | Entries | Closed | Stop exits / closed | Targets | Marks | Closed win rate | Mean net base | Mean net stress | Base PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022–24 | immediate | 1825 | 1824 | 1004 (55.0%) | 820 | 1 | 45.0% | -0.2249% | -0.3657% | 0.818 |
| 2022–24 | confirmed | 559 | 558 | 293 (52.5%) | 265 | 1 | 47.5% | -0.1088% | -0.2475% | 0.908 |
| 2025 | immediate | 687 | 684 | 380 (55.6%) | 304 | 3 | 44.4% | -0.2464% | -0.3874% | 0.802 |
| 2025 | confirmed | 230 | 227 | 132 (58.1%) | 95 | 3 | 41.9% | -0.3505% | -0.4858% | 0.728 |

Returns are decimal-fraction outputs converted to percentages here. Mean net
includes the separately labelled terminal marks: one in each 2022–24 arm and
three in each 2025 arm. Stop rate and closed win rate exclude those marks.
All actual closed target hits here are net winners and all stop exits are net
losses. Counts are the same at both cost levels. Quote-based SL/TP is 2%/2.5%;
realized returns include adverse fills, fees and funding and are not ±2%/2.5%.

The confirmed arm clears only the minimum 50-closed-trades condition. It fails
positive base/stress means, base PF>=1.15 in both periods, and consistent stressed
mean improvement. All three tokens have negative stressed means in both periods
for both arms. Confirmation's 2022 mean is positive (+0.4532% base/+0.3165% stress);
2023, 2024 and 2025 are negative. A single positive year is not a survivor.

## What confirmation changed
| Period | Raw setups | Confirm | Skipped stops | Skipped targets | Selected at immediate price | Actual confirmed price | Selection effect (pp) | Delay effect (pp) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| evaluation | 904 | 261 | 379 | 263 | -0.0245% | -0.5113% | +0.3634% | -0.4868% |
| historical | 2383 | 603 | 1039 | 741 | +0.0839% | -0.2137% | +0.4371% | -0.2976% |

These are overlapping RAW opportunities, not the chronological portfolio. In
2025 there are 904 eligible immediate setups; only 261 confirm. Confirmation skips
379 would-be stops but also 263 target winners (plus one terminal mark).
Among the 261 confirmed parents, delaying entry converts 28 immediate target hits
into stops; zero immediate stop hits become targets. The older period has 40
target-to-stop conversions and zero stop-to-target conversions.

The apparent selection benefit is retrospective: deciding at the original entry
which setups WILL confirm uses a future candle. It is an attribution diagnostic,
not a tradable early-entry rule. At base costs the selected 2025 parents would
average +0.1065% at the earlier price, but the executable confirmed entry averages
-0.3803%. Its later entry/bracket placement loses about 0.4867 percentage points
per raw confirmed trade. Selection alone cannot be claimed as an edge.

Chronological occupancy is also replayed. In 2025 the arms share 195 admitted
parents, with 492 control-only and 35 confirmation-only admissions. In 2022–24
there are 473 shared, 1352 control-only and 86 confirmation-only admissions.
See admission_decomposition.csv and the full parent-change ledger. Confirmation
loses less in TOTAL because it takes many fewer losing trades; that does not
make its negative per-trade expectancy profitable.

## Uncertainty and diagnostics
| Period | Entry | Stress mean | 95% four-week block interval |
| --- | --- | --- | --- |
| evaluation | confirmed | -0.4858% | [-0.7823%, -0.1820%] |
| historical | confirmed | -0.2475% | [-0.4585%, -0.0278%] |
| evaluation | immediate | -0.3874% | [-0.4992%, -0.2707%] |
| historical | immediate | -0.3657% | [-0.4731%, -0.2686%] |

Intervals use 10,000 shared-calendar week resamples, retaining empty weeks;
both 1-week and 4-week versions are in the tables. They are descriptive after
repeated exploration. The stressed confirmation-minus-immediate difference in
2025 is -0.0984 percentage points; its 4-week interval spans -0.4026 to +0.2011 pp,
so the relative deterioration is not precisely estimated. Neither arm meets the
absolute profit criterion. Reused 2025 is not independent confirmation.

Entry-time RSI14, volume ratio, ADX14, hourly 24h/168h returns and path excursions
are preserved. entry_feature_diagnostics.csv separates token, side and exit reason.
No RSI/ADX/volume threshold was selected. Excursions exclude the exit minute
because its ordering is uncertain; they are descriptive path data, never entry
features. The immediate trade ledger leaves confirmation_close blank so a later
confirmation value is not mistaken for something known at immediate entry.
The separate setup/parent files intentionally contain later outcomes.

## Execution and verification
First strict reclaim per UTC setup day/side. Parent day is candle OPEN day;
fixed preceding full UTC day levels. Immediate arm fills after reclaim; confirmed
arm requires the immediately next completed candle close beyond the setup high
(long) or low(short), then fills the next minute open. Equality/late confirmation
fails. Shared membership, costs, barriers, gap/tie rules and occupancy are frozen.

13 synthetic tests passed. Independently reconstructed 3503 first
setups from minute candles and verified 4151 raw exit paths, eight independent
admission replays, six raw input hashes and nine frozen feature hashes.
124 reported rows reconciled; the uncompressed ledger contains 6,602 cost-scenario
rows: 2,512 immediate admissions and 789 confirmed admissions, each at two costs.
The arms overlap and these are not 6,602 independent trades.

Attempt1 failed before signals/outcomes because a report local shadowed the
execution module. Original code/freeze/log are preserved. Attempt2 corrected only
the variable name and refroze unchanged rules before scoring; results_v2 is the
completed run. ATTEMPT_LOG.md explains the distinction.

## Decision and next evidence
Archive this rule as a failed confirmation variant. Keep the approved hourly
compression paper pilot at its existing parameters. Do not infer that its
positive historical result validates this reversal family, or vice versa.
Prioritize independent-token acquisition/audit under the frozen replication
protocol and prospective paper evidence. A different future entry hypothesis
must first pass the duplicate audit and receive a separate frozen protocol.
No automatic indicator rescue, extra parameter search or reserved 2026 evaluation.
No runtime strategy, approval, exit or leverage change was made.

Public evidence: existing draft PR99; aggregate tables and this protocol/report.
Private checkpoint: full code, failed attempt, setup funnel, raw paths,
chronological ledgers, audit evidence and fresh-restore verification.
