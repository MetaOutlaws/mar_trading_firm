# Zone-aware entry timing: completed findings

5 October2026. Decision: this fixed zone-entry timing policy does not pass the full exploratory screen. Do not adopt it as an improved default entry. Exit timing has not been changed or tested.

## Scope and isolated change

18 zone-timing policies (3 tokens × 2 directions × 3 entry clocks), 18 fixed-delay controls and 18 immediate-entry replications. Two reused historical periods, two cost scenarios and paired/chronological views produce432 aggregate rows. This is not432 independent hypotheses. No2026 outcomes were opened.

| Policy | Action after original signal |
|---|---|
| A immediate | Original entry at next available minute open |
| W fixed wait | Wait6 entry-clock bars, then market enter if original4h regime remains aligned |
| Z zone timing | Enter on rejection of a support/resistance zone frozen at the original signal; otherwise use the same6-bar deadline fallback |

Missing-zone signals would enter immediately. During waiting, regime loss cancels the setup and partition end censors it. Longs use support; shorts use resistance. Stops1%, targets2.5%, original4h regime exits and all modeled costs are unchanged. No daily or extra4h swing-structure filter. Six bars is setup waiting (30min/90min/6h), not a position holding cap. Market entries use actual next-open quotes with taker costs, not hypothetical zone-price or maker fills.

## 2025 results

Cells show mean net return per trade notional, with completed trades in parentheses. These are not account returns. Any open-at-boundary mark is included in the mean and flagged separately in evidence.

| Token | Side | Entry | A immediate | W fixed wait | Z zone timing |
|---|---|---|---|---|---|
| BTCUSDT | Short | 5m | -0.230% (279) | -0.213% (252) | -0.199% (250) |
| BTCUSDT | Short | 15m | -0.112% (186) | -0.238% (170) | -0.242% (174) |
| BTCUSDT | Short | 60m | -0.274% (101) | -0.313% (72) | -0.280% (74) |
| BTCUSDT | Long | 5m | -0.158% (147) | -0.094% (138) | -0.088% (137) |
| BTCUSDT | Long | 15m | +0.016% (106) | -0.045% (98) | -0.032% (100) |
| BTCUSDT | Long | 60m | +0.030% (69) | +0.220% (50) | +0.238% (48) |
| ETHUSDT | Short | 5m | -0.267% (594) | -0.231% (517) | -0.224% (521) |
| ETHUSDT | Short | 15m | -0.148% (359) | -0.172% (307) | -0.194% (316) |
| ETHUSDT | Short | 60m | -0.393% (169) | -0.275% (116) | -0.259% (121) |
| ETHUSDT | Long | 5m | -0.143% (319) | -0.198% (294) | -0.190% (295) |
| ETHUSDT | Long | 15m | -0.221% (220) | -0.097% (180) | -0.104% (180) |
| ETHUSDT | Long | 60m | -0.105% (93) | +0.057% (62) | +0.015% (67) |
| SOLUSDT | Short | 5m | -0.302% (711) | -0.337% (631) | -0.343% (634) |
| SOLUSDT | Short | 15m | -0.298% (434) | -0.245% (347) | -0.231% (352) |
| SOLUSDT | Short | 60m | -0.348% (178) | -0.460% (132) | -0.473% (135) |
| SOLUSDT | Long | 5m | -0.304% (444) | -0.277% (398) | -0.287% (400) |
| SOLUSDT | Long | 15m | -0.189% (276) | -0.223% (224) | -0.262% (229) |
| SOLUSDT | Long | 60m | -0.187% (115) | -0.391% (82) | -0.388% (85) |

## Cross-period interpretation

| Period | Z improves A | Z improves W | Z has positive mean | Z passes full screen |
|---|---:|---:|---:|---:|
| 2022–2024 | 9/18 | 5/18 | 0/18 | 0 |
| 2025 | 9/18 | 10/18 | 2/18 | 0 |

All18 zone-policy discovery means are negative. In2025 only BTC1h long and ETH1h long are positive under base costs. Neither passes across periods. No paired net-per-original-opportunity Z-minus-A or Z-minus-W comparison has a strictly positive lower bound under the stated36-comparison bootstrap adjustment. This does not prove equivalence or absence of any possible zone effect.

BTC1h long is the most positive2025 zone result: +0.238% net/trade, PF1.363,48 completed trades; stress mean+0.138%. It still fails the50-trade minimum and loses−0.142%/trade in2022–2024(PF0.830). The fixed-delay control returns+0.220% in2025, versus+0.030% immediate. Most of the observed improvement over immediate entry therefore also appears without zone confirmation. That is descriptive attribution, not randomized causality.

ETH1h long returns+0.015% in2025, PF1.019,67 trades; stress mean−0.085%. It loses−0.360% in discovery. It is also below thePF1.15 screen. Do not present these annual positives as full-research passes.

## Did mapping remove opportunities?

No. All 84,530 original candidates remain in each policy audit. Timing changes executed trades and pending capacity; the map itself does not delete a candidate. Candidate counts overlap across timeframes and are not independent market events.

| Execution measure, both periods | A immediate | W fixed wait | Z zone timing |
|---|---:|---:|---:|
| Executed positions including boundary marks | 19,346 | 16,450 | 16,638 |
| Signals blocked while pending | 0 | 5,762 | 4,929 |
| Signals blocked while in a position | 65,184 | 62,108 | 62,767 |
| Accepted setups canceled on regime loss | 0 | 208 | 194 |
| Accepted setups censored at partition end | 0 | 2 | 2 |

Only 2,443/16,638 executed Z entries (14.68%) were zone-rejection confirmations. The other 14,195 entries (85.32%) used a deadline fallback. Relevant zones happened to exist for every candidate in this particular sample; missing-zone fallback is implemented and tested.

