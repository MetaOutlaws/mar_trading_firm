# MAR research handover — updated 7 October 2026

Owner: Brian / Meta Outlaws. Repository: MetaOutlaws/mar_trading_firm.
Purpose: reproducible handover and restart without reconstructing the chat.

## Start here

## Latest owner decision and stop-only experiment — 7 October 2026

Brian explicitly approved hourly compression on BTC/ETH/SOL, both directions,
for PAPER use at SL2% / TP2.5%. Preserve the original positive baseline and
record owner approval separately from independent research qualification.
The runtime module and guarded activation script are prepared and tested;
Singapore is active in DigitalOcean, but this chat has no SSH execution access.
**Cloud activation/scanning is pending, not verified.** No cloud write occurred.

The stop-only protocol was published before scoring. With TP fixed at 2.5%,
2025 results (closed/stops; net base/stress) are: SL1% 37/25, -0.1092%/-0.2385%;
SL2% 36/14, +0.4992%/+0.3685%; SL3% 36/13, +0.2627%/+0.1320%;
SL4% 36/10, +0.4418%/+0.3111%; SL5% 36/8, +0.5779%/+0.4477%.
SL1% loses 11 baseline target winners. SL5% recovers six of 14 baseline stops,
but has lower mean R than SL2%. No alternative improves both stressed mean net
and mean R in both partitions; the approved 2% baseline remains unchanged.
Read hourly_stop_width_20261007/FINDINGS.md and PROTOCOL.md.

Verification: 143 raw signals, 715 independent barriers, 20 independent
admission replays, 266 exactly reconciled baseline rows, 1,330 alternative
ledger rows. Six implementation tests pass; 143 research entry signals and
1,734 rolling candidate checks match. No new token or 2026 price scoring.

Next research: a separately frozen profit-protection comparison with unchanged
hourly entries and initial 2%/2.5% barriers, counting winners cut short as well
as stopped-trade profits saved. It has NOT run. New-token confirmation remains
pending. None of the old negative family findings or positive hourly findings
has been overwritten. Older status sections below describe their dated stages.


## Latest completed follow-ups — 7 October 2026

Read `family_followups_20261007/FINDINGS.md` and its pre-scoring `PROTOCOL.md`
relative to the research root. Brian approved three focused hypotheses:
hourly compression, the extreme-funding predicate and 4h trend alignment.

Primary 2% stop / 2.5% target, reused 2025:

| Variant | Closed trades | Stops | Mean net base | Mean net stress |
|---|---:|---:|---:|---:|
| Hourly compression | 36 | 14 (38.9%) | +0.4992% | +0.3685% |
| Original extreme-funding breakout | 211 | 124 (58.8%) | -0.3952% | -0.5490% |
| Same breakout without the extreme-funding predicate | 1,462 | 800 (54.7%) | -0.2210% | -0.3663% |
| Trend pullback with aligned 4h regime | 220 | 115 (52.3%) | -0.1036% | -0.2440% |
| Original trend pullback | 361 | 193 (53.5%) | -0.1538% | -0.2927% |

Mean returns include terminal marks: two for funding, three for its comparator,
two for original pullbacks; none for hourly compression or aligned pullbacks.
Closed counts and stop fractions exclude marks.

Hourly compression alone meets the local continuation point criterion. Its
2022–24 mean is +0.2268% base / +0.1037% stress on 97 trades, but 2023 lost
money and confidence intervals cross zero. Historical stressed performance
turns negative without BTC. This remains exploratory, not a confirmed edge.
The 3%/3% hourly sensitivity has 35 closed 2025 trades, 14 stops and +0.3439%
base / +0.2126% stress. It changes both barriers.

Funding and trend-alignment hypotheses have no continuation support under
their frozen primary criteria. Record these comparisons as complete; no
automatic threshold sweep follows. Shock reversal and the learned rule remain
paused pending materially new hypotheses/data.

