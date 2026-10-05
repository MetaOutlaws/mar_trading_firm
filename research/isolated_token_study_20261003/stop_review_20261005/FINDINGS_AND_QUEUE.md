# Stop-width review and research queue

5 October 2026. This is a review of completed evidence and a queue update. No new stop-width backtest or cost-aware exit backtest has been run.

## What was actually tested

No controlled fixed 1%, 2%, 3%, 4%, 5% stop grid has been completed. The diagnostic optimization tested fixed 1%, 1.5× hourly ATR14 and 2.5× hourly ATR14; ATR stops were clipped to 0.5–3%. ATR is measured from completed hourly candles at entry. These variable stops are not the same as fixed 2% or fixed 3%; neither 4% nor 5% was part of that study. ATR stops could also be narrower than 1% in low volatility.

The later daily/zone-entry/zone-exit controlled studies deliberately retained 1% to isolate their own interventions. That was an experimental control, not evidence that 1% is optimal.

## Selected ATR-stop outcomes

Below compares the same selected entry logic with fixed 1% against the optimized 2.5× ATR stop. Median stop describes executed optimized positions, not a fixed setting. Stop-out rates use completed positions only. Means include any partition-boundary mark. ETH 2024 has one such mark in addition to its 183 completed positions.

| Token | Year | Side | Clock | ATR stop median | 1% stopped / closed | ATR stopped / closed | 1% mean net | ATR mean net | Other changes |
|---|---|---|---|---|---|---|---|---|---|
| BTC | 2024 | Long | 15m | 1.93% | 117/194 (60.3%) | 44/125 (35.2%) | -0.078% | +0.148% | Stop only |
| BTC | 2025 | Long | 15m | 1.55% | 59/99 (59.6%) | 38/77 (49.4%) | -0.302% | -0.453% | Stop only |
| ETH | 2024 | Short | 5m | 2.59% | 224/337 (66.5%) | 79/183 (43.2%) | -0.213% | -0.341% | Stop only |
| ETH | 2025 | Short | 5m | 3.00% | 376/548 (68.6%) | 125/221 (56.6%) | -0.284% | -0.457% | Stop + target, policy |
| SOL | 2024 | Short | 15m | 3.00% | 163/248 (65.7%) | 57/155 (36.8%) | -0.224% | -0.197% | Stop only |
| SOL | 2025 | Short | 15m | 3.00% | 191/283 (67.5%) | 70/170 (41.2%) | -0.222% | -0.195% | Stop only |

All six optimized outcomes failed the full research screen. Five comparisons change only the stop rule relative to their selected-entry control; ETH 2025 also changes the target from 2.5% to 3% and removes the regime exit. These are selected configurations with reused historical evaluation periods, not a complete fixed-width sweep or untouched validation. Wider stops change subsequent capacity and trade count.

Fewer stops did not consistently improve net returns: BTC improved in 2024 and worsened in 2025; ETH deteriorated; SOL losses narrowed without becoming profitable. A larger average loss can offset a lower stop-out rate. Variable notional at equal risk must also be assessed, as in the earlier R-based report.

## Recovery evidence already available

The earlier stop-recovery audit pools overlapping configurations, so counts below are configuration observations, not independent trades. The seven-day horizon is diagnostic only; no position holding cap. Target means each stopped configuration’s original target, not a universal 2.5% target.

| Token | Eligible stop observations | Target within 7 days | Target before 2% adverse move | Median 1% stop / hourly ATR |
|---|---|---|---|---|
| BTCUSDT | 6002 | 58.4% | 20.6% | 1.36 |
| ETHUSDT | 12185 | 78.3% | 23.2% | 0.81 |
| SOLUSDT | 14775 | 78.1% | 24.4% | 0.75 |

This supports investigating volatility and adverse excursion. It does not establish profitability with a 2% stop: it omits the full changed strategy path and its executable scheduling. Entry costs, larger losing tails, funding, regime exits and unfilled/censored cases still matter.

## Complete stop-out reporting for the latest controlled study

Each row separates token, side, clock, entry method and historical period. Original exit and zone exit both use a 1% initial stop. Stops/closed and stop percentage count stop-triggered exits; other completed outcomes are target or regime exits. Boundary valuations remain separate. These are independent research configurations, not a combined portfolio.

### 2022–2024

