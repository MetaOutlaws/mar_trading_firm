# MAR research handover — 6 October 2026

Owner: Brian / Meta Outlaws. Repository: MetaOutlaws/mar_trading_firm.
Purpose: reproducible handover and restart without reconstructing the chat.

## Start here

1. Read FINDINGS.md for the latest primary-audit result and its limits.
2. Read PROTOCOL.md and RECONSTRUCTION_AMENDMENT.md before rerunning anything.
3. Use the private checkpoint archive for complete code, detailed evidence and
   historical files. Public GitHub contains reports, protocols and aggregates;
   it is not the only copy of the research evidence.

## Durable artifacts

| Artifact | Purpose | Verification |
|---|---|---|
| isolated_token_study_1m_2022_20261002_v2.zip | Original BTC/ETH/SOL data and funding, saved privately | SHA256 below; 17 ZIP members pass CRC |
| MAR_research_checkpoint_20261006.zip | Research code, existing evidence, current reconstruction, primary comparison and pinned public-report snapshot | SHA256SUMS.json verifies every packaged payload |
| individual_trades_reconstructed.csv.gz | 38,469 reconstructed baseline positions, base costs | Reconstruction manifest and 72-row published reconciliation |
| prediction_v1/primary_summary.csv | 36 period-specific primary results, CIs, coverage and flags | Prediction manifest |
| prediction_v1/paired_signals.csv.gz | Every matched signal and mean control result | Prediction manifest |
| prediction_v1/control_draws.csv.gz | All 1,126,166 control draws, including reuse | Prediction manifest |
| prediction_v1/excluded_signals.csv.gz | Unmatched/censored signal reasons | Prediction manifest |
| published_snapshot/ | 23 research files retrieved from pinned GitHub commit | Snapshot index and package hashes |

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

Original row-level identity is not proven. The reconstructed export does not
claim to reproduce the former feature-enriched CSV column for column.

## Pending, not running in the background

- Secondary one-hour/24-hour excursion and matched costed-exit diagnostics.
- Separate breakout/retest entry protocol and test.
- Separate profit-protection comparison.
- The cost-aware minimum zone-target-distance fallback remains unverified as
  completed; check evidence before asserting it has run.
- Fresh confirmation of any future selected strategy. 2025 is already reused.

Existing ATR-cap comparisons have already been completed and failed their
screen. A new adaptive-stop experiment must name a genuinely different
hypothesis; do not silently repeat or relabel the old test.

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
