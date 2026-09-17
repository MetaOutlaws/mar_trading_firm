# Revalidation kit — certified vs exploratory

CEO LOCK Option B / 1-week DONE. Keyed to
`RESEARCH_VERSION = wf-f01-oos-window-v1` (F01 OOS window repair, #60).

This kit **re-measures** the three research-approved book survivors and writes
a Board deltas report. It does **not** promote, does **not** write
`approved=true`, and does **not** touch `config/approved_strategies.json`.

Live stays off. Auto-advance stays off. Eng never self-unfreezes.

## Certified vs exploratory

| Class | What it is | This kit |
|---|---|---|
| **Certified survivor** | A row in `config/approved_strategies.json` with `approved: true`. On HEAD that is exactly three keys (all SHORT). The 12 Sep review and 17 Sep Board calendar treat these as **candidates pending revalidation**, not proof. | Re-run only these, with **pinned certified params** (empty search grid — not a new promotion). |
| **Exploratory** | `paper_override: true` rows, every `approved: false` row, coding-only sleeves, new families, Job 133. | Listed and **skipped**. Do not pool them into the validated scorecard. |

Frozen certified keys (must match the live book exactly or the kit fails closed):

- `atr_channel_breakout:BTCUSDT:SHORT:4h`
- `atr_channel_breakout:ETHUSDT:SHORT:4h`
- `doji_star_reversal:SOLUSDT:SHORT:1h`

Exploratory paper-override keys currently on the book (not re-run):

- `mass_index_reversal:SOLUSDT:LONG:4h`
- `mass_index_reversal:ETHUSDT:SHORT:4h`
- `mama_fama_cross:BTCUSDT:SHORT:4h`
- `mama_fama_cross:ETHUSDT:SHORT:4h`

Gates are unchanged: **PF ≥ 1.15**, bootstrap CI excludes zero, beats-random.
The kit *reports* whether each survivor still clears those gates. Clearing
them is **not** an approval stamp.

## Commands

From the repo root (after `pip install -e .`):

```bash
# Full kit: F01+F02+F03+gate regressions, then survivor re-runs, then report
python scripts/run_revalidation_kit.py

# Book inventory + SHA-256 only (no pytest, no walk-forward)
python scripts/run_revalidation_kit.py --check-book

# Regressions the kit depends on (reuse existing tests)
python scripts/run_revalidation_kit.py --regressions-only

# Certified survivors only (requires Bybit public klines / local parquet cache)
python scripts/run_revalidation_kit.py --survivors-only

# Pytest of the kit’s own guards (no book write)
pytest tests/test_revalidation_kit.py tests/test_walkforward.py \
       tests/test_paper_cash_hydrate.py tests/test_f03_fee_funding.py \
       tests/test_validate_gates.py
```

Artifacts (gitignored, same as other research reports):

- `research/artifacts/revalidation_kit_<UTC>.json`
- `research/artifacts/revalidation_kit_<UTC>.md`
- copies at `research/artifacts/revalidation_kit_latest.{json,md}`

There is **no** `--write` / `--stamp` flag. `scripts/validate_strategy.py`
without `--no-write` is the approvals writer; **do not** point it at these
survivors during the freeze.

## What the survivor re-run measures

For each certified key the kit:

1. Reads the stored params and `oos_*` from the book (prior certified result).
2. Loads the same family + symbol + side + timeframe.
3. Walk-forwards with **empty `search_space`** so the certified params are
   evaluated under F01 half-open `[test_start, test_end)` windows. Warmup bars
   seed indicators; they are not tradable.
4. Runs the same `_evaluate_gates` (PF / CI / beats-random) used by promotion.
5. Emits prior vs current PF, trades, expectancy, drawdown, win rate, plus the
   new CI and fold windows (prior rows have no `research_version` / CI).

It does **not** merge the verdict into the approval book.

## How CEO / Board uses the report to decide freeze lift

1. Confirm `approval_book_unchanged` is true. The book (including the existing
   three `approved=true` rows) must be byte-identical. Eng does not stash,
   reset, or rewrite it to manufacture a green kit.
2. Confirm F01 / F02 / F03 regressions are green (`regressions.ok`).
3. Read each survivor’s deltas vs stored `oos_*`. A collapse in PF, a CI that
   now includes zero, or a beats-random fail is evidence the stored approval
   does not survive corrected windowing/costs.
4. `kit_green` is true only when inventory matches, the book is unchanged,
   regressions passed, all three survivors ran, **and** all three still clear
   the hard gates.
5. **If `kit_green` is true, the Board may lift the freeze.** That decision is
   the Board’s. This kit never writes `approved=true`. Eng never self-unfreezes.
6. **If `kit_green` is false, the freeze stays.** No new promotions. Existing
   three rows remain candidates. Exploratory walks elsewhere are still allowed;
   they are not this kit.

Not a go-live recommendation. `TRADING_MODE=paper`. `PIPELINE_AUTO_ADVANCE`
fail-closed. Job 133 stays dead. F04 golden-tape, F05 exit-supervision, and
§5 promotion-gate hardening are separate packages.
