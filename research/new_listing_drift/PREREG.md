# FROZEN PRE-REGISTRATION: new_listing_drift_short (Munha, 2026-10-16)
Paper only. Live off. Not Inbox. I have not computed or read any outcome on main (2023-10-15..2025-06-30), the H2-2025 holdout or 2026.

## 0. Pinned inputs (sha256 verified 2026-10-16 ~15:20 GST)
| File | sha256 |
|---|---|
| Proposal `briefs/proposals/2026-10-16_shumba_proposal_new_listing_drift_short.json` | 3ee54412e5a3114db69cd81a01d3b56656cd323a5db218435d868a0b8305a3ba |
| Frozen rules `briefs/proposals/2026-10-16_shumba_DRAFT_new_listing_drift_short.json` | d4453d107c99f743f29c1af46729621c7de790e44f746fffd0c3e6c779b188f8 |
| LOCK `briefs/locks/new_listing_drift_short_20261016/LOCK_new_listing_drift_short.md` | e693c8709f0fda22444fc1b51f9b58de83fa4a949b1b9d90751feedb7f9eac6e |
| Kill file `research/new_listing_20261016/PRESTATED_THRESHOLD_listing.md` | bc1ac015… |
| Tape C SUMS (universe96) | ab447221… (check passed, 0 fail) |
| Tape D SUMS (delisted perps, Tsuro) | 5d81bda354fae0740111e693ab5a42df9a9c56df20c01c014ff8f18e399b5039 (check passed, 0 fail) |
| Tape N SUMS (new-listing survivors) | 9c9916e2… (check passed, 0 fail) |
| Cost sampler `research/cost_measurement_20261009/bybit_sampler/SHA256SUMS_sampler.txt` | e1ac28e7… |
| Cost Part 2 `briefs/2026-10-10_munha_cost_measurement_part2_sampler.md` | 1e016bb3… |

## 1. Frozen cell (verbatim, LOCK e693c870 / rules d4453d10)
> Cell exactly as d4453d10: short the new USDT perp plus an equal-notional BTCUSDT long at next_open after the first full 1h bar closing >= launch+24h; 14d hold, or the last tradable bar before delivery; -12% spread stop on 1h closes, filled next open; 0.31% per leg-trade on entry and exit; funding included on both legs and never zero-filled. Tapes C ab447221, D 5d81bda3, N (survivor pull 9c9916e2).

