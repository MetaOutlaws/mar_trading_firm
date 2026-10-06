# Trade anatomy: RSI, Connors RSI and stop location

6 October 2026. Completed annotation and outcome-diagnostic stage. **No strategy or entry filter changed. No adaptive-stop, oscillator-filter or cost-aware zone-exit backtest has been run in this stage.**

## Main findings

All 84,530 original opportunities were annotated with entry-time context, including all 19,346 baseline executed positions (19,341 completed and five boundary marks). All 36 baseline configuration-period means and exit counts reconcile. No opportunity was removed, and no 2026 outcome was opened.

1. Conventional direction-appropriate oscillator extremes were absent at the existing EMA-reclaim signals: zero RSI <30 longs / ≥70 shorts, and zero Connors RSI <10 longs / ≥90 shorts. This is true across all 84,530 candidates, not only executed positions. Such an added requirement at signal would admit no existing candidates.

2. Extremes in the preceding three completed entry-clock bars exist but are uncommon. In 2025, only 121/4,800 completed baseline positions (2.5%) had a recent RSI extreme; 272/4,800 (5.7%) had a recent Connors extreme. Those are membership counts on existing trades, not results of a rescheduled filtered strategy.

3. Winners and stop-outs have similar pooled, direction-separated oscillator medians. Some subgroup associations are positive, but the sparse samples and inconsistent cross-period direction do not establish an oscillator edge.

4. Stop location relative to supporting zones does not produce a universal discriminator. A stop before the zone occurs among 61.6% of 2025 stop-outs and 64.0% of winners. Simply observing that many losing stops were before support/resistance would have been misleading without winners as controls.

## Oscillator coverage

An extreme is direction-aware: RSI <30 long / ≥70 short; Connors <10 long / ≥90 short. The recent-extreme window excludes the signal candle. “Bars” use each entry clock, so three bars spans 15 minutes, 45 minutes or three hours.

| Period | Condition | Closed trades | Condition present | Share | Adequate matched cells /18 | Positive adjusted association |
|---|---|---|---|---|---|---|
| 2022–2024 | RSI extreme at signal | 14541 | 0 | 0.0% | 0 | 0 |
| 2022–2024 | RSI extreme in previous 3 bars | 14541 | 366 | 2.5% | 5 | 3 |
| 2022–2024 | Connors extreme at signal | 14541 | 0 | 0.0% | 0 | 0 |
| 2022–2024 | Connors extreme in previous 3 bars | 14541 | 782 | 5.4% | 12 | 6 |
| 2025 | RSI extreme at signal | 4800 | 0 | 0.0% | 0 | 0 |
| 2025 | RSI extreme in previous 3 bars | 4800 | 121 | 2.5% | 1 | 1 |
| 2025 | Connors extreme at signal | 4800 | 0 | 0.0% | 0 | 0 |
| 2025 | Connors extreme in previous 3 bars | 4800 | 272 | 5.7% | 4 | 1 |

“Adequate” here only means at least20 exposed and20 control observations after common-support matching. It is a modest diagnostic count threshold, not strategy qualification or sufficient statistical power. Zero current-extreme counts are not missing indicator values; indicator coverage is complete.

The current trigger often arrives after the rebound/breakdown. That describes the observed sample and trigger behavior, not proof that RSI is useless. A true oversold-setup/confirmation system would need its own explicitly timed setup state and new entry test. Do not quietly loosen thresholds until a favorable subgroup appears.

## Winners versus stopped losses, 2025

Medians below pool timeframes/tokens within direction, so they provide descriptive context only; the full cell tables remain separate. “Winner” means positive net return, including profitable regime exits.

| Side | Outcome | Count | Median RSI14 | Median Connors RSI |
|---|---|---|---|---|
| Short | stop_loss | 2078 | 48.21 | 20.74 |
| Short | winner | 845 | 48.30 | 20.86 |
| Long | stop_loss | 1181 | 51.44 | 79.20 |
| Long | winner | 549 | 51.65 | 78.56 |