| Entry | Token | Side | Clock | Original stopped / closed | Target / regime / boundary | Zone stopped / closed | Target / regime / boundary |
|---|---|---|---|---|---|---|---|
| Immediate | BTC | Short | 5m | 541/799 (67.7%) | 206/52/1 | 573/1588 (36.1%) | 966/49/1 |
| Immediate | BTC | Short | 15m | 370/541 (68.4%) | 151/20/1 | 333/988 (33.7%) | 638/17/1 |
| Immediate | BTC | Short | 60m | 183/266 (68.8%) | 75/8/1 | 119/404 (29.5%) | 282/3/1 |
| Immediate | BTC | Long | 5m | 491/768 (63.9%) | 215/62/0 | 552/1628 (33.9%) | 1015/61/0 |
| Immediate | BTC | Long | 15m | 387/586 (66.0%) | 168/31/0 | 358/1107 (32.3%) | 720/29/0 |
| Immediate | BTC | Long | 60m | 197/301 (65.4%) | 99/5/0 | 146/454 (32.2%) | 305/3/0 |
| Immediate | ETH | Short | 5m | 782/1164 (67.2%) | 316/66/1 | 789/2089 (37.8%) | 1236/64/1 |
| Immediate | ETH | Short | 15m | 500/756 (66.1%) | 213/43/0 | 447/1271 (35.2%) | 784/40/0 |
| Immediate | ETH | Short | 60m | 242/342 (70.8%) | 91/9/1 | 157/462 (34.0%) | 300/5/0 |
| Immediate | ETH | Long | 5m | 676/984 (68.7%) | 251/57/0 | 690/1686 (40.9%) | 941/55/0 |
| Immediate | ETH | Long | 15m | 502/713 (70.4%) | 183/28/0 | 451/1122 (40.2%) | 645/26/0 |
| Immediate | ETH | Long | 60m | 226/322 (70.2%) | 92/4/0 | 157/415 (37.8%) | 255/3/0 |
| Immediate | SOL | Short | 5m | 1312/1894 (69.3%) | 534/48/0 | 1294/2765 (46.8%) | 1424/47/0 |
| Immediate | SOL | Short | 15m | 775/1117 (69.4%) | 327/15/0 | 672/1495 (44.9%) | 810/13/0 |
| Immediate | SOL | Short | 60m | 308/431 (71.5%) | 122/1/0 | 222/480 (46.2%) | 257/1/0 |
| Immediate | SOL | Long | 5m | 1349/1937 (69.6%) | 547/41/0 | 1342/2605 (51.5%) | 1225/38/0 |
| Immediate | SOL | Long | 15m | 824/1168 (70.5%) | 324/20/0 | 714/1438 (49.7%) | 708/16/0 |
| Immediate | SOL | Long | 60m | 323/452 (71.5%) | 126/3/0 | 240/484 (49.6%) | 242/2/0 |
| Fixed delay | BTC | Short | 5m | 501/738 (67.9%) | 194/43/1 | 526/1360 (38.7%) | 792/42/1 |
| Fixed delay | BTC | Short | 15m | 315/467 (67.5%) | 131/21/1 | 284/750 (37.9%) | 445/21/1 |
| Fixed delay | BTC | Short | 60m | 139/202 (68.8%) | 52/11/0 | 113/276 (40.9%) | 154/9/0 |
| Fixed delay | BTC | Long | 5m | 463/725 (63.9%) | 205/57/0 | 517/1460 (35.4%) | 886/57/0 |
| Fixed delay | BTC | Long | 15m | 330/502 (65.7%) | 146/26/0 | 299/854 (35.0%) | 532/23/0 |
| Fixed delay | BTC | Long | 60m | 161/242 (66.5%) | 77/4/0 | 115/324 (35.5%) | 206/3/0 |
| Fixed delay | ETH | Short | 5m | 705/1053 (67.0%) | 289/59/1 | 715/1805 (39.6%) | 1033/57/0 |
| Fixed delay | ETH | Short | 15m | 438/634 (69.1%) | 163/33/1 | 377/954 (39.5%) | 546/31/0 |
| Fixed delay | ETH | Short | 60m | 181/258 (70.2%) | 70/7/0 | 137/328 (41.8%) | 181/10/0 |
| Fixed delay | ETH | Long | 5m | 632/903 (70.0%) | 228/43/0 | 642/1439 (44.6%) | 754/43/0 |
| Fixed delay | ETH | Long | 15m | 440/627 (70.2%) | 160/27/0 | 384/858 (44.8%) | 449/25/0 |
| Fixed delay | ETH | Long | 60m | 174/244 (71.3%) | 63/7/0 | 122/310 (39.4%) | 181/7/0 |
| Fixed delay | SOL | Short | 5m | 1134/1664 (68.1%) | 491/39/0 | 1104/2269 (48.7%) | 1127/38/0 |
| Fixed delay | SOL | Short | 15m | 597/884 (67.5%) | 271/16/0 | 518/1118 (46.3%) | 585/15/0 |
| Fixed delay | SOL | Short | 60m | 203/302 (67.2%) | 95/4/0 | 168/344 (48.8%) | 171/5/0 |
| Fixed delay | SOL | Long | 5m | 1197/1710 (70.0%) | 479/34/0 | 1159/2194 (52.8%) | 1002/33/0 |
| Fixed delay | SOL | Long | 15m | 641/919 (69.7%) | 258/20/0 | 562/1080 (52.0%) | 500/18/0 |
| Fixed delay | SOL | Long | 60m | 199/302 (65.9%) | 99/4/0 | 170/328 (51.8%) | 152/6/0 |
| Zone timing | BTC | Short | 5m | 510/748 (68.2%) | 194/44/1 | 530/1368 (38.7%) | 795/43/1 |
| Zone timing | BTC | Short | 15m | 323/476 (67.9%) | 132/21/1 | 289/772 (37.4%) | 462/21/1 |
| Zone timing | BTC | Short | 60m | 148/210 (70.5%) | 51/11/0 | 118/293 (40.3%) | 166/9/0 |
| Zone timing | BTC | Long | 5m | 464/725 (64.0%) | 205/56/0 | 520/1465 (35.5%) | 889/56/0 |
| Zone timing | BTC | Long | 15m | 333/505 (65.9%) | 146/26/0 | 301/866 (34.8%) | 541/24/0 |
| Zone timing | BTC | Long | 60m | 168/248 (67.7%) | 76/4/0 | 113/341 (33.1%) | 225/3/0 |
| Zone timing | ETH | Short | 5m | 709/1058 (67.0%) | 290/59/1 | 720/1811 (39.8%) | 1034/57/0 |
| Zone timing | ETH | Short | 15m | 449/646 (69.5%) | 163/34/1 | 392/982 (39.9%) | 558/32/0 |
| Zone timing | ETH | Short | 60m | 192/267 (71.9%) | 69/6/0 | 139/349 (39.8%) | 202/8/0 |
| Zone timing | ETH | Long | 5m | 645/922 (70.0%) | 231/46/0 | 655/1457 (45.0%) | 757/45/0 |
| Zone timing | ETH | Long | 15m | 450/635 (70.9%) | 160/25/0 | 398/881 (45.2%) | 460/23/0 |
| Zone timing | ETH | Long | 60m | 186/251 (74.1%) | 60/5/0 | 133/319 (41.7%) | 181/5/0 |
| Zone timing | SOL | Short | 5m | 1146/1672 (68.5%) | 487/39/0 | 1126/2291 (49.1%) | 1126/39/0 |
| Zone timing | SOL | Short | 15m | 603/892 (67.6%) | 275/14/0 | 527/1132 (46.6%) | 592/13/0 |
| Zone timing | SOL | Short | 60m | 213/313 (68.1%) | 97/3/0 | 176/357 (49.3%) | 179/2/0 |
| Zone timing | SOL | Long | 5m | 1193/1706 (69.9%) | 480/33/0 | 1160/2194 (52.9%) | 1002/32/0 |
| Zone timing | SOL | Long | 15m | 644/929 (69.3%) | 263/22/0 | 563/1092 (51.6%) | 509/20/0 |
| Zone timing | SOL | Long | 60m | 205/313 (65.5%) | 103/5/0 | 161/342 (47.1%) | 174/7/0 |

