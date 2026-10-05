# Zone-aware exits: completed controlled comparison

5 October 2026. All three entry-policy comparisons completed under one frozen exit rule. Historical evidence is exploratory.

## What changed

Only the profit target changed. At actual entry, use the near edge of the nearest confirmed opposing hourly zone wholly ahead of entry, only when it lies inside the original 2.5% target. Otherwise retain 2.5%. Freeze the target throughout the trade. Longs use resistance; shorts use support. Entries, initial 1% stop, original 4h regime exit, taker execution costs and funding remain unchanged. No daily filter, holding cap or 2026 scoring.

The protocol was committed locally before execution at 29e4c0a; implementation and tests at 2caa00b. The pre-run GitHub publication attempt timed out in automatic approval review, so it was not established as published before execution.

## Complete scope

54 new exit-policy cells (3 entry methods × 3 tokens × 2 directions × 3 clocks), each with its unchanged-exit control. Two periods, two cost cases and paired/chronological views produce 864 aggregate rows. These are not 864 independent hypotheses. All 432 control rows reproduce the archived study.

## Summary by entry policy

| Entry | Period | Improved / 18 | Positive / 18 | Full-screen passes / 18 |
|---|---|---|---|---|
| Immediate | 2022–2024 | 5 | 0 | 0 |
| Immediate | 2025 | 5 | 0 | 0 |
| Fixed delay | 2022–2024 | 5 | 0 | 0 |
| Fixed delay | 2025 | 4 | 0 | 0 |
| Zone timing | 2022–2024 | 7 | 0 | 0 |
| Zone timing | 2025 | 2 | 0 | 0 |

## Decision and interpretation

Do not adopt this fixed opposing-zone target cap. All 54 new zone-exit cells have negative base means in both complete historical periods; none passes the screen. Some cells lose less, but that is not profitability.

The BTC 1h long 2025 example illustrates the failure: immediate entry changes from +0.030% to −0.226% net/trade; fixed delay from +0.220% to −0.022%; zone timing from +0.238% to −0.061%. Win rates rise in all three of these examples while expectancy deteriorates. Earlier exits increase subsequent trading capacity, so counts differ.

The exact matched-entry diagnostic also has a negative pooled mean delta for every entry method in both periods. Net gains forgone exceed net gains protected in each pooled group. Thus changed capacity does not fully explain the deterioration. This is an aggregate diagnostic, not a statement that every individual cell worsened.

About 24–28% of shortened-target chronological positions would have nonpositive target returns after modeled fees/slippage even before funding. Median shortened targets are only about 0.55–0.65%. The rule often cuts the upside while retaining the original 1% stop. These findings concern this static target cap, not all zone-aware exits.

Recommended next bounded hypothesis: a cost-aware minimum target distance, using costs known at entry, with fallback to the original target when the zone is too close. Freeze a single threshold before testing; keep entry, stop and regime exit fixed. Do not tune that threshold alongside trailing stops or zone definitions. This follow-up has NOT been run, and none of the current variants is selected for deployment.

The full screen spans BOTH periods: at least 50 completed trades each, positive base net means and PF ≥1.15 each, positive stressed means each. A higher mean with fewer trades is not by itself stronger evidence. Full-screen counts repeat across period rows because they are cross-period decisions.

## 2025 comparison, every cell

Each cell is average net return on trade notional, not account return. Boundary marks are included in averages and counted separately in CSV evidence. Deltas between means include changes to executable capacity.

