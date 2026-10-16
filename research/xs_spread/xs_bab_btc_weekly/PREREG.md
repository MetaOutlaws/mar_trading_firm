# FROZEN PRE-REGISTRATION: xs_bab_btc_weekly (Munha, 2026-10-16)
Paper only. Live off. Not Inbox. I have not computed or read any outcome on main (2023-10-15..2025-06-30), the H2-2025 holdout or 2026.

## 0. Pinned inputs (sha256 verified 2026-10-16)
| File | sha256 |
|---|---|
| Draft rules `briefs/proposals/2026-10-16_shumba_DRAFT_xs_bab_btc_weekly.json` | 1ca85938af74ab45811089325fcae03ce4b0032bab7ccdbdd0f12cc2e7075a10 |
| LOCK `briefs/locks/xs_bab_btc_20261016/LOCK_xs_bab_btc_weekly.md` | 76da2e9e677579305bb61fc36f17eaa6f37e67efb878bb92787bc46dfeaecdc6 |
| Kill file `research/bab_btc_20261016/PRESTATED_THRESHOLD_bab.md` | 12dd3ae0… |
| Counts `bab_counts.py` / `bab_counts_out.json` | e682ddd9… / ebb5e3ef… |
| Tape C SUMS (universe96) | ab447221… (check passed); perp_1h e974ef5a…, membership_pit 3f856213… |
| Cost sampler SUMS / Cost Part 2 | e1ac28e7… / 1e016bb3… |

**Timestamp issue:** the draft's `frozen_at` field reads 15:40 GST, but Garwe verified the file mtime as 15:12:31 and the LOCK is ~15:20. The field is probably a typo; Garwe should confirm. It changes no gate.

## 1. Frozen cell (verbatim, draft 1ca85938 "rules")
> rebalance: Monday 00:00 UTC (W-MON). feature: beta_i = OLS slope of 90 daily log returns (closes sampled at 00:00 UTC) of perp i on BTCUSDT, min 60 valid pairs; all inputs strictly before the rebalance bar close. universe: tape C 96 names (SUMS ab447221), BTCUSDT excluded. eligible: PIT listed at t via membership_pit, >=31d perp history, valid beta. sort: terciles by beta. long: bottom tercile (low beta). short: top tercile (high beta). weighting: equal-weight within leg; legs scaled to be ex-ante beta-neutral per Frazzini-Pedersen (long notional 1/mean_beta_L, short 1/mean_beta_H, normalised to $1 gross per side on average), per-side leverage ratio capped at 3. hold: 7d to next rebalance. stop: 12% per coin from entry; re-entry only at next rebalance. fill: next_open. cost: 0.31% per leg-trade. ts_rule: features strictly before bar close.

LOCK 76da2e9e additions: funding is included on both legs and never zero-filled, and net dollar exposure, BTC funding and costs are in the P&L.

**P&L unit:** the weekly net book return per $1 average gross per side. It is w_L·mean(long leg returns) − w_H·mean(short leg returns), **including the net dollar exposure (w_L − w_H) as it falls**, plus funding paid or received on every leg, minus 0.31% × traded notional (every entry, exit, stop and rebalance-weight change). The cluster is the ISO week.

### Cost levels
1. **Official: 0.31% per leg-trade on traded notional.** All hard gates bind at this level.
2. **Measured RT, reported only.**
   - Tsuro's sampler covers BTC, ETH and SOL only. Tape-C alts are unmeasured.
   - The secondary column uses 0.181% per leg-trade, the SOL conservative p90 RT (Part 2 1e016bb3), as an alt proxy. It is labelled "proxy, alts unmeasured".
   - **Veto:** if the measured column and the official column disagree in sign, that is a veto. A measured-level result never rescues a FAIL at 0.31%.

## 2. MDE, power, drag, P(pass)
- **Week-clusters:** n = 90 on main (283.9 leg-trade entries a year; a median of 82 eligible names; about 26 names per leg).
- **MDE:** one-sided α = 0.05, 80% power, normal approximation, gives d = **0.262**.
- **Planning input (disclosed):**
  - Script `research/xs_bab_prereg_20261016/plan_pre_cut.py`, tape C, bars before 2023-10-15 only.
  - Sample: 114 weeks from 2021-08-02 to 2023-10-02, about 16 names per leg. Price-only, with no stop and no funding.
  - Results:
    - SD of the weekly gross spread: 5.62%
    - Mean gross: +0.27% a week (d ≈ 0.05)
    - Mean weights: long 1.22, short 0.78, so the book is net **long about $0.44**. The 3x cap never bound.
    - Realized traded notional: about 0.46 per week, giving cost drag of about **0.14% a week** at 0.31% (about 0.08% at the proxy).
    - Funding drag on the net-long exposure: roughly 0.05–0.1% a week at typical +0.01%/8h. This is an estimate, not measured here.
