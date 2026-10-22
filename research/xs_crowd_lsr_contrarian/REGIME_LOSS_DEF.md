# FROZEN PRE-REGISTRATION: xs_sentiment_beta_mid_v2 (Munha, 2026-10-21)
Paper only. Live off. Not Inbox. Preregistration only: I computed no main-sample count and read no outcome on main (2023-10-15..2025-06-30), the H2-2025 holdout or 2026. My only return read is the pre-cut planning read in §2 (rebalances whose 7-day hold ends before 2023-10-15 00:00 UTC).

## 0. Pinned inputs (sha256 verified 2026-10-21)
| File | sha256 |
|---|---|
| LOCK `briefs/locks/xs_sentiment_beta_mid_v2_20261021/LOCK_xs_sentiment_beta_mid_v2.md` | a7077be3982c98991e5f1b9ca46a1d320e47a8d37fca4401f2e5adffba45d835 |
| Proposal (filing) `briefs/proposals/2026-10-21_shumba_proposal_xs_sentiment_beta_mid_v2.json` | b5a319b73fed76e9550f7385326e2a92093e162edd2f2599d5f62fdfbfd08082 |
| Draft v2 `briefs/proposals/2026-10-21_shumba_DRAFT_xs_sentiment_beta_mid_v2.json` | 50df2de5fdcd25e7f1ee1c1c8741a2cd90e4ad2ec62cdbf2c5ab2605a12f988d |
| Rules + kill v2 `research/xs_sentiment_beta_mid_20261020/PRESTATED_THRESHOLD_sb_v2.md` | 0c4c3e39ae73eb01526c1e97b4dd8eb86ca1db1116dc0178e7386c71c3641f1b (byte-identical to the proposal's `frozen_rules_verbatim`) |
| Counts v2 `sb_counts_v2.py` / `sb_counts_v2_out.json` | 8ddba7edd7b26cf5996d2c831c715549d11240857ca4aa3e0fc0fe1cadfb0d6a / f163baaa3746f3e40500a33e6b61351102d23ba10d4eab6c152b7f37dff23451 |
| Sanity `sb_sanity.py` | 449e611a5479b69cf18e384a574d00dd33bd03056027054d8fe1e847479c6344 |
| A1 preview `sb_counts_A1.py` / `sb_counts_A1_out.json` | bea1b3ce… / 066f7b41… |
| v1 (NOT_FILED) draft / rules / note | 282a096c… / b26a9aa5… / 7a455fe0… |
| **F&G tape** `research/fear_greed_20261020/SHA256SUMS` | 9e18129eac459d8fd0b809e4ea00413c8b0e50397d225e995c2768a233dfe63b (`sha256sum -c` 5/5 OK) |
| F&G fear_greed_daily.parquet / .csv / raw/fng_limit0.json.gz / pull_fng.py / COVERAGE.md | d47f2394… / 0ad5fd35… / aa085caa… / 143f9371… / d8716352… |
| **Tape C** `research/universe96_full_history_20261016/SHA256SUMS` | ab4472210b9f4ef357fabaa746d7fa20f0eec9b781fafe52461df378be44acd9 |
| Tape C perp_1h.parquet / funding.parquet / membership_pit.parquet | e974ef5a… / b8e28b42… / 3f856213… |
| **Planning script** `research/xs_sentiment_beta_mid_v2_prereg_20261021/plan_pre_cut.py` | 630fa7de6579f99132449680032625126dd00ac88208b93ffdc7dca76b56655f |
| Planning outputs plan_pre_cut.json / plan_weekly.csv | bec29dc2… / f2f74694… |

Timestamp note: the LOCK header says "~13:10 GST"; its box mtime is 13:04. Label only; box mtime governs, as in prior LOCKs.

## 1. Frozen cell (verbatim, rules + kill 0c4c3e39)
```
# xs_sentiment_beta_mid: rules + kill stated BEFORE the F&G tape exists on the box (Shumba, written 2026-10-20T03:36:38+0400 per box clock)
Paper only. Live off. No F&G data on box at writing; nothing counted; Shumba never computes returns.
Citation: Han, S. (2025) Investor sentiment and cross-section of cryptocurrency returns. JBEF 46, 101043. DOI 10.1016/j.jbef.2025.101043 (peer-reviewed; RePEc + Crossref). Claim: intermediate sentiment-beta coins beat low AND high by 3.57%/wk risk-adjusted (Nov 2018-Jul 2024).
Inputs: alternative.me FGI daily (value 0-100, timestamp = UTC day); tape C perp 1h closes (SUMS ab447221), daily closes sampled 00:00 UTC as in counts.py c6fe438a.
Feature at Monday 00:00 UTC rebalance t: OLS of coin daily log return on [BTCUSDT daily log return, dFGI = (FGI_d - FGI_{d-1})/100] over the 90 UTC days ending day t-2 (days t-1 excluded so every FGI value used is >=24h old; min 60 complete triples). b_s = dFGI coefficient (market-controlled sentiment beta; construction is Shumba's a-priori reading of "controlling for market", disclosed).
Universe: tape C 96, PIT elig() (>=31d history), BTCUSDT excluded. Sort b_s into terciles.
Side: LONG middle tercile (weight +1.0 total), SHORT bottom tercile (-0.5) and top tercile (-0.5); equal-weight within legs; dollar-neutral. Hold 7d to next Monday. Stop 12% per coin from entry, re-entry next rebalance. Fill next_open. ts < close for all inputs. Cost 0.31% per leg-trade.
Windows: main 2023-10-15..2025-06-30; holdout 2025-07-01..2025-12-31; 2026 veto only. Grade cap B (survivorship).
Gates: PF>=1.15 net; week-cluster mean R CI excludes 0; beats random (1000 draws, seed 20261016: same leg sizes drawn from the PIT-eligible set each Monday); >=100 leg-trades/yr; main >=30 ISO weeks; holdout week-mean R>0 and PF>=1.15.
KILL (main), NOT_FILED if any comparator exceeds 0.50, on BOTH score s1 = rank(b_s) and s2 = extremeness |pct_rank(b_s)-0.5| (s2 is what the trade actually sorts on):
 mean |Spearman rho| or mean leg Jaccard (legs: s1 terciles; s2 = middle tercile vs comparator middle tercile and extremes vs comparator extremes; larger-overlap orientation) against:
 BAB beta90 (bab_counts.py e682ddd9) [the explicit BAB-variant test], ret60, mom3, skew168, TK60 (tk_counts.py c143f354), ivol30, vol60, max7, size30, amih30 (counts.py c6fe438a);
 new_listing_drift_short: Jaccard of (symbol,hour) short-leg hours vs NL main-cohort first 14d.
Coverage gate: NOT_FILED if FGI missing on >2% of days in 2023-07-01..2025-12-31, or median eligible names with valid b_s < 30 in main.
Nothing here may change after hashing.

## v2 AMENDMENT (Shumba, written 2026-10-21T12:58:47+0400 per box clock). Supersedes nothing silently: v1 (b26a9aa5) stays on disk and is reported NOT_FILED.
Reason (data semantics, found in a features-only check, no returns read): alternative.me row stamped UTC day k measures UTC day k-1 (corr(dFGI_k, BTC return day k-1) = 0.684; vs day k = -0.017; sb_sanity.py 449e611a). v1 as literally implemented paired dFGI with the wrong day, so its b_s was noise.
v2 changes exactly two things, nothing else:
 (a) dFGI stamped k is paired with coin and BTC returns of UTC day k-1.
 (b) regression window = return days t-92 .. t-3 (90 days), so the newest FGI row used is stamped t-2 and was final by t-1 00:00 (>=24h old; alternative.me revises the current-day row intraday).
All sides, legs, weights, stop, fill, cost, windows, gates, kill comparators (s1 and s2), the 0.50 threshold and the coverage gate are unchanged from v1 above.
```

### Implementation reading (binding on the harness; no rule change)
- **Regression window:** return days t-92..t-3 inclusive (90 UTC days; the v2 AMENDMENT governs, not the stale "ending t-2" text in v1 or the comment on line 12 of sb_counts_v2.py). The newest FGI row used is stamped t-2. dFGI stamped k = (FGI_k − FGI_{k−1})/100, paired with coin and BTC returns of UTC day k−1. A triple with a missing FGI row (e.g. stamps 2024-10-26/27) is dropped, never zero-filled or interpolated; min 60 complete triples.
- **Legs/weights:** long middle tercile, +$1.00 total EW; short bottom tercile −$0.50 EW and top tercile −$0.50 EW. Dollar-neutral. Terciles are floor(n/3) at each end, the rest middle (as in sb_counts_v2.py).
- **Stop:** 12% adverse per coin from entry (long −12%, short +12%), exit per harness convention (next 1h open after breach), flat until next rebalance.
- **P&L unit:** weekly net book return on $1 long + $1 short: Σ w·r over all legs + funding received − funding paid (actual 8h prints over held hours, never zero-filled; ex-ante gap rule as in prior cells) − cost × traded notional (every entry, exit, stop exit, stop re-entry, weight change). Cluster = ISO week.
- **Draws:** the rules say 1,000 random draws; desk standard 2,000 is used (same test, more draws).

### Cost levels
1. **Official 0.31% per leg-trade on traded notional — binds every gate.**
2. **Measured-cost column, report-only:** 0.158% per leg-trade = mean of BTC 0.135% and SOL 0.181% measured RT (Tsuro sampler; alts unmeasured, labelled "proxy, alts unmeasured"). **Sign-flip veto:** if the mean weekly net at 0.158% and at 0.31% differ in sign, that vetoes. The measured column never rescues a FAIL at 0.31%.

## 2. MDE, power, turnover, drag (normal approximation, pre-cut planning)
- **Clusters:** n = 90 ISO weeks on main; counts (features only, f163baaa): 884.4 leg-trade entries/yr, median 81 valid b_s, so ~27 names per tercile.
- **MDE:** one-sided α=0.05, 80% power: d = (1.645+0.842)/√90 = **0.262** (weekly net mean / SD).
- **Planning read (disclosed):** plan_pre_cut.py 630fa7de; tape C + F&G tape; 108 rebalances 2021-09-13..2023-10-02 (each hold ends before 2023-10-15); exact v2 feature and legs; median 57.5 valid b_s (~16.5 per tercile); 12% stop on 1h close with exit at next 1h open; actual funding.
  - Stops: **13.2 per week, 28% of positions per week.**
  - Traded notional incl. stop exits and re-entries: **1.80 per week** on $2 gross.
  - **Cost drag: 0.56% /wk at 0.31%** (0.28% /wk at 0.158%). Funding: −0.03% /wk. **Total drag ≈ 0.58% /wk.**
  - Gross mean **+0.31% /wk**, SD 4.93%; **net at 0.31% −0.26% /wk**, SD 4.96%.
  - Planning SD band for main: 4.96% scaled by √(16.5/27) ≈ 3.9% (optimistic, assumes idiosyncratic diversification) to 5.0% → **3.9–5.0% /wk**. Caveat: the BAB and TK main runs both came in with higher SD than planned (8.5% vs 5.7–7.3% on TK).
- **Required edge:** **MDE net = 0.262 × (3.9–5.0) ≈ 1.0–1.3% /wk net**, so **gross needed ≈ 1.6–1.9% /wk** against ~0.58% /wk drag. Cost is about a third of the needed gross.
- **Power:** at the pre-cut planning mean (−0.26% net), **power ≈ 2%**. Han (2025) reports 3.57% /wk risk-adjusted (Nov 2018–Jul 2024); if half survived on 96 liquid perps (~1.8% gross, ~1.2% net), power ≈ 70–85%; at a quarter (~0.9% gross, ~0.3% net), ≈ 15–20%.

## 3. Beats-random (turnover-matched)
- Null: each main rebalance, a random split of the same PIT-eligible set with valid b_s into three groups of the same sizes (bottom k, middle n−2k, top k); long the random "middle" +$1.00, short the two random "extremes" −$0.50 each; EW, dollar-neutral, same 12% stop, next_open fill, actual funding, 0.31% on traded notional.
- Turnover matching: carry the previous random book forward and redraw exactly the realized number of names changed in each group that week; stop re-entries follow the random book's own stops.
- **2,000 permutations, seed 20261016.** One-sided p = (1 + #{random mean weekly net ≥ observed}) / 2001; pass requires p < 0.05.

## 4. Hard gates on main (desk standing gates only; net at 0.31%, funding included). No extra comparators.
- PF ≥ 1.15 (weekly net book returns).
- Week-cluster bootstrap 95% CI of mean weekly net excludes zero, positive side (10,000 resamples).
- Turnover-matched beats-random p < 0.05 (2,000 permutations, seed 20261016).
- ≥ 30 OOS leg-trades and ≥ 30 week-clusters.
- ≥ 50% of quarterly folds profitable.
- No losing regime: BTC 4h EMA50/EMA200 ±1% band (BULL/BEAR/CHOP) at the last closed 4h bar ≤ rebalance; a regime with ≥ 5 weeks and mean weekly net < 0 fails; < 5 weeks report-only.
- Max DD < 25% on compounded weekly net equity.
- Measured-cost sign-flip veto (§1).
- Already settled from features-only counts, not re-gated here: ≥ 100 leg-trades/yr (884.4), main ≥ 30 ISO weeks (90), coverage (FGI missing 0.11%), kill (max 0.388 s2_J_ret60 < 0.50).

## 5. Holdout (BINDING) and 2026
- **Holdout H2 2025 (2025-07-01..2025-12-31, 26 weeks) is BINDING** because Han's sample (Nov 2018–Jul 2024) overlaps main 2023-10-15..2024-07; H2 2025 is the only fully out-of-publication test. One look, only after main outputs + verdict are hashed, sealed and main PASSes. Pass = week-cluster mean net > 0 and PF ≥ 1.15 at 0.31% with funding. No 30-week floor. **A holdout fail is a cell FAIL.**
- **2026 veto-only:** ≥ 10 week-clusters with mean ≤ 0 vetoes; < 10 report-only.

## 6. Disclosures (LOCK a7077be3, verbatim)
1. sb_sanity.py read BTC daily returns 2023-07..2025-12 contemporaneously with dFGI (a feature-input alignment check). No forward/outcome returns read. The filing's "no returns read" is reworded to "no outcome returns read".
2. sb_counts_A1 (12:58:26) previewed counts for the pairing-only fix before v2 froze. Features/counts only; disclosed.
3. dF is collinear with BTC daily return (rho ~0.68 at the corrected alignment); b_s is the partial coefficient controlling for BTC. Disclosed, not a fail.
4. Han's sample (Nov 2018-Jul 2024) overlaps main 2023-10-15..2024-07. H2 2025 holdout is the only fully out-of-publication test and is binding.
5. Stale comment line 12 of sb_counts_v2.py says "ending t-2"; code ends at t-3. The harness must implement the rules text (window t-92..t-3) and fix the comment.
6. Grade cap B (survivorship).

Cross-check against Shumba's list: all five of his points are covered (kill max 0.388 s2_J_ret60 is the LOCK's correction in its Gates section; wording "no outcome returns read" = #1; A1 preview = #2; dF ~0.68 = #3; holdout binding = #4). Where wording differs, the LOCK text above governs.

Munha additions (mine, not the LOCK's):
- This prereg made one pre-cut planning read of returns (§2), on rebalances whose hold ends before 2023-10-15.
- The F&G tape is a single retrospective pull (`limit=0`, 2026-10-19T23:39Z), not point-in-time (see §7).
- Sealed today and earlier: xs_realized_skew, xs_bab_btc_weekly and xs_prospect_value_weekly main FAILs were read before this prereg; all three lost to stop-driven cost. No comparator is added for them (kill already run, max 0.388).

## 7. Pre-run DATA condition — **main run BLOCKED**
**The main run is BLOCKED until Tsuro's point-in-time spot-check of the F&G tape PASSES.** Per the LOCK: ≥ 10 archived snapshots of the alternative.me FNG API/page (e.g. Wayback captures) spread over 2023-10..2025-12, comparing every row that was ≥ 24h old at capture against the tape; any revised value → BLOCKED until ruled; report SHA-hashed. If too few captures exist, the tape is accepted as a declared retrospective proxy only by CEO ruling, and that ruling's hash is added to the manifest.

## 8. Order of work
1. Garwe countersigns this prereg (COUNTERSIGN.md).
2. Brian CEO YES; Chiremba builds the harness, which must hash COUNTERSIGN.md into the manifest and implement t-92..t-3 (comment fixed).
3. Scorer + harness hashes; Garwe ACKs. No metric read before the ACK.
4. Tsuro F&G spot-check PASS (or CEO ruling), hashed.
5. Main runs once blind; FINAL hash after the random book is written; Garwe seals main.
6. Munha scores main. Holdout one look only on main PASS (binding). Then 2026 veto.

A FAIL (main or holdout) seals the class: no retune of window, alignment, terciles, leg weights, stop, no sign flip, no leg or regime subset, no re-file as a variant. Gates unchanged. Live off.

## 9. Honest P(pass)
- P(main passes all hard gates) ≈ **6%**. The pre-cut net is negative (−0.26% /wk) with power ≈ 2% at that mean; drag ≈ 0.58% /wk from stop churn (28%/wk stopped). The only upside is Han's large published effect, which overlaps the first ~9 months of main but has no post-publication evidence.
- P(binding holdout passes | main passes) ≈ 50% (26 weeks, PF ≥ 1.15, mean > 0).
- **P(pass main + holdout) ≈ 3%.** Below the 10% slot rule; stated, not a veto. This excludes a further risk that the F&G spot-check blocks the run.