### Immediate
| Token | Side | Clock | Original exit | Zone exit | Closed original / zone | Zone PF | Zone win rate | Zone MTM DD* |
|---|---|---|---|---|---|---|---|---|
| BTC | Short | 5m | -0.230% | -0.251% | 279 / 531 | 0.496 | 33.3% | +133.357% |
| BTC | Short | 15m | -0.112% | -0.200% | 186 / 350 | 0.540 | 42.0% | +70.074% |
| BTC | Short | 60m | -0.274% | -0.259% | 101 / 140 | 0.443 | 42.1% | +36.936% |
| BTC | Long | 5m | -0.158% | -0.174% | 147 / 422 | 0.536 | 28.4% | +73.456% |
| BTC | Long | 15m | +0.016% | -0.182% | 106 / 267 | 0.507 | 37.5% | +50.158% |
| BTC | Long | 60m | +0.030% | -0.226% | 69 / 131 | 0.447 | 39.7% | +30.694% |
| ETH | Short | 5m | -0.267% | -0.236% | 594 / 884 | 0.585 | 38.0% | +208.734% |
| ETH | Short | 15m | -0.148% | -0.174% | 359 / 487 | 0.668 | 45.2% | +92.212% |
| ETH | Short | 60m | -0.393% | -0.343% | 169 / 187 | 0.410 | 38.0% | +69.365% |
| ETH | Long | 5m | -0.143% | -0.209% | 319 / 502 | 0.619 | 37.3% | +105.694% |
| ETH | Long | 15m | -0.221% | -0.298% | 220 / 340 | 0.439 | 37.4% | +101.901% |
| ETH | Long | 60m | -0.105% | -0.263% | 93 / 111 | 0.465 | 39.6% | +31.812% |
| SOL | Short | 5m | -0.302% | -0.282% | 711 / 1023 | 0.563 | 34.0% | +290.298% |
| SOL | Short | 15m | -0.298% | -0.291% | 434 / 586 | 0.537 | 36.3% | +173.537% |
| SOL | Short | 60m | -0.348% | -0.362% | 178 / 201 | 0.445 | 35.3% | +74.269% |
| SOL | Long | 5m | -0.304% | -0.366% | 444 / 663 | 0.446 | 30.2% | +243.889% |
| SOL | Long | 15m | -0.189% | -0.321% | 276 / 383 | 0.496 | 35.8% | +123.716% |
| SOL | Long | 60m | -0.187% | -0.300% | 115 / 131 | 0.503 | 35.9% | +44.699% |

### Fixed delay
| Token | Side | Clock | Original exit | Zone exit | Closed original / zone | Zone PF | Zone win rate | Zone MTM DD* |
|---|---|---|---|---|---|---|---|---|
| BTC | Short | 5m | -0.213% | -0.217% | 252 / 442 | 0.571 | 40.0% | +96.394% |
| BTC | Short | 15m | -0.238% | -0.233% | 170 / 269 | 0.524 | 41.3% | +63.387% |
| BTC | Short | 60m | -0.313% | -0.312% | 72 / 98 | 0.383 | 38.8% | +34.174% |
| BTC | Long | 5m | -0.094% | -0.175% | 138 / 373 | 0.565 | 31.9% | +65.409% |
| BTC | Long | 15m | -0.045% | -0.133% | 98 / 227 | 0.634 | 41.9% | +36.069% |
| BTC | Long | 60m | +0.220% | -0.022% | 50 / 91 | 0.931 | 46.2% | +10.229% |
| ETH | Short | 5m | -0.231% | -0.252% | 517 / 756 | 0.564 | 37.2% | +192.330% |
| ETH | Short | 15m | -0.172% | -0.204% | 307 / 377 | 0.644 | 41.6% | +82.356% |
| ETH | Short | 60m | -0.275% | -0.358% | 116 / 128 | 0.447 | 35.2% | +46.708% |
| ETH | Long | 5m | -0.198% | -0.230% | 294 / 444 | 0.594 | 37.8% | +103.005% |
| ETH | Long | 15m | -0.097% | -0.173% | 180 / 243 | 0.651 | 45.7% | +42.581% |
| ETH | Long | 60m | +0.057% | -0.104% | 62 / 71 | 0.788 | 38.0% | +15.336% |
| SOL | Short | 5m | -0.337% | -0.311% | 631 / 852 | 0.543 | 35.0% | +266.958% |
| SOL | Short | 15m | -0.245% | -0.282% | 347 / 440 | 0.566 | 35.2% | +124.035% |
| SOL | Short | 60m | -0.460% | -0.372% | 132 / 144 | 0.459 | 32.6% | +55.436% |
| SOL | Long | 5m | -0.277% | -0.309% | 398 / 556 | 0.528 | 34.7% | +173.157% |
| SOL | Long | 15m | -0.223% | -0.348% | 224 / 282 | 0.481 | 33.3% | +99.401% |
| SOL | Long | 60m | -0.391% | -0.407% | 82 / 94 | 0.400 | 33.0% | +42.703% |

