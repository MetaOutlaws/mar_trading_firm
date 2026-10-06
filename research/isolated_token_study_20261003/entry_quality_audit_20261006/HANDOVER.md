# MAR research handover — 6 October 2026

Owner: Brian / Meta Outlaws. Repository: MetaOutlaws/mar_trading_firm.
Purpose: reproducible handover and restart without reconstructing the chat.

## Start here

1. Read FINDINGS.md for the primary-audit result, SECONDARY_FINDINGS.md for
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

Original row-level identity is not proven. The reconstructed export does not
claim to reproduce the former feature-enriched CSV column for column.

## Pending, not running in the background

- Separate profit-protection comparison.
- The cost-aware minimum zone-target-distance fallback remains unverified as
  completed; check evidence before asserting it has run.
- Fresh confirmation of any future selected strategy. 2025 is already reused.

Existing ATR-cap comparisons have already been completed and failed their
screen. A new adaptive-stop experiment must name a genuinely different
hypothesis; do not silently repeat or relabel the old test.

The latest breakout/retest rule is closed with a failed screen; do not tune its
lookback, ATR band or expiry merely to make a historical cell survive. Complete the
research record by reading the completed costed diagnostic, then freeze any new
entry or profit-protection hypothesis separately. The planned profit-protection
test must keep reference entries, initial stop/target and regime exit fixed,
and replay occupancy to measure both saved profits and winners cut short.
More model credits do not change sample independence. Reserve unused data for
eventual confirmation.

## Restart instructions

Extract the checkpoint into a new directory. Extract the original source ZIP
into `data_cache/` there. Use Python 3.12; the recorded run used 3.12.14.

```bash
python -m pip install -r research/isolated_token_study_20261003/entry_quality_audit_20261006/requirements-audit.txt
python verify_checkpoint.py
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
