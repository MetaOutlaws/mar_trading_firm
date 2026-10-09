# Hourly compression: failed-breakout exit experiment

7 October 2026. BTC, ETH, SOL; both directions; hourly entries; research only.

**Decision: reject this exit rule under the frozen improvement screen and retain the approved 2% stop / 2.5% target baseline.** Early range-failure exits reduce actual stop-loss hits but sacrifice too many eventual target winners. Both periods have negative stressed average net return under the treatment. No paper exit settings changed.

## Rule and scope

At entry, fix the same boundary used by the entry signal: the high of the 20 completed hours preceding the breakout candle for longs, or their low for shorts. The breakout candle is excluded. Starting with the first full hour after entry, a close at/below that boundary for a long or at/above it for a short triggers an exit at the following minute open. The boundary never moves. Initial 2% SL, 2.5% TP, entries, costs and admission rules remain fixed; no timeout or re-entry rule is added.

Resting stop/target orders take priority when already executed before the close or breached at the scheduled exit open. Otherwise the next-open exit occurs before that minute’s later extrema. The independent validator explicitly checks that order of events and the different funding timing for open versus intrabar exits.

Protocol commit before scoring: `fe51e67511a8ae7b738d7a27c7a0914d3573ba75`. Same 143 membership-eligible raw signals and six original price/funding files; 2022–24 and flat-reset reused 2025. No 2026 outcomes, extra-token scoring or leverage tests.

## Chronological results

Average returns are net percentage of position notional per trade, including both fees, slippage and funding. Stress doubles slippage. Counts below are positions per arm; cost scenarios do not add independent trades.

| Period | Rule | Trades | Actual SL exits | Failure exits | Targets | Net win rate | Mean net, base | Mean net, stress |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2022–24 | Baseline | 97 | 44 | 0 | 53 | 54.6% | +0.2268% | +0.1037% |
| 2022–24 | Failed-breakout exit | 104 | 12 | 59 | 33 | 31.7% | -0.0432% | -0.1654% |
| 2025 | Baseline | 36 | 14 | 0 | 22 | 61.1% | +0.4992% | +0.3685% |
| 2025 | Failed-breakout exit | 38 | 2 | 23 | 13 | 34.2% | +0.1031% | -0.0254% |

There are no terminal marks. All 82 chronological failed-breakout exits are net losses at both cost levels. In 2025, actual stop hits fall from 14 to 2, but total losing trades rise from 14 to 25 after including the 23 early exits. In 2022–24, losing trades rise from 44 to 71. Counting only hard-stop hits would conceal the deterioration.

## Same-entry trade-off

The matched comparison holds the ORIGINAL admitted entry set fixed. It isolates the exit effect before crediting the extra trades enabled by released capacity.

| Period | Original stops improved by early exit | Original target winners cut short | Stressed mean change on matched entries |
|---|---:|---:|---:|
| 2022–24 | 32 of 44 | 23 of 53 | -0.3178 percentage points |
| 2025 | 12 of 14 | 11 of 22 | -0.5164 percentage points |

All intercepted original stops improved, but remained net losses. In 2025 those 12 positions improved from an average −2.3646% to −1.0624%. The 11 sacrificed target winners fell from +2.1197% to −0.9910%. Saving roughly 1.3 percentage points per intercepted stop could not offset losing roughly 3.1 points per sacrificed winner.

## Released capacity and full accounting

| Period | Retained entries | Extra admissions | Extra targets / failure exits | Exit effect on retained trades | Extra-trade contribution | Total strategy change |
|---|---:|---:|---|---:|---:|---:|
| 2022–24 | 97 | 7 | 3 / 4 | -30.8274 | +3.5633 | -27.2641 |
| 2025 | 36 | 2 | 2 / 0 | -18.5908 | +4.3605 | -14.2303 |

The final three columns are additive percentage-point units across trades, not compounded account returns. No baseline entry was dropped. Two additional winning trades partly offset the 2025 damage; seven extra trades partly offset historical damage. Both complete chronological comparisons still worsen. The 2025 treatment has 13 target hits: 11 surviving original targets plus two newly admitted targets.

## What the reversals teach us

Returning inside this boundary is not a reliable enough failure signal for this exit rule. Of the 11 sacrificed 2025 target winners, six triggered failure at the first post-entry hourly close; the median trigger time was one hour. The 12 intercepted original stops had a median trigger time of 6.5 hours. Historical cut winners also had a one-hour median. These timing observations are post-test diagnostics, not evidence that a chosen waiting period would work.