### Zone timing
| Token | Side | Clock | Original exit | Zone exit | Closed original / zone | Zone PF | Zone win rate | Zone MTM DD* |
|---|---|---|---|---|---|---|---|---|
| BTC | Short | 5m | -0.199% | -0.218% | 250 / 441 | 0.573 | 39.5% | +96.280% |
| BTC | Short | 15m | -0.242% | -0.246% | 174 / 279 | 0.497 | 40.9% | +69.306% |
| BTC | Short | 60m | -0.280% | -0.338% | 74 / 101 | 0.327 | 34.7% | +37.789% |
| BTC | Long | 5m | -0.088% | -0.177% | 137 / 377 | 0.559 | 31.3% | +66.813% |
| BTC | Long | 15m | -0.032% | -0.138% | 100 / 229 | 0.622 | 41.9% | +36.691% |
| BTC | Long | 60m | +0.238% | -0.060% | 48 / 94 | 0.822 | 47.9% | +9.276% |
| ETH | Short | 5m | -0.224% | -0.239% | 521 / 759 | 0.584 | 37.9% | +184.532% |
| ETH | Short | 15m | -0.194% | -0.227% | 316 / 394 | 0.608 | 41.4% | +95.118% |
| ETH | Short | 60m | -0.259% | -0.291% | 121 / 136 | 0.528 | 37.5% | +40.862% |
| ETH | Long | 5m | -0.190% | -0.224% | 295 / 445 | 0.601 | 38.0% | +100.811% |
| ETH | Long | 15m | -0.104% | -0.174% | 180 / 247 | 0.650 | 45.3% | +43.774% |
| ETH | Long | 60m | +0.015% | -0.200% | 67 / 76 | 0.608 | 35.5% | +20.473% |
| SOL | Short | 5m | -0.343% | -0.305% | 634 / 853 | 0.550 | 35.4% | +262.963% |
| SOL | Short | 15m | -0.231% | -0.299% | 352 / 448 | 0.543 | 34.6% | +135.185% |
| SOL | Short | 60m | -0.473% | -0.377% | 135 / 149 | 0.455 | 32.2% | +57.571% |
| SOL | Long | 5m | -0.287% | -0.312% | 400 / 560 | 0.526 | 34.5% | +176.085% |
| SOL | Long | 15m | -0.262% | -0.376% | 229 / 288 | 0.452 | 32.3% | +109.531% |
| SOL | Long | 60m | -0.388% | -0.410% | 85 / 99 | 0.417 | 34.3% | +45.036% |

*Drawdown is the maximum decline in an additive fixed-notional P&L curve across minute closes. It is not account percentage drawdown, does not compound and can exceed 100%; minute closes can miss intraminute extremes.

## Matched-entry exit attribution

Use the exact original-exit executed entry set and compare both exits for each entry. This isolates direct exit outcomes. These matched paths are diagnostic; each arm’s separate chronological schedule supplies executable counts. Aggregates below pool overlapping research configurations and must not be treated as a portfolio or independent observations. “Protected” and “missed” compare final modeled net outcomes under the two exits, not the best possible future price.
| Entry | Period | Matched entries | Target changed | Improved | Worsened | Mean net delta | Protected units | Missed units |
|---|---|---|---|---|---|---|---|---|
| Immediate | discovery | 14546 | 72.7% | 2704 | 2956 | -0.015% | 42.055 | 44.259 |
| Immediate | validation | 4800 | 73.2% | 867 | 1028 | -0.024% | 13.506 | 14.674 |
| Fixed delay | discovery | 12380 | 71.5% | 2251 | 2493 | -0.019% | 35.025 | 37.356 |
| Fixed delay | validation | 4070 | 71.3% | 746 | 855 | -0.027% | 11.466 | 12.565 |
| Zone timing | discovery | 12520 | 71.8% | 2310 | 2506 | -0.015% | 35.882 | 37.737 |
| Zone timing | validation | 4118 | 71.9% | 748 | 869 | -0.029% | 11.506 | 12.717 |

## Target economics diagnostic

Across base-cost chronological zone-exit positions, the following summarizes only entries whose target was shortened. Hypothetical target net includes taker fees and both sides of slippage, excluding funding; an actual position may stop or exit on regime first. These pooled counts overlap across configurations.
| Entry | Shortened-target positions | Median target distance | Target net ≤0 before funding |
|---|---|---|---|
| Immediate | 24384 | 0.549% | 28.3% |
| Fixed delay | 18921 | 0.645% | 23.9% |
| Zone timing | 19276 | 0.642% | 23.8% |

