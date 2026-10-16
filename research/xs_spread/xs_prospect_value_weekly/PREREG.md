# FROZEN PRE-REGISTRATION: xs_prospect_value_weekly (Munha, 2026-10-16)
Paper only. Live off. Not Inbox. I have not computed or read any outcome on main (2023-10-15..2025-06-30), the H2-2025 holdout or 2026. The only return read made for this prereg is the pre-cut planning read in §2 (bars strictly before 2023-10-15).

## 0. Pinned inputs (sha256 verified 2026-10-16)
| File | sha256 |
|---|---|
| Draft rules `briefs/proposals/2026-10-16_shumba_DRAFT_xs_prospect_value_weekly.json` | b815ed4db98f8b72e17803742434d51cbb4437278f2d5ddfb42f060bda783d2e |
| LOCK `briefs/locks/xs_prospect_value_20261016/LOCK_xs_prospect_value_weekly.md` | a712319ac9175e2e41befbbcae4c0dee7d18a3d077e14f3fa1e1bae38d702c15 |
| Kill file `research/xs_prospect_value_weekly_20261016/PRESTATED_THRESHOLD_tk.md` | 62e906ffd6a2f359559c1b8dde525d4778419cd8fc0ce9f81409b3b9ce6f8f73 |
| Counts `tk_counts.py` / `tk_counts_out.json` | c143f354… / 716d4ea8… |
| Garwe clone check `garwe_clone/clone_check_ret60.py` / `clone_out.json` | 1d232515… / 988d3e43… |
| Tape C SHA256SUMS (universe96) | ab4472210b9f4ef357fabaa746d7fa20f0eec9b781fafe52461df378be44acd9 |
| Tape C perp_1h.parquet / funding.parquet / membership_pit.parquet | e974ef5a… / b8e28b42… / 3f856213… |
| Planning script `research/xs_prospect_prereg_20261016/plan_pre_cut.py` | e96b83d1f898e8776e1ab472f4225bd624adeb593bce484ce2645298389720bc |

**Timestamp note:** the draft's `frozen_at` and kill file header say ~17:45 GST; Garwe's LOCK records file mtimes 17:32:25, before tk_counts.py (17:32:38). LOCK rules the label a typo; box mtime governs. No gate changes.

## 1. Frozen cell (verbatim, draft b815ed4d "rules")
> rebalance: Monday 00:00 UTC. feature: TK value of past 60 daily log returns (min 50), see prestated file. universe: tape C 96 (SUMS ab447221), PIT membership, >=31d history. long: bottom TK tercile. short: top TK tercile. weighting: equal-weight, dollar-neutral. hold: 7d. stop: 12% per coin; re-entry next rebalance. fill: next_open. cost: 0.31% per leg-trade. ts_rule: features strictly before bar close.

Feature definition (verbatim, prestated 62e906ff): past 60 daily log returns (00:00 UTC closes, last uses bar opened Sun 23:00; min 50), raw (not market-adjusted), each obs prob 1/n; value v(x)=x^0.88 for x>=0, -2.25(-x)^0.88 for x<0; cumulative decision weights with w+(p)=p^0.61/(p^0.61+(1-p)^0.61)^(1/0.61), w-(p) same with 0.69. TK = sum of weighted values. BTCUSDT included.

Windows: main 2023-10-15..2025-06-30; holdout 2025-07-01..2025-12-31; 2026 veto only.
LOCK a712319a additions: funding included, never zero-filled, ex-ante gap rule applies; 0.31%/leg; harness must hash the countersign file into the manifest (549deb0b fix); grade cap B; gate "no losing regime".

**P&L unit:** weekly net book return on $1 long + $1 short (dollar-neutral; the ~0 net exposure is booked as it falls, including drift from stops). = mean(long leg) − mean(short leg) + funding received − funding paid on every leg (actual 8h prints over held hours) − 0.31% × traded notional (every entry, exit, stop exit, stop re-entry, rebalance). Stopped coins sit in cash until next rebalance. Cluster = ISO week.

