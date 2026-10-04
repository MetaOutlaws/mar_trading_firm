# Entry diagnostics and trailing exits — 2026-10-04

Isolated research. Status: `CLOSED_NULL`. Read `FINDINGS.md`. All 18 Stage 2 configs failed validation on the box run and on Munha's independent score. Stage 3 was skipped. 2026 was not scored. Do not merge this PR for trading, and do not enlarge the budget.

The protocol text is `EXECUTION_ADDENDUM.md`. Numeric trade cells in `experiment_ledger.csv` are blank because those CSVs were not in this workspace. See `results/TABLES_TO_ATTACH.md`.

## Reproduce the tests

From the repository root, with numpy, pandas, and pyarrow installed:

```bash
python3 -m unittest discover -s research/isolated_token_study_20261003/entry_trailing_20261004 -p "test_*.py"
```

The tests use synthetic bars. They do not open a market cache.

## Reproduce a locked market run

This budget is closed. Do not rerun it to search for a pass. The command below is the one the box was expected to use. Do not commit raw parquet files.

```bash
python3 research/isolated_token_study_20261003/entry_trailing_20261004/run_study.py \
  --cache /path/to/cache \
  --out /path/to/new_output_directory \
  --acknowledge-garwe-lock
```

`--out` must be a directory that does not exist yet. Without `--acknowledge-garwe-lock` the process exits 2 and does not open the cache.

Cache layout:

```text
BTCUSDT_1m.parquet
ETHUSDT_1m.parquet
SOLUSDT_1m.parquet
funding/BTCUSDT_funding.parquet
funding/ETHUSDT_funding.parquet
funding/SOLUSDT_funding.parquet
```

Archive SHA256: `344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc`

## What a completed run writes

All of these land in `--out`, not in git, until a later review commits tables:

- `manifest.json` — source hashes, the six input hashes, audit counts. `scores_2026` is false.
- `stage1_summary.csv`, `stage1_effects.csv` — 96 descriptive cells, including failures, plus matched feature differences.
- `stage2_summary.csv` — all 18 entry configs. The gate sample is the declustered 4-hour fixed horizon.
- `frozen_selection.json` — at most one entry id per token, written before any exit is scored. Null when the screen fails.
- `{entry_id}_{discovery|validation}_{comparable|stress|desk}_trades.csv.gz` — declustered Stage 2 trades.
- `stage3_summary.csv` — present even when empty. `stage3_NOT_SCORED.txt` explains an empty freeze.
- When a token freezes: `s3_{TOKEN}_{entry_id}_{exit}_{partition}_{cost}_{paired|chronological}_trades.csv.gz`.
- `experiment_ledger.csv` in this folder is the decision record: 18 validation failures, Stage 3 skipped, numeric cells blank until the box files are attached.

Per-trade columns: `experiment_id`, `entry`, `exit_bar`, `side`, `entry_price`, `exit_price`, `partial_price`, `gross_return`, `fees`, `funding`, `net_return`, `reason`, `ambiguous`, `holding_minutes`, `mfe`, `mae`, `giveback`, `activated`.

Stage 3 screens, if a freeze exists, use the chronological one-position trade list. Paired rows isolate the exit on identical entries and are not a second search. Drawdown is the peak-to-trough decline of the cumulative sum of unit-notional net returns. It is not account equity.
