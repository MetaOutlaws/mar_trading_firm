# Hourly compression: profit-protection experiment

7 October 2026. BTC, ETH, SOL; both directions; hourly entries. Research only.

**Decision: retain the approved 2% stop / 2.5% target baseline.** Moving the stop to the entry quote after a completed one-minute close at +2% reduced average net returns in both studied periods. It fails the predeclared improvement screen. The paper scanner continues with its existing exits.

## What was held fixed

Same 143 raw hourly signals, entry eligibility, 2% initial stop, 2.5% target, no timeout, funding, fees, slippage, token occupancy and basket limits. The sole treatment is a once-only stop move to the original entry quote after +1R (+2%) is confirmed by a one-minute close, effective from the next minute. Target/stop orders already hit have priority over that close. This is price break-even; costs still apply.

The protocol was published before scoring at commit `8f26ae5a4c49f521dbdee860c209387fea203976`. The 2022–24 and reused 2025 partitions reset flat. No 2026 outcome, new token, live setting or leverage was tested.

## Chronological results

Returns are average net percentage of position notional per trade, including fees, slippage and funding. Stress doubles slippage. Counts are unique admitted trades per arm, not the sum of cost scenarios.

| Period | Exit rule | Trades | Original stops | Protective stops | Targets | Net win rate | Mean net, base | Mean net, stress |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2022–24 | Baseline | 97 | 44 | 0 | 53 | 54.6% | +0.2268% | +0.1037% |
| 2022–24 | Price BE after +2% | 97 | 42 | 4 | 51 | 52.6% | +0.2159% | +0.0928% |
| 2025 | Baseline | 36 | 14 | 0 | 22 | 61.1% | +0.4992% | +0.3685% |
| 2025 | Price BE after +2% | 36 | 13 | 5 | 18 | 50.0% | +0.2754% | +0.1445% |

There are no terminal marks. All nine protective exits were net losses at both cost levels. Total stop-order exits rose from 44 to 46 in 2022–24 and from 14 to 18 in 2025, even though the original 2% stop was hit less often. Thus counting only original stops would give a misleading impression of improvement.

## Losses saved versus target winners sacrificed

| Period | Original stops intercepted | Target winners cut short | Change in stressed average net return |
|---|---:|---:|---:|
| 2022–24 | 2 of 44 | 2 of 53 | -0.0109 percentage points |
| 2025 | 1 of 14 | 4 of 22 | -0.2240 percentage points |

In 2025, intercepting one original stop saved 1.9982 additive percentage points across the matched trades, but cutting four target winners lost 10.0607 points. Net effect: −8.0625 additive points, or −0.2240 points per trade. These sums are not compounded account returns. Both arms admitted exactly the same trades; no new or dropped admissions explain the difference.

In 2022–24, two stopped trades were intercepted and two target winners were cut short. Each lost target gives up roughly 2.5% gross while an intercepted original stop saves roughly 2%; equal counts therefore need not break even. Funding and costs are included in the exact comparison.

## What the paths reveal

These are completed favorable closes before the baseline exit minute. Excluding the exit minute avoids assuming an unknown intrabar order.

| Period and original outcome | Trades | Reached +1% close | Reached +1.5% close | Reached +2% close |
|---|---:|---:|---:|---:|
| 2022–24, stopped | 44 | 15 | 6 | 2 |
| 2022–24, target | 53 | 51 | 49 | 46 |
| 2025, stopped | 14 | 4 | 3 | 1 |
| 2025, target | 22 | 22 | 22 | 21 |

Only 1 of the 14 stopped 2025 trades and 2 of the 44 historical stops reached a +2% close. Even a +1% close occurred in only 4/14 and 15/44 stops. Late protection therefore reaches only a small part of the losing population. Earlier protection is not proven superior: eventual winners also travel through those levels, and their intervening retracements must be replayed. The 1% and 1.5% rows are diagnostics, not tested exit alternatives.

## Token and calendar-year breakdown

All figures below are stressed mean net return per trade. Counts and original/protective/target exits are in `subgroups.csv`.

| Group | Trades | Baseline | Protection |
|---|---:|---:|---:|
| 2022–24 BTCUSDT | 39 | +0.3442% | +0.3298% |
| 2022–24 ETHUSDT | 36 | -0.3040% | -0.2486% |
| 2022–24 SOLUSDT | 22 | +0.3446% | +0.2315% |
| 2025 BTCUSDT | 17 | +0.3247% | +0.0267% |
| 2025 ETHUSDT | 8 | +0.4909% | -0.1334% |
| 2025 SOLUSDT | 11 | +0.3472% | +0.5288% |
| 2022, all three tokens | 27 | +0.4866% | +0.4866% |
| 2023, all three tokens | 24 | -0.4624% | -0.4624% |
| 2024, all three tokens | 46 | +0.1744% | +0.1514% |
| 2025, all three tokens | 36 | +0.3685% | +0.1445% |

The apparent 2025 SOL benefit comes from one intercepted stop, while BTC and ETH lose target winners. Historical SOL worsens. That does not support adopting a SOL-specific protection rule. All four changed historical trades occurred in 2024; 2022 and 2023 are unchanged. The baseline’s negative 2023 remains visible.

## Uncertainty and decision

| Period | Stressed change in mean net return | 95% 1-week block interval | 95% 4-week block interval |
|---|---:|---:|---:|
| 2022–24 | -0.0109 pp | [-0.1108, +0.0792] pp | [-0.1085, +0.0779] pp |
| 2025 | -0.2240 pp | [-0.5208, +0.0463] pp | [-0.5714, +0.0571] pp |

Both point comparisons worsen and all difference intervals include zero. This rejects this rule under the exploratory continuation screen; it does not establish that every form of profit protection is harmful. The baseline remains positive in the two pooled periods, but its confidence intervals also span zero. Reused history and 36 evaluation trades do not establish certain profitability.

## Next hypothesis

Keep the approved baseline scanning. The next focused candidate is a **failed-breakout exit**: test whether a completed hourly close back inside the pre-entry breakout boundary identifies failure early enough to reduce losses without ejecting too many winners. The boundary must be fixed using entry-time data, and the exit executed no earlier than the next minute. Freeze that rule and its comparator before scoring. This is a proposed experiment, not a finding or a deployed rule. A broad trigger sweep is not justified by this result.

Broader-token and prospective confirmation remain the main route to testing whether the entry edge generalizes. The failed protection rule does not erase the positive original baseline.

## Validation and handover

19 tests passed, covering hand-worked long/short timing, gaps, both-barrier cases and 400 randomized path comparisons with prefix-causality checks. Six market-input and nine feature hashes matched; 143 raw signals were retained. All 286 raw baseline rows and 266 admitted baseline scenario rows reproduced exactly. Every raw arm path passed an independent scalar state-machine check (286 paths); eight independent occupancy replays and four effect decompositions reconciled. The saved ledger has 532 rows: 133 admissions × two exit arms × two cost scenarios. These are not 532 independent trades.

A separate report audit reconciled 124 pooled/subgroup/contrast/matched rows and all frozen source/output hashes. Detailed plain CSVs and the private incremental checkpoint preserve signals, paths, changed trades, full ledgers, code, protocol and verification. The prior full checkpoint and original raw data remain prerequisites for a complete rerun.

Operational evidence: the user-supplied screenshot returned `scanning_verified` for all six hourly BTC/ETH/SOL long/short paper configurations with `errors: []`, for the cycle started 2026-10-07T10:05:31.385232+00:00. It verifies that completed cycle; this chat has no continuous SSH monitoring. No production exit rule changed in this experiment.
