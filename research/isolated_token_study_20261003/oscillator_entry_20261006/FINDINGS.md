# Oscillator recovery entries: completed results

6 October 2026. Frozen before outcomes at local commit d817e88. **Neither RSI recovery nor Connors RSI recovery passes the predefined strategy screen.** All 54 cells, including 18 original EMA controls, fail. No entry promoted; no live settings changed. 432 strategy rows and 144 baseline reconciliations completed. Input and imported-source hashes verified; no 2026 features or outcomes used.

## What changed

Original EMA20-cross entry replaced with completed-candle RSI14 recovery above30 for longs/below70 for shorts, or Connors RSI(3,2,100) recovery above10/below90. The prior bar must be at/beyond the threshold. Current4h trend regime remains mandatory, using the original EMA50/200 and slope conditions. Next-minute market entry; no zone, volume or additional candle filter. BTC/ETH/SOL, long/short separately,5m/15m/1h. Stops1%, targets2.5%, regime exits, fees/slippage and funding held fixed. No holding-time cap. Full definitions in PROTOCOL.md.

This tests two specific implementations, not all oscillator-based entries. The previous extreme need not have occurred in an aligned regime. No threshold was changed after viewing outcomes.

## Pooled chronological results

Trade-weighted descriptive summaries across separate strategies; not portfolio returns. Different policies admit different trades. Means include boundary marks; stop rates use completed trades.

| Period | Entry | Completed | Stops | Stop rate | Net/trade |
|---|---|---:|---:|---:|---:|
| discovery | ema20 | 14,541 | 9,988 | 68.69% | -0.2552% |
| discovery | rsi_recovery | 6,036 | 3,898 | 64.58% | -0.2720% |
| discovery | connors_recovery | 8,685 | 5,910 | 68.05% | -0.2959% |
| validation | ema20 | 4,800 | 3,259 | 67.90% | -0.2352% |
| validation | rsi_recovery | 1,992 | 1,304 | 65.46% | -0.3444% |
| validation | connors_recovery | 2,994 | 1,980 | 66.13% | -0.2502% |

RSI improves chronological net/trade versus EMA in9/18 discovery cells but only2/18 validation cells. Connors improves5/18 and6/18 respectively. All18 RSI validation means are negative. The only positive Connors validation cell is ETH1h short:65 completed trades,34 stops, +0.0374% net/trade, PF1.056; discovery is -0.1892%, and doubled-slippage validation is -0.0625%. It fails the screen. Six RSI validation cells and three Connors cells have fewer than50 completed trades.

## Entry-only diagnostics: a lead, not a profitable system

We measured forward4h and24h endpoints without stops or regime exits, using all candidate signals with full windows. These are diagnostic horizons, not tested holding-cap strategies. Matching balances calendar month, UTC hour, aligned regime and discovery-defined volatility tertile; it does not balance every confounder. Signals/controls selected without replacement within strata; full pair evidence retained. Candidate paths overlap across time and timeframes, so counts are not independent trials. No significance claim is made.

2025 matched observations, pooled with equal signal/control counts per cell. Delta is signal minus matched-control net return in percentage points. All signal means below remain negative after costs.

| Entry | Horizon | Matched signals | Signal net | Control net | Difference (pp) |
|---|---:|---:|---:|---:|---:|
| ema20 | 4h | 20,703 | -0.2455% | -0.2326% | -0.0130 |
| ema20 | 24h | 20,703 | -0.2960% | -0.1811% | -0.1148 |
| rsi_recovery | 4h | 3,313 | -0.3084% | -0.2525% | -0.0559 |
| rsi_recovery | 24h | 3,313 | -0.0913% | -0.3624% | +0.2711 |
| connors_recovery | 4h | 5,117 | -0.2497% | -0.2828% | +0.0331 |
| connors_recovery | 24h | 5,117 | -0.1400% | -0.2636% | +0.1236 |

RSI24h matched advantage appears in13/18 discovery cells and15/18 validation cells; Connors24h in11/18 in each period. This is a relative improvement, not demonstrated net profitability. RSI4h pooled2025 results are worse than matched controls, so there is no consistent immediate advantage. The24h result warrants a separately frozen confirmation hypothesis; it does not justify silently widening stops or selecting a24h exit on these same outcomes. Raw all-signal, matching-coverage, MFE/MAE and stressed diagnostics are supplied in CSVs.

