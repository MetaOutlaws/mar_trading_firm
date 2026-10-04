# Entry diagnostics and trailing exits — 2026-10-04

Isolated research. Status: `CLOSED_NULL`. Read `FINDINGS_2026-10-04.md`. All 18 Stage 2 configs fail the pre-registered screen. The freeze is null, so Stage 3 was not scored. `scores_2026` is false. Do not merge this PR for trading, and do not enlarge the budget.

The protocol text is `EXECUTION_ADDENDUM.md`. `experiment_ledger.csv` is the box ledger. The verbatim output directory, including per-trade files and Munha's memo, is `results_box_20261004/`.

## Reproduce the tests

From the repository root, with numpy, pandas, and pyarrow installed:

```bash
python3 -m unittest discover -s research/isolated_token_study_20261003/entry_trailing_20261004 -p "test_*.py"
```

The tests use synthetic bars. They do not open a market cache. They also check that the committed ledger still contains the sealed `model_l2_SOLUSDT_long` cells.

## Reproduce a locked market run

This budget is closed. Do not rerun it to search for a pass. The command below is how the box run was invoked. The archived output is already in `results_box_20261004/`. A new `--out` directory would be a regeneration, not a new search. Do not commit raw parquet files.

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

## What the archived run contains

- `manifest.json` — source hashes, the six input hashes, audit counts. `scores_2026` is false. The file does not contain git SHA `c2693bc`.
- `stage1_summary.csv`, `stage1_effects.csv` — descriptive cells, including failures. Not the screen.
- `stage2_summary.csv` — all 18 entry configs. `passes_screen` is False on every row.
- `frozen_selection.json` — null for BTCUSDT, ETHUSDT, and SOLUSDT.
- 108 `{entry_id}_{discovery|validation}_{comparable|stress|desk}_trades.csv.gz` files — declustered Stage 2 trades.
- `stage3_summary.csv` — a single newline. `stage3_NOT_SCORED.txt` says the four exit specs were not applied.
- `experiment_ledger.csv` — the 18 scored Stage 2 rows.
- `MUNHA_NULL_2026-10-04.md` — Munha's score of those artifacts. He did not rerun.

Per-trade columns: `experiment_id`, `entry`, `exit_bar`, `side`, `entry_price`, `exit_price`, `partial_price`, `gross_return`, `fees`, `funding`, `net_return`, `reason`, `ambiguous`, `holding_minutes`, `mfe`, `mae`, `giveback`, `activated`.
