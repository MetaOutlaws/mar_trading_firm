# H-RETEST-EXPANSION-01 preparation status

Updated 9 October 2026 before any additional-token outcome was opened.

## Completed outcome-blind work

- Restored and verified the cumulative research reference chain. The latest
  retest checkpoint outer SHA256 is
  `a0d73470e4607d7995d4f789107d06d301de77747d8452bf05b73eaa3f4d3a80`;
  all 1,254 files in its current manifest match.
- Restored the original BTC/ETH/SOL minute/funding archive. Its outer SHA256 is
  `344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc`;
  all six minute/funding inputs match the hashes frozen by the completed retest
  experiment.
- Added an outcome-blind collector audit. It verifies the collector manifest,
  frozen membership, catalog, 2022-2025 minute grids, OHLC validity, funding
  coverage and the closed-2026 boundary before writing an audited cache.
- Added an atomic run record owned by `codex_independent`. It refuses a second
  claim once this exact independent comparison is active or recorded.
- Added synthetic tests for manifest paths, changed inputs, membership/rank
  rules, the 2026/reference exclusions and duplicate-run prevention.

## Current blocker

The user-supplied Windows-local dataset directory is not mounted or readable
in this workspace. No replacement dataset, Library upload or
GitHub-linked data manifest was accessible at this checkpoint. This is an
access fact only; it does not imply anything about the user's local files.

No additional-token signal, trade, return, win-rate or 2026 price outcome was
opened. No run record was claimed, because there is not yet a dataset manifest
to bind the independent run to.

## Remaining gates before scoring

1. Audit and hash the accessible collector output with `data_gate.py`.
2. Complete the new-token adapter and reproduce all 69 reference signals plus
   the frozen three-token control/treatment ledgers.
3. Freeze reviewed source, protocol, audited inputs and membership hashes.
4. Atomically claim and execute one independent H-RETEST-EXPANSION-01 run.
5. Independently verify every path, cost, admission replay, paired attribution
   and report row before publishing aggregate evidence and private CSV ledgers.

Grok output, if later found, remains separate prior-use evidence and is not used
to select thresholds, tokens, sides or the retest deadline.