### Cost levels
1. **Official 0.31% per leg-trade on traded notional — binds all hard gates.**
2. **Measured-RT proxy, report-only:** 0.158% per leg-trade = mean of BTC 0.135% and SOL 0.181% measured RT (Tsuro sampler; alts unmeasured, labelled "proxy"). **Sign-flip veto:** if the proxy column and the official column disagree in sign of mean weekly net, that vetoes. The proxy never rescues a FAIL at 0.31%.

## 2. MDE, power, turnover, drag
- **Clusters:** n = 90 ISO weeks on main; 477.6 leg-trade entries/yr; median 83 eligible; ~26.7 names/leg (tk_counts_out, features only).
- **MDE:** one-sided α=0.05, 80% power, normal approx: d = (1.645+0.842)/√90 = **0.262** (weekly net mean / SD).
- **Planning read (disclosed):** `plan_pre_cut.py` e96b83d1, tape C, bars strictly before 2023-10-15; 118 weeks 2021-07-05..2023-10-02, ~15.9 names/leg; exact frozen TK feature and terciles, next_open fill, **12% stop simulated on 1h highs/lows** (exit at stop level, re-entry next rebalance), funding from tape C prints.
  - Stops: **10.1 stop exits per week, 34% of positions/week.**
  - Realized traded notional: **1.33 per week per $1/side** (≈ 2.0× the 0.66 the rule implies without stops). This undercounts slightly (a stopped name that stays in its tercile also books an exit), so I plan on **1.33–1.6**. Annualised that is ~69–83× notional.
  - **Cost drag at 0.31%: 0.41–0.50% /wk**; at the proxy 0.21–0.25% /wk.
  - Funding: book paid **0.10% /wk** net pre-cut (0 gaps pre-cut on tape C).
  - **Total drag ≈ 0.51–0.60% /wk.**
  - Gross spread SD 7.33% /wk at 16/leg; scaled to ~27/leg ≈ 5.7% (optimistic, assumes idio diversification) → planning SD band **5.7–7.3% /wk**.
  - Pre-cut mean gross spread **+0.14% /wk** (long leg −0.08, short leg +0.22), i.e. **net ≈ −0.4% /wk**.
- **Required edge:** MDE net = 0.262 × (5.7–7.3) = **1.5–1.9% net /wk**, so **gross needed ≈ 2.0–2.5% /wk** against 0.5–0.6% drag. Cost+funding is ~25% of the needed gross; variance remains binding but cost is now material (stops doubled turnover).
- **Paper benchmark:** Chen et al. 2022: 1 xs-SD TK = −0.71% /wk (1,573 coins, 2014–20). A tercile spread is ~2 SD → ~1.4% gross /wk, ~0.85% net after drag: d ≈ 0.12–0.15, power ≈ 25–35% even if the published effect survived fully on 96 liquid perps after 2020. At the pre-cut planning mean, power < 5%.

