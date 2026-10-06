# Fixed-stop comparison: completed findings

5 October 2026. Immediate baseline entries; fixed 1%, 2%, 3%, 4%, 5% initial stops. **Wider stops improve some BTC-long results, but no configuration passes the full exploratory screen.** The cost-aware zone-target study remains queued and was not included.

## Scope and result

90 configurations: 3 tokens × 2 directions × 3 entry clocks × 5 stop widths. All entry methods here are immediate baseline entries. Target remains 2.5%; regime exit and execution costs are unchanged. No holding cap or 2026 scoring. The two historical periods have been reused, so this is exploratory evidence, not untouched validation. All 720 aggregate rows include two cost scenarios and two views; these are not 720 independent hypotheses.

Four BTC-long settings have positive mean net returns in both complete periods. None meets all trade-count, profit-factor and cost-stress criteria. Wider stops should not be dismissed as uniformly unhelpful, but a lower stop-out rate does not establish an edge.

## Summary across the 18 research groups

Stop counts below pool separate token/side/timeframe configurations and can overlap in market exposure. They are not a portfolio or independent events. Each width is rescheduled chronologically, so trade counts differ.

| Stop | 2025 closed | 2025 stopped | Stopped % | Positive 2022–24 /18 | Positive 2025 /18 | Full passes /18 |
|---|---|---|---|---|---|---|
| 1% | 4800 | 3259 | 67.9% | 0 | 2 | 0 |
| 2% | 3193 | 1621 | 50.8% | 0 | 2 | 0 |
| 3% | 2468 | 924 | 37.4% | 0 | 2 | 0 |
| 4% | 2078 | 567 | 27.3% | 2 | 2 | 0 |
| 5% | 1862 | 388 | 20.8% | 3 | 4 | 0 |

The screen requires at least 50 completed trades per period, positive means and PF ≥1.15 in both base-cost periods, and positive means with doubled slippage in both periods. This is an exploratory screen, not production certification.

## Positive in both periods: why these still fail

| Token | Entry | Stop | 2022–24 net | 2025 net | PF early/later | Closed early/later | Stress net early/later |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 5m long | 5% | +0.088% | +0.140% | 1.071/1.119 | 266/55 | -0.012% / +0.039% |
| BTCUSDT | 15m long | 5% | +0.042% | +0.002% | 1.033/1.001 | 221/47 | -0.058% / -0.098% |
| BTCUSDT | 60m long | 4% | +0.024% | +0.206% | 1.018/1.194 | 156/41 | -0.076% / +0.106% |
| BTCUSDT | 60m long | 5% | +0.011% | +0.200% | 1.008/1.188 | 153/41 | -0.089% / +0.100% |

## BTC 1-hour long: complete stop comparison

This previously discussed example is shown for continuity, not selected as a deployable winner. Net returns are per trade notional after costs. R rescales return by the initial stop distance, holding initial modeled price risk constant; it is not account return.

| Stop | Closed | Stopped | Stop % | 2025 net/trade | Mean R | PF | Win % | MTM DD R |
|---|---|---|---|---|---|---|---|---|
| 1% | 69 | 42 | 60.9% | +0.030% | +0.0300 | 1.040 | 34.8% | 12.26 |
| 2% | 52 | 19 | 36.5% | +0.043% | +0.0213 | 1.042 | 46.2% | 6.27 |
| 3% | 46 | 11 | 23.9% | -0.061% | -0.0202 | 0.949 | 50.0% | 4.58 |
| 4% | 41 | 3 | 7.3% | +0.206% | +0.0515 | 1.194 | 56.1% | 3.07 |
| 5% | 41 | 1 | 2.4% | +0.200% | +0.0401 | 1.188 | 56.1% | 2.58 |

## All cells: net return and stop counts

Every cell below is **mean net return; stop exits / completed positions**. Means include cost-inclusive boundary marks; denominators exclude boundary marks. Stops, targets and regime exits sum to completed positions. Full annual/cost/risk metrics are retained locally.

### 2022–2024