| Outcome | 1% stop location | Count | Share within outcome |
|---|---|---|---|
| winner | before_near_edge | 892 | 64.0% |
| winner | inside_band | 250 | 17.9% |
| winner | beyond_far_edge | 252 | 18.1% |
| winner | missing | 0 | 0.0% |
| stop_loss | before_near_edge | 2008 | 61.6% |
| stop_loss | inside_band | 603 | 18.5% |
| stop_loss | beyond_far_edge | 648 | 19.9% |
| stop_loss | missing | 0 | 0.0% |

For longs the supporting zone is mapped support, and for shorts it is mapped resistance. Before/inside/beyond describes the stop level relative to that band; the zone map is candle-derived. Changing stops to sit beyond a band has not been tested here.

## Controlling for market conditions

Each diagnostic comparison stays within token, side and entry clock. Exposed and unexposed original executed trades are compared within calendar quarter and volatility tertile; volatility cutoffs are learned from discovery candidate features only. Strata require at least two observations on each side and are weighted by the smaller group. This controls these coarse categories, not all confounding. Regime direction is already fixed by the baseline; continuous regime strength can still differ. No causal effect is claimed.

Ordinary95% calendar-block bootstrap intervals use both one-week and four-week blocks, 500 draws each. They are exploratory and unadjusted for 216 contrast/period rows, earlier searches and possible longer dependence. Sparse samples can produce misleading narrow intervals. No signal filter was implemented and no incremental executable return has been established.

No oscillator contrast has a positive adjusted point estimate with adequate matched counts in BOTH periods. Four-week intervals also fail to show a positive lower bound for any adequately sampled oscillator comparison in either period. This does not establish equivalence or rule out other oscillator definitions.

## Recent-extreme diagnostics: every cell

Each row refers to completed baseline positions with a recent extreme, not a tradable filtered strategy. Net/trade and stopped/closed are descriptive outcomes on those existing entries. Adjusted difference is exposed minus unexposed mean net within common-support strata; it is expressed in percentage points.

### 2022–2024

