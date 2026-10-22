# FROZEN PRE-REGISTRATION: xs_crowd_lsr_contrarian v2 (Munha, 2026-10-22)
Paper only. Live off. Not Inbox. Preregistration only. I wrote no harness code, computed no main-sample count and read no price outcome of this cell (or of any L-sorted portfolio) on main (2023-10-15..2025-06-30), the H2-2025 holdout or 2026. Inputs I read are listed in §0, and anything I saw is marked in §6 (SEEN-PRE-CUT / SEEN-MAIN-CARRY). The paper book stays 12+56 and is untouched by this prereg.

**STATUS HEADER**
- LOCK: Garwe **LOCK PASS, grade cap B** (LOCK f50257a1, 2026-10-22 08:45 GST).
- **BLOCKER 1: Brian's CEO YES is required before any harness code.** Order of work is in §8. Garwe countersigns first.
- **BLOCKER 2 (LSR tape restatement): RESOLVED BY CEO RULING, not by a clean PIT pass.** Tsuro's PIT check (REPORT.md 1533b11c, SUMS 6c6f27be) still reads "VALUES: BLOCKED (revision found)": before the cutover, Bybit's published value = 0.35 + 0.30 × tape. Brian ruled option (a) at 2026-10-21 14:58 GST and confirmed it at 15:12 GST. Under that ruling, every rebalance whose 7-day feature window touches 2025-05-01..2025-06-01 is dropped, and the raw tape is used as is with no rescaling. The ruling is frozen into rules v2 (5e1fac2c). The LOCK records it as "Tape used as-is" and says "Rank-invariance cure accepted 07:14 GST". No open data block remains on the LSR tape. Caveat: the ruling exists as text inside the proposal and the rules file. No standalone ruling file with its own hash exists, so the harness manifest pins rules 5e1fac2c and proposal 54ada927 as the ruling's carrier (ambiguity A6).
- P(pass) ≈ **4%**, which is **below the CEO slot rule (P ≥ 10%)**. That is stated here, not a veto by me. Brian decides.