| Token | Side | Clock | 1% | 2% | 3% | 4% | 5% |
|---|---|---|---|---|---|---|---|
| BTC | Short | 5m | -0.240%; 541/799 | -0.297%; 253/506 | -0.305%; 142/381 | -0.252%; 87/321 | -0.272%; 64/287 |
| BTC | Short | 15m | -0.193%; 370/541 | -0.329%; 193/374 | -0.383%; 117/299 | -0.394%; 75/255 | -0.378%; 50/226 |
| BTC | Short | 60m | -0.192%; 183/266 | -0.289%; 102/194 | -0.348%; 62/165 | -0.425%; 38/142 | -0.385%; 28/134 |
| BTC | Long | 5m | -0.160%; 491/768 | -0.113%; 200/463 | -0.104%; 110/363 | -0.013%; 61/303 | +0.088%; 30/266 |
| BTC | Long | 15m | -0.173%; 387/586 | -0.126%; 159/357 | -0.100%; 87/284 | +0.034%; 42/232 | +0.042%; 25/221 |
| BTC | Long | 60m | -0.069%; 197/301 | -0.027%; 99/208 | -0.021%; 54/171 | +0.024%; 30/156 | +0.011%; 15/153 |
| ETH | Short | 5m | -0.199%; 782/1164 | -0.240%; 368/735 | -0.231%; 207/561 | -0.239%; 139/476 | -0.319%; 103/430 |
| ETH | Short | 15m | -0.168%; 500/756 | -0.196%; 257/519 | -0.256%; 158/420 | -0.311%; 113/376 | -0.324%; 78/337 |
| ETH | Short | 60m | -0.255%; 242/342 | -0.363%; 140/256 | -0.408%; 87/215 | -0.348%; 55/194 | -0.396%; 40/178 |
| ETH | Long | 5m | -0.268%; 676/984 | -0.262%; 292/590 | -0.279%; 160/441 | -0.179%; 101/368 | -0.219%; 59/307 |
| ETH | Long | 15m | -0.288%; 502/713 | -0.392%; 244/459 | -0.368%; 139/359 | -0.336%; 88/295 | -0.342%; 54/266 |
| ETH | Long | 60m | -0.213%; 226/322 | -0.335%; 129/235 | -0.483%; 88/200 | -0.473%; 52/171 | -0.556%; 37/159 |
| SOL | Short | 5m | -0.301%; 1312/1894 | -0.330%; 645/1214 | -0.321%; 388/936 | -0.327%; 269/794 | -0.391%; 204/698 |
| SOL | Short | 15m | -0.277%; 775/1117 | -0.271%; 406/774 | -0.310%; 263/624 | -0.339%; 191/546 | -0.354%; 137/488 |
| SOL | Short | 60m | -0.318%; 308/431 | -0.385%; 192/340 | -0.412%; 126/283 | -0.419%; 93/254 | -0.441%; 67/235 |
| SOL | Long | 5m | -0.303%; 1349/1937 | -0.320%; 646/1210 | -0.337%; 394/930 | -0.308%; 253/745 | -0.277%; 173/635 |
| SOL | Long | 15m | -0.325%; 824/1168 | -0.342%; 421/780 | -0.413%; 283/642 | -0.357%; 181/527 | -0.310%; 129/472 |
| SOL | Long | 60m | -0.336%; 323/452 | -0.377%; 193/348 | -0.407%; 129/286 | -0.339%; 89/253 | -0.270%; 63/229 |

### 2025

| Token | Side | Clock | 1% | 2% | 3% | 4% | 5% |
|---|---|---|---|---|---|---|---|
| BTC | Short | 5m | -0.230%; 185/279 | -0.306%; 86/183 | -0.295%; 46/138 | -0.293%; 21/107 | -0.325%; 13/96 |
| BTC | Short | 15m | -0.112%; 119/186 | -0.226%; 67/138 | -0.240%; 34/110 | -0.196%; 17/89 | -0.244%; 11/85 |
| BTC | Short | 60m | -0.274%; 70/101 | -0.420%; 43/78 | -0.200%; 17/63 | -0.353%; 11/61 | -0.347%; 5/58 |
| BTC | Long | 5m | -0.158%; 91/147 | -0.081%; 37/95 | -0.056%; 20/74 | -0.036%; 10/63 | +0.140%; 4/55 |
| BTC | Long | 15m | +0.016%; 62/106 | +0.125%; 25/70 | +0.069%; 14/57 | -0.045%; 5/49 | +0.002%; 3/47 |
| BTC | Long | 60m | +0.030%; 42/69 | +0.043%; 19/52 | -0.061%; 11/46 | +0.206%; 3/41 | +0.200%; 1/41 |
| ETH | Short | 5m | -0.267%; 412/594 | -0.282%; 178/349 | -0.276%; 107/267 | -0.259%; 65/218 | -0.286%; 45/194 |
| ETH | Short | 15m | -0.148%; 240/359 | -0.318%; 137/257 | -0.294%; 82/203 | -0.326%; 54/172 | -0.319%; 35/154 |
| ETH | Short | 60m | -0.393%; 128/169 | -0.347%; 71/127 | -0.379%; 44/108 | -0.430%; 31/95 | -0.302%; 19/85 |
| ETH | Long | 5m | -0.143%; 212/319 | -0.090%; 92/192 | +0.029%; 49/143 | +0.040%; 29/119 | +0.001%; 19/104 |
| ETH | Long | 15m | -0.221%; 152/220 | -0.337%; 79/146 | -0.342%; 45/112 | -0.292%; 25/94 | -0.214%; 16/84 |
| ETH | Long | 60m | -0.105%; 62/93 | -0.199%; 36/69 | -0.249%; 22/57 | -0.256%; 13/53 | -0.317%; 8/50 |
| SOL | Short | 5m | -0.302%; 491/711 | -0.332%; 227/435 | -0.319%; 121/307 | -0.339%; 81/257 | -0.360%; 57/218 |
| SOL | Short | 15m | -0.298%; 304/434 | -0.345%; 161/297 | -0.384%; 97/232 | -0.311%; 63/197 | -0.433%; 48/174 |
| SOL | Short | 60m | -0.348%; 129/178 | -0.501%; 84/142 | -0.547%; 52/114 | -0.611%; 38/102 | -0.604%; 28/94 |
| SOL | Long | 5m | -0.304%; 303/444 | -0.267%; 136/274 | -0.225%; 76/203 | -0.148%; 45/166 | -0.224%; 35/146 |
| SOL | Long | 15m | -0.189%; 179/276 | -0.180%; 96/197 | -0.120%; 57/156 | -0.024%; 32/121 | -0.181%; 25/110 |
| SOL | Long | 60m | -0.187%; 78/115 | -0.262%; 47/92 | -0.224%; 30/78 | -0.368%; 24/74 | -0.378%; 16/67 |