| Token | Side | Clock | Recent extreme | Stops/closed | Net/trade | Matched exposed/control | Adjusted delta pp | 4-week CI pp | Coverage flag |
|---|---|---|---|---|---|---|---|---|---|
| BTC | S | 5m | Connors | 31/40 | -0.518% | 32/528 | -0.192% | [-0.575%, +0.315%] | adequate |
| BTC | S | 5m | RSI | 18/28 | -0.327% | 19/425 | +0.156% | [-0.472%, +0.841%] | sparse |
| BTC | S | 15m | Connors | 24/37 | +0.024% | 33/341 | +0.138% | [-0.200%, +0.504%] | adequate |
| BTC | S | 15m | RSI | 11/16 | -0.108% | 6/68 | -0.450% | [-1.461%, -0.111%] | sparse |
| BTC | S | 60m | Connors | 11/12 | -0.915% | 9/98 | -1.304% | [-1.624%, -1.123%] | sparse |
| BTC | S | 60m | RSI | 1/3 | +1.131% | 0/0 | — | [—, —] | sparse |
| BTC | L | 5m | Connors | 28/50 | +0.168% | 45/478 | +0.368% | [-0.187%, +0.835%] | adequate |
| BTC | L | 5m | RSI | 21/39 | +0.102% | 30/395 | +0.278% | [-0.180%, +0.835%] | adequate |
| BTC | L | 15m | Connors | 33/44 | -0.351% | 33/328 | -0.245% | [-0.794%, +0.338%] | adequate |
| BTC | L | 15m | RSI | 15/20 | -0.466% | 10/169 | -0.380% | [-1.501%, +1.044%] | sparse |
| BTC | L | 60m | Connors | 10/17 | +0.219% | 8/74 | +0.340% | [-1.243%, +2.329%] | sparse |
| BTC | L | 60m | RSI | 1/1 | -1.218% | 0/0 | — | [—, —] | sparse |
| ETH | S | 5m | Connors | 39/54 | -0.237% | 45/803 | +0.067% | [-0.353%, +0.528%] | adequate |
| ETH | S | 5m | RSI | 20/32 | -0.173% | 21/702 | +0.382% | [-0.406%, +1.402%] | adequate |
| ETH | S | 15m | Connors | 32/40 | -0.506% | 32/493 | -0.273% | [-0.818%, +0.532%] | adequate |
| ETH | S | 15m | RSI | 11/17 | +0.027% | 7/108 | +0.292% | [-1.077%, +1.485%] | sparse |
| ETH | S | 60m | Connors | 13/18 | -0.232% | 10/133 | +0.523% | [-0.927%, +2.005%] | sparse |
| ETH | S | 60m | RSI | 0/2 | +2.289% | 0/0 | — | [—, —] | sparse |
| ETH | L | 5m | Connors | 41/60 | -0.195% | 52/605 | +0.069% | [-0.435%, +0.603%] | adequate |
| ETH | L | 5m | RSI | 26/44 | -0.101% | 35/581 | +0.172% | [-0.292%, +0.655%] | adequate |
| ETH | L | 15m | Connors | 31/39 | -0.502% | 34/451 | -0.390% | [-0.792%, -0.092%] | adequate |
| ETH | L | 15m | RSI | 9/11 | -0.577% | 5/120 | -0.163% | [-1.096%, +1.019%] | sparse |
| ETH | L | 60m | Connors | 11/15 | -0.286% | 8/46 | -0.626% | [-1.418%, +0.263%] | sparse |
| ETH | L | 60m | RSI | 2/2 | -1.213% | 0/0 | — | [—, —] | sparse |
| SOL | S | 5m | Connors | 70/101 | -0.257% | 91/1362 | +0.127% | [-0.120%, +0.332%] | adequate |
| SOL | S | 5m | RSI | 43/62 | -0.446% | 55/1168 | -0.284% | [-0.648%, +0.154%] | adequate |
| SOL | S | 15m | Connors | 47/58 | -0.658% | 54/837 | -0.473% | [-0.758%, -0.168%] | adequate |
| SOL | S | 15m | RSI | 14/20 | -0.256% | 10/351 | -0.651% | [-1.378%, +0.124%] | sparse |
| SOL | S | 60m | Connors | 18/26 | -0.241% | 19/132 | +0.143% | [-0.874%, +1.089%] | sparse |
| SOL | S | 60m | RSI | 2/2 | -1.308% | 0/0 | — | [—, —] | sparse |
| SOL | L | 5m | Connors | 63/95 | -0.186% | 90/1596 | +0.125% | [-0.196%, +0.506%] | adequate |
| SOL | L | 5m | RSI | 40/52 | -0.615% | 43/1177 | -0.425% | [-0.798%, +0.041%] | adequate |
| SOL | L | 15m | Connors | 40/56 | -0.360% | 45/852 | -0.032% | [-0.479%, +0.636%] | adequate |
| SOL | L | 15m | RSI | 8/12 | -0.155% | 2/66 | +0.644% | [-1.122%, +2.366%] | sparse |
| SOL | L | 60m | Connors | 17/20 | -0.786% | 8/100 | -0.815% | [-1.588%, -0.033%] | sparse |
| SOL | L | 60m | RSI | 2/3 | -0.147% | 0/0 | — | [—, —] | sparse |

### 2025

