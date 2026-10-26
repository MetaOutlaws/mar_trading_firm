# Integration handoff for Codex / Grokbot

Implement the fixed MAR-3R-FORWARD-09 experiment in `protocol.json`. Do not
optimize another historical parameter or deploy the candidate evaluator alone.
This handoff is committed for review; no external message was sent.

## Begin with evidence

1. Read this PR, `SOURCE_RECONCILIATION.json`, PR #149 at its actual current head,
   and the current default branch. Capture the running container's release,
   mounted source hashes and effective runtime overrides with the read-only
   audit plus worker/ledger receipts. Do not print credentials or copy `.env`.
2. Keep the production checkout, balances, open positions and kill flags intact.
   No migration is necessary. This trial adds internal simulated portfolios, not exchange accounts.
   In particular, do not invoke `deploy_recovery_paper.sh` for this trial.
3. Pin hourly L01/F111 and original BL8 source identities. This baseline contains
   those two strategies, not every unrelated strategy on the existing production paper book.
   Record old A00-to-current-source and research-to-forward-execution differences.

## Implement the isolated runtime

- Feed the same contemporaneous H/B/C3 candidates and immutable quote snapshots
  to I, IC, IM and IF. Apply source priority H, B, C3, then symbol/UID. Equal
  priority opposing signals are rejected. Do not let one book's capacity or
  outcome suppress the candidate feed or another book's opportunity record.
- Use the candidate evaluator and allocation functions in this branch. Build
  complete UTC hourly OHLCV/turnover from verified public data, a fixed persisted
  EMA seed and a causal incremental feed. Every missing/unavailable instrument
  is an observation; never silently replace a delisted token with an alias.
- Twelve internal simulated portfolios each begin flat at 20,000 USDT of simulated cash. Enforce all protocol gates,
  including same-symbol inclusive exit-minute occupancy, two per sector,
  20 daily entries, fee-aware planned risk, remaining gross headroom, C24 and
  the independent 15% drawdown entry latch. Keep all raw losses and manual stops.
- Round quantity down to verified exchange lot increments and recompute risk
  against the depth-priced fill without increasing quantity. Use actual fresh
  depth, not a future candle close. Original 2R entry eligibility remains in
  force even though the short's actual fixed target is 3R.
- Persist raw observations, signals, every per-book reason, simulated fills,
  cash, positions, protection state, funding settlements and recovery state
  atomically. Use stable event IDs; exact duplicates are idempotent, conflicting
  duplicates fail closed. Never silently replace a missing/corrupt ledger.
- Freeze quote/exit sampling cadence in the release and verify the latency
  budget. Evaluate observed stop before target; hourly protection is effective
  no earlier than the next minute. Do not backfill missed entries at old prices,
  invent intrabar order, or use an exit observed later to finance an earlier
  entry. Gap and stale-price outcomes remain explicitly incomplete.
- Accrue signed observed funding exactly once, entry boundary excluded / exit
  included. Missing funding remains unknown and holds new funded admissions;
  existing exits still execute. C24 cannot clear drawdown, manual or data holds.
- Independently follow each executable signal at 2,000 USDT hypothetical
  notional, including signals blocked by capital, slots, sector, occupancy,
  daily loss, streak, drawdown or the fixed IF filter. Link outcomes to all four
  decisions. Invalid/missed price observations remain recorded without a fake
  trade. Overlapping opportunities have no funded-portfolio ROI.
- Baseline, moderate, and severe keep separate simulated admissions and cash.
  Reports show four strategy comparisons. Baseline and moderate are prominent.
  Severe is secondary display only. Quote snapshots are observations; fees and extra slippage
  are model assumptions. Do not describe paper fills as exchange execution.
- Provide daily overall/calendar-year/token/sector/source returns and R,
  drawdown, count, expectancy, win rate, profit factor, costs, exposure, blocked
  opportunities and data coverage. Show open versus completed outcomes.

## Required execution evidence before starting the clock

The candidate receipt in this branch is already complete. The remaining test
is a portfolio/runtime integration test, not a new strategy search:

- four books receiving exactly the same input IDs, with independent cash/gates;
- no double-scaled half-size headroom; unchanged incumbent sizing;
- all rejection causes still reach the opportunity recorder;
- restart and abrupt-death replay with exact cash/position/event reconciliation;
- no repeated funding, correct short sign, delayed funding and partial quote gaps;
- causal same-minute close/entry ordering and next-minute protection;
- C24 boundary cases and preservation of drawdown/manual/data latches;
- quote freshness, missed-window handling, zero-fill scan and unavailable tokens;
- hour/four-hour boundary, seed continuation and no future-bar feature access;
- public market GET allowlist with no exchange credentials/order route supplied.

Return an isolated release SHA, image digest, effective config hash, seed hash,
fresh runtime audit, test receipt and installation plan. When the authorized
operator starts the reviewed trial, record the actual first future cutoff,
first complete scan and reconciled book evidence. Until then set
`paper_trial_started=false` and `activation_verified=false`. Do not mark this
preparation PR as an activated trading release.

Keep the separate PR149 recovery deployment and carry-data research workstreams
intact; report their real status without overwriting it to complete this task.