- **Required edge:** at main's larger universe (about 26 per leg), SD scales to about 4.4% a week. The MDE at d = 0.262 is then **about 1.15–1.47% net a week**, so the **gross needed is about 1.3–1.7% a week** against a total cost-plus-funding drag of about 0.2–0.25% a week. Cost is a minor share; variance is the binding constraint.
- **Power:** at the planning d ≈ 0.05, power is about 15%.
- **Additional constraints:**
  - The LOCK's extra gate (no losing regime) adds failure paths.
  - The net-long $0.44 means a 2024-25 alt bear could break DD even when beta-neutral ex ante.
  - BAB in crypto mostly loads on the low-IVOL and size factors. Sealed low-IVOL scored −0.05% a week on main (per the LOCK).
- **P(pass at all hard gates on main): about 4%.** That is below the CEO's 10% slot rule and below Shumba's ~10% prior. I state it but do not veto on it; the LOCK stands.

## 3. Beats-random (turnover-matched)
- **Null:** at each main rebalance, draw random rank-splits of the same PIT-eligible set.
- **Matching:**
  - Same name count per leg (k, k).
  - Each leg is weighted by the same Frazzini-Pedersen formula using the **random** legs' mean betas.
  - Same 3x per-side cap, same 12% stop, next_open fill and funding.
  - Realized turnover is matched: the previous random book is carried forward, and exactly the realized number of names changed on each leg is re-drawn.
  - Cost is the same 0.31% per traded notional.
- **Draws:** **2,000** permutations (the draft says 1,000 draws; 2,000 is the desk standard and the same test), seed 20261016.
- **Test:** one-sided p = (1 + #{random mean ≥ observed}) / 2001. Pass requires p < 0.05.

## 4. Hard gates on main (net at 0.31%, funding included)
- PF ≥ 1.15
- Week-cluster bootstrap 95% CI of the mean weekly net excludes zero on the positive side (10,000 resamples)
- Beats-random p < 0.05
- At least 30 OOS leg-trades and at least 30 week-clusters
- At least 100 leg-trades a year (draft gate)
- At least 50% of quarterly folds profitable
- Max DD < 25% on compounded weekly net equity
- **No losing regime (LOCK).** Regime is the BTC 4h EMA50/EMA200 with a ±1% band (BULL/BEAR/CHOP), labelled at the last closed 4h bar at or before the rebalance. A regime with at least 5 weeks and a mean weekly net < 0 fails this gate. A regime with fewer than 5 weeks is report-only.
- Measured-RT sign veto as in §1.

## 5. Holdout and 2026
- **Holdout H2 2025** (26 weeks): one look only, after main outputs are hashed and only if main passes. Pass requires a positive week-cluster mean net and PF ≥ 1.15. No 30-week floor.
- **2026 is veto-only** (41 weeks): with at least 10 week-clusters, a mean ≤ 0 vetoes. Below 10 it is report-only.

## 6. Disclosures and overlap
- **Kill means on main (feature-only, bab_counts_out ebb5e3ef):**
  - low-IVOL: J 0.26, ρ 0.196
  - xs_realized_skew (sealed FAIL dead78cb): J 0.266, ρ 0.177
  - MAX7: J 0.163, ρ 0.357
  - momentum: J 0.305, ρ 0.294
  - size: J 0.287, ρ 0.237
  - amihud: J 0.263, ρ 0.148
  - **btc_shock gate short: J 0.454.** This is under the pre-stated 0.50 line, and Garwe ruled it is not a variant. It is near the line, and btc_shock's high-beta short is a sealed FAIL (+0.001R).
- **alt_btc_* families:** BAB uses a 90-day OLS beta on BTC, not an alt/BTC price ratio (alt_btc_ratio*) or a lag/reclaim (alt_btc_lag_reclaim, NOT FILED).
  - No overlap statistic against alt_btc_* exists in the counts, so this is a **gap**.
  - alt_btc_residual_stretch_fade also uses a BTC regression, but it trades the residual level, not the slope.
  - I recommend Garwe confirm that no alt_btc_* comparator needs a count. I did not compute one, because that would be a new count on main features.
- **Outcome leaks:**
  - The LOCK says low-IVOL outcomes were viewed on main, "Munha aa19efc8, −0.05%/wk". **I cannot find a file with sha aa19efc8 on the box.** My own IVOL read (9342cc4d) was pre-2023-10-15 only, on the 26-name tape, and it found IVOL's edge sat in the short-high-IVOL leg, which correlates with the high-beta short. Garwe should confirm the source of aa19efc8. It is disclosed either way.
  - The xs_realized_skew main FAIL (dead78cb) was read today; ρ 0.177 to BAB.
  - This prereg made one pre-cut planning read (§2).
- **Survivorship:** tape C has 96 names, and delisted perps are absent (tape D is not in the frozen universe). That likely flatters the short high-beta leg. Grade is capped at B.
- **Exposure:** the legs are not dollar-neutral (net long about $0.44 in planning), so net exposure is in the P&L.

## 7. Order of work
1. Brian gives a CEO YES for the harness.
2. Chiremba hashes the harness and scorer.
3. Garwe ACKs those hashes. No metric is read before the ACK.
4. Main is run, and its outputs and verdict are hashed.
5. The holdout gets one look, only if main passes.
6. The 2026 veto is read.

A FAIL seals xs_bab_btc_weekly: no retune of the beta window, cap, terciles, stop or hedge, no sign flip, no leg or regime subset and no re-file as a variant. Every gate is unchanged. Live stays off.
