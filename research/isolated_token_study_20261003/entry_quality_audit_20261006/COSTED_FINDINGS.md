# Matched costed-entry findings — 6 October 2026

**Decision: the standalone zone-rejection entry still has no demonstrated robust advantage. In 2025 it underperformed matched entry times under both stop/target settings. Its pooled return was already negative before execution costs.** The primary prediction gate remains failed (0/18); this secondary diagnostic does not create a new selection gate.

## Scope and what the counts mean

This completes the pending costed component of the zone-entry audit. It tests BTC/ETH/SOL, 5m/15m/1h entries, long and short, with completed 4h regime context. The two arms are 2% SL / 2.5% TP and 3% SL / 3% TP. There is no maximum holding period. Stops, targets, regime exits, fees, slippage and funding use the unchanged execution engine.

These are **independent simulated signal opportunities, including overlapping entries**, not executed positions or a combined portfolio. Counts differ from the previous chronological breakout/retest experiment because both the entry family and the treatment of simultaneous signals differ. Within this test, exactly the same matched signal and control times are used in both arms and cost scenarios.

Of 59,617 original zone signals, 58,690 matched (98.45%); 927 did not. There are 1,126,229 control draws and 583,902 distinct control-time keys summed across cells. Keys can overlap across timeframes; neither number represents independent observations. One control is reused at most 15 times within a cell. The weight-concentration effective-control count in coverage.csv does not adjust for temporal dependence.

## Matched results, base costs

| Period | SL / TP | Matched opportunities | Zone net/opportunity | Control net/opportunity | Zone minus control (pp) | Zone stop-outs | Control stop rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| discovery | 2% / 2.5% | 44,345 | -0.301% | -0.316% | +0.014 | 21,041 (47.5%) | 49.7% |
| discovery | 3% / 3.0% | 44,345 | -0.349% | -0.395% | +0.046 | 15,251 (34.5%) | 38.1% |
| validation | 2% / 2.5% | 14,345 | -0.440% | -0.354% | -0.086 | 6,832 (47.6%) | 48.7% |
| validation | 3% / 3.0% | 14,345 | -0.429% | -0.351% | -0.079 | 4,691 (32.7%) | 34.5% |

Each signal receives one unit of weight; its controls together receive one unit. Stop rates exclude boundary marks. Discovery has 33 signal boundary marks under 2%/2.5% and 118 under 3%/3%; 2025 has none. Pooled summaries are descriptive and no pooled confidence claim is made. “Validation” in CSV files means reused 2025 historical evaluation, not fresh validation.

The relative advantage is small and positive in pooled 2022–24, then negative in 2025. A lower zone stop-out rate than controls does not translate into better net return. Stop/target arms also differ in TP, so this is not a pure stop-width intervention.

## Where the losses arise

| Period | SL / TP | Quoted return | Slippage drag | Fees | Funding | Net |
| --- | --- | --- | --- | --- | --- | --- |
| discovery | 2% / 2.5% | -0.0545% | 0.1299% | 0.1100% | 0.0069% | -0.3013% |
| discovery | 3% / 3.0% | -0.0960% | 0.1299% | 0.1100% | 0.0129% | -0.3487% |
| validation | 2% / 2.5% | -0.1954% | 0.1320% | 0.1101% | 0.0027% | -0.4402% |
| validation | 3% / 3.0% | -0.1839% | 0.1321% | 0.1101% | 0.0034% | -0.4295% |

Net equals quoted return minus slippage drag, fees and funding. Positive funding is paid; negative funding is received. Quoted return already includes the prescribed exit policy, before slippage, fees and funding. It does not isolate the entry trigger from that policy.

For 2025, the 2%/2.5% arm starts at -0.1954% quoted return; costs add approximately 0.2448 percentage points of loss, leaving -0.4402%. The 3%/3% arm starts at -0.1839%; costs add 0.2456 points, leaving -0.4295%. Lower modeled costs alone would not make either pooled result profitable at these exits. Doubled slippage produces -0.5723% and -0.5616% net respectively; relative performance against controls remains negative.

## Why fewer stop-outs did not solve profitability

| 2025 SL / TP | Stop | Target | Regime | Boundary |
| --- | --- | --- | --- | --- |
| 2% / 2.5% | 6832 | 4906 | 2607 | 0 |
| 3% / 3.0% | 4691 | 5240 | 4414 | 0 |

On the same 14,345 matched 2025 entry opportunities, stop-outs fall by 2,141 between arms. At aggregate level this is accompanied by 334 more target exits and 1,807 more regime exits. These count differences are not a trade-by-trade transition classification. Wider stops can leave positions open to exit later through the regime rule; fewer stops alone do not establish recovery or profit. Net improvement between the two arms is only about 0.0108 percentage points per opportunity, and both remain negative.

## Cell-level uncertainty and exceptions