Validation: 108 original event groups, 57,728 unique raw barrier checks,
48 independent admission replays, 48 pooled/1,116 subgroup/96 annual/24 contrast
rows, and 36,488 ledger rows including alternative variants and cost scenarios.
The old 3,736-row compression basket reproduced exactly. Four focused tests pass.
A rejection-log integrity mismatch was reconstructed to its original recorded
hash exactly; the mismatched copy and recovery evidence are retained. No outcome
or entry rule changed in that recovery.

The private `MAR_entry_family_followups_checkpoint_20261007.zip` contains all
needed source, frozen features, detailed new evidence, prior comparator evidence,
reports and restore instructions. Only the separately saved original candle/
funding ZIP is needed as an external input. Its separate checkpoint-verification
JSON records archive hash and fresh restore checks.

Next: collect/audit additional-token data and predeclare a separate hourly
confirmation comparison before viewing new outcomes. Keep the original broader
all-clock primary protocol and its eight-new-token gate intact. Update the
candidate-set/multiplicity plan before independent confirmation. No new-token
test, 2026 price scoring, cloud change, leverage test or forward process started.


Read [RESEARCH_ROADMAP.md](../RESEARCH_ROADMAP.md) for the current hypothesis sequence, decisions and experiment reporting rules. The three focused follow-ups are complete; only hourly compression met the local continuation point criterion. The prior positive examples were selected configurations, while the full-family and shared-position tests were negative.

Read the latest completed experiment below first; the older stages follow.

## Earlier completed three-token basket — 7 October 2026

Brian authorized a local BTC/ETH/SOL diagnostic while additional-token data
were unavailable. Read `three_token_compression_20261007/FINDINGS.md` relative
to the research root, and its frozen scope amendment `PROTOCOL.md`.

- All three entry clocks (5m, 15m, 1h), both sides, unchanged compression entry;
  full raw opportunities replayed under shared per-token occupancy.
- Pooled 2025 primary 2% SL / 2.5% TP: 222 closed trades, 114 stops (51.35%),
  mean net -0.0559% base / -0.1839% stressed slippage. No terminal mark.
- Pooled 3% SL / 3% TP: 196 entries, 195 closed, 102 stops (52.31% of closed),
  one terminal mark; mean net -0.3885% base / -0.5196% stress including the mark.
- Both arms negative in historical 2022–24 too. No qualified strategy.
- Admitted 1h primary subset: 27 evaluation trades, 11 stops, +0.4201% base /
  +0.2869% stress. Confidence intervals cross zero. This is a post-review
  descriptive subset of the shared basket, not a separately replayed 1h system.
- Original 216 compression cells reconciled; four focused tests passed.
  Eighteen signal groups, 2,992 independent raw barrier checks, eight admission
  replays and 232 pooled/subgroup/annual summaries verified; 3,736 ledger rows
  include alternative arms and duplicated base/stress scenarios.
- 2026 remains unscored. Zero new tokens. No production or leverage changes.

`MAR_three_token_compression_checkpoint_20261007.zip` contains the full source
needed for this run, the nine frozen feature files, all new evidence, reference
verification and restoration instructions. It requires only the separately
saved original `isolated_token_study_1m_2022_20261002_v2.zip` for raw candles and
funding; older evidence archives remain available for earlier research stages.
The new archive's `CHECKPOINT_SHA256SUMS.json` and `verify_checkpoint.py` verify
its payload. Its outer SHA256 and published commit are in the separate
`MAR_three_token_compression_checkpoint_verification_20261007.json`.

Additional-token acquisition remains pending. No Grok/SSH/cloud collection was
started from this workspace. If pursuing 1h alone, freeze a new hypothesis and
replay all hourly signals before independent new-asset/forward confirmation.
Do not treat this three-token diagnostic as passing the original eight-new-token gate.