## What happened to the ORIGINAL 1% stop-outs?

Matched-entry diagnosis retains exactly the entries executed by the 1% baseline, then changes only the stop. The target and regime exit still operate. Unlike independently rescheduled strategies, this diagnostic does not replace the entry set when positions last longer. Counts pool overlapping configurations; do not treat them as a single tradable portfolio.

| Stop | Same original stop-outs | Net-positive outcomes | Target exits | Stop exits | Regime exits | Mean net outcome |
|---|---|---|---|---|---|---|
| 1% | 3259 | 0 (0.0%) | 0 | 3259 | 0 | -1.257% |
| 2% | 3259 | 596 (18.3%) | 590 | 2480 | 189 | -1.378% |
| 3% | 3259 | 1018 (31.2%) | 1009 | 1795 | 455 | -1.333% |
| 4% | 3259 | 1261 (38.7%) | 1252 | 1302 | 705 | -1.291% |
| 5% | 3259 | 1392 (42.7%) | 1383 | 990 | 886 | -1.312% |

At 5%, 42.7% of the original 2025 stop-outs become net-positive outcomes. Nevertheless their pooled mean net outcome worsens from −1.257% to −1.312%. Larger residual losses and regime exits offset the recovered trades. This does not mean every cell worsens; the cell-specific tables and matched summary preserve the differences.

## Useful diagnostic leads, not entry rules

The following concerns the 1% baseline in 2025. Excursions exclude the exit minute because intraminute high/low order is unknown. These are retrospective descriptions, not information available at entry.

- 951/3,259 stopped configuration-trades (29.2%) had already moved at least 1% favorably before the exit minute. This is a specific lead for later profit-protection research, but does not show that a trailing rule would improve expectancy.
- Median 1% stop distance among stopped observations was 0.81 hourly ATR. The target-winner control median was 0.83 ATR, so that pooled volatility measure alone does not separate winners from stopped trades.
- Stop placement relative to the entry-time support band for longs/resistance band for shorts:

| Stop position | Stopped observations | Share |
|---|---|---|
| before_near_edge | 2008 | 61.6% |
| beyond_far_edge | 648 | 19.9% |
| inside_band | 603 | 18.5% |

“Before near edge” means the price reaches the stop before reaching the mapped supporting band; “inside band” means the stop lies inside it; “beyond far edge” places the stop past it. These counts alone do not demonstrate that moving a stop beyond a band creates an edge. Use all winning/non-stopped controls and entry-time features in any later hypothesis.

## Exit reasons and equal-risk detail

2025, every cell. B/T/R/M columns are stop, target, regime, boundary respectively. Minute-close drawdown is additive fixed-notional drawdown divided by stop width (R), not an account equity percentage. Gaps/costs can lose more than 1R.