## 0. Pinned inputs (sha256 verified 2026-10-22 ~08:50 GST)
| File | sha256 |
|---|---|
| Garwe LOCK `briefs/locks/xs_crowd_lsr_contrarian_v2_20261022/LOCK_xs_crowd_lsr_contrarian_v2.md` | f50257a1ca974ff6f2e3e9ee75e9a081e900d4c5e85060b2c4e8afbc81034515 |
| Proposal as LOCKed `briefs/proposals/2026-10-22_shumba_proposal_xs_crowd_lsr_contrarian.pre_status_fix.json` | 4c25ddedaea4fd9821a7e134e00a0d71e34ef8c2f5242203df4e9e467a85c153 (matches the LOCK's "4c25ddedaea4…c153") |
| Proposal current (status-line fix only) `...xs_crowd_lsr_contrarian.json` | 54ada92780b1c89ac84ed36032dcddc743f179dc9b25534af55e1cd28a73a795 |
| Prior proposal versions (kept, not filed) | pre_munha_fields 0e0878ba3b51fc1d… / pre_v2 265a90e5cdcbc1a8… / pre_pit_decl fed46f151b7e92b1… / pre_7facedfb f2518d26b95a374e… / DRAFT 2026-10-20 7227fb175eaf1650… |
| Rules + kill v2 `research/xs_crowd_lsr_contrarian_20261020/PRESTATED_THRESHOLD_lsr_v2.md` (frozen 2026-10-21 14:59:50 GST) | 5e1fac2c493ae45ab1fbd143896eb2f64291fd5ea13a97880d40e87c5c01b4e5 |
| Rules v1 `PRESTATED_THRESHOLD_lsr.md` (2026-10-20 03:36:38 GST) | 05d58470572af3507d15e148ef2cccb1e1f14a9b16ec505391a4605d6065aa2d |
| **Sizing addendum** `PRESTATED_SIZING_lsr_v2.md` (frozen 2026-10-22 07:16:13 GST) | 5f6e436f83c66b08dff254a9ac091dfb8c15a2d19ec83889f27cb91f30888e0a |
| SHA256SUMS_v2_prerun / SHA256SUMS_v2_sizing | `sha256sum -c`: 3/3 OK and 5/5 OK |
| Counts script v2 / output | ae5ed1a3085678f5d71703180b919b4381eb8f02d587c1d549ca76971bd463f1 / 231fe7d0f9e2f975055988ccd3974b938585cf150aa895fa5cb5e9fb0cc2b0a2 |
| n-per-rebalance script / output | 024a6da2d6a49e387a6d876acf7cdc4314dd439860ab3fb4e460b243fb0aee1a / b401d0a6e4fb7558430b701a56e39c3a78a6f561951c4f8b2825f036fe70bbf4 |
| Cost/DD fields script / output (`lsr_munha_fields_v2`) | e651b09485479bea47a15ecfec53cb6a0d0aacb90bd95585d2d081f340237b25 / 86d82986fd759a3854867aaed22b54d505e4b414ead19b495205164d6d493782 |
| dACC-PIT + sizing script / output | 53cf2f171ec19123b252c079d21ca3a6062f4d0afe5bbac8b208783f147f17ff / 599ecb535fe80911e531c83cc558373f12755bc20d6975040f06e52736fca987 |
| LSR tape `research/bybit_lsratio_20261020/SHA256SUMS` | 2787b82f6cbc903a4c1a4e727351256eb5c7bec3b6ff0dc0abc28a1d98e0c884 |
| OI tape `research/bybit_oi_1h_20261020/SHA256SUMS` | 63d4518c87a9fc45d4e4dc75fc926f3bd15f6d4b762e32844b0493145e47f596 |
| Tsuro PIT check SHA256SUMS / REPORT.md | 6c6f27be314d6bdcc7f8c80c1505c2e4c3666bf77e5e309c70e2269fda96abc2 / 1533b11ced6727bd2f594cc16022238f17490feafea476fdca54895c54550ae2 |
| Tsuro PIT-derived folder SHA256SUMS | 7facedfb12c17b55acc664258a6b2b744e5090bb159da726c8ad88aa9d865e9f |
| Tape C `research/universe96_full_history_20261016/SHA256SUMS` (prices, funding b8e28b42) | ab4472210b9f4ef357fabaa746d7fa20f0eec9b781fafe52461df378be44acd9 (`sha256sum -c` 290 OK) |
| N-tape `research/new_listings_perp_20261016/SHA256SUMS` (perp_1h, funding, membership) | 9c9916e2ec3e58a22a7b45f88ec957c12ffae9943fde48feda78bc6eb8b40f3c (`sha256sum -c` OK) |
| LOCK scratch rerun `briefs/locks/.../scratch_rerun/` | h0 and h3 counts = 231fe7d0 (byte-identical under PYTHONHASHSEED=0). h1 bd4b7a0d, h2 53901b2c and an unpinned top-level 7196549d differ, which demonstrates the hash-seed tie sensitivity (§1, tie-break). |
| Template `briefs/templates/prereg_template_v2.md` | b1a06d20915affc88694dd7565c1656ec6f46180d8256619a7b92a376e42b4bc |

**Proposal status-line check (Brian item a).** A JSON field diff of 54ada927 against the LOCKed 4c25dded finds exactly three differences: `status` (the stale "today's 1 filing used by xs_sentiment_beta_mid_v2" text is replaced by "FILED_TO_GARWE_2026-10-22_08:37_GST … LOCK f50257a1"), `disclosures[9]` (stale Oct-21 slot text replaced) and a new `status_fix_note`. All other fields, including rules, counts, pins, kill, sizing, cost/DD fields and the PIT declaration, are byte-identical in value. **Scored content is unchanged.** LOCK carry-item 5 ("status text stale") is cured. The LOCK binds to 4c25dded. Both hashes go in the manifest.

## 1. Frozen cell (verbatim rules body, 5e1fac2c; sizing 5f6e436f governs sizing only)
```
Input: Bybit /v5/market/account-ratio, period 1d, field buyRatio (share of accounts net long), per symbol; a value is usable at t only if its timestamp + 1d <= t (period closed) and timestamp < t.
Feature at Monday 00:00 UTC rebalance t: L = mean buyRatio of the last 7 closed daily periods (min 5).
Universe: tape C 96 + N-tape USDT LinearPerpetual names, PIT eligible (>=31d perp history, listed at t), valid L. Terciles on L.
Side (contrarian): LONG bottom tercile (crowd most short), SHORT top tercile (crowd most long); equal-weight, dollar-neutral; hold 7d; stop 12% per coin, re-entry next rebalance; fill next_open; ts < close; 0.31% per leg-trade.
Windows: main 2023-10-15..2025-06-30; holdout H2 2025; 2026 veto only. Grade cap B (delisted names likely absent from the ratio endpoint).
V2 DECLARED EXCLUSION (the only change vs v1 05d58470; ruling Brian 2026-10-21 14:58 GST option (a)): drop every Monday 00:00 UTC rebalance t whose feature window (the 7 daily periods dated t-7d..t-1d UTC that feed L) touches any date 2025-05-01..2025-06-01 inclusive, i.e. drop t iff t-7d <= 2025-06-01 and t-1d >= 2025-05-01. By calendar this is exactly Mondays 2025-05-05, 2025-05-12, 2025-05-19, 2025-05-26, 2025-06-02 (all in main; holdout and 2026 untouched). A dropped rebalance opens no position, is not counted as an ISO week, and contributes no kill-test row; the next kept rebalance enters fresh. The account-ratio tape is used as is, with no rescaling. [...reason text as in 5e1fac2c...] Annualisation denominators (calendar span of each window) are unchanged.
Gates: PF>=1.15 net; week-cluster CI excludes 0; beats random (1000 draws, seed 20261016, same leg sizes from eligible set); >=100 leg-trades/yr; main >=30 ISO weeks; holdout week-mean R>0 and PF>=1.15.
Nothing here may change after hashing.
```
Sizing (5f6e436f, verbatim core): "Fixed gross exposure G = 1.18 x equity at every kept rebalance: long leg 0.59 x equity, short leg 0.59 x equity (dollar-neutral). Equal weight within each leg: per-name weight = 0.59 / n_leg of equity … A stopped name's notional goes to cash until the next kept rebalance (no redistribution). No other sizing change."

Citation (from rules): Dunbar & Owusu-Amoako (2023), JBEF 39, 100812. Transfer GAP (disclosed): the paper is time-series BTC/ETH on CME/CFTC trader categories. This cell applies the idea cross-sectionally to Bybit's account ratio. The paper reports no weekly effect size.

### Implementation reading (binding on the harness; no rule change)
- **Rebalances:** Monday 00:00 UTC, main kept Mondays only (85 ISO weeks). 2025-05-05, 05-12, 05-19, 05-26 and 06-02 open no position and are not weeks. All positions from the 2025-04-28 rebalance close at their normal 7-day exit (Mon 2025-05-05 00:00 open), so the book is flat through the gap. 2025-06-09 enters fresh, with full entry cost charged.
- **Feature:** L from the ls1d tape, rows with ts in [t−7d, t−1d] (ts+1d ≤ t), min 5 of 7 (as lsr_counts_v2.py ae5ed1a3). Raw tape, no rescaling.
- **Terciles and deterministic tie-break (Garwe item 3; Shumba steer). PINNED, and the seed alone is NOT relied on:** sort the valid-L names by the composite key **(L ascending, symbol string ascending, byte-wise ASCII)** using a stable sort over a symbol-sorted list (not over a `set`). k = floor(n/3). Bottom tercile (LONG) = the first k in that order. Top tercile (SHORT) = the last k in that order. So among names tied on L at the top boundary, the alphabetically later symbols go short. The same pinned ordering applies to every tercile in the kill comparators, the random-book eligible set and the survivor split. The harness **also** sets PYTHONHASHSEED=0 as belt-and-braces. The binding rule is the explicit (L, symbol) key, because the LOCK showed the hash seed moves J_fund7d 0.255–0.258 (h1/h2 reruns differ from 231fe7d0).
- **Minimum names (Brian item b; prestated here because the LOCK does not state one):** a kept rebalance trades only if **n_leg = k ≥ 10 names per leg** (that is, ≥ 30 valid-L names). The LOCK and features-only counts (b401d0a6, SEEN) show a main minimum of 24/leg (48 names in position, median 92) and a holdout minimum of 75/leg, with 0 rebalances under 10. So the floor is not expected to bind on main or holdout. **What happens if it binds is not stated in the LOCK or rules. I flag it for Garwe (A2).** Proposed default, mirroring the v2 exclusion's treatment of dropped Mondays: the rebalance opens no position, is not an ISO week and is reported. It is not counted as a flat zero-return week. Garwe rules before countersign.
- **Sizing (frozen, 5f6e436f):** at each kept rebalance, target weights are +0.59/n_L of current equity per long name and −0.59/n_S per short name (G = 1.18). Each kept Monday rebalances back to target. Traded notional = Σ|target_new − drifted_old| over every name (entries, exits and equal-weight resizes, including drift resets).
- **Stop:** 12% adverse per coin from its entry fill (long −12%, short +12%), checked on 1h closes. Exit at the next 1h open (harness convention). The notional goes to cash (no redistribution) until the next kept rebalance. Re-entry happens only at the next kept rebalance, if the name is still in its tercile, and is charged as an entry.
- **Fill:** next_open = the open of the 1h bar starting at Monday 00:00 UTC. Prices: tape C perp_1h ∪ N-tape perp_1h (both pinned).
- **Delist mid-hold:** exit at the last available 1h close, cost charged, cash until the next rebalance.
- **Funding:** actual 8h prints over the hours held, from tape C funding ∪ N-tape funding. I checked: all 140 held symbols missing from tape C funding exist in N-tape funding (697 symbols). Funding is never zero-filled or imputed in the harness. Where a held name has no print for a funding timestamp it was held through, that is listed and handled with the prior cells' ex-ante gap rule. Note: the planning funding figure in §2a imputed uncovered names with the covered-leg mean. The harness does not.
- **P&L unit:** weekly net return on equity = Σ w·r over held legs + funding received − funding paid − cost × traded notional. Equity compounds weekly. Cluster = ISO week of the kept rebalance.
- **Cost (Garwe item 2):** **0.31% of notional on EVERY one-way leg-trade, entry AND exit** (a replaced name pays 0.62% round trip), plus stop exits and re-entries. The counts' 954.7/yr is **entries only**. Entries plus exits ≈ 33.54 name-trades/wk × 52.18 ≈ **1,750 one-way leg-trades/yr**, before stops.
- **Random book draws (Garwe item 5):** **1,000 draws at seed 20261016, binding** (the rules text). The template default of 2,000 is NOT used for this cell.

### Cost levels
1. **Official 0.31% per one-way leg-trade on traded notional. This level binds every gate.**
2. **Measured-cost column, report-only:** 0.158% per leg-trade = mean of BTC 0.135% and SOL 0.181% measured RT (Tsuro sampler, cost part 2). Labelled "proxy, alts unmeasured". For a ~92-name alt book this is likely optimistic. **Sign-flip veto:** if mean weekly net at 0.158% and at 0.31% differ in sign, the cell is vetoed. The measured column never rescues a FAIL at 0.31%.

## 2. MDE, power, turnover, drag (normal approximation, pre-cut planning)
- **Clusters:** n = 85 kept ISO weeks on main (231fe7d0).
- **MDE:** one-sided α = 0.05, 80% power (template): d = (1.645 + 0.842)/√85 = **0.270**. The 95% two-sided CI gate is the stricter test: d = (1.96 + 0.842)/√85 = **0.304**.
- **Planning read: n/a for signal returns.** The LSR tape starts 2023-10-01 (BTC 2023-10-01; earlier rows exist only as the BTC depth probe), so no pre-cut L-sorted planning read is possible. Nothing was computed. The only return read is random 46/46 baskets on tape C, pre-main 2022-01-03..2023-10-02, signal-independent (599ecb53 / 86d82986), which is SEEN-PRE-CUT.
- **SD band (equity units at G = 1.18):** σ per unit gross = 1.211% (analytic k = 46) to 1.545% (empirical random draws, median k = 30), so **1.43–1.82% of equity per week**. Stress case ×1.5 for factor tilts (the BAB and TK main runs came in above plan) is **2.7%**.
- **MDE net = 0.270 × (1.43–1.82) ≈ 0.39–0.49% of equity/wk** (0.43–0.55% at the CI-strict d. Under the 2.7% stress SD, 0.73–0.82%).
- **Required gross:** MDE net + trading drag (0.151% eq/wk at planning turnover, up to 0.30% at 2× stop churn) ≈ **0.54–0.79% of equity/wk** (≈ 0.46–0.67% of gross), before any funding credit.
- **Power (CI-strict, at 1.43 / 1.82 / 2.7% SD), by gross edge in equity %/wk at planning turnover:**
  - 0: 0.2% / 0.3% / 0.7%
  - 0.25: 9% / 7% / 5%
  - 0.50: 62% / 42% / 22%
  - 0.75: 97% / 86% / 53%
  - 1.00: ~100% / 99% / 83%
- Funding credit alone (zero price edge; net ≈ −0.151 + 0.195 = +0.045% eq/wk, SEEN-MAIN-CARRY) gives power ≈ 4–5%.
- PF ≥ 1.15 needs a weekly mean/SD of only ≈ 0.056 under normality, so the CI gate binds first.

### 2a. [REQUIRED, C1] Turnover and breakeven disclosure
| Item | Value | Source |
|---|---|---|
| Expected leg-trades per year (entries + exits + stop exits + re-entries + weight changes) | **954.7 entries/yr; ≈ 1,750 one-way (entries + exits)/yr**, before stops. FLOOR: stop exits and re-entries are unknown without returns. Prior weekly XS cells realised 1.3–2.6× planned turnover. Holdout 1,287.4 entries/yr. | 231fe7d0; 86d82986 (33.54 name-trades/wk) |
| Expected traded notional per week, as a multiple of gross book | **0.412× gross/wk** (median 0.349). With the two fresh full entries amortised, 0.436×. | 86d82986 (83 consecutive-week pairs, features only) |
| Cost drag per week at 0.31% per leg | **0.128% of gross/wk = 0.151% of equity/wk** (0.135% gross with fresh entries). At 2× stop churn, ≈ 0.26% gross / 0.30% equity. | = 0.4119 × 0.31% |
| Funding drag per week (actual 8h prints) | **−0.166% of gross/wk (a CREDIT)** = −0.195% eq. Median −0.053%. Lagged-PIT check −0.193%. Covers 61% of names; uncovered names were imputed in planning only. | 86d82986; tape C funding b8e28b42 |
| **Total drag per week (cost + funding)** | **−0.038% of gross/wk mean (net credit); +0.055% median.** Conservative trading-only figure: 0.128%. | |
| **Breakeven gross per week** | **0.128% of gross/wk trading-only (0.151% eq)**. With funding: −0.038% mean / +0.055% median. Trading-only is the conservative bar. | |
| Expected gross per week | **Not available.** The paper reports no weekly effect (abstract only, tables paywalled), and no pre-cut signal read is possible. None is invented. | proposal §3d |

### 2b. [DISCLOSED, C2] 2× breakeven rule: EXEMPT for this cell
- The ratio is **not computable** (no expected gross). 2× breakeven, trading-only, = 0.255% of gross/wk (0.090% with mean funding credit).
- **EXEMPT per Brian (CEO) ruling, relayed 2026-10-22 ~07:14 GST.** The ratio is disclosed and **does not bind**. It is not a gate, not a LOCK condition and not a veto.

### 2c. [REQUIRED, C3] Per-leg sizing calibrated to the DD gate: FROZEN from 5f6e436f
- **One pre-stated rule:** fixed G = 1.18 × equity (0.59 per leg), equal weight within each leg, stopped notional to cash. Per name 1.28% of equity at the median 46/leg (2.46% at min 24, 0.80% at max 74).
- **Calibration:** pre-main only (Mondays 2022-01-03..2023-10-02, last t 2023-10-02, 92 weeks), random 46/46 baskets on tape C, seed 20261016. Target E[MDD] 16.5% from sqrt(π/2)·σ_w·G·√85 with σ_w = 1.211%. Monte Carlo (20,000 paths): E[MDD] 13.7% at zero drift (P(>25%) 4.9%) and 18.4% at −0.11%/wk drift (P(>25%) 18.2%).
- **Disclosure (Garwe item 4; LOCK carry-item 3):** the sizing sim's "cost-only" drift used **−0.11%/wk** per unit gross, which is **below the breakeven 0.128%/wk** (trading-only, mean). The DD stress is therefore slightly optimistic. It is more optimistic again if stop churn doubles turnover (≈ 0.26%/wk). Gross is unaffected.
- **Further disclosure (mine):** the empirical random-draw σ was 1.545% (86d82986), and that σ would have given G = 0.92 for a 16.5% target. At G = 1.18 with σ = 1.545%, the analytic E[MDD] is ≈ 21%, still below 25% but with a thin margin. G = 1.18 is frozen as filed. **Any change to sizing after a main DD has been seen is a retune, which makes it a new cell. A FAIL still seals the class.**

## 3. Beats-random (turnover-matched)
- **Null:** at each kept main rebalance, draw from the same PIT-eligible set with valid L (pinned ordering) a random "bottom" of k names and a disjoint random "top" of k names. Same G = 1.18, 0.59 per leg, equal weight, same 12% stop, next_open fill, actual funding, 0.31% on traded notional, same dropped Mondays and same fresh re-entry on 2025-06-09.
- **Turnover matching:** carry the previous random book forward and redraw exactly the realised number of names changed in each leg that week. Stop re-entries follow the random book's own stops.
- **1,000 draws, seed 20261016 (binding).** One-sided p = (1 + #{random mean weekly net ≥ observed}) / 1001. A pass requires p < 0.05.

## 4. Hard gates on main (desk standing gates, UNCHANGED; net at 0.31% per one-way leg, funding included)
- PF ≥ 1.15 (weekly net returns on equity).
- Week-cluster bootstrap 95% CI of mean weekly net excludes zero, on the positive side (10,000 resamples, seed 20261016).
- Turnover-matched beats-random p < 0.05 (1,000 draws, seed 20261016).
- ≥ 30 OOS leg-trades and ≥ 30 week-clusters (85 expected).
- ≥ 50% of folds profitable. Folds = calendar quarters of kept weeks: 2023Q4 (from 10-16) through 2025Q2, 7 folds. Pass needs ≥ 4 profitable.
- Max DD < 25% on compounded weekly net equity (§1).
- Measured-cost sign-flip veto (§1).
- Already settled from features-only counts, not re-gated here: ≥ 100 leg-trades/yr (954.7), main ≥ 30 ISO weeks (85), coverage (BTC from 2023-10-01, median coverage 1.0, median valid L 140), and kill (max 0.318 J_amih < 0.50; dACC tape 0.102/0.234, PIT 0.097/0.232).
- **Regime check:** the LOCK and rules state none. It is reported only: BTC 4h EMA50/EMA200 ±1% band at the last closed 4h bar ≤ rebalance. It is not a gate here. Garwe may rule otherwise before countersign (A3).
- Nothing in §2a–§2c or §6a loosens or replaces any line above.

## 5. Holdout and 2026
- **Holdout H2 2025 (2025-07-01..2025-12-31, 26 weeks, 0 dropped) is BINDING per the frozen rules** (holdout week-mean R > 0 and PF ≥ 1.15, at 0.31% with funding). **It opens only on a main PASS (Garwe item 6).** One look, only after the main outputs and verdict are hashed and sealed. No 30-week floor. **A holdout fail is a cell FAIL.**
- 2026 is veto-only: ≥ 10 week-clusters with mean ≤ 0 vetoes; fewer than 10 is report-only. Oct 16–21 2026 counts as n = 1 and is never evidence.

## 6. Disclosures
LOCK f50257a1 carry-items, each covered:
1. Survivor vs later-delisted split, reported up front and report-only: see §6a.
2. Cost on entry AND exit at 0.31%; 954.7 counts entries only: see §1 Cost and §2a.
3. Sizing-sim drift −0.11%/wk vs breakeven 0.128% mean: see §2c. Gross unaffected.
4. Deterministic tercile tie-break pinned in the harness: (L, symbol) key, see §1.
5. Proposal status text stale: cured in 54ada927; scored content unchanged (§0).
6. ~92 names per rebalance (main median; 48–148): weekly turnover is high, stated as is with no redesign. Fresh re-entry after the gap on 2025-06-09 (full entry cost). The kill covers only the XS legs of oi_funding_z and toptrader (the full TS cells were not re-instantiated cross-sectionally). CME→Bybit source move (transfer GAP).

Further LOCK and proposal disclosures: grade cap B (the ratio endpoint holds only 19 Closed symbols of 775, so delisted names are largely absent). The LSR tape is a retrospective pull (2026-10-20/21) with the declared pre-cutover affine restatement. Price-based kill comparators were computed on tape-C names only (n ≈ 80). J_new_listing_hours = 0 is structural. Sign (contrarian) is from the paper and was frozen before any LSR data existed. Context: Kogan et al. (2024) find retail crypto trades momentum-like, which cuts against a clean contrarian prior.

Marks (Munha):
- **SEEN-PRE-CUT:** pre-main random-basket return dispersion (2022-01-03..2023-10-02, signal-independent) in 599ecb53 / 86d82986.
- **SEEN-MAIN-FEATURES** (no outcomes): counts, n per rebalance, tercile turnover and kill means on main/holdout/2026 (231fe7d0, b401d0a6, 86d82986). Symbol lists and status metadata of the LSR, tape C and N-tape (to check funding coverage and the delisted source).
- **SEEN-MAIN-CARRY:** the main-window funding carry of the cell's own terciles (mean −0.166% of gross/wk credit, median −0.053%), computed by Shumba under the Garwe/parent ruling and read by me. Funding is a P&L component of main, so this is disclosed as a partial look at one component of the outcome. No price outcome was read. It cannot be used to retune anything.
- Prior seals read before this prereg: xs_realized_skew, xs_bab_btc_weekly and xs_prospect_value_weekly main FAILs (stop-driven cost), the toptrader_crowd_divergence lean FAIL and the new_listing_drift_short FAIL. No comparator is added (kill already run).

### 6a. [REQUIRED, C4] Survivor vs later-delisted split: REPORT-ONLY, stated up front (Garwe item 1)
- Every main and holdout metric (mean weekly net, PF, trades, hit rate, funding, cost, stops) is reported side by side for (i) symbols with `status == "Trading"` and (ii) symbols with `status == "Closed"` in the LSR tape metadata `bybit_lsratio_20261020/per_symbol/ls1d|ls1h/*.meta.json` (pulled 2026-10-20/21, tape 2787b82f; 756 Trading / 19 Closed). A symbol absent from that metadata takes its status from the N-tape/tape-C membership last_bar (before the 2026-10-16 10:00 UTC cutoff = Closed).
- Attribution: per-name P&L contributions summed within each group, plus each group's share of leg-trades.
- Membership is fixed from those pinned files before main runs and is never re-cut.
- **Report-only.** It never gates, never rescues and never becomes a subset. The cell is graded on the full book. The listing rerun showed delisted names behaving very differently (+9.44% vs +2.31%/trade), which is why this is reported up front.

## 7. Pre-run data conditions
- LSR tape restatement: **resolved by CEO ruling (a)** (see header), frozen in rules 5e1fac2c. The harness asserts LSR SUMS 2787b82f and that the 5 dropped Mondays are exactly those listed.
- The harness asserts SUMS for tape C (ab447221), N-tape (9c9916e2) and OI (63d4518c), and the funding coverage check (tape C ∪ N-tape) before the first metric. Any held name with no 1h price over its hold makes the run BLOCKED and reported, never silently dropped.
- The harness manifest hashes this prereg, COUNTERSIGN.md, LOCK f50257a1, proposals 4c25dded and 54ada927, rules 5e1fac2c and sizing 5f6e436f.

## 8. Order of work
1. Garwe LOCK (done, f50257a1).
2. This prereg frozen and hashed.
3. Garwe countersign, including rulings on A1–A6.
4. **Brian CEO YES (required before any harness code).**
5. Chiremba scorer/harness, with COUNTERSIGN.md hashed into the manifest, the pinned (L, symbol) tie-break and PYTHONHASHSEED=0.
6. Garwe ACK (no metric read before the ACK).
7. Main runs once, blind. FINAL hash after the 1,000-draw random book is written. Garwe seals main.
8. Munha scores.
9. Holdout, one look, only on main PASS (binding).
10. 2026 veto.

A FAIL (main or the binding holdout) seals the class. No subset (survivors, legs, regimes, quarters), no flip to momentum, no retune of window, L lookback, terciles, stop or exclusion, no resize, and no re-file as a variant. Gates unchanged. Live off. The paper book stays 12+56, untouched.

## 9. Honest P(pass)
- **P(main passes all hard gates) ≈ 7%.**
  - No effect size is available. The source is time-series CME positioning on BTC/ETH, transferred to a Bybit cross-section.
  - Every recent weekly XS cell (skew, BAB, prospect) failed on stop-driven cost, and toptrader crowd failed lean.
  - Kogan et al. suggest the opposite sign is plausible.
  - The structural funding credit (+0.195% eq/wk, SEEN-MAIN-CARRY) roughly offsets planning-level trading cost, so the gross price edge needed for the CI gate is still ≈ 0.4–0.8% eq/wk.
  - DD risk at G = 1.18 is non-trivial (18% P(>25%) at cost-only drift in the sim).
- P(binding holdout passes | main) ≈ 55% (26 weeks; mean > 0 and PF ≥ 1.15).
- **P(pass) ≈ 4%** (my band 3–5%). **This is below the CEO slot rule (P(pass) ≥ 10%).** Stated, not a veto by me. **Brian decides.**
- 2× breakeven ratio (§2b): not computable. EXEMPT per CEO, disclosed, non-binding.

## Open ambiguities for Garwe (rule before countersign; none changes a gate)
- **A1. Proposal pin.** The parent brief named "LSR v2 0e0878ba". On disk, 0e0878ba is `.pre_munha_fields.json`, a prior version. The LOCK binds 4c25dded (filing) and the current file is 54ada927 (status-only). This prereg pins 4c25dded and 54ada927.
- **A2. Short rebalance.** The minimum is set at ≥ 10 names per leg. What happens when a rebalance falls short is not in the LOCK. Proposed: skip (no position, not a week) rather than count it flat. It is not expected to bind (main min 24/leg).
- **A3. Regime check.** No regime gate is in the LOCK. Here it is report-only. (The sentiment_beta prereg had "no losing regime" as a hard gate.)
- **A4. Random draws.** 1,000 (rules + your item 5) is used, overriding the template's 2,000 default.
- **A5. Measured-cost column.** 0.158% (BTC/SOL proxy) on a ~92-name alt book. Confirm that the proxy is acceptable for the veto column.
- **A6. Ruling hash.** Brian's 14:58/15:12 ruling (a) has no standalone hashed file. It is carried by rules 5e1fac2c and proposal 54ada927. Confirm that this is enough for the manifest, or ask Brian for a ruling file.
- Also noted: the funding carry figure was computed on main with leg-mean imputation for 39% of names. The harness uses actual N-tape funding instead (all 140 names covered), so the realised credit may differ.
