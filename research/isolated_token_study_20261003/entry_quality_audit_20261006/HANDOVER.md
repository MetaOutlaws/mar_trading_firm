# MAR research handover — updated 7 October 2026

Owner: Brian / Meta Outlaws. Repository: MetaOutlaws/mar_trading_firm.
Purpose: reproducible handover and restart without reconstructing the chat.


## Latest completed: previous-day sweep confirmation — 7 October 2026

Duplicate audit corrected the novelty claim: prior_day_extreme_reject was already
family 118/PR16. No exact 15m next-candle confirmation variant was found in the
inspected GitHub/Grokbot records; external runtime history is not certified.
The separately frozen confirmation comparison is now completed and REJECTED.
Protocol-before-scoring commit 7403b72ef1a8c99e920ddcd39dfa3c0597547781.

2025 immediate: 687 entries, 684 closed, 380 stops, 304 targets, 3 terminal marks;
mean net -0.2464% base/-0.3874% stress. Confirmed: 230 entries, 227 closed, 132 stops,
95 targets, 3 marks; mean -0.3505%/-0.4858%, closed win rate 41.85%.
2022–24 immediate 1,825 entries/1004 stops/-0.2249% base/-0.3657% stress;
confirmed 559 entries/293 stops/-0.1088%/-0.2475%. Neither arm is profitable.
Confirmation filters both losers and winners, and later entry consumes the
apparent selection benefit. All three tokens are negative under stress in both
periods. Do not rescue this failed rule by selecting a positive year or cell.

13 tests, 3503 independently reconstructed first setups, 4,151 raw-path checks,
eight admissions and 124 report-row reconciliations passed. 6,602 scenario rows
are 2,512 immediate plus 789 confirmed admissions at two costs, not independent
trades. Read sweep_confirmation_20261007/{NOVELTY_AUDIT,PROTOCOL,FINDINGS}.md.
results_v2 is complete; results_v1 is a preserved pre-scoring software failure.

Next: acquire/audit additional-token data for the frozen replication protocol
and collect prospective evidence from the approved hourly pilot. This new entry
comparison and both previous exit treatments are closed. No further experiment
runs in the background; reserved 2026 remains unscored. Any future entry test
needs a distinct, audited hypothesis and pre-scoring protocol.

The latest observed cloud cycle remains 2026-10-07T10:05:31.385232+00:00,
six hourly BTC/ETH/SOL LONG/SHORT paper configurations, errors [].
No current SSH channel or newer cloud observation is claimed.

Restore MAR_sweep_and_exit_studies_checkpoint_20261007.zip on top of
MAR_hourly_compression_checkpoint_20261007.zip, keeping the original raw ZIP
separately. This combined increment includes both earlier exit studies and the
sweep comparison. The separate previous exit increments are not also required.
See sweep_confirmation_handover/RESTORE_SWEEP_STUDY.md and verify hashes.


## Start here

## Latest completed: fixed failed-breakout exit — 7 October 2026

The predeclared rule exits at the next minute open after a completed hourly
close back through the FIXED entry-time 20-hour breakout boundary. Original
hourly entries, SL2% / TP2.5%, costs and admission limits remain unchanged.
Protocol was published before scoring at fe51e67511a8ae7b738d7a27c7a0914d3573ba75.

Decision: reject this treatment under the frozen improvement screen. In 2025,
36 baseline trades become 38: actual stops fall 14 to 2, but 23 early failure
exits and 13 targets produce +0.1031% base / -0.0254% stressed mean net return,
versus baseline +0.4992% / +0.3685%. Net win rate falls 61.1% to 34.2%.
On the same 36 entries, 12 original stops improve but 11 target winners are
cut short. Two new winning entries only partly offset the damage.

In 2022–24, 97 baseline trades become 104: 12 stops, 59 failure exits, 33
targets, -0.0432% base / -0.1654% stress, versus +0.2268% / +0.1037% baseline.
Seven newly admitted trades partly offset, but do not reverse, the lost returns.
All three tokens worsen under stressed costs in both partitions. Every one of
the 82 chronological failure exits is a net loss at both cost levels.

Read hourly_failed_breakout_20261007/FINDINGS.md and PROTOCOL.md. Validation:
22 tests; 143 independently reconstructed entry boundaries; 286 independent
raw paths; 286 raw/266 admitted baseline rows exactly reconciled; eight
independent admissions; 124 report-row checks. The 550 ledger rows are cost
scenarios across 133 baseline and 142 treatment admissions, not 550 independent
trades. There are 78 affected original admissions in the changed-trades CSV.

Both the price-break-even and fixed failed-breakout exit hypotheses are now
completed with negative improvement findings. Keep the approved baseline
unchanged and pause further fitting of these exits to the same history.
Priorities: acquire/audit additional-token data for the existing frozen
replication protocol and collect prospective paper evidence. Preserve reserved
2026 outcomes and the broader-token qualification rules. A future exit study
requires a distinct hypothesis and separately frozen protocol. No test is
running in the background; no production exit changes or leverage tests.