| Token | Side | Clock | Stop | B/T/R/M | Stopped % | Mean R | DD R | PF | Win % |
|---|---|---|---|---|---|---|---|---|---|
| BTC | S | 5m | 1% | 185/71/23/0 | 66.3% | -0.2298 | 64.53 | 0.720 | 28.0% |
| BTC | S | 5m | 2% | 86/67/30/0 | 47.0% | -0.1532 | 28.46 | 0.734 | 38.8% |
| BTC | S | 5m | 3% | 46/61/31/0 | 33.3% | -0.0983 | 14.88 | 0.776 | 47.1% |
| BTC | S | 5m | 4% | 21/50/36/0 | 19.6% | -0.0732 | 9.02 | 0.787 | 49.5% |
| BTC | S | 5m | 5% | 13/47/36/0 | 13.5% | -0.0651 | 7.32 | 0.777 | 51.0% |
| BTC | S | 15m | 1% | 119/55/12/0 | 64.0% | -0.1121 | 26.43 | 0.859 | 30.1% |
| BTC | S | 15m | 2% | 67/55/16/0 | 48.6% | -0.1129 | 18.63 | 0.803 | 40.6% |
| BTC | S | 15m | 3% | 34/52/24/0 | 30.9% | -0.0800 | 10.99 | 0.820 | 47.3% |
| BTC | S | 15m | 4% | 17/44/28/0 | 19.1% | -0.0489 | 7.07 | 0.854 | 49.4% |
| BTC | S | 15m | 5% | 11/43/31/0 | 12.9% | -0.0487 | 6.52 | 0.827 | 50.6% |
| BTC | S | 60m | 1% | 70/26/5/0 | 69.3% | -0.2740 | 29.24 | 0.684 | 25.7% |
| BTC | S | 60m | 2% | 43/29/6/0 | 55.1% | -0.2098 | 16.85 | 0.671 | 37.2% |
| BTC | S | 60m | 3% | 17/30/16/0 | 27.0% | -0.0667 | 7.82 | 0.846 | 47.6% |
| BTC | S | 60m | 4% | 11/29/21/0 | 18.0% | -0.0883 | 7.09 | 0.757 | 47.5% |
| BTC | S | 60m | 5% | 5/28/25/0 | 8.6% | -0.0694 | 5.16 | 0.763 | 48.3% |
| BTC | L | 5m | 1% | 91/41/15/0 | 61.9% | -0.1582 | 26.17 | 0.800 | 29.9% |
| BTC | L | 5m | 2% | 37/40/18/0 | 38.9% | -0.0403 | 10.94 | 0.922 | 43.2% |
| BTC | L | 5m | 3% | 20/36/18/0 | 27.0% | -0.0186 | 5.82 | 0.952 | 50.0% |
| BTC | L | 5m | 4% | 10/33/20/0 | 15.9% | -0.0091 | 5.94 | 0.970 | 54.0% |
| BTC | L | 5m | 5% | 4/32/19/0 | 7.3% | +0.0279 | 2.75 | 1.119 | 58.2% |
| BTC | L | 15m | 1% | 62/36/8/0 | 58.5% | +0.0163 | 20.71 | 1.022 | 34.0% |
| BTC | L | 15m | 2% | 25/33/12/0 | 35.7% | +0.0624 | 7.96 | 1.132 | 47.1% |
| BTC | L | 15m | 3% | 14/30/13/0 | 24.6% | +0.0230 | 5.71 | 1.062 | 52.6% |
| BTC | L | 15m | 4% | 5/26/18/0 | 10.2% | -0.0112 | 3.76 | 0.964 | 53.1% |
| BTC | L | 15m | 5% | 3/26/18/0 | 6.4% | +0.0003 | 3.21 | 1.001 | 55.3% |
| BTC | L | 60m | 1% | 42/24/3/0 | 60.9% | +0.0300 | 12.26 | 1.040 | 34.8% |
| BTC | L | 60m | 2% | 19/24/9/0 | 36.5% | +0.0213 | 6.27 | 1.042 | 46.2% |
| BTC | L | 60m | 3% | 11/23/12/0 | 23.9% | -0.0202 | 4.58 | 0.949 | 50.0% |
| BTC | L | 60m | 4% | 3/23/15/0 | 7.3% | +0.0515 | 3.07 | 1.194 | 56.1% |
| BTC | L | 60m | 5% | 1/23/17/0 | 2.4% | +0.0401 | 2.58 | 1.188 | 56.1% |
| ETH | S | 5m | 1% | 412/151/31/0 | 69.4% | -0.2669 | 159.29 | 0.689 | 26.9% |
| ETH | S | 5m | 2% | 178/136/35/0 | 51.0% | -0.1411 | 50.03 | 0.762 | 41.0% |
| ETH | S | 5m | 3% | 107/126/34/0 | 40.1% | -0.0922 | 28.17 | 0.799 | 49.4% |
| ETH | S | 5m | 4% | 65/116/37/0 | 29.8% | -0.0646 | 18.18 | 0.827 | 55.0% |
| ETH | S | 5m | 5% | 45/109/40/0 | 23.2% | -0.0572 | 12.90 | 0.820 | 58.8% |
| ETH | S | 15m | 1% | 240/105/14/0 | 66.9% | -0.1480 | 67.70 | 0.820 | 30.1% |
| ETH | S | 15m | 2% | 137/101/19/0 | 53.3% | -0.1592 | 46.61 | 0.740 | 40.5% |
| ETH | S | 15m | 3% | 82/98/23/0 | 40.4% | -0.0979 | 28.18 | 0.791 | 49.3% |
| ETH | S | 15m | 4% | 54/92/26/0 | 31.4% | -0.0814 | 18.25 | 0.791 | 54.1% |
| ETH | S | 15m | 5% | 35/87/32/0 | 22.7% | -0.0637 | 12.70 | 0.804 | 57.1% |
| ETH | S | 60m | 1% | 128/39/2/0 | 75.7% | -0.3931 | 73.15 | 0.574 | 23.1% |
| ETH | S | 60m | 2% | 71/51/5/0 | 55.9% | -0.1734 | 24.52 | 0.727 | 40.2% |
| ETH | S | 60m | 3% | 44/52/12/0 | 40.7% | -0.1262 | 16.01 | 0.745 | 48.1% |
| ETH | S | 60m | 4% | 31/50/14/0 | 32.6% | -0.1075 | 11.92 | 0.738 | 52.6% |
| ETH | S | 60m | 5% | 19/49/17/0 | 22.4% | -0.0604 | 8.12 | 0.815 | 57.6% |
| ETH | L | 5m | 1% | 212/92/15/0 | 66.5% | -0.1428 | 50.37 | 0.824 | 32.0% |
| ETH | L | 5m | 2% | 92/83/17/0 | 47.9% | -0.0452 | 19.35 | 0.917 | 47.9% |
| ETH | L | 5m | 3% | 49/76/18/0 | 34.3% | +0.0096 | 11.56 | 1.024 | 58.7% |
| ETH | L | 5m | 4% | 29/68/22/0 | 24.4% | +0.0100 | 9.26 | 1.032 | 62.2% |
| ETH | L | 5m | 5% | 19/63/22/0 | 18.3% | +0.0001 | 8.43 | 1.001 | 63.5% |
| ETH | L | 15m | 1% | 152/60/8/0 | 69.1% | -0.2213 | 53.74 | 0.738 | 28.6% |
| ETH | L | 15m | 2% | 79/57/10/0 | 54.1% | -0.1685 | 26.62 | 0.726 | 41.1% |
| ETH | L | 15m | 3% | 45/53/14/0 | 40.2% | -0.1141 | 13.79 | 0.759 | 49.1% |
| ETH | L | 15m | 4% | 25/50/19/0 | 26.6% | -0.0731 | 9.39 | 0.805 | 54.3% |
| ETH | L | 15m | 5% | 16/48/20/0 | 19.0% | -0.0428 | 8.53 | 0.858 | 58.3% |
| ETH | L | 60m | 1% | 62/29/2/0 | 66.7% | -0.1051 | 18.21 | 0.871 | 31.2% |
| ETH | L | 60m | 2% | 36/30/3/0 | 52.2% | -0.0993 | 11.48 | 0.833 | 43.5% |
| ETH | L | 60m | 3% | 22/29/6/0 | 38.6% | -0.0829 | 7.28 | 0.823 | 50.9% |
| ETH | L | 60m | 4% | 13/29/11/0 | 24.5% | -0.0639 | 5.22 | 0.829 | 54.7% |
| ETH | L | 60m | 5% | 8/28/14/0 | 16.0% | -0.0634 | 4.62 | 0.800 | 56.0% |
| SOL | S | 5m | 1% | 491/198/22/0 | 69.1% | -0.3021 | 219.05 | 0.671 | 28.7% |
| SOL | S | 5m | 2% | 227/181/27/0 | 52.2% | -0.1660 | 74.78 | 0.735 | 43.0% |
| SOL | S | 5m | 3% | 121/156/30/0 | 39.4% | -0.1062 | 38.66 | 0.779 | 52.1% |
| SOL | S | 5m | 4% | 81/143/33/0 | 31.5% | -0.0848 | 28.33 | 0.783 | 56.8% |
| SOL | S | 5m | 5% | 57/129/32/0 | 26.1% | -0.0721 | 20.51 | 0.783 | 60.1% |
| SOL | S | 15m | 1% | 304/124/6/0 | 70.0% | -0.2984 | 135.73 | 0.678 | 28.8% |
| SOL | S | 15m | 2% | 161/127/9/0 | 54.2% | -0.1723 | 54.11 | 0.732 | 43.1% |
| SOL | S | 15m | 3% | 97/119/16/0 | 41.8% | -0.1280 | 33.46 | 0.746 | 51.7% |
| SOL | S | 15m | 4% | 63/114/20/0 | 32.0% | -0.0778 | 18.61 | 0.804 | 58.4% |
| SOL | S | 15m | 5% | 48/104/22/0 | 27.6% | -0.0865 | 18.22 | 0.752 | 60.3% |
| SOL | S | 60m | 1% | 129/49/0/0 | 72.5% | -0.3480 | 65.17 | 0.635 | 27.5% |
| SOL | S | 60m | 2% | 84/57/1/0 | 59.2% | -0.2503 | 38.34 | 0.638 | 40.1% |
| SOL | S | 60m | 3% | 52/56/6/0 | 45.6% | -0.1824 | 25.62 | 0.664 | 49.1% |
| SOL | S | 60m | 4% | 38/56/8/0 | 37.3% | -0.1526 | 21.11 | 0.664 | 54.9% |
| SOL | S | 60m | 5% | 28/56/10/0 | 29.8% | -0.1208 | 17.66 | 0.684 | 59.6% |
| SOL | L | 5m | 1% | 303/122/19/0 | 68.2% | -0.3038 | 136.73 | 0.665 | 28.6% |
| SOL | L | 5m | 2% | 136/117/21/0 | 49.6% | -0.1337 | 37.61 | 0.778 | 43.8% |
| SOL | L | 5m | 3% | 76/105/22/0 | 37.4% | -0.0752 | 18.03 | 0.833 | 52.7% |
| SOL | L | 5m | 4% | 45/97/24/0 | 27.1% | -0.0369 | 10.72 | 0.896 | 59.0% |
| SOL | L | 5m | 5% | 35/88/23/0 | 24.0% | -0.0447 | 9.05 | 0.854 | 61.0% |
| SOL | L | 15m | 1% | 179/86/11/0 | 64.9% | -0.1888 | 52.84 | 0.783 | 31.5% |
| SOL | L | 15m | 2% | 96/89/12/0 | 48.7% | -0.0902 | 20.55 | 0.845 | 45.7% |
| SOL | L | 15m | 3% | 57/85/14/0 | 36.5% | -0.0401 | 10.43 | 0.908 | 55.1% |
| SOL | L | 15m | 4% | 32/74/15/0 | 26.4% | -0.0059 | 5.77 | 0.983 | 62.0% |
| SOL | L | 15m | 5% | 25/68/17/0 | 22.7% | -0.0362 | 6.15 | 0.881 | 61.8% |
| SOL | L | 60m | 1% | 78/37/0/0 | 67.8% | -0.1869 | 28.06 | 0.789 | 32.2% |
| SOL | L | 60m | 2% | 47/41/4/0 | 51.1% | -0.1311 | 14.27 | 0.787 | 44.6% |
| SOL | L | 60m | 3% | 30/42/6/0 | 38.5% | -0.0747 | 11.56 | 0.839 | 53.8% |
| SOL | L | 60m | 4% | 24/42/8/0 | 32.4% | -0.0919 | 10.26 | 0.770 | 56.8% |
| SOL | L | 60m | 5% | 16/40/11/0 | 23.9% | -0.0757 | 7.23 | 0.774 | 59.7% |

