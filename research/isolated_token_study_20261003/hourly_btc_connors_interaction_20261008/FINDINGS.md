# Hourly compression: BTC / Connors interaction results

Combination improves historical efficiency but adds no 2025 trades or improvement over Connors alone. The strict predeclared criterion therefore FAILS. Retain the combined rule as an exploratory historical candidate, with standalone Connors still the latest owner-approved PAPER preference.

Protocol committed before scoring: `6d2d4018935efb439e9acfe3e8b299976f2496f1`. One successful `results_v1`. Same BTC/ETH/SOL 1h entries, SL2%/TP2.5%, fees/funding, membership and portfolio admission rules. No 2026 outcome scored. This is a replay of verified cached minute-path opportunities, not a new minute-path simulation.

## All four arms

| Period | Arm | Trades | Stops | Targets | Win rate | Base mean net | Stressed mean net |
|---|---|---:|---:|---:|---:|---:|---:|
| 2022–24 | Original baseline | 97 | 44 | 53 | 54.64% | +0.2268% | +0.1037% |
| 2022–24 | BTC confirmation | 89 | 37 | 52 | 58.43% | +0.4017% | +0.2825% |
| 2022–24 | Connors RSI | 60 | 26 | 34 | 56.67% | +0.3193% | +0.1952% |
| 2022–24 | BTC + Connors | 56 | 22 | 34 | 60.71% | +0.5051% | +0.3849% |
| 2025 | Original baseline | 36 | 14 | 22 | 61.11% | +0.4992% | +0.3685% |
| 2025 | BTC confirmation | 35 | 13 | 22 | 62.86% | +0.5791% | +0.4505% |
| 2025 | Connors RSI | 19 | 5 | 14 | 73.68% | +1.0580% | +0.9205% |
| 2025 | BTC + Connors | 19 | 5 | 14 | 73.68% | +1.0580% | +0.9205% |

Stress doubles slippage only. These are average returns on trade notional; additive sums are not portfolio returns and are not leverage recommendations. Arms and cost cases overlap. Repeatedly reviewed 2025 is exploratory.

## Stops saved and winners sacrificed

- Versus Connors in 2022–24: exactly four stopped trades excluded, zero target winners lost, zero new or occupancy-displaced trades. Trades 60 to 56, stops 26 to 22, targets remain 34. Stressed mean rises from +0.1952% to +0.3849%.
- Versus Connors in 2025: identical 19 trades, five stops and 14 targets. BTC rejects no additional Connors-qualified trade. The 2025 incremental return is exactly zero.
- Versus the original baseline historically: directly excludes 23 stops and 19 targets, then admits one new ETH stop. Actual stops fall 44 to 22, targets 53 to 34. No displacement through changed occupancy.
- Versus BTC-only historically: excludes 16 stops and 18 targets, then admits one ETH stop. Mean improves, but stressed additive net sum falls from +0.251390 to +0.215525. Fewer trades can sacrifice total opportunity even when average quality improves.
- Versus the original baseline in 2025: excludes nine stops and eight targets. Versus BTC-only: excludes eight stops and eight targets. No new admissions or occupancy displacement.

## Incremental uncertainty

Paired 10,000-draw week-block bootstrap, including empty weeks. Intervals below are percentage-point changes in stressed mean net return. Unadjusted for multiple research attempts.

| Period | Both versus | Difference | 1-week 95% interval | 4-week 95% interval |
|---|---|---:|---:|---:|
| 2025 | Original baseline | +0.5520 pp | [-0.0245, +1.1654] | [+0.0846, +1.1300] |
| 2025 | BTC confirmation | +0.4700 pp | [-0.1221, +1.0859] | [-0.0130, +1.0511] |
| 2025 | Connors RSI | +0.0000 pp | [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| 2022–24 | Original baseline | +0.2811 pp | [-0.1575, +0.6891] | [-0.1612, +0.7137] |
| 2022–24 | BTC confirmation | +0.1024 pp | [-0.3107, +0.4876] | [-0.2962, +0.4824] |
| 2022–24 | Connors RSI | +0.1897 pp | [+0.0416, +0.3819] | [+0.0399, +0.3992] |

Historical incremental intervals versus Connors are positive at both block lengths, but comparisons versus BTC and the baseline span zero. The 2025 comparison versus BTC also spans zero at both lengths. Identical 2025 Connors trades yield [0,0] incremental intervals; this means no incremental information in this sample, not certainty of future equivalence.

The combined absolute stressed-mean intervals still span zero historically at both block lengths. In2025 the four-week interval is positive but the one-week interval spans zero, as with the identical Connors sample.

## Concentration and retained hypotheses

All four annual stressed means for the combination are positive (2022 +0.3511%, 2023 +0.6696%, 2024 +0.2845%, 2025 +0.9205%). All leave-one-token-out means are positive in both periods. Historical ETH remains negative; small subgroup samples and overlap still limit confidence. These are not independent confirmation.

The combination is now highest historical mean and tied highest 2025 mean among these four fixed arms, but it did not satisfy the predeclared strict improvement over each standalone in both periods. Do not rewrite that criterion after seeing the tie. There is no automatic switch to the combined rule.

Next: preserve H-EXT-REGIME-01 and H-RSI-REGIME-01 and freeze common causal trend/chop states before studying their conditional performance. Keep the BTC/Connors historical gain as H-BTC-CRSI-REGIME-01 (regime explanation unvalidated). Do not equate 2022–24 with trending or 2025 with chop. Wider-token and prospective confirmation remain separate gates; more tokens may share exposures and may not reproduce this edge.

## Approval, runtime and reproducibility

Owner approval for standalone Connors is recorded separately in `hourly_connors_filter_20261008/OWNER_APPROVAL.md`. Original scientific decision files stay unchanged. Runtime code matches 143 research opportunities and 143 trailing windows; 17 focused tests pass. DigitalOcean reports the Singapore VM active. This workspace cannot reach SSH; installation and scanning of Connors are NOT VERIFIED. The tested standalone installer and verification command are supplied. Latest observed original scan remains 2026-10-07T10:05:31.385232+00:00.

Inputs and both cached studies are hash-verified. Raw baseline cost rows reconcile exactly (286). All existing admitted arms reconcile (baseline 266, BTC 248, Connors 158 cost rows). Sixteen independent admission replays and twelve attribution checks pass. Full private checkpoint includes all paths, causal contexts and individual trades; public GitHub holds protocol, source and aggregate results.
