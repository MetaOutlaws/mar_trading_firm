# Hourly compression: stop-width findings

7 October 2026. Hypothesis published before scoring. BTC/ETH/SOL, 1h, both sides; TP fixed at 2.5%. Original 2% stop reference and its positive findings are unchanged. These are reused-history diagnostics, not an independent confirmation.

## Decision

Retain the owner-approved 2% stop / 2.5% target for the paper pilot. No alternative passes the frozen requirement to improve both mean net return and mean net R at stressed costs in both historical 2022–24 and reused 2025. A 5% stop improves 2025 return per unit of notional but more than doubles initial price risk; its risk-normalized mean is lower. This does not prove 2% is globally optimal.

## 2025: chronological replay

| Stop | Closed | Stops | Stop rate | Targets | Win rate | Net/trade base | Net/trade stress | Mean R stress |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1% | 37 | 25 | 67.6% | 12 | 32.4% | -0.1092% | -0.2385% | -0.2385 |
| 2% | 36 | 14 | 38.9% | 22 | 61.1% | +0.4992% | +0.3685% | +0.1843 |
| 3% | 36 | 13 | 36.1% | 23 | 63.9% | +0.2627% | +0.1320% | +0.0440 |
| 4% | 36 | 10 | 27.8% | 26 | 72.2% | +0.4418% | +0.3111% | +0.0778 |
| 5% | 36 | 8 | 22.2% | 28 | 77.8% | +0.5779% | +0.4477% | +0.0895 |

## 2022–24: chronological replay

| Stop | Closed | Stops | Stop rate | Targets | Win rate | Net/trade base | Net/trade stress | Mean R stress |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1% | 101 | 62 | 61.4% | 39 | 38.6% | +0.1171% | -0.0058% | -0.0058 |
| 2% | 97 | 44 | 45.4% | 53 | 54.6% | +0.2268% | +0.1037% | +0.0519 |
| 3% | 96 | 33 | 34.4% | 63 | 65.6% | +0.3781% | +0.2552% | +0.0851 |
| 4% | 95 | 27 | 28.4% | 68 | 71.6% | +0.4198% | +0.2965% | +0.0741 |
| 5% | 95 | 24 | 25.3% | 71 | 74.7% | +0.3684% | +0.2448% | +0.0490 |

There are no terminal marks in these arms. Net includes fees, slippage and recorded settled funding. One trade per token at a time; each arm replays every original raw signal. Counts across stops/costs describe alternative systems and must not be added as independent trades. Net percentages are per-trade return on notional, not account returns. R divides by each arm's initial stop; an equal-risk interpretation would require smaller positions for wider stops. No leverage, liquidation or full equity simulation was performed.

## Did stopped trades recover?

Matched counterfactuals on the 36 baseline-admitted 2025 entries:

| Alternative stop | Baseline stops reaching target | Remaining stops | Baseline target winners lost to stops | Net difference per matched trade (base) |
|---|---:|---:|---:|---:|
| 1% | 0/14 | 14 | 11 | -0.6746% |
| 2% | 0/14 | 14 | 0 | +0.0000% |
| 3% | 1/14 | 13 | 0 | -0.2365% |
| 4% | 4/14 | 10 | 0 | -0.0575% |
| 5% | 6/14 | 8 | 0 | +0.0787% |

At 1%, 11 of the baseline's 22 targets are lost; the tighter chronological replay also admits one extra winner. At 3%, only one of 14 baseline stops recovers in 2025, insufficient to cover the larger remaining losses. At 5%, six recover and eight still stop. All 36 baseline entries remain admitted at 3–5% in 2025. Historical occupancy changes: 3% blocks one original entry; 4–5% block two. Matched raw opportunities include overlaps and are not an executable portfolio.

## Uncertainty and concentration

All 1-week and 4-week absolute stressed-mean confidence intervals cross zero in both partitions. The sample remains small; these intervals do not correct for the selection in earlier entry searches. No token-specific stop is selected from sparse subgroup cells.

| Stop | 2025 stressed net mean | 95% interval, 4-week blocks | Historical stressed net mean |
|---|---:|---:|---:|
| 1% | -0.2385% | -0.7014% to +0.2100% | -0.0058% |
| 2% | +0.3685% | -0.2725% to +1.0038% | +0.1037% |
| 3% | +0.1320% | -0.6468% to +0.8645% | +0.2552% |
| 4% | +0.3111% | -0.6974% to +1.2975% | +0.2965% |
| 5% | +0.4477% | -0.7787% to +1.6238% | +0.2448% |

## Validation and saved evidence

Six raw input hashes and nine frozen feature hashes verified. 143 unchanged raw hourly signals, 715 independent minute-barrier checks, 20 independent admission replays, and 266 baseline ledger rows (133 positions × two cost scenarios) reconcile. Full ledger: 1,330 rows across alternatives and costs. All 20 pooled results were independently reconciled again for reporting. No 2026 price scoring, new-token result or cloud activation occurred.

The paper implementation separately passed six focused tests and entry parity against 143 historical signals plus 1,734 rolling-history candidates. The runtime retains the desk's execution contract; see HOURLY_COMPRESSION_APPROVAL.md for fill/stop/funding/occupancy differences. Deployment is pending SSH execution, not owner permission.

## Next hypothesis

Profit protection after a favorable excursion may reduce full-stop losses without sacrificing too many target winners. First inspect pre-exit paths, preserving ambiguity on the exit minute, then freeze one bounded protection rule and its activation level before scoring it. Hold the hourly entry, 2% initial stop and 2.5% target fixed. Report saved losses, winners cut short, net return, holding time and occupancy effects. This next experiment has not yet run. Additional-token/forward confirmation stays separate.