All 36 base-cost arm/group combinations have negative matched-signal mean net return in 2022–24. In 2025, two of 18 cells under 2%/2.5% and three of 18 under 3%/3% have positive means. For example, BTC 1h long with 3%/3% earns +0.213% per opportunity in 2025, but is negative in discovery and its uplift interval includes zero. No 2025 cell in either arm has a positive four-week-block lower bound for paired net uplift.

BTC 5m short under 3%/3% has a positive ordinary four-week lower bound in discovery, but negative uplift in 2025. ETH 1h short and SOL 1h short have negative ordinary four-week upper bounds in 2025 under both arms. These are unadjusted secondary comparisons across many cells; they are not new tradable short/long filters.

Bootstrap intervals use 10,000 draws with one- and four-week entry-calendar blocks, keeping each signal and its controls paired. They preserve within-week control reuse, but longer holding paths and repeated use of historical data limit inference. The original simultaneous primary gate is unchanged.

## Matching coverage

| Entry clock | Original signals | Matched | Coverage | Unmatched |
| --- | --- | --- | --- | --- |
| 5m | 34,019 | 33,962 | 99.83% | 57 |
| 15m | 18,141 | 17,973 | 99.07% | 168 |
| 60m | 7,457 | 6,755 | 90.59% | 702 |

Matching holds token, direction, clock, period, calendar week, six-hour UTC block, regime and volatility tertile fixed. The volatility cutoffs were learned on discovery data only. Signals need at least five controls, with at most twenty sampled. No outcome determines a match. Unlike horizon diagnostics, no four-hour boundary exclusion is imposed; open opportunities are marked at the period end. This yields three more matched signals than the primary 4h diagnostic. Full exclusions and as-of context are retained.

## Every 2025 base-cost contrast