## Annual outcomes

Net return by actual entry year. Positions spanning years within discovery remain assigned to actual entry year; these are not independently restarted annual simulations.

| Token | Side | Clock | Stop | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|
| BTC | S | 5m | 1% | -0.238% (514) | -0.161% (91) | -0.281% (194) | -0.230% (279) |
| BTC | S | 5m | 2% | -0.319% (332) | -0.191% (61) | -0.290% (113) | -0.306% (183) |
| BTC | S | 5m | 3% | -0.291% (243) | -0.145% (52) | -0.440% (86) | -0.295% (138) |
| BTC | S | 5m | 4% | -0.220% (200) | -0.171% (48) | -0.393% (73) | -0.293% (107) |
| BTC | S | 5m | 5% | -0.246% (182) | -0.252% (45) | -0.361% (60) | -0.325% (96) |
| BTC | S | 15m | 1% | -0.162% (344) | -0.152% (65) | -0.295% (132) | -0.112% (186) |
| BTC | S | 15m | 2% | -0.324% (244) | -0.242% (46) | -0.387% (84) | -0.226% (138) |
| BTC | S | 15m | 3% | -0.356% (194) | -0.256% (40) | -0.541% (65) | -0.240% (110) |
| BTC | S | 15m | 4% | -0.340% (161) | -0.323% (37) | -0.589% (57) | -0.196% (89) |
| BTC | S | 15m | 5% | -0.320% (143) | -0.391% (34) | -0.533% (49) | -0.244% (85) |
| BTC | S | 60m | 1% | -0.190% (165) | -0.311% (38) | -0.127% (63) | -0.274% (101) |
| BTC | S | 60m | 2% | -0.255% (123) | -0.499% (25) | -0.268% (46) | -0.420% (78) |
| BTC | S | 60m | 3% | -0.290% (103) | -0.701% (23) | -0.294% (39) | -0.200% (63) |
| BTC | S | 60m | 4% | -0.417% (85) | -0.473% (20) | -0.418% (37) | -0.353% (61) |
| BTC | S | 60m | 5% | -0.424% (81) | -0.550% (20) | -0.195% (33) | -0.347% (58) |
| BTC | L | 5m | 1% | -0.434% (139) | -0.099% (295) | -0.099% (334) | -0.158% (147) |
| BTC | L | 5m | 2% | -0.512% (78) | -0.005% (177) | -0.057% (208) | -0.081% (95) |
| BTC | L | 5m | 3% | -0.643% (60) | +0.013% (145) | -0.007% (158) | -0.056% (74) |
| BTC | L | 5m | 4% | -0.686% (52) | +0.161% (116) | +0.096% (135) | -0.036% (63) |
| BTC | L | 5m | 5% | -0.725% (45) | +0.254% (101) | +0.253% (120) | +0.140% (55) |
| BTC | L | 15m | 1% | -0.323% (94) | -0.182% (236) | -0.110% (256) | +0.016% (106) |
| BTC | L | 15m | 2% | -0.394% (61) | -0.123% (142) | -0.023% (154) | +0.125% (70) |
| BTC | L | 15m | 3% | -0.504% (44) | -0.076% (117) | +0.021% (123) | +0.069% (57) |
| BTC | L | 15m | 4% | -0.497% (37) | +0.024% (90) | +0.230% (105) | -0.045% (49) |
| BTC | L | 15m | 5% | -0.542% (36) | +0.090% (83) | +0.208% (102) | +0.002% (47) |
| BTC | L | 60m | 1% | -0.597% (51) | -0.002% (116) | +0.075% (134) | +0.030% (69) |
| BTC | L | 60m | 2% | -0.846% (34) | +0.105% (81) | +0.158% (93) | +0.043% (52) |
| BTC | L | 60m | 3% | -1.110% (27) | +0.240% (66) | +0.135% (78) | -0.061% (46) |
| BTC | L | 60m | 4% | -0.973% (23) | +0.255% (61) | +0.146% (72) | +0.206% (41) |
| BTC | L | 60m | 5% | -1.022% (22) | +0.386% (59) | +0.019% (72) | +0.200% (41) |
| ETH | S | 5m | 1% | -0.195% (707) | -0.182% (120) | -0.213% (337) | -0.267% (594) |
| ETH | S | 5m | 2% | -0.242% (454) | -0.089% (76) | -0.292% (205) | -0.282% (349) |
| ETH | S | 5m | 3% | -0.178% (343) | -0.153% (62) | -0.377% (156) | -0.276% (267) |
| ETH | S | 5m | 4% | -0.208% (295) | -0.057% (55) | -0.389% (126) | -0.259% (218) |
| ETH | S | 5m | 5% | -0.304% (266) | -0.076% (52) | -0.465% (112) | -0.286% (194) |
| ETH | S | 15m | 1% | -0.089% (435) | -0.296% (94) | -0.265% (227) | -0.148% (359) |
| ETH | S | 15m | 2% | -0.071% (300) | -0.267% (61) | -0.406% (158) | -0.318% (257) |
| ETH | S | 15m | 3% | -0.152% (251) | -0.238% (51) | -0.482% (118) | -0.294% (203) |
| ETH | S | 15m | 4% | -0.210% (218) | -0.109% (47) | -0.591% (111) | -0.326% (172) |
| ETH | S | 15m | 5% | -0.259% (197) | -0.153% (44) | -0.531% (96) | -0.319% (154) |
| ETH | S | 60m | 1% | -0.189% (165) | -0.302% (56) | -0.322% (121) | -0.393% (169) |
| ETH | S | 60m | 2% | -0.245% (127) | -0.435% (40) | -0.497% (89) | -0.347% (127) |
| ETH | S | 60m | 3% | -0.344% (111) | -0.374% (36) | -0.528% (68) | -0.379% (108) |
| ETH | S | 60m | 4% | -0.243% (98) | -0.477% (36) | -0.439% (60) | -0.430% (95) |
| ETH | S | 60m | 5% | -0.364% (91) | -0.306% (32) | -0.497% (55) | -0.302% (85) |
| ETH | L | 5m | 1% | -0.250% (252) | -0.360% (355) | -0.194% (377) | -0.143% (319) |
| ETH | L | 5m | 2% | -0.205% (153) | -0.430% (220) | -0.133% (217) | -0.090% (192) |
| ETH | L | 5m | 3% | -0.360% (112) | -0.424% (162) | -0.084% (167) | +0.029% (143) |
| ETH | L | 5m | 4% | -0.125% (89) | -0.392% (135) | -0.012% (144) | +0.040% (119) |
| ETH | L | 5m | 5% | -0.219% (73) | -0.440% (116) | -0.000% (118) | +0.001% (104) |
| ETH | L | 15m | 1% | -0.258% (184) | -0.394% (255) | -0.209% (274) | -0.221% (220) |
| ETH | L | 15m | 2% | -0.366% (121) | -0.578% (164) | -0.236% (174) | -0.337% (146) |
| ETH | L | 15m | 3% | -0.340% (91) | -0.619% (129) | -0.154% (139) | -0.342% (112) |
| ETH | L | 15m | 4% | -0.440% (73) | -0.636% (106) | +0.002% (116) | -0.292% (94) |
| ETH | L | 15m | 5% | -0.497% (64) | -0.678% (97) | +0.064% (105) | -0.214% (84) |
| ETH | L | 60m | 1% | -0.199% (69) | -0.249% (129) | -0.184% (124) | -0.105% (93) |
| ETH | L | 60m | 2% | -0.497% (55) | -0.326% (90) | -0.244% (90) | -0.199% (69) |
| ETH | L | 60m | 3% | -0.659% (43) | -0.498% (82) | -0.365% (75) | -0.249% (57) |
| ETH | L | 60m | 4% | -0.918% (38) | -0.459% (70) | -0.219% (63) | -0.256% (53) |
| ETH | L | 60m | 5% | -1.042% (33) | -0.523% (68) | -0.318% (58) | -0.317% (50) |
| SOL | S | 5m | 1% | -0.290% (1153) | -0.283% (296) | -0.344% (445) | -0.302% (711) |
| SOL | S | 5m | 2% | -0.275% (750) | -0.360% (181) | -0.458% (283) | -0.332% (435) |
| SOL | S | 5m | 3% | -0.266% (584) | -0.375% (135) | -0.436% (217) | -0.319% (307) |
| SOL | S | 5m | 4% | -0.320% (501) | -0.327% (113) | -0.346% (180) | -0.339% (257) |
| SOL | S | 5m | 5% | -0.392% (441) | -0.370% (98) | -0.402% (159) | -0.360% (218) |
| SOL | S | 15m | 1% | -0.211% (649) | -0.388% (204) | -0.355% (264) | -0.298% (434) |
| SOL | S | 15m | 2% | -0.161% (459) | -0.387% (133) | -0.466% (182) | -0.345% (297) |
| SOL | S | 15m | 3% | -0.187% (370) | -0.408% (106) | -0.548% (148) | -0.384% (232) |
| SOL | S | 15m | 4% | -0.209% (331) | -0.484% (90) | -0.579% (125) | -0.311% (197) |
| SOL | S | 15m | 5% | -0.172% (293) | -0.473% (78) | -0.730% (117) | -0.433% (174) |
| SOL | S | 60m | 1% | -0.235% (231) | -0.437% (97) | -0.393% (103) | -0.348% (178) |
| SOL | S | 60m | 2% | -0.302% (192) | -0.600% (70) | -0.397% (78) | -0.501% (142) |
| SOL | S | 60m | 3% | -0.214% (156) | -0.696% (56) | -0.625% (71) | -0.547% (114) |
| SOL | S | 60m | 4% | -0.237% (142) | -0.751% (49) | -0.569% (63) | -0.611% (102) |
| SOL | S | 60m | 5% | -0.190% (130) | -0.944% (48) | -0.590% (57) | -0.604% (94) |
| SOL | L | 5m | 1% | -0.239% (231) | -0.277% (971) | -0.357% (735) | -0.304% (444) |
| SOL | L | 5m | 2% | -0.372% (151) | -0.293% (611) | -0.338% (448) | -0.267% (274) |
| SOL | L | 5m | 3% | -0.323% (117) | -0.301% (478) | -0.392% (335) | -0.225% (203) |
| SOL | L | 5m | 4% | -0.243% (95) | -0.270% (376) | -0.382% (274) | -0.148% (166) |
| SOL | L | 5m | 5% | -0.244% (83) | -0.192% (316) | -0.402% (236) | -0.224% (146) |
| SOL | L | 15m | 1% | -0.329% (130) | -0.284% (579) | -0.377% (459) | -0.189% (276) |
| SOL | L | 15m | 2% | -0.407% (90) | -0.222% (387) | -0.476% (303) | -0.180% (197) |
| SOL | L | 15m | 3% | -0.442% (74) | -0.266% (322) | -0.596% (246) | -0.120% (156) |
| SOL | L | 15m | 4% | -0.415% (65) | -0.134% (264) | -0.635% (198) | -0.024% (121) |
| SOL | L | 15m | 5% | -0.540% (60) | -0.126% (241) | -0.490% (171) | -0.181% (110) |
| SOL | L | 60m | 1% | -0.436% (48) | -0.251% (212) | -0.405% (192) | -0.187% (115) |
| SOL | L | 60m | 2% | -0.515% (35) | -0.242% (171) | -0.506% (142) | -0.262% (92) |
| SOL | L | 60m | 3% | -0.473% (29) | -0.193% (140) | -0.647% (117) | -0.224% (78) |
| SOL | L | 60m | 4% | -0.258% (24) | -0.110% (127) | -0.643% (102) | -0.368% (74) |
| SOL | L | 60m | 5% | -0.210% (22) | -0.116% (115) | -0.476% (92) | -0.378% (67) |