## 3. Beats-random (turnover-matched)
- Null: each main rebalance, random rank-split of the same PIT-eligible set into legs of the same size k (same names-per-leg count), equal-weight, dollar-neutral, same 12% stop on 1h path, re-entry next rebalance, next_open fill, actual funding, 0.31% on traded notional.
- Turnover matching: carry the previous random book forward and redraw exactly the realized number of names changed on each leg that week (stop re-entries follow the random book's own stops).
- **2,000 permutations, seed 20261016** (draft says 1,000; 2,000 is desk standard, same test).
- One-sided p = (1 + #{random mean weekly net ≥ observed}) / 2001; pass requires p < 0.05.

## 4. Hard gates on main (net at 0.31%, funding included)
- PF ≥ 1.15 (weekly net book returns).
- Week-cluster bootstrap 95% CI of mean weekly net excludes zero, positive side (10,000 resamples).
- Beats-random p < 0.05.
- ≥ 30 leg-trades and ≥ 30 week-clusters; ≥ 100 leg-trades/yr (draft gate).
- ≥ 50% of quarterly folds profitable.
- Max DD < 25% on compounded weekly net equity.
- No losing regime (LOCK): BTC 4h EMA50/EMA200 ±1% band (BULL/BEAR/CHOP) at the last closed 4h bar ≤ rebalance; regime with ≥5 weeks and mean weekly net < 0 fails; <5 weeks report-only.
- Funding-gap ex-ante rule per LOCK; gaps reported by leg; never zero-filled.
- Proxy-cost sign-flip veto (§1).

## 5. Holdout and 2026
- **Holdout H2 2025 (26 weeks):** one look, only after main outputs + verdict are hashed and main PASSes. Pass = positive week-cluster mean net and PF ≥ 1.15. No 30-week floor.
- **2026 veto-only:** ≥10 week-clusters with mean ≤ 0 vetoes; <10 report-only.

## 6. REPORT-ONLY: 60d return partialled out
- Each main week t: cross-sectional OLS over eligible names, r_{i,t+1} (7d next_open→next_open, gross price) = a_t + b_t·z(TK_i,t) + c_t·z(ret60_i,t) + e, with ret60 = sum of the same 60 daily log returns (min 50), both z-scored cross-sectionally.
- Report mean b_t and its t-stat on week-clusters (Fama–MacBeth, Newey–West lag 1 also shown), and the same with TK alone.
- Garwe's features-only check: ρ(TK, ret60) = 0.643, J 0.498. Not a gate, not a kill, never rescues or vetoes. A main PASS whose TK coefficient has t < 1 after partialling is flagged "momentum-explained" for Brian.

## 7. Disclosures and overlap
- **Adjacent leak:** Brian's edge sweep e3acd03f showed xs_momentum_3w at −24.6 bp/wk net on 2024–25, i.e. on this main window. Long low-TK ≈ long past losers, so the known momentum loss favours this cell's sign. Sign is from Chen et al. 2022, not the sweep, but the lucky-direction risk is real.
- **Overlap on main, features only (tk_counts_out 716d4ea8):** sealed xs_realized_skew (FAIL): J 0.271, ρ 0.192; MAX7 (max_lottery, NOT FILED): J 0.135, ρ 0.202; sealed xs_bab_btc_weekly (FAIL, beta90): J 0.340, ρ 0.355; mom3 J 0.363 ρ 0.424; vol60 J 0.350 ρ 0.362; ivol J 0.249 ρ 0.173; size30 0.294/0.262; amihud 0.302/0.289; ret60 (clone check) 0.498/0.643. All under the 0.50 kill line; ret60 J is at 0.498.
- **Sealed outcomes read today:** xs_realized_skew main FAIL and xs_bab_btc_weekly main FAIL (both read before this prereg). BAB's short high-beta leg lost; TK-high overlaps high-beta at J 0.34. Disclosed.
- **My screens:** 9342cc4d (`briefs/2026-10-16_munha_published_effects_ranking.md`) and aa19efc8 (`research/published_effects_explore_20261016/ivol_3030/explore_3030.py`) — both found on the box, both pre-cut only (bars < 2023-10-15). Correction to the BAB prereg, which said aa19efc8 could not be found: it is the IVOL 30/30 explore script, pre-cut.
- **Survivorship:** tape C 96 omits delisted perps (tape D not in universe). High-TK (lottery-like) short leg likely flattered. **Grade cap B.**
- **Stops:** pre-cut 34%/wk of positions stopped; the stop rule, not the signal, dominates turnover. Not retunable.

## 8. Order of work
1. Brian CEO YES for the harness.
2. Chiremba hashes harness + scorer (countersign hashed into manifest).
3. Garwe ACKs the scorer hash. No metric read before ACK.
4. Main runs; outputs + verdict hashed; Garwe seals.
5. Score; holdout one look only on main PASS; then 2026 veto.

A FAIL seals the xs_prospect_value class: no retune of window, γ/λ parameters, terciles, stop, sign flip, leg/regime subset, or re-file as a variant. Gates unchanged. Live off.

## 9. Honest P(pass)
**P(pass all main hard gates) ≈ 3%.** Pre-cut net is negative (≈ −0.4%/wk), drag is 0.5–0.6%/wk because stops double turnover, the published effect (if intact) gives ~25–35% power, the momentum-adjacent tailwind on 2024–25 is the main upside, and the no-losing-regime and DD gates add failure paths. Below the 10% slot rule and below Shumba's ~8% draft prior; stated, not a veto.
