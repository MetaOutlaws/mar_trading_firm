# Result tables still to attach

The decision is already recorded: all 18 Stage 2 configs fail validation, Stage 3 was skipped, 2026 was not scored. This directory does not contain the box or Munha numeric files. They were not on the cloud VM.

Please attach, without changing a threshold:

- `stage2_summary.csv` from the box run, one row for each of the 18 ids, with trade count, mean, profit factor, doubled-slippage means, and the desk 31 bp means for discovery and validation.
- `frozen_selection.json` from that run. It should be null for BTCUSDT, ETHUSDT, and SOLUSDT.
- `stage3_summary.csv` if the runner wrote an empty file, or `stage3_NOT_SCORED.txt`.
- Declustered per-trade `csv.gz` files if they were kept: `{entry_id}_{discovery|validation}_{comparable|stress|desk}_trades.csv.gz`.
- Munha's independent score table, if it is a separate file from the box summary.

Until those files are added, the ledger leaves the numeric cells blank on purpose. `frozen_selection.json` and `stage2_screen.csv` in this folder record only the confirmed screen outcome.
