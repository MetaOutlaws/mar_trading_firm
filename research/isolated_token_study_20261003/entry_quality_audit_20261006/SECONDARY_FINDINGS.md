# Secondary entry timing findings — 6 October 2026

**The 1h and 24h diagnostics do not establish an entry edge or reverse the failed primary 4h gate.** Pooled favourable excursion is lower for zone signals than matched controls at both horizons and in both periods. Closing-return uplift is negative at 1h in both periods; the positive 24h uplift is much smaller in 2025.

The entry clocks remain 5m, 15m and 1h on BTC/ETH/SOL, long and short. The 4h regime is context. The 1h/4h/24h measurements are observation horizons, not forced trade exits. Rules are frozen in SECONDARY_PROTOCOL.md; the original primary protocol remains an immutable pre-run document.

## Pooled descriptive outcomes

| Horizon | Period | Measure | Matched | Signal | Control | Difference (pp) |
| --- | --- | --- | --- | --- | --- | --- |
| 1h | discovery | mae | 44,345 | 0.5627% | 0.5722% | -0.0095 |
| 1h | discovery | mfe | 44,345 | 0.4909% | 0.5316% | -0.0407 |
| 1h | discovery | ret | 44,345 | -0.0152% | -0.0117% | -0.0035 |
| 1h | validation | mae | 14,345 | 0.5431% | 0.5159% | +0.0272 |
| 1h | validation | mfe | 14,345 | 0.4633% | 0.4857% | -0.0224 |
| 1h | validation | ret | 14,345 | -0.0332% | -0.0154% | -0.0179 |
| 24h | discovery | mae | 44,275 | 2.7732% | 2.8244% | -0.0511 |
| 24h | discovery | mfe | 44,275 | 2.7232% | 2.7984% | -0.0752 |
| 24h | discovery | ret | 44,275 | 0.0533% | -0.1344% | +0.1877 |
| 24h | validation | mae | 14,345 | 2.6879% | 2.6375% | +0.0504 |
| 24h | validation | mfe | 14,345 | 2.4961% | 2.6760% | -0.1799 |
| 24h | validation | ret | 14,345 | -0.0978% | -0.1186% | +0.0208 |

Return is signed entry-open to final-close movement. MFE is maximum favourable movement; MAE is maximum adverse movement, expressed as a positive magnitude. A negative MFE difference is worse for the signals; a negative MAE difference is better. All are uncosted, full-window minute-bar observations. Excursion extremes do not imply attainable fills. Pooled means weight each matched signal equally and are descriptive; there is no pooled significance claim. Repeated and overlapping controls reduce independence.

## Per-cell uncertainty

Of 18 token/clock/direction groups, two have positive 1h closing-return uplift in both periods (ETH 5m long; SOL 15m short), and four have positive 24h uplift in both (BTC 5m long; SOL 5m long; SOL 5m short; SOL 15m short). None of the 2025 closing-return cells at either horizon has a positive lower bound under the ordinary 95% four-week-block interval. These secondary intervals are unadjusted across many comparisons. They cannot support selecting those groups or replace the primary simultaneous-interval gate, which remains 0/18 passed.

## Evidence and limits

117,310 matched signal-horizon observations; 2,251,014 control draws; 216 metric/cell/period/horizon result rows. The horizon-specific cohorts differ slightly because complete windows must stay inside the historical partition. The same causal features, volatility bins learned from 2022–24, matching strata and fixed seed are reused. All draws and exclusions are retained privately; `secondary_v1/secondary_summary.csv` contains means, coverage and both interval lengths.

One focused synthetic window test passed: exact endpoint, long/short symmetry and exclusion of bars outside the observation window. Frozen output hashes verified. Secondary runner freeze commit: `ad1f1c6`; protocol freeze commit: `536abb5`.

The matched costed-opportunity exit diagnostic has not run. No execution policy was changed by this measurement stage, and no 2026 observations were scored. Historical 2025 has already been reused and is not fresh validation.
