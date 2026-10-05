# Incremental context test: results

Completed 5 October 2026. Decision: do not add this daily trend filter to the baseline. Keep the non-blocking support/resistance map as research context. No configuration qualifies for promotion.

## What changed

| Arm | Entry context | Status |
|---|---|---|
| A | Original 4h EMA50/200 trend plus lower-clock EMA20 reclaim | Archived baseline replicated |
| B | A plus the exact PR97 confirmed 4h higher-high/higher-low or lower-high/lower-low permission | Archived structure test replicated |
| C | B plus completed daily close vs EMA50 and its 3-day slope | Only new tradable variable |

All arms keep the original 1% stop, 2.5% target, 4h EMA-regime exit, costs and no holding cap. Daily swing structure, new entry patterns and parameter optimization were not added. The zone map cannot reject an entry or change a stop, target, exit or fill. The daily trend definition has two fixed predicates; their individual contributions are not separately estimated.

18 new daily-filter configurations, with 36 A/B reference replications. Three arms × 18 token/direction/timeframe cells × two periods × two costs × two views = 432 aggregate rows. The earlier 108-configuration proposal was not executed.

## Non-blocking zone map

| Token | Original opportunities | Annotated | Both active pivot bands mapped | Zone-based rejections |
|---|---:|---:|---:|---:|
| BTCUSDT | 28,685 | 28,685 | 28,270 (98.55%) | 0 |
| ETHUSDT | 28,434 | 28,434 | 28,080 (98.76%) | 0 |
| SOLUSDT | 27,411 | 27,411 | 26,880 (98.06%) | 0 |

All 84,530 original opportunities were retained in the annotated universe. Both support and resistance could be mapped for 98.46%; this is coverage, not a claim of proximity or proven liquidity. Opportunities without a mapped band are still retained. Counts include overlapping timeframe signals and are not independent market events.

Bands come from causally confirmed hourly pivots, with ATR widths, 30-day expiry and completed-hour invalidation. All valid bands are considered, without the former six-zone cap. Each row records nearest active support/resistance, distance in percent and ATR, confirmation time, age, overlap touches, range position, previous daily high/low and opposing target room. Touch counts are descriptive, not validated strength scores. Candle bands are proxies for possible supply/demand, not measured resting orders.

## 2025 comparison

Cells show mean net return on trade notional and completed trade count in parentheses. These are not account returns. Means include boundary valuations when present.

| Token | Side | Entry | A: baseline | B: +4h structure | C: +daily trend | C minus B, percentage points |
|---|---|---|---|---|---|---:|
| BTCUSDT | Short | 5m | -0.230% (279) | -0.193% (144) | -0.218% (137) | -0.025 |
| BTCUSDT | Short | 15m | -0.112% (186) | +0.020% (100) | +0.010% (95) | -0.010 |
| BTCUSDT | Short | 60m | -0.274% (101) | -0.140% (50) | -0.123% (46) | +0.016 |
| BTCUSDT | Long | 5m | -0.158% (147) | -0.072% (98) | -0.096% (97) | -0.024 |
| BTCUSDT | Long | 15m | +0.016% (106) | -0.089% (65) | -0.126% (64) | -0.037 |
| BTCUSDT | Long | 60m | +0.030% (69) | +0.116% (38) | +0.116% (38) | +0.000 |
| ETHUSDT | Short | 5m | -0.267% (594) | -0.250% (263) | -0.272% (258) | -0.022 |
| ETHUSDT | Short | 15m | -0.148% (359) | -0.079% (166) | -0.123% (163) | -0.044 |
| ETHUSDT | Short | 60m | -0.393% (169) | -0.345% (82) | -0.445% (79) | -0.100 |
| ETHUSDT | Long | 5m | -0.143% (319) | -0.042% (173) | -0.076% (168) | -0.034 |
| ETHUSDT | Long | 15m | -0.221% (220) | -0.069% (117) | -0.049% (115) | +0.020 |
| ETHUSDT | Long | 60m | -0.105% (93) | -0.253% (40) | -0.228% (39) | +0.025 |
| SOLUSDT | Short | 5m | -0.302% (711) | -0.348% (286) | -0.347% (282) | +0.000 |
| SOLUSDT | Short | 15m | -0.298% (434) | -0.252% (179) | -0.228% (175) | +0.024 |
| SOLUSDT | Short | 60m | -0.348% (178) | -0.381% (79) | -0.381% (79) | +0.000 |
| SOLUSDT | Long | 5m | -0.304% (444) | -0.314% (242) | -0.314% (242) | -0.000 |
| SOLUSDT | Long | 15m | -0.189% (276) | -0.287% (150) | -0.281% (149) | +0.006 |
| SOLUSDT | Long | 60m | -0.187% (115) | -0.374% (56) | -0.374% (56) | +0.000 |

## Effect of each permission

| Period | Original opportunities | B retained | C retained | Additional retention, C/B | C improves B net/trade |
|---|---:|---:|---:|---:|---:|
| 2022–2024 | 63,772 | 25,958 (40.70%) | 24,677 (38.70%) | 95.07% | 6/18 |
| 2025 | 20,758 | 8,805 (42.42%) | 8,636 (41.60%) | 98.08% | 6/18 |

B and C are explicitly tested trade-permission filters, so they can reduce entries. Those reductions must not be attributed to zone mapping. The map alone has zero rejections. Counts above are candidate opportunities before the one-open-position restriction.

