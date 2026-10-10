# MAR F111 paper implementation handoff — 10 October 2026

## Status and requested outcome

Implement and activate `mar_f111_r12_extension_latefloor_v1` (research case **F111**) for **paper trading across all 96 supplied tokens, LONG and SHORT: 192 eligible scan sleeves**. The owner has authorized this paper implementation and activation. Live trading is not authorized.

**This commit contains a handoff and frozen reference logic, not a working implementation or evidence of activation.** Do not set an activation flag and call the job complete. Inspect, implement, test, deploy to the existing designated Singapore paper worker, and verify fresh runtime evidence. Preserve current capital, sizing, risk controls, unrelated strategies and supervision of existing positions.

The repository baseline inspected was `d82aacc5319f7f660b0321623c94dcce2ef3f092`, default branch `feat/employee-floor-and-openai`. Inspect newer repository and deployed changes before editing. Do not overwrite another agent's work.

## Files and source of truth

- `F111_paper_activation_spec.json`: all 96 exact research symbols, gates, entry/exit settings and telemetry. Treat it as requirements, not an existing application's configuration schema.
- `REFERENCE_RULES.md`: precise units, timing, costs, implementation pitfalls and research limitations.
- `references/`: byte-for-byte research source snapshots. These are reference code, not runnable production modules in this folder. Imports and underlying datasets belong to the private checkpoint; do not wire these scripts directly into the worker or rerun their searches.
- `SOURCE_MANIFEST.json`: hashes of the committed handoff and source snapshots, plus original source paths.

The complete private archive is `MAR_R12_I11_factorial_checkpoint_20261010.zip`, 153167196 bytes, SHA256 `03fbcc49d6d6e97325eb5c6b837e09fdd4a5edaea7dcf1b2fe255c5b89292637`. The owner can attach it privately. It contains code, historical opportunity/decision/trade ledgers, verification results, report and earlier dependencies; raw candles/funding are external. Extract preserving relative paths and follow the enclosed RESTORE.md only if raw replay is needed. Do not publish this archive, raw data, trade ledgers, credentials or operational access details in this public repository.

Key paths relative to the extracted research root:

- `mar_r12_i11_factorial_20261010/PROTOCOL.md`, `FREEZE.json`, `run.py`, `audit.py` and `MAR_R12_I11_AI_handoff_20261010.json`.
- `mar_r12_i11_factorial_20261010/books.parquet`, `source_decisions.parquet`, `all96_token_support.csv`, `protection_changed_trades.parquet`, `paired_intervals.parquet`, `VERIFICATION.json` and `portfolio/VERIFICATION.json`.
- `mar_protection_surface_20261010/simulator.py`, `common.py`, `policies.csv`, `entries.parquet`, `sources.parquet` and `results/opportunities.parquet`.
- `mar_retest_expiry_20261010/run_paths.py` for exact retest timing and its independently written scalar check.
- `mar_overnight_research_20261010/run_stages12.py` for independent admission/accounting.

Private archive access is not implied by knowing its filename. If unavailable, proceed with implementation and synthetic causal tests, but explicitly leave saved-path parity unverified; never invent a passing result. Older archived `execution_enabled=false` fields record research status; the current paper authorization is the separate scope described here.

## Existing repository integration points

Inspect these files and their tests before implementation:

- `core/strategy/hourly_compression_btc_connors_loweff_v1.py` and its parent strategy: preserve original hourly compression, BTC-direction, Connors-RSI and low-efficiency logic.
- `core/execution/engine.py`: existing entries execute immediately; persistent retest and protection lifecycles need integration.
- `core/execution/paper.py` and its cash/ledger dependencies: reuse the paper broker, accounting and restart recovery.
- `scripts/run_paper_trading.py`: previously inspected default scan interval was 900 seconds, with exit polling every 15 seconds and potentially blocking AI work. This is not automatically equivalent to the minute research tape.
- `scripts/enable_hourly_btc_connors_loweff.py`: existing six-sleeve BTC/ETH/SOL pilot uses fixed 2% SL / 2.5% TP. Running this script alone does NOT activate F111.
- `scripts/deploy_hourly_btc_connors_loweff.py`, `scripts/repair_hourly_compression_mount.py`, `tests/test_hourly_btc_connors_loweff.py`, `tests/test_hourly_btc_connors_loweff_deploy.py`: inspect established deployment, mount and backup practices; adapt carefully.