1. Read ../compression_replication_20261006/RUN_STATUS.md for the latest work:
   broader-token protocol/collector/runner are prepared and verified, but new
   market-data acquisition is blocked in this workspace. No new-token result.
   Read ../entry_discovery_20261006/FINDINGS.md for the latest completed entry research.
   Compression expansion has sparse positive leads, but 0/180 new configurations
   passed the frozen screen. 2026 remains unscored in that experiment.
   Read FINDINGS.md for the primary-audit result, SECONDARY_FINDINGS.md for
   the completed 1h/24h audit, COSTED_FINDINGS.md for the completed matched
   costed-opportunity diagnostic, and ../breakout_retest_20261006/FINDINGS.md
   for the completed standalone breakout/retest experiment. No entry qualified.
2. Read each frozen protocol and RECONSTRUCTION_AMENDMENT.md before rerunning.
   Protocol status text describes the pre-run state; this handover tracks completion.
3. Use the private checkpoint archive for complete code, detailed evidence and
   historical files. Public GitHub contains reports, protocols and aggregates;
   it is not the only copy of the research evidence.

## Durable artifacts

| Artifact | Purpose | Verification |
|---|---|---|
| isolated_token_study_1m_2022_20261002_v2.zip | Original BTC/ETH/SOL data and funding, saved privately | SHA256 below; 17 ZIP members pass CRC |
| MAR_research_checkpoint_20261006.zip | Updated research code/evidence, reconstruction, primary and secondary comparisons, breakout/retest results and pinned report snapshots | SHA256SUMS.json verifies every packaged payload; previous saved version retained |
| MAR_entry_discovery_checkpoint_20261006.zip | Incremental discovery code/evidence, features, training labels, signals, ledgers, report snapshot and updated handover; restore alongside the base checkpoint | DISCOVERY_SHA256SUMS.json and verify_discovery_checkpoint.py; base archive SHA recorded below |
| individual_trades_reconstructed.csv.gz | 38,469 reconstructed baseline positions, base costs | Reconstruction manifest and 72-row published reconciliation |
| prediction_v1/primary_summary.csv | 36 period-specific primary results, CIs, coverage and flags | Prediction manifest |
| prediction_v1/paired_signals.csv.gz | Every matched signal and mean control result | Prediction manifest |
| prediction_v1/control_draws.csv.gz | All 1,126,166 control draws, including reuse | Prediction manifest |
| prediction_v1/excluded_signals.csv.gz | Unmatched/censored signal reasons | Prediction manifest |
| secondary_v1/ | 1h/24h observations, all matches/exclusions, 216 result rows | Secondary manifest |
| costed_v1/ | 144 matched costed comparisons, complete outcomes/draws/pairs/exclusions and cost attribution | Run manifest and COSTED_REPORT_VERIFICATION.json |
| ../breakout_retest_20261006/results_v1/ | 576 costed result rows, 140,120 ledger rows including both costs, setups and 432 control contrasts | Run manifest and REPORT_VERIFICATION.json |
| published_snapshot/ | 23 research files retrieved from pinned GitHub commit | Snapshot index and package hashes |
| published_stage2_snapshot/ | Exact newly published reports, protocols and aggregate tables | Package hashes and ARTIFACT_INDEX.json |
| published_costed_snapshot/ | Latest costed protocol, findings, aggregates and updated handover | Package hashes and ARTIFACT_INDEX.json |

Base research checkpoint (costed stage, saved version 2) SHA256:
`7d357d4b5176d8190ee8efdd42fb3a6bd02a0b2c94262dc8b04ea04c49d9dc92`

Original data ZIP SHA256:
`344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc`

Pinned public report commit:
`f55bcac0cdd8e3c82768205958424a99e14f4582`

Important version distinction: the PR98 description was stale at recovery and
still called fixed-stop work queued. The published fixed-stop, adaptive-stop,
standalone-zone and winner-diagnostics files describe later completed work.
Use their contents and the pinned snapshot, not the old PR description.

## What is complete

- Six original candle/funding hashes verified; no new data substitution.
- 57 earlier artifact/hash/archive checks passed.
- Standalone-zone reconstruction: 38,469 positions; all 72 published 2025
  configuration rows match counts exactly and returns/PF within report rounding.
- Primary matched-entry audit: 58,687 matched signals; 36 period results;
  0/18 groups pass the frozen two-period gate.