### 2025

| Entry | Token | Side | Clock | Original stopped / closed | Target / regime / boundary | Zone stopped / closed | Target / regime / boundary |
|---|---|---|---|---|---|---|---|
| Immediate | BTC | Short | 5m | 185/279 (66.3%) | 71/23/0 | 199/531 (37.5%) | 309/23/0 |
| Immediate | BTC | Short | 15m | 119/186 (64.0%) | 55/12/0 | 115/350 (32.9%) | 224/11/0 |
| Immediate | BTC | Short | 60m | 70/101 (69.3%) | 26/5/0 | 48/140 (34.3%) | 88/4/0 |
| Immediate | BTC | Long | 5m | 91/147 (61.9%) | 41/15/0 | 104/422 (24.6%) | 304/14/0 |
| Immediate | BTC | Long | 15m | 62/106 (58.5%) | 36/8/0 | 69/267 (25.8%) | 191/7/0 |
| Immediate | BTC | Long | 60m | 42/69 (60.9%) | 24/3/0 | 40/131 (30.5%) | 89/2/0 |
| Immediate | ETH | Short | 5m | 412/594 (69.4%) | 151/31/0 | 394/884 (44.6%) | 460/30/0 |
| Immediate | ETH | Short | 15m | 240/359 (66.9%) | 105/14/0 | 203/487 (41.7%) | 272/12/0 |
| Immediate | ETH | Short | 60m | 128/169 (75.7%) | 39/2/0 | 86/187 (46.0%) | 99/2/0 |
| Immediate | ETH | Long | 5m | 212/319 (66.5%) | 92/15/0 | 218/502 (43.4%) | 271/13/0 |
| Immediate | ETH | Long | 15m | 152/220 (69.1%) | 60/8/0 | 142/340 (41.8%) | 191/7/0 |
| Immediate | ETH | Long | 60m | 62/93 (66.7%) | 29/2/0 | 42/111 (37.8%) | 68/1/0 |
| Immediate | SOL | Short | 5m | 491/711 (69.1%) | 198/22/0 | 472/1023 (46.1%) | 529/22/0 |
| Immediate | SOL | Short | 15m | 304/434 (70.0%) | 124/6/0 | 264/586 (45.1%) | 315/7/0 |
| Immediate | SOL | Short | 60m | 129/178 (72.5%) | 49/0/0 | 95/201 (47.3%) | 106/0/0 |
| Immediate | SOL | Long | 5m | 303/444 (68.2%) | 122/19/0 | 312/663 (47.1%) | 332/19/0 |
| Immediate | SOL | Long | 15m | 179/276 (64.9%) | 86/11/0 | 174/383 (45.4%) | 198/11/0 |
| Immediate | SOL | Long | 60m | 78/115 (67.8%) | 37/0/0 | 58/131 (44.3%) | 73/0/0 |
| Fixed delay | BTC | Short | 5m | 164/252 (65.1%) | 65/23/0 | 173/442 (39.1%) | 245/24/0 |
| Fixed delay | BTC | Short | 15m | 114/170 (67.1%) | 44/12/0 | 100/269 (37.2%) | 155/14/0 |
| Fixed delay | BTC | Short | 60m | 50/72 (69.4%) | 17/5/0 | 38/98 (38.8%) | 56/4/0 |
| Fixed delay | BTC | Long | 5m | 82/138 (59.4%) | 41/15/0 | 103/373 (27.6%) | 255/15/0 |
| Fixed delay | BTC | Long | 15m | 59/98 (60.2%) | 31/8/0 | 60/227 (26.4%) | 160/7/0 |
| Fixed delay | BTC | Long | 60m | 27/50 (54.0%) | 20/3/0 | 21/91 (23.1%) | 65/5/0 |
| Fixed delay | ETH | Short | 5m | 353/517 (68.3%) | 135/29/0 | 345/756 (45.6%) | 383/28/0 |
| Fixed delay | ETH | Short | 15m | 210/307 (68.4%) | 88/9/0 | 173/377 (45.9%) | 195/9/0 |
| Fixed delay | ETH | Short | 60m | 82/116 (70.7%) | 30/4/0 | 66/128 (51.6%) | 58/4/0 |
| Fixed delay | ETH | Long | 5m | 199/294 (67.7%) | 80/15/0 | 199/444 (44.8%) | 232/13/0 |
| Fixed delay | ETH | Long | 15m | 119/180 (66.1%) | 56/5/0 | 95/243 (39.1%) | 144/4/0 |
| Fixed delay | ETH | Long | 60m | 39/62 (62.9%) | 22/1/0 | 27/71 (38.0%) | 44/0/0 |
| Fixed delay | SOL | Short | 5m | 441/631 (69.9%) | 168/22/0 | 423/852 (49.6%) | 407/22/0 |
| Fixed delay | SOL | Short | 15m | 233/347 (67.1%) | 103/11/0 | 206/440 (46.8%) | 224/10/0 |
| Fixed delay | SOL | Short | 60m | 99/132 (75.0%) | 32/1/0 | 72/144 (50.0%) | 71/1/0 |
| Fixed delay | SOL | Long | 5m | 267/398 (67.1%) | 112/19/0 | 260/556 (46.8%) | 277/19/0 |
| Fixed delay | SOL | Long | 15m | 152/224 (67.9%) | 69/3/0 | 137/282 (48.6%) | 142/3/0 |
| Fixed delay | SOL | Long | 60m | 59/82 (72.0%) | 21/2/0 | 47/94 (50.0%) | 46/1/0 |
| Zone timing | BTC | Short | 5m | 161/250 (64.4%) | 66/23/0 | 173/441 (39.2%) | 244/24/0 |
| Zone timing | BTC | Short | 15m | 116/174 (66.7%) | 45/13/0 | 103/279 (36.9%) | 162/14/0 |
| Zone timing | BTC | Short | 60m | 50/74 (67.6%) | 18/6/0 | 38/101 (37.6%) | 57/6/0 |
| Zone timing | BTC | Long | 5m | 81/137 (59.1%) | 41/15/0 | 104/377 (27.6%) | 258/15/0 |
| Zone timing | BTC | Long | 15m | 60/100 (60.0%) | 32/8/0 | 61/229 (26.6%) | 162/6/0 |
| Zone timing | BTC | Long | 60m | 24/48 (50.0%) | 19/5/0 | 23/94 (24.5%) | 67/4/0 |
| Zone timing | ETH | Short | 5m | 355/521 (68.1%) | 137/29/0 | 344/759 (45.3%) | 387/28/0 |
| Zone timing | ETH | Short | 15m | 218/316 (69.0%) | 88/10/0 | 183/394 (46.4%) | 201/10/0 |
| Zone timing | ETH | Short | 60m | 85/121 (70.2%) | 32/4/0 | 66/136 (48.5%) | 66/4/0 |
| Zone timing | ETH | Long | 5m | 199/295 (67.5%) | 81/15/0 | 198/445 (44.5%) | 234/13/0 |
| Zone timing | ETH | Long | 15m | 119/180 (66.1%) | 55/6/0 | 97/247 (39.3%) | 146/4/0 |
| Zone timing | ETH | Long | 60m | 43/67 (64.2%) | 23/1/0 | 30/76 (39.5%) | 46/0/0 |
| Zone timing | SOL | Short | 5m | 444/634 (70.0%) | 168/22/0 | 422/853 (49.5%) | 409/22/0 |
| Zone timing | SOL | Short | 15m | 235/352 (66.8%) | 106/11/0 | 211/448 (47.1%) | 227/10/0 |
| Zone timing | SOL | Short | 60m | 101/135 (74.8%) | 32/2/0 | 75/149 (50.3%) | 72/2/0 |
| Zone timing | SOL | Long | 5m | 270/400 (67.5%) | 112/18/0 | 264/560 (47.1%) | 279/17/0 |
| Zone timing | SOL | Long | 15m | 158/229 (69.0%) | 68/3/0 | 143/288 (49.7%) | 142/3/0 |
| Zone timing | SOL | Long | 60m | 62/85 (72.9%) | 22/1/0 | 52/99 (52.5%) | 46/1/0 |