## Implementation sequence

1. Inspect the existing Singapore paper worker, actual checkout/commit, container configuration, mounts, scheduler, mode, positions and persisted cash before mutation. The previously documented project/state paths are `/data/app` and `/data/state`; verify them. Do not create a new VM or start the duplicate New York worker. Do not print secrets or publish runtime positions/access details.
2. Back up code/configuration and ledger using consistent, supported methods. Preserve symlinks and mounted file behavior. Establish a rollback that continues exit supervision and retains newly written paper state; do not roll the ledger back blindly.
3. Implement the exact gates, persistent pending retests, minute decisions, original ATR/R tracking, monotone cost-aware protection and telemetry. Keep these independent of blocking AI calls. Enforce paper mode and ensure no live-approved plan can select this strategy. Reject stale/missing inputs explicitly; never backfill an actionable price from the past.
4. Retain all 96 symbols in the eligibility and coverage registry, including zero-history tokens. Resolve current exchange instruments through verified metadata. Delisted/unavailable symbols must have explicit status; never substitute a renamed token or contract multiplier silently. A 96-token registry does not mean 96 currently tradable instruments. Record actual available coverage and outstanding gaps.
5. Preserve existing risk limits and capital. Do not infer account sizing or leverage from the study's 0.02 research risk units. Maintain per-token occupancy, deduplication and existing kill switches. Collect every original signal and rejection even when portfolio or agent risk controls prevent entry; report those deviations separately from frozen strategy decisions.
6. Verify deterministic timing, execution/accounting and restart behavior before deployment. Required cases: long and short; exact threshold/equality edges; final retest minute; touch and reclaim in the same completed minute; no touch; expiry; missing minutes; stale data; same-minute opposite signals; no same-timestamp re-entry; restart before/after touch, reclaim, fill and protection activation; funding debit/credit; fees on both legs; gap through stop; stop/target precedence; no duplicate orders/cashflows; no live-plan leakage. Replay saved private paths against the frozen reference where available. New synthetic tests are not new research results.
7. Apply changes to the existing paper service only after tests pass. Retire superseded hourly ENTRY sleeves while retaining their legacy position exit supervision. Do not retroactively convert open positions to F111. Use a versioned configuration and hash. Avoid duplicate worker starts and cash resets.
8. Verify a completed fresh scan after activation, all 192 sleeve statuses or explicit instrument-unavailable records, current feature/data timestamps, persisted state and paper-only routing. Observe pending/entry/protection telemetry when qualifying signals naturally arise. If none arise, report zero signals/trades honestly; distinguish synthetic path verification from observed forward execution. Do not manufacture trades to prove activation.

## Required completion report to the owner

Return the implementation branch and commit, tests run and results, deployment/rollback details, actual deployed commit/configuration hash, activation time (UTC and Asia/Dubai), actual eligible/available/scanned token and sleeve counts, unavailable instruments with reasons, fresh worker heartbeat/cycle evidence, confirmation of paper-only routing, and whether a real forward pending entry/fill/protection event has yet occurred. Report unresolved gaps precisely. Keep credentials, private addresses and trade-level logs in the owner's private channel.

Do not claim improved returns, a guaranteed profit floor, or a proven strategy. Do not open historical 2026 backtests or tune thresholds during this deployment. New forward paper observations from activation onward are authorized. Do not contact other people/bots or make live/broker/account/leverage changes.