## Decision, verification and queue

Do not promote a stop width from this study. BTC long deserves separate attention because some wider-stop settings remain positive across periods, but the effects are weak under cost stress and/or too sparsely sampled. ETH and SOL do not establish persistent profitability. Reduced R losses partly reflect smaller notional at wider stops; this is risk scaling, not proof of better entry quality.

All 144 reference rows reconcile, including exit reason counts; maximum mean error 9.84e-17. Three targeted tests pass, including 800 scalar execution comparisons across the five widths and both sides. Six market input hashes, original execution source and annotation archive bytes match. Full source/data provenance and all trade records are retained locally.

The minimum economically viable zone-target test remains queued, not run. It should use the existing 1% reference if the aim is to isolate the new distance floor: this stop study has not justified replacing that control with a selected wider stop. A different stop requires its own matching unchanged-exit and unmodified-zone-cap controls. Do not combine a new stop, profit-protection rule and zone floor in one experiment.

No fixed maximum holding period, live changes, worker changes or Grokbot message. Historical reuse, minute-bar fill ambiguity, modeled costs/funding, overlapping configurations and absence of joint portfolio sizing limit inference.

The detailed protocol was committed locally before execution, but automatic approval review blocked its GitHub upload as disclosure of methodology. Publication is restricted to these findings and aggregate tables within the previously authorized scope. Detailed scripts, records and protocol remain local.
