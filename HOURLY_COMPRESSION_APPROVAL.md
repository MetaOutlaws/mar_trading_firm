# Hourly compression v1 — owner-approved paper pilot

Owner approval received 7 October 2026. Strategy `hourly_compression_v1`:
BTCUSDT, ETHUSDT, SOLUSDT; 1h; LONG and SHORT; SL 2%; TP 2.5%; no holding
timeout. No new tokens, live trading or leverage change is authorized here.
All existing research results are retained unchanged.

## Status

Implementation prepared and locally verified. The operator attempted activation
on 7 October 2026: code installation succeeded, but approval replacement failed
with EBUSY because the JSON file is individually bind-mounted. **Approval and
scanning are not yet verified.** The corrected host-side repair preserves the
existing book, pauses its container readers by stopping them, replaces the host
file atomically, then starts the same containers and checks remounted bytes.

The six records use `paper_override=true`, `approved=false`, and unrestricted
regime activation. In this codebase `approved` means research/live eligibility;
it is deliberately separate from the owner's paper approval. An additional
runtime guard refuses this strategy outside PAPER mode or outside BTC/ETH/SOL.
The script merges six additions, backs up the existing cloud approval book,
preserves persistent-state symlinks, and refuses conflicting existing records.
It does not copy the repository's old approval book to the cloud.

## Preserved baseline

2025: 36 closed trades, 22 targets, 14 stops (38.9%), net mean +0.4992% at base
costs / +0.3685% at doubled slippage. Historical 2022–24: 97 trades, 44 stops,
+0.2268% / +0.1037%. These are per-trade returns, not account returns.
2023 lost money and confidence intervals span zero. Owner paper approval does
not change the exploratory research classification. Extra-token tests will be
separate records; new evidence may change confidence without rewriting history.

## Entry rule and validation

Prior 6-bar mean TR / prior 60-bar median TR <= 0.7; current TR >= 1.5 times
prior Wilder ATR14; volume >= 1.5 times prior 20-bar median volume. Long requires
a bullish close above the prior 20-bar high, close in the top quarter, and
nonnegative 24h return. Short mirrors these conditions. Completed 1h candles
only. No RSI, ADX, funding or regime directional filter is added.

Validation: six focused tests cover both directions, causal prefix invariance,
volume rejection, gaps, frozen exits, paper-only scope atomic activation/backup, recent-cycle verification, and six plan rows with
exclusion from the approved-only plan. Historical parity checks cover 32,904
hours per token/side, 143 raw signals and 1,734 rolling-window candidates.
All frozen research membership-period feature-eligibility flags were true;
the runtime requires at least 800 contiguous hourly candles. This establishes
entry-predicate parity on the available history, not fill/account parity.

## Execution differences that forward paper must measure

The research simulator enters at the next minute open and anchors brackets to
that unslipped quote, charges adverse slippage on both legs, uses actual settled
funding and minute stop-first paths. The existing desk uses its `exec-f04-v1`
contract: sampled execution after the signal, fill-relative brackets, sampled
15-second stop supervision and its own costs/funding. It shares token occupancy
and risk/agent limits with other enabled strategies. A clean standalone replay
does not include those competing strategies or operational delays.

This patch retains the desk's execution/risk rules. It does not silently change
other open trades to the historical simulator's contract. It also does not add a
new monthly universe-selection service; paper scope is the explicit three-token
owner whitelist. Log forward signals, rejections, delays and fills separately
and reconcile paper versus the reference before interpreting performance.

## Operator activation and verification

Use the revised `enable_hourly_compression_20261007.py` through SSH with HOST
`python3 -`, not `docker exec`. It verifies PAPER mode and pinned runtime/code
hashes, discovers the writable file-bind source via Docker inspect, and refuses
unexpected running consumers. Only the previously running paper engine and API
may be stopped. After both readers/writers stop, it rereads the current host
approval book, backs it up, merges six additions and atomically replaces that
host file while retaining permissions and ownership. It starts the original
containers in a finally block, then checks they see identical current bytes.
It never truncates the mounted file under active readers or changes the entry
rule, risk settings or live approval. Container data is retained by stop/start.

The previous installer ran far enough to install code but failed before the
approval replacement. The v2 repair accepts only that known old helper hash or
the new helper hash; unknown modifications still require review. Its container
helper is now idempotent when all six exact approval rows already exist, so
finalization does not try renaming a mounted file again.

Validation: 15 automated tests including simulated EBUSY, untouched bytes on
failure, host atomic merge/backup and metadata, repeat application, consumer
stop/start ordering, failure recovery, and complete generated-command flow.
Actual Singapore repair and fresh scanning confirmation remain pending operator
execution. No new historical research result or strategy parameter changed.

After installing, run `python /app/scripts/enable_hourly_compression.py --verify`
inside that container after a fresh completed cycle. `installed_awaiting_cycle`
is not scanning confirmation. Only `scanning_verified`, with all six rows in a
recent post-activation cycle and no halted/blocked/error status, completes it.

If installation reports a failure, retain its output and named backup; do not
retry using a broader Git checkout. To disable only this pilot, remove its six
paper-override rows atomically after inspecting the current book. Existing
positions remain subject to their original exit supervision; never delete
positions or replace the entire approval file with an old backup blindly.

## Next research

The separately frozen SL1–5% / fixed TP2.5% diagnostic has completed. No arm
beats baseline on both net mean and risk-normalized mean in both partitions.
Keep the owner-approved SL2% setting. Next: predeclare a narrow profit-protection
test on these same entries, measuring stopped-trade profits saved and target
winners cut short. Additional-token confirmation remains pending data.
