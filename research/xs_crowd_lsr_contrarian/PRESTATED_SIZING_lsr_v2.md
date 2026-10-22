# xs_crowd_lsr_contrarian v2: PRESTATED SIZING ADDENDUM (Shumba)
Frozen at box time 2026-10-22T07:16:13+0400 GST (UTC+4); this equals the file's box mtime. Paper only, live off.
FROZEN BEFORE ANY OUTCOME READ: no return of this cell, of any long/short-ratio-sorted portfolio, or of any L-tercile leg has been computed or read in any window. Inputs used: L features (raw tape, as in lsr_counts_v2.py ae5ed1a3), tape C funding (carry, b8e28b42), and price returns of RANDOM baskets only (seed 20261016), pre-main window only.
Scope: this addendum changes POSITION SIZING ONLY. Signal, universe, terciles, timing, fill, 7d hold, 12% stop, 0.31% per leg-trade cost, windows, the v2 exclusion and all gates/kill rules in PRESTATED_THRESHOLD_lsr_v2.md (5e1fac2c) are unchanged.

## Sizing rule
- Fixed gross exposure G = 1.18 x equity at every kept rebalance: long leg 0.59 x equity, short leg 0.59 x equity (dollar-neutral).
- Equal weight within each leg: per-name weight = 0.59 / n_leg of equity (1.28% at the main median n_leg = 46; 2.46% at the min 24; 0.80% at the max 74). Holdout (median 80.5/leg) uses the same G.
- A stopped name's notional goes to cash until the next kept rebalance (no redistribution). No other sizing change.

## Calibration (pre-data, DD gate 25%, target expected max DD about 16.5%)
- Vol estimate: for each pre-main Monday t (2022-01-03..2023-10-02, 92 weeks, tape C PIT-eligible names, median N 60.5, min 37), weekly cross-sectional variance s_t^2 of simple 7d returns (close t to close t+7d). A random equal-weight k=46 long / k=46 short basket per unit gross returns 0.5*(meanL - meanS), so Var = 0.25*2*s_t^2/46 (iid draw, no finite-population correction because pre-main N < 92). sigma_w = sqrt(mean_t Var) = 1.211% per week per unit gross. (Empirical cross-check: 200 random permutation draws/week at k = min(46, N/2), median k 30, gave 1.545%, consistent with 1.211 x sqrt(46/30) = 1.50%.) Signal-independent; no cell returns.
- Max-DD formula: E[MDD] ~= sqrt(pi/2) * sigma_w * G * sqrt(T), the zero-drift Brownian limit of Magdon-Ismail et al. (2004), T = 85 kept main weeks. Assumptions: zero drift, iid weekly returns, no stops, continuous-monitoring limit (conservative versus weekly marks).
- Solve: G = 0.165 / (1.2533 * 0.01211 * sqrt(85)) = 1.179, set to 1.18.
- Monte Carlo check (20,000 paths, 85 weeks, seed 20261016; weekly sd = bootstrap of pre-main dispersion x sqrt(0.5/46), Gaussian noise): at G = 1.179, zero drift: E[MDD] 13.7%, median 12.7%, P(MDD > 25%) 4.9%. Drift of -0.11%/wk per unit gross (zero gross edge, trading cost only, no funding credit): E[MDD] 18.4%, median 17.7%, P(MDD > 25%) 18.2%. So the expected max DD is 13.7-18.4% (analytic 16.5%), which brackets the 15-18% band.
- Known biases (disclosed, not adjusted): (1) a tercile-sorted book can have systematic factor tilts (beta, size; kill rho vs size30 0.30, vs BAB beta 0.20) that a random basket lacks, so realized vol may exceed sigma_w. (2) 12% stops truncate single-name tails. (3) The main universe (median 140) is wider than pre-main (60.5), which does not change the k = 46 formula.

Sources: lsr_dacc_pit_and_sizing_v2.py (53cf2f17) -> lsr_dacc_pit_and_sizing_v2_out.json (599ecb53); lsr_munha_fields_v2.py (e651b094) -> lsr_munha_fields_v2_out.json (86d82986).
Nothing here may change after hashing.