Current operational evidence remains the operator-supplied scanning_verified
for all six hourly BTC/ETH/SOL LONG/SHORT configurations, errors [], cycle
2026-10-07T10:05:31.385232+00:00. No newer cloud observation is claimed here.

Restore MAR_exit_studies_checkpoint_20261007.zip on top of the full
MAR_hourly_compression_checkpoint_20261007.zip. This combined increment
contains both exit studies; the earlier standalone profit-protection increment
is not also required. Keep the original raw candle/funding ZIP separately.
Follow RESTORE_EXIT_STUDIES.md and verify all hashes.

## Previous completed: profit protection and confirmed paper scan — 7 October 2026

The operator's screenshot returned `scanning_verified` for all six hourly
BTC/ETH/SOL LONG/SHORT paper configurations, with `errors: []`. The completed
cycle started at 2026-10-07T10:05:31.385232+00:00, after successful activation.
This is evidence of that cycle, not continuous SSH monitoring by this chat.

The profit-protection protocol was published before scoring at
8f26ae5a4c49f521dbdee860c209387fea203976. One fixed treatment moved the stop to
the entry quote on the minute after a completed +2% favorable close, keeping
hourly entries, initial SL2% / TP2.5%, costs and occupancy fixed.

Result: reject this treatment under its improvement screen. In 2025, 36 trades
remain; original stops fall 14 to 13, but five protective exits cut four target
winners and intercept only one original stop. Mean net falls +0.4992% to
+0.2754% base, and +0.3685% to +0.1445% stress. Net win rate falls 61.1% to 50.0%.
In 2022–24, 97 trades remain; two original stops and two target winners are
intercepted, and stressed mean falls +0.1037% to +0.0928%. No extra or dropped
admissions explain either comparison. All nine protective exits are net losses
at both cost levels. The approved paper baseline stays unchanged.

Read hourly_profit_protection_20261007/FINDINGS.md and PROTOCOL.md. Verification:
19 tests; 286 independent raw path checks; 286 raw/266 admitted baseline rows
reconciled exactly; eight independent admissions; 124 report-row checks.
532 ledger rows represent 133 admissions × two arms × two cost scenarios.
All prior outcomes and frozen evidence remain intact. No new-token or 2026
outcome, live change, or leverage test.

Proposed next research: freeze one failed-breakout exit at a completed hourly
close back inside the ENTRY-TIME breakout boundary, with next-minute execution,
and compare winners cut short with losses reduced. This has NOT run and is
not approved for deployment. Broader-token/forward confirmation remains
pending; reused 2025 is not an independent holdout.

Restore the incremental MAR_profit_protection_checkpoint_20261007.zip AFTER
the full MAR_hourly_compression_checkpoint_20261007.zip; keep the original
raw candle/funding ZIP separate. Follow RESTORE_PROFIT_PROTECTION.md and verify
each manifest. No experiment is running in the background.

## Latest owner decision and stop-only experiment — 7 October 2026

Brian explicitly approved hourly compression on BTC/ETH/SOL, both directions,
for PAPER use at SL2% / TP2.5%. Preserve the original positive baseline and
record owner approval separately from independent research qualification.
The runtime module and guarded activation script are prepared and tested;
Singapore is active in DigitalOcean, but this chat has no SSH execution access.
At that earlier preparation stage, cloud activation was pending. The current\noperator-confirmed scanning status is recorded above.

The stop-only protocol was published before scoring. With TP fixed at 2.5%,
2025 results (closed/stops; net base/stress) are: SL1% 37/25, -0.1092%/-0.2385%;
SL2% 36/14, +0.4992%/+0.3685%; SL3% 36/13, +0.2627%/+0.1320%;
SL4% 36/10, +0.4418%/+0.3111%; SL5% 36/8, +0.5779%/+0.4477%.
SL1% loses 11 baseline target winners. SL5% recovers six of 14 baseline stops,
but has lower mean R than SL2%. No alternative improves both stressed mean net
and mean R in both partitions; the approved 2% baseline remains unchanged.
Read hourly_stop_width_20261007/FINDINGS.md and PROTOCOL.md.

Verification: 143 raw signals, 715 independent barriers, 20 independent
admission replays, 266 exactly reconciled baseline rows, 1, 330 alternative
ledger rows. Six implementation tests pass; 143 research entry signals and
1,734 rolling candidate checks match. No new token or 2026 price scoring.

At this earlier stage, the queued research was a profit-protection comparison with unchanged
hourly entries and initial 2%/2.5% barriers, counting winners cut short as well
as stopped-trade profits saved. That comparison has since completed; see the latest section above. New-token confirmation remains
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
- Secondary 1h/24h diagnostic: 117, 310 matched signal-horizon observations,
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
