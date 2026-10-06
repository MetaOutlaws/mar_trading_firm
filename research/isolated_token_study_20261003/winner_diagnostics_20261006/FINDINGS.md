# Winners versus losers: paths, indicators and prediction

6 October2026. **38,469 individual standalone-zone positions examined; all144 original base-cost groups reconciled. No tested filter establishes profitability.** Includes all four stop/target arms, three tokens, three timeframes, both directions,2022–2024 discovery and reused2025 validation. These records overlap across arms/timeframes and are not independent market events. No2026 outcomes or production changes.

Protocol and code frozen at a9745e5. A JSON numpy-scalar serialization repair(e2df4d1) changed no feature/selection rule. Discovery selections frozen at ca0c336 before validation replay. Five entry-feature families, three discovery tertiles each,36 primary configuration cells:540 candidate bins. One discovery-cohort filter qualified;35 cells yielded no filter. Full rescheduled strategy failed for that filter in both periods.

## 1. What winners actually look like

2025 pooled completed trades, separately for each stop/TP. Winner means positive NET return, not simply a target touch. Empirical break-even = average net loss magnitude/(average net win + average net loss magnitude). It describes the observed payoff mixture and is not a guaranteed future threshold. Net wins/losses below include fees, slippage and funding.

| Stop / TP | Completed | Winners | Actual win rate | Avg net winner | Avg net loss | Empirical break-even |
|---|---:|---:|---:|---:|---:|---:|
| 1% / 2.5% | 3,409 | 907 | 26.61% | 2.097% | -1.197% | 36.34% |
| 2% / 2.5% | 2,321 | 908 | 39.12% | 2.114% | -2.005% | 48.68% |
| 3% / 2.5% | 1,853 | 874 | 47.17% | 2.137% | -2.636% | 55.24% |
| 3% / 3% | 1,719 | 740 | 43.05% | 2.581% | -2.630% | 50.47% |

Most winners are target hits, but not all:2%/2.5% has844 target winners and64 profitable regime exits;3%/3% has687 target winners and53 profitable regime exits. Winner size is partly mechanically set by TP, but costs, funding and other exits still affect it.

The quoted36% break-even is approximately relevant only to the1%/2.5% payoff under these costs. With target/stop-only exits, base fees/slippage but no funding/gaps, break-even ranges across tokens/directions are:

| Stop / TP | Costed barrier-only break-even range |
|---|---:|
| 1% / 2.5% | 34.57%–37.44% |
| 2% / 2.5% | 49.11%–51.34% |
| 3% / 2.5% | 58.36%–60.19% |
| 3% / 3% | 53.50%–55.17% |

Empirical thresholds differ because actual losses include regime exits and the full cost/funding path. Increasing win rate alone is insufficient when average losses also increase.

## 2. Winner adversity and stopped-trade missed profit

We exclude exit-minute high/low because a minute candle cannot establish whether an extreme happened before or after the exit. These are conservative pre-exit observations from entry quote, not tick-exact total excursions. Same-minute exits are flagged, with no observed prior-minute excursion. Percentiles below do not directly specify optimal stops or targets.

| Stop / TP | Winners | Winner median adverse move | Winner90th-percentile adverse move | Winners adverse>=1% | Stopped trades | Stopped trades previously favorable>=1% |
|---|---:|---:|---:|---:|---:|---:|
| 1% / 2.5% | 907 | 0.378% | 0.826% | 0 | 2,328 | 611 |
| 2% / 2.5% | 908 | 0.562% | 1.592% | 270 | 1,166 | 417 |
| 3% / 2.5% | 874 | 0.756% | 2.357% | 369 | 668 | 256 |
| 3% / 3% | 740 | 0.832% | 2.363% | 328 | 667 | 291 |

For2%/2.5%,270/908 winners(29.7%) first experienced at least1%adverse movement; for3%/3%,328/740(44.3%). This supports studying variable stops. Conversely417/1166(35.8%) and291/667(43.6%) stopped trades had first offered at least1%favorable movement. That motivates studying giveback, but taking profit earlier could also truncate large winners. Any exit change requires a separate all-trade simulation; these hindsight paths are not live predictors.

## 3. Entry-time indicators versus exit-time indicators

Features use completed entry-clock candles. RSI14 is Wilder; Connors RSI is(3,2,100); ADX14 uses Wilder smoothing; relative volume = signal candle volume / median of20 preceding candles, excluding the signal candle. ATR% uses Wilder ATR14. Exit features use only entry-clock candles completed by the exit minute's OPEN. Exit indicators are outcome descriptions and were forbidden in prediction.