## Annual zone-exit results

Mean net return and completed count, by actual entry year. Positions spanning years within discovery are assigned to actual entry year. Annual averages do not constitute an independently reset annual simulation.

### Immediate
| Token | Side | Clock | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| BTC | Short | 5m | -0.233% (930) | -0.208% (259) | -0.205% (399) | -0.251% (531) |
| BTC | Short | 15m | -0.202% (596) | -0.192% (168) | -0.230% (224) | -0.200% (350) |
| BTC | Short | 60m | -0.209% (236) | -0.293% (88) | -0.124% (80) | -0.259% (140) |
| BTC | Long | 5m | -0.363% (248) | -0.215% (634) | -0.186% (746) | -0.174% (422) |
| BTC | Long | 15m | -0.303% (158) | -0.239% (446) | -0.180% (503) | -0.182% (267) |
| BTC | Long | 60m | -0.465% (62) | -0.224% (195) | -0.140% (197) | -0.226% (131) |
| ETH | Short | 5m | -0.198% (1092) | -0.229% (382) | -0.208% (615) | -0.236% (884) |
| ETH | Short | 15m | -0.173% (644) | -0.272% (238) | -0.210% (389) | -0.174% (487) |
| ETH | Short | 60m | -0.229% (214) | -0.220% (100) | -0.237% (148) | -0.343% (187) |
| ETH | Long | 5m | -0.262% (345) | -0.238% (670) | -0.215% (671) | -0.209% (502) |
| ETH | Long | 15m | -0.263% (239) | -0.256% (439) | -0.230% (444) | -0.298% (340) |
| ETH | Long | 60m | -0.238% (79) | -0.253% (178) | -0.228% (158) | -0.263% (111) |
| SOL | Short | 5m | -0.316% (1617) | -0.289% (512) | -0.297% (636) | -0.282% (1023) |
| SOL | Short | 15m | -0.275% (836) | -0.355% (304) | -0.318% (355) | -0.291% (586) |
| SOL | Short | 60m | -0.323% (253) | -0.333% (118) | -0.540% (109) | -0.362% (201) |
| SOL | Long | 5m | -0.345% (270) | -0.323% (1290) | -0.349% (1045) | -0.366% (663) |
| SOL | Long | 15m | -0.300% (146) | -0.303% (693) | -0.350% (599) | -0.321% (383) |
| SOL | Long | 60m | -0.445% (50) | -0.325% (227) | -0.362% (207) | -0.300% (131) |

### Fixed delay
| Token | Side | Clock | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| BTC | Short | 5m | -0.238% (792) | -0.198% (244) | -0.221% (324) | -0.217% (442) |
| BTC | Short | 15m | -0.193% (437) | -0.258% (146) | -0.206% (167) | -0.233% (269) |
| BTC | Short | 60m | -0.295% (157) | -0.250% (59) | -0.332% (60) | -0.312% (98) |
| BTC | Long | 5m | -0.422% (219) | -0.206% (574) | -0.169% (667) | -0.175% (373) |
| BTC | Long | 15m | -0.278% (123) | -0.202% (336) | -0.171% (395) | -0.133% (227) |
| BTC | Long | 60m | -0.376% (42) | -0.221% (137) | -0.183% (145) | -0.022% (91) |
| ETH | Short | 5m | -0.182% (953) | -0.248% (325) | -0.229% (527) | -0.252% (756) |
| ETH | Short | 15m | -0.231% (462) | -0.254% (193) | -0.212% (299) | -0.204% (377) |
| ETH | Short | 60m | -0.228% (145) | -0.211% (79) | -0.308% (104) | -0.358% (128) |
| ETH | Long | 5m | -0.308% (308) | -0.275% (594) | -0.220% (537) | -0.230% (444) |
| ETH | Long | 15m | -0.213% (177) | -0.291% (337) | -0.254% (344) | -0.173% (243) |
| ETH | Long | 60m | -0.322% (55) | -0.234% (128) | -0.189% (127) | -0.104% (71) |
| SOL | Short | 5m | -0.314% (1311) | -0.310% (429) | -0.281% (529) | -0.311% (852) |
| SOL | Short | 15m | -0.209% (603) | -0.271% (242) | -0.319% (273) | -0.282% (440) |
| SOL | Short | 60m | -0.272% (179) | -0.443% (86) | -0.375% (79) | -0.372% (144) |
| SOL | Long | 5m | -0.364% (219) | -0.331% (1091) | -0.327% (884) | -0.309% (556) |
| SOL | Long | 15m | -0.315% (111) | -0.299% (518) | -0.274% (451) | -0.348% (282) |
| SOL | Long | 60m | -0.059% (32) | -0.254% (152) | -0.327% (144) | -0.407% (94) |