| Token | Clock | Side | SL / TP | Matched | Zone net | Control net | Difference (pp) | 4-week CI (pp) | Zone stops |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BTCUSDT | 5m | L | 2% / 2.5% | 1367 | -0.025% | -0.160% | +0.135 | [-0.112, +0.346] | 321 (23.5%) |
| BTCUSDT | 5m | L | 3% / 3.0% | 1367 | 0.036% | -0.100% | +0.136 | [-0.120, +0.410] | 173 (12.7%) |
| BTCUSDT | 5m | S | 2% / 2.5% | 1441 | -0.599% | -0.476% | -0.123 | [-0.374, +0.089] | 684 (47.5%) |
| BTCUSDT | 5m | S | 3% / 3.0% | 1441 | -0.562% | -0.513% | -0.050 | [-0.360, +0.209] | 334 (23.2%) |
| BTCUSDT | 15m | L | 2% / 2.5% | 687 | -0.042% | -0.118% | +0.076 | [-0.112, +0.221] | 162 (23.6%) |
| BTCUSDT | 15m | L | 3% / 3.0% | 687 | 0.063% | -0.031% | +0.095 | [-0.131, +0.309] | 85 (12.4%) |
| BTCUSDT | 15m | S | 2% / 2.5% | 757 | -0.654% | -0.501% | -0.153 | [-0.395, +0.061] | 384 (50.7%) |
| BTCUSDT | 15m | S | 3% / 3.0% | 757 | -0.586% | -0.544% | -0.042 | [-0.344, +0.253] | 189 (25.0%) |
| BTCUSDT | 60m | L | 2% / 2.5% | 259 | 0.027% | -0.107% | +0.134 | [-0.062, +0.306] | 63 (24.3%) |
| BTCUSDT | 60m | L | 3% / 3.0% | 259 | 0.212% | 0.036% | +0.177 | [-0.067, +0.408] | 32 (12.4%) |
| BTCUSDT | 60m | S | 2% / 2.5% | 265 | -0.578% | -0.328% | -0.250 | [-0.584, +0.093] | 136 (51.3%) |
| BTCUSDT | 60m | S | 3% / 3.0% | 265 | -0.553% | -0.327% | -0.226 | [-0.703, +0.262] | 67 (25.3%) |
| ETHUSDT | 5m | L | 2% / 2.5% | 1224 | -0.216% | -0.270% | +0.055 | [-0.261, +0.262] | 574 (46.9%) |
| ETHUSDT | 5m | L | 3% / 3.0% | 1224 | -0.205% | -0.318% | +0.114 | [-0.288, +0.382] | 426 (34.8%) |
| ETHUSDT | 5m | S | 2% / 2.5% | 1738 | -0.671% | -0.510% | -0.160 | [-0.337, +0.001] | 991 (57.0%) |
| ETHUSDT | 5m | S | 3% / 3.0% | 1738 | -0.732% | -0.573% | -0.159 | [-0.464, +0.126] | 737 (42.4%) |
| ETHUSDT | 15m | L | 2% / 2.5% | 652 | -0.172% | -0.151% | -0.022 | [-0.337, +0.192] | 316 (48.5%) |
| ETHUSDT | 15m | L | 3% / 3.0% | 652 | -0.158% | -0.200% | +0.043 | [-0.385, +0.310] | 239 (36.7%) |
| ETHUSDT | 15m | S | 2% / 2.5% | 887 | -0.633% | -0.487% | -0.146 | [-0.323, +0.020] | 500 (56.4%) |
| ETHUSDT | 15m | S | 3% / 3.0% | 887 | -0.675% | -0.555% | -0.119 | [-0.407, +0.134] | 370 (41.7%) |
| ETHUSDT | 60m | L | 2% / 2.5% | 213 | 0.013% | 0.063% | -0.051 | [-0.353, +0.190] | 100 (46.9%) |
| ETHUSDT | 60m | L | 3% / 3.0% | 213 | -0.170% | 0.064% | -0.234 | [-0.663, +0.088] | 89 (41.8%) |
| ETHUSDT | 60m | S | 2% / 2.5% | 296 | -0.731% | -0.409% | -0.322 | [-0.514, -0.109] | 179 (60.5%) |
| ETHUSDT | 60m | S | 3% / 3.0% | 296 | -0.693% | -0.435% | -0.258 | [-0.504, -0.062] | 140 (47.3%) |
| SOLUSDT | 5m | L | 2% / 2.5% | 1110 | -0.561% | -0.405% | -0.156 | [-0.390, +0.033] | 569 (51.3%) |
| SOLUSDT | 5m | L | 3% / 3.0% | 1110 | -0.497% | -0.341% | -0.156 | [-0.452, +0.193] | 416 (37.5%) |
| SOLUSDT | 5m | S | 2% / 2.5% | 1551 | -0.552% | -0.380% | -0.171 | [-0.496, +0.168] | 845 (54.5%) |
| SOLUSDT | 5m | S | 3% / 3.0% | 1551 | -0.570% | -0.355% | -0.215 | [-0.548, +0.089] | 627 (40.4%) |
| SOLUSDT | 15m | L | 2% / 2.5% | 576 | -0.456% | -0.412% | -0.044 | [-0.322, +0.168] | 283 (49.1%) |
| SOLUSDT | 15m | L | 3% / 3.0% | 576 | -0.575% | -0.390% | -0.186 | [-0.521, +0.169] | 226 (39.2%) |
| SOLUSDT | 15m | S | 2% / 2.5% | 813 | -0.530% | -0.412% | -0.118 | [-0.420, +0.215] | 446 (54.9%) |
| SOLUSDT | 15m | S | 3% / 3.0% | 813 | -0.505% | -0.364% | -0.141 | [-0.442, +0.134] | 325 (40.0%) |
| SOLUSDT | 60m | L | 2% / 2.5% | 202 | -0.467% | -0.253% | -0.213 | [-0.668, +0.097] | 105 (52.0%) |
| SOLUSDT | 60m | L | 3% / 3.0% | 202 | -0.529% | -0.175% | -0.354 | [-0.804, +0.055] | 86 (42.6%) |
| SOLUSDT | 60m | S | 2% / 2.5% | 307 | -0.535% | -0.258% | -0.277 | [-0.494, -0.017] | 174 (56.7%) |
| SOLUSDT | 60m | S | 3% / 3.0% | 307 | -0.519% | -0.115% | -0.405 | [-0.702, -0.075] | 130 (42.3%) |

The CSV contains both historical periods, both costs, full coverage, stop counts, profit factors, win rates, net R and cost attribution. Returns and intervals in CSV are decimal fractions; multiply by 100 for percentages or percentage-point differences. Control stop counts are raw reused draw counts; use control_stop_rate for the equally weighted comparison. They must not be presented as independent executed trades.

## Reproducibility and next step

- Protocol frozen at `16a5b19`, runner at `19ab4e6`, before scoring.
- Six original input hashes verified; no 2026 scored and no parameter retuning.
- All 72 chronological reference rows reproduce counts and means; maximum mean-return discrepancy is 9.81e-17. This check does not make opportunity returns a portfolio backtest.
- Two focused tests passed for outcome-blind matching, exclusion of original signals, minimum control count, unequal control-pool weighting and cost-component identity.
- Report verification checked 184 frozen output hashes and independently reconciled all 144 comparison rows with their saved outcomes, pairs and control weights. The outcome cache has 2,574,076 rows including both policies and both cost scenarios; it is not an independent sample of that size.
- The private checkpoint contains every outcome, draw, matched pair, exclusion, source file and previous study. Public GitHub contains reports, protocols and aggregates. Original zone-row identity remains unproven.

The planned next experiment is profit protection on unchanged reference entries: freeze one causal profit-lock rule, keep the initial stop/target and regime policy fixed, then replay position occupancy and measure profits retained against winners cut short. It remains pending. The present results do not justify another stop-width grid or promotion of zone rejection as an established entry edge. A different entry hypothesis requires a separate frozen design and unused confirmation data. Cloud settings and trading approvals were not changed.