## Every 2025 strategy cell, baseline costs

| Token | TF min | Side | Entry | Completed | Stops | Stop rate | Net/trade | PF |
|---|---:|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | 5 | short | connors_recovery | 228 | 149 | 65.35% | -0.2601% | 0.680 |
| BTCUSDT | 5 | short | ema20 | 279 | 185 | 66.31% | -0.2298% | 0.720 |
| BTCUSDT | 5 | short | rsi_recovery | 167 | 106 | 63.47% | -0.3365% | 0.584 |
| BTCUSDT | 5 | long | connors_recovery | 141 | 85 | 60.28% | -0.0923% | 0.880 |
| BTCUSDT | 5 | long | ema20 | 147 | 91 | 61.90% | -0.1582% | 0.800 |
| BTCUSDT | 5 | long | rsi_recovery | 117 | 74 | 63.25% | -0.2887% | 0.646 |
| BTCUSDT | 15 | short | connors_recovery | 121 | 69 | 57.02% | -0.1684% | 0.775 |
| BTCUSDT | 15 | short | ema20 | 186 | 119 | 63.98% | -0.1121% | 0.859 |
| BTCUSDT | 15 | short | rsi_recovery | 80 | 48 | 60.00% | -0.3152% | 0.590 |
| BTCUSDT | 15 | long | connors_recovery | 92 | 53 | 57.61% | -0.0482% | 0.935 |
| BTCUSDT | 15 | long | ema20 | 106 | 62 | 58.49% | 0.0163% | 1.022 |
| BTCUSDT | 15 | long | rsi_recovery | 63 | 34 | 53.97% | -0.1413% | 0.804 |
| BTCUSDT | 60 | short | connors_recovery | 51 | 31 | 60.78% | -0.2688% | 0.656 |
| BTCUSDT | 60 | short | ema20 | 101 | 70 | 69.31% | -0.2740% | 0.684 |
| BTCUSDT | 60 | short | rsi_recovery | 14 | 5 | 35.71% | -0.3941% | 0.356 |
| BTCUSDT | 60 | long | connors_recovery | 36 | 21 | 58.33% | -0.0583% | 0.923 |
| BTCUSDT | 60 | long | ema20 | 69 | 42 | 60.87% | 0.0300% | 1.040 |
| BTCUSDT | 60 | long | rsi_recovery | 16 | 6 | 37.50% | -0.0275% | 0.954 |
| ETHUSDT | 5 | short | connors_recovery | 427 | 297 | 69.56% | -0.2670% | 0.688 |
| ETHUSDT | 5 | short | ema20 | 594 | 412 | 69.36% | -0.2669% | 0.689 |
| ETHUSDT | 5 | short | rsi_recovery | 288 | 203 | 70.49% | -0.3902% | 0.555 |
| ETHUSDT | 5 | long | connors_recovery | 258 | 171 | 66.28% | -0.1510% | 0.815 |
| ETHUSDT | 5 | long | ema20 | 319 | 212 | 66.46% | -0.1428% | 0.824 |
| ETHUSDT | 5 | long | rsi_recovery | 193 | 136 | 70.47% | -0.3458% | 0.602 |
| ETHUSDT | 15 | short | connors_recovery | 197 | 132 | 67.01% | -0.2204% | 0.733 |
| ETHUSDT | 15 | short | ema20 | 359 | 240 | 66.85% | -0.1480% | 0.820 |
| ETHUSDT | 15 | short | rsi_recovery | 127 | 74 | 58.27% | -0.1676% | 0.775 |
| ETHUSDT | 15 | long | connors_recovery | 126 | 86 | 68.25% | -0.2684% | 0.683 |
| ETHUSDT | 15 | long | ema20 | 220 | 152 | 69.09% | -0.2213% | 0.738 |
| ETHUSDT | 15 | long | rsi_recovery | 75 | 49 | 65.33% | -0.4270% | 0.480 |
| ETHUSDT | 60 | short | connors_recovery | 65 | 34 | 52.31% | 0.0374% | 1.056 |
| ETHUSDT | 60 | short | ema20 | 169 | 128 | 75.74% | -0.3931% | 0.574 |
| ETHUSDT | 60 | short | rsi_recovery | 22 | 13 | 59.09% | -0.3843% | 0.517 |
| ETHUSDT | 60 | long | connors_recovery | 41 | 27 | 65.85% | -0.2583% | 0.683 |
| ETHUSDT | 60 | long | ema20 | 93 | 62 | 66.67% | -0.1051% | 0.871 |
| ETHUSDT | 60 | long | rsi_recovery | 14 | 8 | 57.14% | -0.4583% | 0.375 |
| SOLUSDT | 5 | short | connors_recovery | 471 | 335 | 71.13% | -0.4093% | 0.570 |
| SOLUSDT | 5 | short | ema20 | 711 | 491 | 69.06% | -0.3021% | 0.671 |
| SOLUSDT | 5 | short | rsi_recovery | 333 | 225 | 67.57% | -0.3779% | 0.588 |
| SOLUSDT | 5 | long | connors_recovery | 297 | 201 | 67.68% | -0.2701% | 0.699 |
| SOLUSDT | 5 | long | ema20 | 444 | 303 | 68.24% | -0.3038% | 0.665 |
| SOLUSDT | 5 | long | rsi_recovery | 227 | 165 | 72.69% | -0.4672% | 0.511 |
| SOLUSDT | 15 | short | connors_recovery | 202 | 130 | 64.36% | -0.2603% | 0.700 |
| SOLUSDT | 15 | short | ema20 | 434 | 304 | 70.05% | -0.2984% | 0.678 |
| SOLUSDT | 15 | short | rsi_recovery | 137 | 85 | 62.04% | -0.2846% | 0.666 |
| SOLUSDT | 15 | long | connors_recovery | 145 | 100 | 68.97% | -0.3222% | 0.647 |
| SOLUSDT | 15 | long | ema20 | 276 | 179 | 64.86% | -0.1888% | 0.783 |
| SOLUSDT | 15 | long | rsi_recovery | 88 | 53 | 60.23% | -0.2071% | 0.748 |
| SOLUSDT | 60 | short | connors_recovery | 57 | 36 | 63.16% | -0.3022% | 0.650 |
| SOLUSDT | 60 | short | ema20 | 178 | 129 | 72.47% | -0.3480% | 0.635 |
| SOLUSDT | 60 | short | rsi_recovery | 22 | 16 | 72.73% | -0.7103% | 0.267 |
| SOLUSDT | 60 | long | connors_recovery | 39 | 23 | 58.97% | -0.2152% | 0.725 |
| SOLUSDT | 60 | long | ema20 | 115 | 78 | 67.83% | -0.1869% | 0.789 |
| SOLUSDT | 60 | long | rsi_recovery | 9 | 4 | 44.44% | -0.4455% | 0.363 |

## Verification, interpretation and next step

Three new synthetic tests passed: exact crossings/equality/long-short mirroring/NaNs, feature prefix independence, and matching-stratum/no-replacement/exclusion behavior. Four existing anatomy indicator tests passed. Every original EMA result reconciles to the fixed1 study (144 count/mean/exit comparisons). Full evidence includes all candidates, scheduled base/stress trades, forward paths, matched pairs, entry-year tables and volatility edges. The completed manifest identifies the pre-run commit and source/data hashes.

The screen requires at least50 completed trades in both2022–2024 and2025, positive means and PF>=1.15 in both at base costs, and positive means in both under doubled slippage. This is reused historical research, not fresh confirmation. Recent nulls should not be erased by a favorable subset or pooled forward diagnostic. Stop counts alone do not tell us whether an entry is good.

Next entry-family candidate from the agreed sequence is standalone zone rejection, independent of an EMA-cross trigger. It needs its own frozen protocol and common exit controls. Breakout/retest follows separately. Keep the economically viable zone-target fallback queued separately. Do not combine RSI, zones, wider stops and new targets in one test. No new tuning was run after these results.
