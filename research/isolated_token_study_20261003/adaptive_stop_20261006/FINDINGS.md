# Adaptive ATR stops: completed comparison

6 October 2026. Protocol and runner frozen in local commit ea84b4e before outcomes. BTC, ETH and SOL; long/short; 5m, 15m and 1h; 2022–2024 discovery and reused 2025 validation. No 2026 outcomes. Original entries, 2.5% targets, regime exits, fees and funding unchanged. ATR uses completed-hour ATR14 ×2.5, clipped to 0.5–3% or 0.5–5%, fixed at entry.

## Finding

**None of the 54 configuration-policy cells passed the fixed-notional or equal-initial-risk screen.** Reduced stop frequency is not sufficient evidence of an edge. ATR3 improved net/trade over fixed1 in only 3/18 discovery cells and 6/18 validation cells. Raising the ATR cap from 3% to 5% improved net/trade in 12/18 cells in each period, but no configuration qualified. This does not establish an optimal stop range.

## Pooled descriptive totals

These are trade-weighted summaries across distinct token/timeframe/direction strategies, not portfolio returns. Policies have different position durations and entry counts. Means include boundary marks; stopped-out rates use completed trades.

| Period | Stop policy | Completed | Stopped out | Stop rate | Net/trade | Mean net R |
|---|---|---:|---:|---:|---:|---:|
| discovery | fixed1 | 14,541 | 9,988 | 68.69% | -0.2552% | -0.2552 |
| discovery | atr_cap3 | 8,268 | 3,774 | 45.65% | -0.2973% | -0.1155 |
| discovery | atr_cap5 | 7,301 | 2,977 | 40.78% | -0.2899% | -0.0976 |
| validation | fixed1 | 4,800 | 3,259 | 67.90% | -0.2352% | -0.2352 |
| validation | atr_cap3 | 2,722 | 1,212 | 44.53% | -0.2625% | -0.1016 |
| validation | atr_cap5 | 2,429 | 983 | 40.47% | -0.2520% | -0.0876 |

Equal-risk losses improved, but remain negative; this accounting scales each trade by its own initial stop distance and is not compounded account equity. Fixed-notional pooled losses worsened versus fixed1. Both views are necessary when interpreting wider stops.

## Every configuration: 2025 baseline costs