- Two focused implementation checks passed by direct Python invocation.
- Secondary 1h/24h diagnostic: 117,310 matched signal-horizon observations,
  2,251,014 control draws, 216 result rows. Primary failure unchanged.
- Standalone breakout/retest: 0/36 configurations pass. All 36 have negative
  discovery mean net return. The three controls also have no passing configuration.
- Five additional focused tests passed (one secondary-window and four setup-state
  tests). All 144 control reconciliations passed; all 576 summary rows match
  their ledgers and respect position occupancy. Sixteen frozen output hashes verified.
- Matched costed-opportunity diagnostic: 58,690 of 59,617 zone signals matched;
  1,126,229 control draws and 144 arm/period/cost contrasts. Pooled 2025 zone
  net returns are -0.4402% and -0.4295%, below matched controls in both arms.
  All discovery arm/group means are negative; the failed primary gate is unchanged.
- Two costed-diagnostic implementation tests passed. All 72 chronological
  reference checks passed; report verification checked 184 frozen output hashes
  and all 144 contrasts against saved outcomes, matched pairs and weights.

- Distinct entry discovery: 180 new configurations plus 72 controls across 5m,
  15m and 1h, both directions and two stop/target arms; 1,512 result rows.
  13 configurations positive in all three historical partitions at normal costs,
  six at doubled slippage, but 0 pre-2025 finalists. Compression supplies five
  of those six sparse stressed-cost leads. No 2026 scoring or strategy promotion.
- Reverse engineering: three depth-two trees and 1,688,248 overlapping training
  opportunities; best selected training regions remained negative after costs.
- Four focused discovery tests passed. Verified 114 frozen output hashes, five
  frozen sources, 3,528 period/annual summaries against 390,696 ledger rows,
  every ledger's occupancy and every training label's pre-2024 dates.

Original row-level identity is not proven. The reconstructed export does not
claim to reproduce the former feature-enriched CSV column for column.

## Broader-token replication setup

Brian approved scaling the unchanged compression entry across a broader token
universe, accepting low per-token trade frequency. PROTOCOL.md freezes monthly
selection of up to 15 new tokens using prior liquidity and listing history.
The primary pooled test uses 2% SL/2.5% TP across all three clocks and both sides,
one position per token, six overall and three per direction. The 3%/3% arm is
descriptive. Historical universe/funding provenance and statistical evidence
are required before qualification; leverage remains untested.

A resumable public-data collector, input validator and offline runner are ready.
Four focused tests passed and 216 prior compression cells reconciled. Direct
Bybit access returned a non-JSON Site Unavailable page, including the collector
preflight. No collector has been launched on Singapore from this workspace.
The private MAR_compression_replication_kit_20261006.zip includes code, protocol,
verification and exact RUN_ME.md instructions. It is a code/readiness package,
not a replacement for the two previous full evidence checkpoints or source data.

## Pending, not running in the background

- Broader-universe replication of the frozen compression entry and historical
  open-interest/liquidation/flow data acquisition; neither has run.