| Token | Side | Clock | Recent extreme | Stops/closed | Net/trade | Matched exposed/control | Adjusted delta pp | 4-week CI pp | Coverage flag |
|---|---|---|---|---|---|---|---|---|---|
| BTC | S | 5m | Connors | 12/16 | -0.506% | 14/163 | -0.216% | [-1.000%, +0.809%] | sparse |
| BTC | S | 5m | RSI | 5/12 | +0.381% | 9/109 | +0.283% | [-0.974%, +1.083%] | sparse |
| BTC | S | 15m | Connors | 8/9 | -0.809% | 7/97 | -0.705% | [-1.323%, +0.520%] | sparse |
| BTC | S | 15m | RSI | 4/5 | -0.508% | 0/0 | — | [—, —] | sparse |
| BTC | S | 60m | Connors | 9/11 | -0.847% | 10/63 | -0.841% | [-1.452%, -0.564%] | sparse |
| BTC | S | 60m | RSI | 2/4 | -0.212% | 2/18 | -0.978% | [-1.372%, -0.006%] | sparse |
| BTC | L | 5m | Connors | 8/15 | +0.231% | 11/77 | +0.404% | [-0.660%, +1.613%] | sparse |
| BTC | L | 5m | RSI | 8/12 | -0.279% | 8/53 | +0.185% | [-0.657%, +1.023%] | sparse |
| BTC | L | 15m | Connors | 6/8 | -0.343% | 4/26 | -1.269% | [-1.866%, -0.659%] | sparse |
| BTC | L | 15m | RSI | 2/3 | -1.073% | 0/0 | — | [—, —] | sparse |
| BTC | L | 60m | Connors | 6/8 | -0.344% | 4/14 | -1.394% | [-3.474%, +0.859%] | sparse |
| BTC | L | 60m | RSI | 0/0 | — | 0/0 | — | [—, —] | sparse |
| ETH | S | 5m | Connors | 23/27 | -0.692% | 25/451 | -0.413% | [-1.040%, +0.346%] | adequate |
| ETH | S | 5m | RSI | 10/17 | +0.235% | 15/326 | +0.135% | [-0.930%, +1.120%] | sparse |
| ETH | S | 15m | Connors | 16/24 | -0.043% | 20/242 | +0.301% | [-0.388%, +0.973%] | adequate |
| ETH | S | 15m | RSI | 3/7 | +0.793% | 6/256 | +1.247% | [-0.028%, +2.576%] | sparse |
| ETH | S | 60m | Connors | 6/11 | +0.382% | 8/56 | +0.689% | [-0.361%, +2.897%] | sparse |
| ETH | S | 60m | RSI | 1/1 | -1.212% | 0/0 | — | [—, —] | sparse |
| ETH | L | 5m | Connors | 12/17 | -0.189% | 13/212 | +0.231% | [+0.036%, +0.419%] | sparse |
| ETH | L | 5m | RSI | 7/10 | -0.369% | 9/163 | -0.592% | [-1.161%, -0.235%] | sparse |
| ETH | L | 15m | Connors | 6/9 | -0.053% | 6/129 | +0.900% | [+0.414%, +2.274%] | sparse |
| ETH | L | 15m | RSI | 1/2 | +0.534% | 0/0 | — | [—, —] | sparse |
| ETH | L | 60m | Connors | 4/6 | -0.047% | 6/59 | -0.177% | [-1.182%, +1.773%] | sparse |
| ETH | L | 60m | RSI | 0/0 | — | 0/0 | — | [—, —] | sparse |
| SOL | S | 5m | Connors | 29/38 | -0.483% | 35/527 | -0.204% | [-0.782%, +0.191%] | adequate |
| SOL | S | 5m | RSI | 16/26 | -0.079% | 23/234 | +0.342% | [-0.474%, +0.936%] | adequate |
| SOL | S | 15m | Connors | 11/14 | -0.562% | 11/200 | -0.063% | [-1.081%, +0.851%] | sparse |
| SOL | S | 15m | RSI | 7/10 | -0.258% | 8/124 | -0.141% | [-1.008%, +0.663%] | sparse |
| SOL | S | 60m | Connors | 5/7 | -0.310% | 2/40 | -1.401% | [-1.912%, -1.117%] | sparse |
| SOL | S | 60m | RSI | 1/1 | -1.313% | 0/0 | — | [—, —] | sparse |
| SOL | L | 5m | Connors | 22/29 | -0.535% | 29/381 | -0.258% | [-0.975%, +0.374%] | adequate |
| SOL | L | 5m | RSI | 8/10 | -0.610% | 8/307 | -0.190% | [-1.249%, +0.571%] | sparse |
| SOL | L | 15m | Connors | 10/17 | +0.126% | 15/213 | +0.282% | [-0.810%, +1.119%] | sparse |
| SOL | L | 15m | RSI | 1/1 | -1.307% | 0/0 | — | [—, —] | sparse |
| SOL | L | 60m | Connors | 4/6 | -0.147% | 4/51 | -0.186% | [-1.325%, +1.158%] | sparse |
| SOL | L | 60m | RSI | 0/0 | — | 0/0 | — | [—, —] | sparse |