All 18 C configurations have negative 2022–2024 mean returns. In 2025 only BTC 15m short and BTC 1h long are positive under base costs. The latter has just 38 completed trades; the former loses under doubled slippage. Neither passes the unchanged full screen. Daily alignment mostly duplicates permission already granted by 4h context, and its incremental benefit is inconsistent.

No C-minus-B 2025 weekly-block bootstrap interval has a strictly positive lower bound after the stated 18-comparison adjustment. Some arms have identical trades and hence zero delta intervals. These intervals do not correct prior historical reuse or all dependence from long holds. No fresh holdout is claimed.

## Annual results: daily filter C

Annual grouping uses entry year; trades crossing years inside the discovery partition remain assigned to entry year. These are not annual simulations restarted flat.

| Token | Side | Entry | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| BTCUSDT | Short | 5m | -0.187% (268) | -0.090% (50) | -0.311% (103) | -0.218% (137) |
| BTCUSDT | Short | 15m | -0.159% (181) | -0.010% (37) | -0.369% (71) | +0.010% (95) |
| BTCUSDT | Short | 60m | -0.361% (88) | -0.744% (18) | -0.225% (32) | -0.123% (46) |
| BTCUSDT | Long | 5m | -0.279% (42) | -0.049% (154) | -0.136% (166) | -0.096% (97) |
| BTCUSDT | Long | 15m | -0.081% (34) | -0.150% (120) | -0.110% (130) | -0.126% (64) |
| BTCUSDT | Long | 60m | -0.289% (19) | -0.042% (59) | +0.065% (70) | +0.116% (38) |
| ETHUSDT | Short | 5m | -0.167% (335) | -0.168% (82) | -0.147% (144) | -0.272% (258) |
| ETHUSDT | Short | 15m | -0.137% (194) | -0.233% (63) | -0.351% (94) | -0.123% (163) |
| ETHUSDT | Short | 60m | -0.334% (72) | -0.291% (28) | -0.390% (47) | -0.445% (79) |
| ETHUSDT | Long | 5m | -0.354% (102) | -0.335% (161) | -0.161% (186) | -0.076% (168) |
| ETHUSDT | Long | 15m | -0.408% (74) | -0.392% (114) | -0.190% (145) | -0.049% (115) |
| ETHUSDT | Long | 60m | -0.490% (29) | -0.076% (49) | -0.088% (61) | -0.228% (39) |
| SOLUSDT | Short | 5m | -0.275% (549) | -0.426% (138) | -0.543% (179) | -0.347% (282) |
| SOLUSDT | Short | 15m | -0.172% (299) | -0.481% (95) | -0.489% (107) | -0.228% (175) |
| SOLUSDT | Short | 60m | -0.099% (104) | -0.770% (39) | -0.515% (44) | -0.381% (79) |
| SOLUSDT | Long | 5m | -0.251% (96) | -0.229% (403) | -0.379% (382) | -0.314% (242) |
| SOLUSDT | Long | 15m | -0.303% (52) | -0.286% (239) | -0.439% (225) | -0.281% (149) |
| SOLUSDT | Long | 60m | -0.638% (26) | -0.263% (90) | -0.503% (90) | -0.374% (56) |

## What to test next, one change at a time

1. Keep the zone map as a descriptive layer. Before making it a trading rule, compare baseline trade paths by distance to support/resistance, range position and opposing room, separately for token, direction and clock. Treat those slices as hypothesis generation, not proof of a tradable edge.
2. Do not automatically retain the daily filter. This test provides no consistent reason to add it. Likewise, 4h structure has no full-screen survivor; it remains a comparison arm, not an established improvement.
3. The next entry experiment should compare ONE predeclared zone-aware timing rule with the existing entry, using the same 4h regime and unchanged stop/target/exit. Do not simultaneously add daily swing structure, widen stops, change targets or vary zone widths.
4. A map can preserve every candidate opportunity, but a later permission or entry-timing rule can change fills or trade counts. Record waiting, missed fills and cancellations instead of claiming that a different execution policy can guarantee identical trades.
5. Stop after this stage to review the evidence. No new entry pattern or 2026 outcome has been tested.

## Verification and provenance

- Seven new tests passed. Six input hashes match archived data. All 72 A/B base-cost chronological configuration-period rows reconcile, with maximum mean error 9.84e-17.
- All 19,346 baseline trade observations across the two partitions map to one annotated opportunity each within their cell. No mapped pivot confirmation occurs after entry. Opportunity keys are unique within token/timeframe/direction.
- Protocol frozen locally in commit b09e288 before the run; implementation in 7bafef3. Source and input hashes are recorded in manifest.json. The protocol was not publicly timestamped before execution; local registration is not independent attestation.
- Minute-close MTM may miss worse intraminute drawdown. Fees/slippage and funding mark proxies remain modeled. Independent research sleeves are not a portfolio simulation.
- No live strategy, approval, worker or VM setting changed.

## Evidence and publication

Local package includes all_results.csv, annual_results.csv, retention.csv, zone_coverage.csv, reconciliation.csv, delta_intervals.json, screen.csv, manifest.json and trade_and_annotation_evidence.zip, plus source and tests. Every failed cell remains recorded.

GitHub publication is limited to this findings report and the protocol. Detailed configuration and trade/annotation evidence remains local pending the specific dataset-export approval previously requested. Grokbot has not been messaged or launched.

Reproduce from the repository root with the frozen data cache:
```bash
PYTHONPATH=/path/to/dependencies python research/isolated_token_study_20261003/incremental_context_20261005/run_incremental.py --cache /path/to/market_cache_v2 --out /path/to/new_results
```