## Reporting standard from this point

Every comparison must show completed trades, stop exits, stop-out percentage, target exits, regime/other exits and boundary marks alongside net expectancy, PF, win rate, average win/loss, drawdown, holding time, funding, and both fixed-notional and equal-initial-risk results. Separate token, direction, timeframe, entry method, year and cost case. Stop-out counts alone cannot establish an edge.

For stopped paths, preserve entry-time regime, known support/resistance location, distance beyond zone edge, ATR-normalized stop, pre-stop favorable excursion, worst adverse excursion, and first-passage order to recovery/target versus each wider stop. Include winners and non-stopped trades as controls, not just recovered losers. Exclude future-defined bottoms from entry features; flag same-minute ambiguity, censoring and overlapping signals. Choose hypotheses on discovery data before later evaluation.

## Research queue

**Recommended next: controlled stop-width study — queued, not run.** Compare fixed 1%, 2%, 3%, 4%, 5% with immediate baseline entry first: 18 cells × 5 widths = 90 configurations including the reference. Keep EMA/regime, 2.5% target, regime exit, costs and zone mapping fixed. No zone target cap, new entry filter or holding cap. Preserve all stop widths; do not shortlist away a side or timeframe. Produce independently scheduled strategy outcomes plus identical-entry path comparisons. Use 2022–2024 and 2025 as exploratory periods; keep 2026 unscored. Report per-trade notional and R (return / initial stop), not an assumed leveraged account return. A 5% stop against a 2.5% target has a different reward/risk balance that must remain visible. Follow with other entry methods only under the same frozen stop protocol, not a changed exit.

**Confirmed queued: minimum economically viable zone-target distance — not run.** Add one predeclared cost-aware minimum to the existing zone target cap; fall back to the original 2.5% target when too close. Keep all other elements fixed. Exact minimum and whether to use 1% reference or a subsequently justified stop must be frozen before outcomes; do not simultaneously change stop and zone-target rule. Modeled fees/slippage are known at entry; future realized funding cannot be used to choose the target. If a different stop is adopted first, rerun its unchanged-exit control and the unmodified zone cap before measuring the incremental cost-floor effect.

The queue is a documented research backlog, not a scheduled/background job. No worker or live changes. Existing GitHub scope remains written findings and aggregate report tables; detailed ledgers/scripts remain local.