This result and the previous price-break-even test both show that some profitable breakouts need room to retrace. They do not establish that all dynamic exits are harmful, or that wider stops are optimal. The isolated 1–5% stop study and both exit studies remain separate records.

## Token, direction and year breakdown

All returns in this table use stressed costs. Counts and exit types are preserved in subgroups.csv.

| Group | Baseline trades | Treatment trades | Baseline mean net | Treatment mean net |
|---|---:|---:|---:|---:|
| 2022–24 BTCUSDT | 39 | 42 | +0.3442% | -0.0746% |
| 2022–24 ETHUSDT | 36 | 39 | -0.3040% | -0.2023% |
| 2022–24 SOLUSDT | 22 | 23 | +0.3446% | -0.2686% |
| 2022–24 LONG | 54 | 59 | +0.2837% | -0.0862% |
| 2022–24 SHORT | 43 | 45 | -0.1223% | -0.2692% |
| 2025 BTCUSDT | 17 | 18 | +0.3247% | -0.0661% |
| 2025 ETHUSDT | 8 | 9 | +0.4909% | -0.0538% |
| 2025 SOLUSDT | 11 | 11 | +0.3472% | +0.0646% |
| 2025 LONG | 26 | 27 | +0.2124% | -0.3832% |
| 2025 SHORT | 10 | 11 | +0.7743% | +0.8529% |
| 2022, all tokens | 27 | 27 | +0.4866% | +0.1584% |
| 2023, all tokens | 24 | 27 | -0.4624% | -0.5510% |
| 2024, all tokens | 46 | 50 | +0.1744% | -0.1320% |
| 2025, all tokens | 36 | 38 | +0.3685% | -0.0254% |

Every token’s stressed mean worsens in both pooled periods. The 2025 short-only cell improves slightly with an extra admission, but historical shorts worsen and remain negative. These small subgroups do not justify a token- or direction-specific deployment.

## Uncertainty

| Period | Chronological mean difference | 95% 1-week block interval | 95% 4-week block interval |
|---|---:|---:|---:|
| 2022–24 | -0.2691 pp | [-0.5930, +0.0403] pp | [-0.5701, +0.0310] pp |
| 2025 | -0.3939 pp | [-1.0283, +0.2264] pp | [-0.9470, +0.0930] pp |

Chronological difference intervals include zero. The 2025 matched-entry 4-week interval is wholly negative, while its 1-week interval includes zero; both are saved in paired_contrasts.csv. These are conditional, reused-history diagnostics, not independent proof. Both stressed treatment means are negative and both point improvements fail the frozen screen, so the decision is clear without claiming universal harm from early exits.

## Decision and next work

Retain the approved hourly compression baseline at SL2% / TP2.5%. Close both tested exit hypotheses with their negative findings. Pause further tuning of these exit rules on the same historical trades. Prioritize collecting/auditing the additional-token data for the existing frozen replication protocol and collecting prospective paper evidence with the unchanged baseline. Preserve the reserved 2026 outcomes and the broader-token qualification rules. Any future exit experiment needs a distinct hypothesis and a new predeclared protocol.

The known positive baseline results remain intact, including their limits: historical 2023 was negative, the pooled confidence intervals span zero and 2025 has been reused. A paper-approved candidate is not yet an independently confirmed profitable edge.

## Validation and reproducibility

22 tests passed (1.00 seconds): 20 hand-worked long/short cases, boundary reconstruction, and 400 randomized independent paths with prefix-causality checks. All 143 boundaries were reconstructed from minute bars strictly before the signal candle. All 286 raw arm paths passed the independent scalar reference; 286 baseline raw and 266 baseline admitted scenario rows reconciled exactly. Eight independent admission replays and four effect decompositions passed.

The separate report audit reconciled 124 pooled/subgroup/contrast/matched rows and all frozen source/output hashes. The full ledger contains 550 scenario rows: 133 baseline plus 142 treatment admissions, each at two costs. There are 78 affected ORIGINAL admissions in the stressed matched CSV; four additional historical failure exits belong to newly admitted trades. Raw matched opportunities can overlap and are not a tradable portfolio.

Protocol, aggregate results, complete token/direction/year tables and findings are published in PR99. The private combined exit-studies checkpoint preserves both experiments, code, exact entry boundaries, timing, detailed ledgers, logs and verification. It restores on top of the full hourly-compression checkpoint; original raw candles/funding remain separate. No cloud runtime change was made by this study. The previously supplied six-configuration paper-scan verification remains the latest observed operational evidence, not continuous monitoring.