## Stop-location associations: every cell

Values are adjusted mean-net differences in percentage points versus other available zone locations. A positive difference can mean smaller losses and does not necessarily mean a profitable group. Counts/coverage/intervals for every row are preserved in contrasts.csv. “Sparse” means fewer than20 observations in either matched arm.

| Token | Side | Clock | Before early | Inside early | Before 2025 | Inside 2025 |
|---|---|---|---|---|---|---|
| BTC | S | 5m | +0.082% | +0.010% | +0.007% | -0.209% |
| BTC | S | 15m | +0.090% | -0.184% | +0.116% | -0.248% |
| BTC | S | 60m | -0.279% | -0.105% | -0.338% | +0.234% |
| BTC | L | 5m | +0.162% | -0.022% | +0.094% | +0.380% (sparse) |
| BTC | L | 15m | +0.069% | -0.172% | -0.037% | -0.182% (sparse) |
| BTC | L | 60m | -0.107% | +0.630% | +0.060% (sparse) | +0.328% (sparse) |
| ETH | S | 5m | -0.048% | -0.088% | +0.261% | -0.091% |
| ETH | S | 15m | -0.084% | +0.004% | +0.140% | +0.005% |
| ETH | S | 60m | -0.239% | -0.186% | +0.266% | +0.027% |
| ETH | L | 5m | +0.127% | -0.261% | +0.164% | +0.103% |
| ETH | L | 15m | +0.182% | -0.119% | -0.203% | +0.269% |
| ETH | L | 60m | -0.119% | +0.259% | -0.689% | +0.596% (sparse) |
| SOL | S | 5m | -0.094% | +0.060% | -0.083% | +0.070% |
| SOL | S | 15m | -0.102% | -0.010% | +0.179% | -0.123% |
| SOL | S | 60m | +0.195% | -0.190% | -0.134% | +0.214% |
| SOL | L | 5m | -0.004% | +0.048% | +0.117% | -0.113% |
| SOL | L | 15m | -0.020% | +0.132% | +0.410% | -0.373% |
| SOL | L | 60m | -0.111% | +0.096% | +0.301% | -0.279% |

Six zone-location comparisons have positive adjusted point estimates and adequate counts in both periods, but none has positive lower bounds under both block lengths in both periods. These weak exploratory associations should not become a filter from this report.

## Decisions and next work

- Keep the unchanged baseline. Do not add a contemporaneous extreme gate: it has zero coverage in this entry family.
- Do not adopt the previous-three-bar extreme condition from these sparse/inconsistent diagnostics. Existing signals and winners must stay visible.
- Proceed to the already planned adaptive-stop comparison as a separate intervention. The planned capped ATR policy still requires its own frozen execution protocol and unchanged controls.
- Keep RSI-only and Connors-only entry work separate. A later setup-memory or momentum-state hypothesis must be preregistered as a new attempt; do not claim this analysis already tested a tradable oscillator entry.
- Keep the minimum economically viable zone-target experiment queued separately. No stop, indicator and exit changes should be combined at this stage.

## Evidence, checks and limits

Protocol frozen locally at b3243df, implementation at8595fc5. Four tests pass (RSI seed/recursion/flat values, streak/rank ties, prefix/closed-bar causality, known matched contrast). Full feature prefixes also match for all nine token/clock series. Six input hashes and archived raw-path/annotation bytes match. All 36 baseline rows reconcile; maximum mean error 9.84e-17. All opportunity keys are unique and feature/zone timestamps precede or equal entry. No indicator missingness remains at baseline signals.

Local evidence includes the full annotated signal tables, outcome and bin summaries, every standardized contrast with two interval choices, discovery-only volatility cutoffs, coverage, reconciliation, source and manifest. Eventual trade outcomes are diagnostic columns, not available-at-entry features. Preserve that distinction when training or reusing the dataset.

Data overlap across clocks and signals; matching is coarse; uncertainty is unadjusted; all history through2025 has been reused. No edge certification, untouched evaluation, portfolio inference, new trade execution or live change follows.