Among all independent candidate plans, Z records11,345 rejection entries,72,659 deadline entries,521 regime cancellations and5 partition-censored plans. These are different from executed single-position counts because many candidates occur while another setup or trade occupies the sleeve. Distinguishing these views avoids crediting overlapping hypothetical entries as a realizable book.

The dominant fallback rate means the proposed timing policy mostly imposes a delay. It has not established a repeatable advantage from entering at a confirmed zone rejection. The current test does not reject all uses of support/resistance or zone-aware exits.

## Annual zone-policy outcomes

Grouped by actual entry year, with completed counts. Trade outcomes spanning years inside discovery stay attributed to actual entry-year, not the year of the original signal or a separately restarted annual simulation.

| Token | Side | Entry | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| BTCUSDT | Short | 5m | -0.242% (478) | -0.191% (85) | -0.244% (185) | -0.199% (250) |
| BTCUSDT | Short | 15m | -0.187% (297) | -0.165% (63) | -0.244% (116) | -0.242% (174) |
| BTCUSDT | Short | 60m | -0.341% (127) | -0.226% (34) | -0.215% (49) | -0.280% (74) |
| BTCUSDT | Long | 5m | -0.451% (134) | -0.105% (285) | -0.071% (306) | -0.088% (137) |
| BTCUSDT | Long | 15m | -0.416% (88) | -0.204% (202) | -0.021% (215) | -0.032% (100) |
| BTCUSDT | Long | 60m | -0.403% (36) | -0.126% (96) | -0.073% (116) | +0.238% (48) |
| ETHUSDT | Short | 5m | -0.152% (638) | -0.201% (117) | -0.262% (303) | -0.224% (521) |
| ETHUSDT | Short | 15m | -0.190% (346) | -0.361% (86) | -0.349% (214) | -0.194% (316) |
| ETHUSDT | Short | 60m | -0.156% (131) | -0.374% (49) | -0.396% (87) | -0.259% (121) |
| ETHUSDT | Long | 5m | -0.317% (237) | -0.347% (342) | -0.209% (343) | -0.190% (295) |
| ETHUSDT | Long | 15m | -0.196% (153) | -0.465% (235) | -0.210% (247) | -0.104% (180) |
| ETHUSDT | Long | 60m | -0.476% (57) | -0.406% (98) | -0.245% (96) | +0.015% (67) |
| SOLUSDT | Short | 5m | -0.264% (1006) | -0.293% (282) | -0.277% (384) | -0.343% (634) |
| SOLUSDT | Short | 15m | -0.124% (503) | -0.307% (176) | -0.382% (213) | -0.231% (352) |
| SOLUSDT | Short | 60m | -0.097% (167) | -0.525% (73) | -0.207% (73) | -0.473% (135) |
| SOLUSDT | Long | 5m | -0.177% (194) | -0.309% (862) | -0.342% (650) | -0.287% (400) |
| SOLUSDT | Long | 15m | -0.274% (106) | -0.313% (455) | -0.284% (368) | -0.262% (229) |
| SOLUSDT | Long | 60m | -0.070% (31) | -0.086% (147) | -0.224% (135) | -0.388% (85) |

## Next isolated step

Keep baseline entry as the reference for the later zone-aware EXIT study, rather than stacking an unproven entry delay with a new exit. Freeze one exit mechanism and compare it with the existing exit, leaving entries, initial stop and costs unchanged. Log whether an earlier exit captures gains, truncates winners or merely reduces exposure; include missed continuation and cost effects. No exit rule has been selected or executed in this study.

For further entry research, first inspect why85% of executed setups fell back and how the frozen zone distance related to waiting and outcome. Do not tune the six-bar deadline, zone width, stop and target together to repair this result. Any further timing rule needs a new bounded protocol and all failed attempts preserved.

## Verification and limitations

- Original immediate baseline matches all36 configuration-period reference rows, maximum mean error 9.84e-17. Six market input hashes match. Annotation bytes match the prior packaged evidence.
- Seven new tests pass, including240 scalar timing-oracle cases, mirrored rejection, no current-signal-candle trigger, next-open gap economics, regime-cancel priority, invalid-zone fallback, missing-zone entry and pending-capacity accounting. Causal timestamp and opportunity-key checks pass on the full produced audit.
- Written protocol was published before this run at GitHub commit d0038a6117d4dbab4ca2c39cea22802f68f95895. Source/test implementation was frozen locally at73b3db9 before execution. Full source/input hashes are in manifest.json.
- Paired observations overlap. Chronological sleeves are independent configurations, not a jointly sized portfolio. Costs and funding marks are modeled; intraminute execution uncertainty remains. Minute-close drawdown can miss intraminute extremes.
- Reused2022–2025 history is exploratory, not fresh confirmation. Bootstrap intervals do not correct the full research history or all long-duration dependence. No2026 scoring, live trading, approval or worker changes.

## Evidence and publication

Local package: protocol, source, tests, all_results.csv, annual_results.csv, operations.csv, reconciliation.csv, opportunity_intervals.json, screen.csv, manifest.json and trade_and_opportunity_evidence.zip. Every candidate, cancellation, blocked signal and failed cell is retained.

GitHub publication contains written findings and aggregate report tables. Detailed scripts, trade records and configuration datasets remain local pending the specific export approval previously requested. Grokbot has not been contacted.

See PASS_CLARIFICATION.md for the unresolved recalled earlier full-research pass and the distinction between historical candidates, audit passes and profitability screens.

Reproduce from repository root:
```bash
PYTHONPATH=/path/to/dependencies python research/isolated_token_study_20261003/zone_entry_timing_20261005/run_zone_entry.py --cache /path/to/market_cache_v2 --annotations /path/to/incremental_results_20261005 --out /path/to/new_zone_results
```