The rules text (d4453d10) governs entry, exit, stop, exclusions and P&L verbatim:
- Universe: every USDT perp in C∪D∪N (LOCK ruling 2: catalog v2), with exclusions HIGH, HOOK, ORBS, DATA, HMSTR (late start >48h), DATAOLD01, LAYER, LITENTRY and MONPRO (empty), and BTCUSDT.
- Tradfi perps are IN per LOCK ruling 1. They affect only the 2026 veto (338 events, 39 week-clusters).
- **Units:** spread R is the short-leg return plus the long-BTC return, per one-leg notional. Net is gross plus funding (short receives the listing funding, long pays BTC funding) minus 2×0.31% = **0.62% per spread trade**.
- **Cluster:** the ISO week of entry.
- **Book for DD:** each event is opened at a fixed 10% of current equity per leg notional (mean concurrency is about 8.2 open shorts, per the proposal's kill test). Equity is marked at each exit. This sizing is a scorer convention only and does not change any trade.

### Cost levels (both are stated; the official one binds)
1. **Official: 0.31% per leg-trade (0.62% per spread).** All hard gates bind at this level.
2. **Measured RT, reported only.**
   - Tsuro's sampler (Part 2 1e016bb3) covers BTC, ETH and SOL only. BTC taker RT is 0.110% central and 0.135% conservative p90; SOL conservative is 0.181%.
   - **No measured figure exists for new-listing or alt names.** New listings trade with spreads and impact that are likely *wider* than SOL's.
   - The secondary column uses BTC leg 0.135% plus listing leg 0.181% (the SOL conservative figure as a floor proxy), giving **0.316% per spread**. It is labelled "proxy, unmeasured for listings".
   - **Veto:** if the measured column and the official column disagree in sign, that is a veto. A measured-level result can never rescue a FAIL at 0.31%.
   - **Caveat:** the true listing-leg cost may exceed 0.31%, so the official 0.31% is not a conservative bound here. Real-cost validation on listing names is required before any promotion.

## 2. MDE, power, drag, P(pass)
- **Week-clusters:** n = 87 on main (364 events, 213 a year).
- **MDE:** one-sided α = 0.05, 80% power, normal approximation, gives d = (1.645+0.842)/√87 = **0.267**.
- **Planning input (disclosed):**
  - Script `research/new_listing_prereg_20261016/plan_pre_cut.py`.
  - Sample: 152 listing events from tapes C and D whose entry plus 14 days fell strictly before 2023-10-15. Entries run from 2021-03-16 to 2023-09-22 across 68 weeks (81 from D, 71 from C).
  - Bias: tape N has no pre-2023 listings, so still-trading non-C names are absent. This sample is **survivorship-biased** (it over-represents survivors in C and later-delisted names in D), so the sign is not informative.
  - Delivery was not handled in this planning pass.
  - Results:
    - SD of net R per event: 18.5%
    - SD of week-cluster means: 16.6%
    - Stop rate: 43%
    - Mean funding: +0.005% per trade
    - Mean gross: +2.31%
    - Mean net at 0.31%: +1.69% (d ≈ 0.10)
- **Required edge:** the MDE at d = 0.267 is **about 4.4% net per spread trade**. Funding drag is about 0. Cost drag is 0.62% at 0.31%, or 0.32% measured-proxy. So the **gross drift needed is about 5.0% per 14-day trade** at 0.31%. Cost is only about 12% of the requirement; the bottleneck is variance, not cost.
- **Power:** at the planning d ≈ 0.10, power is about 24%. Additional constraints:
  - A PF of at least 1.15 needs a positive mean with the 43% stop tail controlled.
  - A DD under 25% with about 8 concurrent short-alt positions is hard; one alt-season week could break it.
  - The contrary paper (Benedetti & Kostovetsky, +48% BHAR in the first 30 days) runs against the short.
- **P(pass at all hard gates on main): about 6%.** That is below the CEO's 10% slot rule. I state it but do not veto on it; the LOCK stands.

## 3. Beats-random
- **The rules' own draw (d4453d10) is adopted and strengthened:**
  - Same names and same event count, short side and BTC hedge.
  - Same 14-day / delivery exit, −12% stop, 0.31% per leg and funding.
  - Entry at a uniformly random 1h bar open within that name's tape life in the same window, **excluding the name's first 15 days**.
- **Why the post-listing age window cannot be matched exactly:** the real entry sits at listing age of about 1 day by definition, so any draw restricted to that age is the real trade. The age-15+ draw is therefore the correct null for "is the *listing timing* special": it tests listing timing versus the same name's later drift, not the drift of a generic short.
- **Additional rules:**
  - A name with no eligible random bar (delisted, or the tape ends within 15 days plus 14 days) keeps its real-entry slot out of the draw. It is not resampled to another name, and the count is reported.
  - Draws: **2,000** (the rules say 1,000; 2,000 is the desk standard, has finer p resolution and is the same test). Seed 20261016.
  - One-sided p = (1 + #{random mean net ≥ observed}) / 2001. Pass requires p < 0.05. This is equivalent to the rules' "exceeds the 95th percentile".

## 4. Hard gates on main (net, at 0.31% per leg plus funding)
- PF ≥ 1.15
- Week-cluster bootstrap 95% CI of mean net R excludes zero on the positive side (10,000 resamples)
- Beats-random p < 0.05
- At least 30 spread trades and at least 30 week-clusters
- At least 100 trades a year (the rules' own gate)
- At least 50% of quarterly folds profitable
- Max DD < 25% (book as in §1)
- Measured-RT sign veto as in §1

## 5. Holdout and 2026
- **Holdout H2 2025** (128 events, 27 week-clusters): one look only, after main outputs are hashed and only if main passes. Pass requires a positive week-cluster mean net R and PF ≥ 1.15. No 30-week floor.
- **2026 is veto-only** (338 events, 39 week-clusters, tradfi included).
  - With at least 10 week-clusters, a mean ≤ 0 vetoes. The rules' own clause adds PF < 1.0 as a veto, and both apply.
  - Below 10 week-clusters it is report-only.
  - 17 events in 2026 are truncated by the data cutoff and are reported as truncated.

## 6. Disclosures
- **Survivorship:**
  - Tape D (Tsuro's delisted-perp tape **5d81bda3**) is used. 47% of main events come from D, 17% of holdout events.
  - The v2 catalog is complete against the 15-Oct snapshot: main 191/192 (HMSTR excluded for late start, not imputed) and holdout 106/106.
  - Relisted or renamed launchTimes may not equal the first Bybit listing.
  - Contracts delisted before 2023 are irrelevant to these windows.
  - Grade is capped at B.
- **Overlap with sealed families:** Jaccard is 0 against turnover_lead, amihud, xs_realized_skew (sealed) and max_lottery, with max |ρ| = 0.16. This is structural, since comparators need at least 31 days of history.
  - It is not alt_btc_lag, btc_shock or compression-on-new-tokens.
  - The BTC hedge leg is shared with every alt-vs-BTC spread, but the signal is listing age, not a ratio, so it is not alt_btc_ratio*.
- **Planning read:** one pre-cut read (§2, survivorship-biased). No main, holdout or 2026 read.
- **Prior screens:** none of today's prior screens touched listings (9342cc4d covered weekend, MAX and IVOL on the 26-name tape; xs_realized_skew main dead78cb).
- **Process and timing:** any new code needs a CEO YES (LOCK). The proposal and rules predate the counts, as verified by Garwe.

## 7. Order of work
1. Chiremba gets a CEO YES for the new code, then hashes the harness and scorer.
2. Garwe ACKs those hashes. No metric is read before the ACK.
3. Main is run, and its outputs and verdict are hashed.
4. The holdout gets one look, only if main passes.
5. The 2026 veto is read.

A FAIL at any stage seals new_listing_drift_short: no retune of the 24h delay, 14-day hold, 12% stop or BTC hedge, no long flip, no tradfi/token subset and no re-file as a variant. Every gate is unchanged. Live stays off.
