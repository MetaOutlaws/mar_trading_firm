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
- Added the frozen adapter boundary. It accepts only a passed audited cache,
  uses membership supplied before scoring, ends new-token contexts at
  2026-01-01 exclusive and contains no outcome-reporting or optimization path.
- Completed the reference-parity gate against the restored cumulative
  checkpoint: all 69 approved source signals, 276 immediate paths, 168 retest
  paths, 69 causal-prefix checks, 24 independent admission replays and the
  complete 260-row immediate plus 160-row retest ledgers reproduced exactly.
- Added the immutable freeze gate. Before a run can be claimed it must re-hash
  the audited cache, membership/catalog, closed-2026 signal inventory,
  protocol, exact runner, preparation record and reference-parity evidence.
- Recorded the disclosed possibility that Grok has previously examined this
  dataset. No Grok outputs have been accessed or used to select or tune this
  independent comparison.

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
2. Run the completed adapter against that audited cache and review the
   outcome-blind signal inventory.
3. Publish the completed scoring/report runner, review it, then bind its exact
   hash with `freeze_gate.py` together with the protocol, audited inputs and
   membership.
4. Atomically claim and execute one independent H-RETEST-EXPANSION-01 run.
5. Independently verify every path, cost, admission replay, paired attribution
   and report row before publishing aggregate evidence and private CSV ledgers.

Grok output, if later found, remains separate prior-use evidence and is not used
to select thresholds, tokens, sides or the retest deadline.

## One-shot scorer prepared — 9 October 2026

`run_expansion.py` now implements the frozen comparison without opening any
additional-token outcomes: immutable-freeze verification, atomic independent-run
claim, 2026 hard boundary, exact retest-prefix checks, actual-fill SL2%/TP2.5%,
separate arm admission books, both return denominators, all token/side cells,
missed-winner and delay accounting, paired 1/4-week bootstrap at both fixed seeds,
concentration sensitivities, protocol classification and hashed output readback.
Synthetic accounting tests pass. The run remains unclaimed pending audited data
and a freeze against the published runner hash.

## Independent result verifier prepared — 9 October 2026

`verify_results.py` is separate from the one-shot scorer. After a completed run
it revalidates frozen hashes and safety flags, reconstructs all 16 independent
portfolio admission replays, recalculates every admitted cash return and both
return denominators, checks every token/side cell and original-signal pair, and
writes a hash-bound independent verification report. Synthetic mutation,
denominator, zero-fill and closed-2026 tests pass. No run was claimed.
