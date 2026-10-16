# FROZEN PRE-REGISTRATION: xs_realized_skew_weekly (Munha, 2026-10-16)

Paper only. Live off. Not Inbox. No outcome on main (2023-10-15..2025-06-30), on the H2-2025 holdout, or on 2026 has been computed or read by me.

## 0. Pinned inputs (sha256 verified 2026-10-16)
| File | sha256 |
|---|---|
| Proposal `briefs/proposals/2026-10-16_shumba_proposal_xs_realized_skew_weekly.json` | 7512025efe7ba96b5b66c1560df4402db6a44b8537a2581d676da0455f331f4e |
| LOCK `briefs/locks/xs_realized_skew_20261016/LOCK_xs_realized_skew_weekly.md` | 974a05adf510dfca0e0c6562ff089282ae85e274edfaa479138915efe079efce |
| Tape C `research/universe96_full_history_20261016/SHA256SUMS` | ab4472210b9f4ef357fabaa746d7fa20f0eec9b781fafe52461df378be44acd9 (`sha256sum -c`: 0 failures) |
| perp_1h.parquet / membership_pit.parquet | e974ef5a… / 3f856213… |

Housekeeping: the proposal's `filed_at` reads 11:45 GST, but the LOCK header reads ~11:40 GST. Garwe should confirm the file order. It changes no gate.

## 1. Frozen cell (verbatim from LOCK 974a05ad)
> Cell (frozen, no retune): Mon 00:00 UTC rebalance. RSK = realized skew of the 168 1h log returns ending at the bar closing <= t, needing >=150 bars, >=31d history, and PIT listing. Long bottom tercile, short top tercile, equal-weight, dollar-neutral, 7d hold, 12% per-coin stop, next_open fill, 0.31% per leg-trade.

Feature (proposal): RSK = sqrt(N)·Σr³/(Σr²)^1.5. Windows: main 2023-10-15..2025-06-30 (90 week-clusters), holdout 2025-07-01..2025-12-31 (26), and 2026 veto-only.

**Unit of analysis:** the weekly net spread return, which is the long-leg EW mean minus the short-leg EW mean, net of costs on realized leg changes and stops. One ISO week counts as one cluster. Trades are leg-trades. PF is computed on weekly net spread returns.

## 2. MDE, power, turnover, cost
- **Power on main:** n = 90 week-clusters, one-sided α = 0.05, normal approximation. The MDE at 80% power is d = 0.262. At Garwe's d = 0.295, power is 0.876.
- **Turnover:** measured on pre-2023-10-15 bars only (feature/membership only): 122 rebalances from 2021-06-14 to 2023-10-09, averaging 16.1 names per leg. The share of positions changed each week is **0.621**. This matches the LOCK's ~33/54 = 0.61. Main will be reported as *realized* turnover; I expect about 27 names per leg.
- **Cost drag on the spread:** 2 legs × 0.31% × 0.62 = **0.385%/wk**, before stop exits.
- **Spread SD (planning, pre-cut):** 4.85%/wk at 16 names per leg. Scaled to 27 names per leg (√(16/27)), this is about 3.7%/wk.
- **Net effect needed at d = 0.295:** about 1.10–1.43%/wk (Shumba's own table gives 0.89–1.18%/wk at an SD of 3–4%). Adding the cost drag, the **gross spread needed is about 1.5–1.8%/wk, or roughly 75–95% a year**. The cost drag alone is about a quarter of the gross requirement.
- **Planning-sign check (pre-cut, disclosed):** the gross no-stop next-open spread over 121 pre-cut weeks was **−0.75%/wk (d = −0.15)**. That is the wrong sign for the Jia–Liu–Yan claim. It is a planning input, not a count, and it does not change the cell.
- **P(pass at all hard gates on main): about 3%.** The reasons are: the required gross edge is very large; the cost drag is 0.385%/wk; the pre-cut sign is negative; and the nearest neighbour MAX (ρ = 0.475) had no gross edge before the cut in my screen 9342cc4d. This is below the CEO's 10% slot rule. I am stating it, not vetoing on it; the LOCK stands.

## 3. Beats-random
- **Null:** at each main rebalance, draw random long and short sets of the same size k from the same PIT-eligible names.
- **Churn matching:** carry the previous random book forward and re-draw exactly the realized number of changed names on each leg. This gives the same realized turnover and the same cost.
- **Treatment:** apply the same 12% stop, next_open fill and 0.31% per leg-trade.
- **Test:** 2,000 permutations with seed 20261016. The p-value is (1 + #{random mean net weekly spread ≥ observed}) / 2001. The cell must be one-sided below 0.05.

## 4. Hard gates on main (all required, net at 0.31% per leg-trade unless stated)
- PF ≥ 1.15
- Week-cluster bootstrap 95% CI of the mean weekly net spread excludes zero, positive side (10,000 resamples)
- Beats-random p < 0.05
- At least 30 OOS leg-trades and at least 30 week-clusters
- At least 50% of quarterly folds profitable
- Max DD < 25% on the compounded weekly net spread equity
- Measured RT cost is reported as a secondary column. It is never used to pass a gate.

## 5. Holdout (H2 2025)
One look only. It is opened only after main outputs are hashed and only if main passes all of §4. Pass requires a positive week-cluster mean net spread and PF ≥ 1.15. There is no 30-week floor; 26 week-clusters are expected.

## 6. 2026
Veto-only. With at least 10 week-clusters, a mean net spread ≤ 0 is a veto. With fewer than 10 week-clusters it is report-only. It can never rescue a FAIL.

## 7. Disclosures
- **Brian's edge sweep e3acd03f** read MAX outcomes over 2021–2025, which includes main and the holdout. RSK vs MAX7 has ρ = 0.475 and Jaccard = 0.393. That is under the pre-stated 0.50 line, so it is cleared, but it is a **partial information leak**. Garwe's LOCK ruling (1) says the paper's mechanism runs through extreme up days, and that the cell is cleared but not certified independent.
- **My published-effects screen 9342cc4d** read MAX (and IVOL and weekend) outcomes only on bars before 2023-10-15. No skewness outcome was computed there.
- **This prereg** read one pre-2023-10-15 planning outcome, the gross spread sign and SD in §2. Script `research/xs_realized_skew_prereg_20261016/plan_pre_cut.py`; outputs `plan_pre_cut.json` and `plan_pre_cut_weekly.csv`.
- **Survivorship:** about 302 delisted perps are absent. The grade is capped at B, as Garwe ruled. Renames are unmapped.

## 8. Order of work
1. Chiremba builds the spread harness on the pinned CostModel and hashes the scorer.
2. Garwe ACKs that scorer hash. No metric is read before the ACK.
3. Main is run, and its outputs and verdict are hashed.
4. The holdout gets one look, only if main passes.
5. The 2026 veto is read.

A FAIL at any stage seals xs_realized_skew_weekly: no retune, no sign flip, no subset, no window or stop change, and no re-file as a variant. Every gate is unchanged. Live stays off.