| Token | TF (minutes) | Side | Policy | Completed | Stops | Stop rate | Net/trade | PF | Mean R | PF R |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 5 | short | atr_cap3 | 166 | 73 | 43.98% | -0.2592% | 0.778 | -0.105 | 0.807 |
| BTCUSDT | 5 | short | atr_cap5 | 155 | 65 | 41.94% | -0.2496% | 0.785 | -0.108 | 0.797 |
| BTCUSDT | 5 | short | fixed1 | 279 | 185 | 66.31% | -0.2298% | 0.720 | -0.230 | 0.720 |
| BTCUSDT | 5 | long | atr_cap3 | 100 | 44 | 44.00% | -0.0479% | 0.949 | 0.004 | 1.007 |
| BTCUSDT | 5 | long | atr_cap5 | 97 | 42 | 43.30% | -0.0284% | 0.969 | 0.014 | 1.024 |
| BTCUSDT | 5 | long | fixed1 | 147 | 91 | 61.90% | -0.1582% | 0.800 | -0.158 | 0.800 |
| BTCUSDT | 15 | short | atr_cap3 | 136 | 68 | 50.00% | -0.2350% | 0.799 | -0.122 | 0.793 |
| BTCUSDT | 15 | short | atr_cap5 | 129 | 62 | 48.06% | -0.2118% | 0.818 | -0.114 | 0.802 |
| BTCUSDT | 15 | short | fixed1 | 186 | 119 | 63.98% | -0.1121% | 0.859 | -0.112 | 0.859 |
| BTCUSDT | 15 | long | atr_cap3 | 75 | 32 | 42.67% | 0.0814% | 1.089 | 0.091 | 1.161 |
| BTCUSDT | 15 | long | atr_cap5 | 75 | 32 | 42.67% | 0.0469% | 1.050 | 0.086 | 1.151 |
| BTCUSDT | 15 | long | fixed1 | 106 | 62 | 58.49% | 0.0163% | 1.022 | 0.016 | 1.022 |
| BTCUSDT | 60 | short | atr_cap3 | 80 | 45 | 56.25% | -0.3717% | 0.692 | -0.143 | 0.788 |
| BTCUSDT | 60 | short | atr_cap5 | 78 | 43 | 55.13% | -0.3361% | 0.718 | -0.126 | 0.811 |
| BTCUSDT | 60 | short | fixed1 | 101 | 70 | 69.31% | -0.2740% | 0.684 | -0.274 | 0.684 |
| BTCUSDT | 60 | long | atr_cap3 | 63 | 37 | 58.73% | -0.0977% | 0.898 | -0.009 | 0.986 |
| BTCUSDT | 60 | long | atr_cap5 | 62 | 36 | 58.06% | -0.0771% | 0.919 | 0.003 | 1.005 |
| BTCUSDT | 60 | long | fixed1 | 69 | 42 | 60.87% | 0.0300% | 1.040 | 0.030 | 1.040 |
| ETHUSDT | 5 | short | atr_cap3 | 285 | 121 | 42.46% | -0.2906% | 0.784 | -0.111 | 0.773 |
| ETHUSDT | 5 | short | atr_cap5 | 237 | 86 | 36.29% | -0.2764% | 0.806 | -0.099 | 0.771 |
| ETHUSDT | 5 | short | fixed1 | 594 | 412 | 69.36% | -0.2669% | 0.689 | -0.267 | 0.689 |
| ETHUSDT | 5 | long | atr_cap3 | 162 | 66 | 40.74% | -0.0103% | 0.991 | -0.019 | 0.960 |
| ETHUSDT | 5 | long | atr_cap5 | 146 | 55 | 37.67% | 0.0046% | 1.004 | -0.024 | 0.947 |
| ETHUSDT | 5 | long | fixed1 | 319 | 212 | 66.46% | -0.1428% | 0.824 | -0.143 | 0.824 |
| ETHUSDT | 15 | short | atr_cap3 | 212 | 93 | 43.87% | -0.3014% | 0.780 | -0.125 | 0.751 |
| ETHUSDT | 15 | short | atr_cap5 | 180 | 68 | 37.78% | -0.2887% | 0.800 | -0.110 | 0.753 |
| ETHUSDT | 15 | short | fixed1 | 359 | 240 | 66.85% | -0.1480% | 0.820 | -0.148 | 0.820 |
| ETHUSDT | 15 | long | atr_cap3 | 123 | 58 | 47.15% | -0.3105% | 0.767 | -0.109 | 0.792 |
| ETHUSDT | 15 | long | atr_cap5 | 114 | 48 | 42.11% | -0.2071% | 0.839 | -0.083 | 0.828 |
| ETHUSDT | 15 | long | fixed1 | 220 | 152 | 69.09% | -0.2213% | 0.738 | -0.221 | 0.738 |
| ETHUSDT | 60 | short | atr_cap3 | 116 | 57 | 49.14% | -0.3886% | 0.726 | -0.187 | 0.674 |
| ETHUSDT | 60 | short | atr_cap5 | 103 | 45 | 43.69% | -0.2621% | 0.813 | -0.142 | 0.724 |
| ETHUSDT | 60 | short | fixed1 | 169 | 128 | 75.74% | -0.3931% | 0.574 | -0.393 | 0.574 |
| ETHUSDT | 60 | long | atr_cap3 | 64 | 32 | 50.00% | -0.2688% | 0.793 | -0.120 | 0.787 |
| ETHUSDT | 60 | long | atr_cap5 | 63 | 30 | 47.62% | -0.3108% | 0.771 | -0.117 | 0.787 |
| ETHUSDT | 60 | long | fixed1 | 93 | 62 | 66.67% | -0.1051% | 0.871 | -0.105 | 0.871 |
| SOLUSDT | 5 | short | atr_cap3 | 322 | 134 | 41.61% | -0.3348% | 0.765 | -0.125 | 0.752 |
| SOLUSDT | 5 | short | atr_cap5 | 249 | 87 | 34.94% | -0.3771% | 0.757 | -0.115 | 0.737 |
| SOLUSDT | 5 | short | fixed1 | 711 | 491 | 69.06% | -0.3021% | 0.671 | -0.302 | 0.671 |
| SOLUSDT | 5 | long | atr_cap3 | 211 | 83 | 39.34% | -0.2119% | 0.839 | -0.078 | 0.837 |
| SOLUSDT | 5 | long | atr_cap5 | 196 | 69 | 35.20% | -0.2219% | 0.841 | -0.067 | 0.846 |
| SOLUSDT | 5 | long | fixed1 | 444 | 303 | 68.24% | -0.3038% | 0.665 | -0.304 | 0.665 |
| SOLUSDT | 15 | short | atr_cap3 | 241 | 107 | 44.40% | -0.3816% | 0.741 | -0.146 | 0.725 |
| SOLUSDT | 15 | short | atr_cap5 | 210 | 81 | 38.57% | -0.3670% | 0.765 | -0.128 | 0.727 |
| SOLUSDT | 15 | short | fixed1 | 434 | 304 | 70.05% | -0.2984% | 0.678 | -0.298 | 0.678 |
| SOLUSDT | 15 | long | atr_cap3 | 162 | 63 | 38.89% | -0.1457% | 0.887 | -0.051 | 0.891 |
| SOLUSDT | 15 | long | atr_cap5 | 145 | 50 | 34.48% | -0.1883% | 0.865 | -0.042 | 0.902 |
| SOLUSDT | 15 | long | fixed1 | 276 | 179 | 64.86% | -0.1888% | 0.783 | -0.189 | 0.783 |
| SOLUSDT | 60 | short | atr_cap3 | 122 | 63 | 51.64% | -0.5351% | 0.657 | -0.214 | 0.640 |
| SOLUSDT | 60 | short | atr_cap5 | 111 | 52 | 46.85% | -0.5337% | 0.679 | -0.173 | 0.676 |
| SOLUSDT | 60 | short | fixed1 | 178 | 129 | 72.47% | -0.3480% | 0.635 | -0.348 | 0.635 |
| SOLUSDT | 60 | long | atr_cap3 | 82 | 36 | 43.90% | -0.2774% | 0.801 | -0.093 | 0.820 |
| SOLUSDT | 60 | long | atr_cap5 | 79 | 32 | 40.51% | -0.3534% | 0.766 | -0.091 | 0.810 |
| SOLUSDT | 60 | long | fixed1 | 115 | 78 | 67.83% | -0.1869% | 0.789 | -0.187 | 0.789 |