- Separate profit-protection comparison (deferred by Brian's entry-research priority).
- The cost-aware minimum zone-target-distance fallback remains unverified as
  completed; check evidence before asserting it has run.
- Fresh confirmation of any future selected strategy. 2025 is already reused.

Existing ATR-cap comparisons have already been completed and failed their
screen. A new adaptive-stop experiment must name a genuinely different
hypothesis; do not silently repeat or relabel the old test.

The latest breakout/retest rule is closed with a failed screen; do not tune its
lookback, ATR band or expiry merely to make a historical cell survive. The latest
entry-discovery experiment is also complete; its positive examples are exploratory
and were highlighted after reviewing 2025. Preserve the exact compression rule
for broader replication; do not tune it to force a historical finalist. The planned profit-protection
test must keep reference entries, initial stop/target and regime exit fixed,
and replay occupancy to measure both saved profits and winners cut short.
More model credits do not change sample independence. Reserve unused data for
eventual confirmation.

## Restart instructions

Extract MAR_research_checkpoint_20261006.zip (base version 2) into a new directory
and run its verify_checkpoint.py BEFORE applying the discovery supplement.
Then extract MAR_entry_discovery_checkpoint_20261006.zip into that same directory
and run verify_discovery_checkpoint.py. The supplement updates START_HERE.md and
the research HANDOVER.md, so the old base hash check is expected to differ for
those files after applying it; its separate original archive remains unchanged.
Extract the original source ZIP into `data_cache/` there. Use Python 3.12; the
recorded run used 3.12.14. The base archive and source data are separately indexed
in DISCOVERY_ARTIFACT_INDEX.json.

```bash
python -m pip install -r research/isolated_token_study_20261003/entry_quality_audit_20261006/requirements-audit.txt
python verify_discovery_checkpoint.py
python research/isolated_token_study_20261003/entry_quality_audit_20261006/audit_inputs.py --cache data_cache
```

Fresh reconstruction (output directory must not already exist):

```bash
python research/isolated_token_study_20261003/entry_quality_audit_20261006/reconstruct_zone.py --cache data_cache --out rerun_reconstruction --published published_snapshot/research/isolated_token_study_20261003/standalone_zone_20261006/FINDINGS.md
```

Fresh primary diagnostic:

```bash
python research/isolated_token_study_20261003/entry_quality_audit_20261006/run_prediction.py --cache data_cache --reconstructed rerun_reconstruction --out rerun_prediction
```

Fresh secondary and breakout/retest runs, each into a new directory:

```bash
python research/isolated_token_study_20261003/entry_quality_audit_20261006/run_secondary.py --cache data_cache --reconstructed rerun_reconstruction --out rerun_secondary
python research/isolated_token_study_20261003/breakout_retest_20261006/run_breakout.py --cache data_cache --reconstructed rerun_reconstruction --out rerun_breakout
```

Fresh entry discovery (also needs scikit-learn 1.8.0):

```bash
python -m pip install scikit-learn==1.8.0
python research/isolated_token_study_20261003/entry_discovery_20261006/run_discovery.py --cache data_cache --reconstructed research/isolated_token_study_20261003/entry_quality_audit_20261006/reconstruction_v1 --out rerun_entry_discovery
```

Fresh costed-opportunity diagnostic:

```bash
python research/isolated_token_study_20261003/entry_quality_audit_20261006/run_costed.py --cache data_cache --reconstructed rerun_reconstruction --out rerun_costed
```

Costed opportunities overlap and do not enforce position occupancy. Their counts
and mean returns are not a portfolio replay. The chronological pass in that runner
is solely a reference check. Do not mistake costed-summary rows or reused control
draws for independent executed trades.

The report generator reads the archived `results_v1` and `secondary_v1` paths;
it is a report/checking utility, not the scoring runner. All entry clocks remain
5m, 15m and 1h. The completed 4h regime is context; 1h/4h/24h outcome horizons
are measurements, not holding caps. This stage did not test the expansion tokens.

The scripts reject changed raw input hashes. Preserve any failed run directory
and its error reason; use a new directory for a corrected invocation.
No elapsed-time promises or background execution are implied by this handover.

## Operating boundaries

Research remains separate from the Singapore cloud paper scanner. Do not copy
an old local approval file onto the server: the cloud approval book differed
from GitHub when checked. No production code, orders, stops, targets, worker
settings or approvals were changed during this recovery/audit.

Never archive credentials, API keys, SSH private keys or environment secrets.
Share the private checkpoint with a named handover recipient only when Brian
authorizes that disclosure. Nothing in this handover grants live-trading rights.

## Required practice for each later experiment

Freeze a protocol; record input/code hashes and package versions; retain every
attempt, negative result and exclusion; export full ledgers plus concise tables;
save a checkpoint; reopen it and verify its manifest; publish permitted reports;
update this status register with completed, pending and blocked work separately.
Do not mark an experiment complete merely because code or a plan was saved.