2025 medians pooled across the TWO user-requested stop/TP arms, split by direction. These distributions mix tokens/timeframes and duplicate some opportunities; use per-cell files for inference.

| Side | Outcome | Entry RSI14 | Exit RSI14 | Entry Connors | Exit Connors | Entry ADX14 | Relative volume |
|---|---|---:|---:|---:|---:|---:|---:|
| short | loser | 56.02 | 63.18 | 29.83 | 76.36 | 24.87 | 1.316× |
| short | winner | 57.00 | 36.14 | 32.04 | 20.42 | 24.66 | 1.201× |
| long | loser | 42.29 | 36.04 | 68.04 | 22.85 | 26.16 | 1.466× |
| long | winner | 43.32 | 63.76 | 67.27 | 78.28 | 26.23 | 1.315× |

Entry RSI and ADX medians show limited separation in these pooled groups. Winners have lower median relative volume than losers in both directions, but that is an association, not a proven rule. Exit RSI strongly separates outcomes, as expected after prices move favorably or adversely; it cannot be used to predict those same outcomes at entry.

Across72 per-configuration comparisons with>=20 winners AND losers in each period, the sign of the winner-minus-loser median difference repeats from discovery to validation in45/72 for ADX,42/72 for Connors,37/72 for relative volume,32/72 for ATR%,29/72 for RSI. These overlapping unadjusted comparisons are descriptive, not significance tests. No universal high-volume, oversold-RSI or high-ADX gate is established.

## 4. Clustering

Within each configuration, rank active ENTRY days by winner count after observing outcomes. Below are median concentration measures across the18 token/timeframe/direction cells in2025. Top10% means ceiling(10%×active days).

| Stop / TP | Winners on top10%days | All trades on those same days |
|---|---:|---:|
| 1% / 2.5% | 28.41% | 19.26% |
| 2% / 2.5% | 27.52% | 18.92% |
| 3% / 2.5% | 25.67% | 19.41% |
| 3% / 3% | 25.00% | 17.64% |

Winners concentrate on some days, but much of the concentration accompanies greater trade activity. The days were selected retrospectively for winner count, so this is NOT evidence by itself that a predictive market regime exists. No significance or calendar filter is claimed. Daily and monthly counts, win rates and net sums are supplied so high-activity days can be compared with genuinely higher-quality days. Entry and exit timestamps are in the individual-trade file.

## 5. Discovery-selected prediction check

The only selected candidate was ETH15m SHORT,3%stop/3%target, relative volume in the discovery middle tercile: **1.0774763286 <= relative volume <1.7636582032**. Based only on previously executed discovery trades, this retained98 trades with +0.2081%net/trade, PF1.169, positive annual means and positive doubled-slippage mean. Thresholds and selection were frozen before checking2025.

Crucially, filtering changes which subsequent signals can be traded. Replaying ALL original eligible signals under the filter produces:

| Period | Positions | Completed | Net/trade | PF | Doubled-slippage net/trade |
|---|---:|---:|---:|---:|---:|
| discovery | 198 | 197 | -0.1890% | 0.858 | -0.2892% |
| validation | 81 | 81 | -0.5743% | 0.636 | -0.6749% |

Discovery includes one boundary valuation in the198positions. The apparent profitable98-trade historical subset becomes unprofitable once actual admission/scheduling is simulated.2025 is also negative and below the PF gate. This is direct evidence against treating winner/loser row selection as a complete strategy test. The other35 cells produced null selections; no fallback threshold or additional feature combination was tried.

## Evidence and limits

All144 base groups reconcile, maximum mean difference <1e-12; six raw market hashes verified; source candidate/zone/trade files checked against archived evidence. Indicator prefix recomputation is identical, and three synthetic tests cover trend/flat ADX, future independence, path exit-minute exclusion and missing values. Source/selection hashes recorded.540 attempted bins are retained in the training ledger.2025 is repeatedly reused research data, so even a surviving filter would require genuinely fresh confirmation. These results reject this bounded selection procedure, not every possible conditional entry/stop policy.

No optimization was deployed. The next useful hypothesis is to test a precisely specified entry-known condition or giveback policy against all opportunities, with a frozen budget, rather than selecting recovered trades using their future paths. Breakout/retest remains the next previously planned standalone entry family; these diagnostics do not silently replace that queue.