## Verification and evidence

All six input file SHA256 hashes match the original study. The restored source ZIP matches 344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc. All 144 fixed1 reference rows reconcile, including exit counts and chronological risk-scaled drawdown; maximum absolute mean difference is 9.85e-17. 432 aggregate rows completed. Cap/floor and per-trade risk tests plus prior scalar-execution checks passed before the run. Initial attempts stopped before scores because the old cache/dependency directory was unavailable; they were not experimental outcomes.

CSV evidence includes both cost scenarios, all configurations and periods, annual results, exit reasons, stop distributions, drawdown and holding times. Matched diagnostics retain the exact fixed1 executed entries and identify originally stopped-out trades; these are diagnostic counterfactuals, not independently feasible portfolio schedules. Full raw and scheduled trade paths are archived separately.

Screen: at least 50 completed trades in each period; positive baseline means and PF≥1.15 in both; positive doubled-slippage means in both. Equal-risk screen substitutes per-position mean R and PF R. None pass either screen. Validation is reused research data, not an untouched final holdout. Multiple comparisons and pooled heterogeneous strategies preclude treating isolated positive cells as confirmed discoveries.

## Next isolated experiments

Retain fixed1 as the reconciled control; do not promote either adaptive policy. Keep the queued economically viable zone-target-distance fallback separate from stop changes. Oscillator entry experiments must use predefined causal windows and thresholds; conventional extremes at the current reclaim signal produced no candidates in the anatomy study. Further token/timeframe stop optimization requires fresh out-of-sample confirmation, not selecting the best reused-2025 result.