### Zone timing
| Token | Side | Clock | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| BTC | Short | 5m | -0.246% (802) | -0.187% (244) | -0.221% (322) | -0.218% (441) |
| BTC | Short | 15m | -0.204% (454) | -0.274% (150) | -0.169% (168) | -0.246% (279) |
| BTC | Short | 60m | -0.309% (167) | -0.240% (62) | -0.361% (64) | -0.338% (101) |
| BTC | Long | 5m | -0.415% (223) | -0.203% (574) | -0.170% (668) | -0.177% (377) |
| BTC | Long | 15m | -0.273% (124) | -0.198% (344) | -0.177% (398) | -0.138% (229) |
| BTC | Long | 60m | -0.418% (45) | -0.235% (142) | -0.112% (154) | -0.060% (94) |
| ETH | Short | 5m | -0.183% (952) | -0.244% (326) | -0.243% (533) | -0.239% (759) |
| ETH | Short | 15m | -0.245% (472) | -0.262% (200) | -0.206% (310) | -0.227% (394) |
| ETH | Short | 60m | -0.258% (160) | -0.271% (82) | -0.227% (107) | -0.291% (136) |
| ETH | Long | 5m | -0.303% (311) | -0.280% (591) | -0.226% (555) | -0.224% (445) |
| ETH | Long | 15m | -0.256% (183) | -0.310% (345) | -0.262% (353) | -0.174% (247) |
| ETH | Long | 60m | -0.421% (58) | -0.359% (131) | -0.223% (130) | -0.200% (76) |
| SOL | Short | 5m | -0.328% (1327) | -0.312% (431) | -0.290% (533) | -0.305% (853) |
| SOL | Short | 15m | -0.219% (608) | -0.277% (248) | -0.308% (276) | -0.299% (448) |
| SOL | Short | 60m | -0.277% (184) | -0.474% (91) | -0.292% (82) | -0.377% (149) |
| SOL | Long | 5m | -0.327% (221) | -0.326% (1087) | -0.338% (886) | -0.312% (560) |
| SOL | Long | 15m | -0.376% (114) | -0.297% (525) | -0.245% (453) | -0.376% (288) |
| SOL | Long | 60m | -0.107% (33) | -0.203% (160) | -0.226% (149) | -0.410% (99) |

## Verification and limitations

Four focused tests pass: target geometry/fallback, conservative simultaneous stop/target handling, barrier/gap economics, and prefix-invariant zone mapping. All 432 prior control means/counts reconcile; maximum mean error 9.97e-17. Prior artifact/source hashes, six market inputs and each reused opportunity-audit archive member match. All original signals remain in audits. A post-run audit confirms identical planned entries across exit arms, positive target distances no greater than 2.5%, and zone-exit times no later than original-exit times for every filled plan.

The intervention only caps the existing target at a nearer opposing zone. It does not test trailing profits, zone invalidation exits or discretionary reactions at zones. No minimum economic target was added; targets very close to entry may incur net losses after taker costs. Favorable gap improvement is not assumed. Funding and costs follow the same historical model as controls.

Repeated use of 2022–2025 means these results are exploratory. No multiple-testing-adjusted proof, fresh validation, production approval, combined portfolio sizing or live change follows from this screen. All failed cells remain recorded.

## Evidence and publication

Local git-backed evidence includes source, tests, protocol, all 864 rows, annual/operation/matched-entry tables, screen, reconciliation, manifest, chronological trade ledgers and complete opportunity audits. GitHub publication is limited to written findings/protocol and aggregate tables within the existing authorized scope. Detailed scripts and ledgers remain local under the prior export restriction. Grokbot has not been contacted.
