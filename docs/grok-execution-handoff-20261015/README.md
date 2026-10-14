# Grokbot: complete the paper execution update

The owner has delegated this operational work to Grokbot. Codex is continuing offline research. Use the existing Singapore paper worker. The repair code is already reviewed/tested locally and published in PR #118, stacked on PR #117. Fetch this branch into your own workspace to read the handoff; fetching does not deploy it.

## Identities and current uncertainty

Read HANDOFF.json for exact commit, tree, configuration hashes and success criteria. **Deploy commit b00c4f73147f8319bc9c227c4f4ffb147fc87154**, not whatever the branch head later becomes. Newer commits may contain handoff documentation only. Original expected server HEAD: 868f1c9a7a34c240dd81fb0c4b2f25b02455d4a4.

The owner's first attempt fetched successfully then the SSH shell closed with `set -e` enabled. No backup or restart confirmation was seen. It may have failed a silent host/HEAD/dirty-files/disable-flag check. Determine the exact failure. Do not assume deployment completed or run the installer blindly. Keep errexit confined to a child script so a failed check does not close the interactive SSH session.

## Inspect, resolve, then install

1. Verify host, current HEAD, both container states and mounts, deployed SHA markers, tracked changes, configuration-marker hash, entry-disable flag and any recent repair backup. Record exit codes and the precise failing preflight check. Do not print environment files, credentials or whole Docker config. Confirm whether any other operator or worker is performing a deployment.
2. If HEAD differs, inspect ancestry and the specific diff. If tracked files differ, preserve a private patch/backup and identify whether the change is a deliberate operator modification, research output or a conflicting code change. Do not use reset --hard, git clean, blanket stashing/restoring, remove the entry-disable flag, or relax a guard merely to proceed. Preserve intentional changes. Report a specific unresolved conflict if it cannot be safely reconciled within the approved repair. If already at the repair SHA, skip installation and verify. If the attempt partially progressed, use its backup and current state to finish/recover without overwriting newer cash or trades.
3. Before installation, inspect docs/runbooks/f111_execution_repair.md and the pinned scripts/deploy_f111_execution_repair.sh. For the expected clean base, extract that exact script outside /data/app and run it with the full repair SHA. It stops the existing paper worker, makes a consistent SQLite/cash/runtime/marker backup, checks out the repair SHA, migrates the guarded L01 marker through the existing API container, and restarts the same containers. Keep the backup path. Inspect any failure before restarting.
4. No second trading worker, no cash/position reset, no live mode, no new order to prove activation, no changed strategy thresholds, timer, sizing, leverage or holding cap. Do not merge PR117 or PR118. A valid zero-fill scan can pass.

## Verify and reconcile

Run the registry verifier and verify_l01_paper.py against the full repair SHA. Observe the worker's own new run/startup/scan evidence rather than relying on a standalone verifier. Wait for its first scan if needed. Check API health, host HEAD, /app/GIT_SHA and persistent DEPLOYED_SHA separately. New config hash is in HANDOFF.json. Save fresh output with timestamps.

The read-only collector is scripts/collect_f111_execution_repair_audit.sh in this handoff commit. Because the deployment is pinned to the earlier repair commit, extract the collector into a private path outside /data/app BEFORE checking out the repair. Run it only after the update. It checks the pinned repair commit, existing context timer, cash journal plus durable SQLite events, positions, post-activation trades, funding coverage and the latest matching pre-upgrade backup. A changed journal during reading requires another consistent capture; do not conceal the unstable read. The older collector is pinned to the old commit and must not be used unchanged.

Reconcile every pre-upgrade open position to its post-upgrade position or a documented closing fill. Preserve stop/target supervision for legacy strategy positions too. Reconcile capital, cash, fees, accrued/closed funding, closed net PnL and durable/JSON event identities without double counting or rewriting history. Open-position funding may receive explicit correction events when observed settlements replace the old estimate. Unknown funding must remain flagged; list every incomplete-at-exit case and follow-up needed. The proxy uses rate times settlement-minute open, not exact exchange mark-price settlement. Registry availability is as-of the new capture, not guaranteed to remain 79/96.

Keep saved_path_parity=UNVERIFIED unless its full stated scope is actually demonstrated. Local tests alone do not justify changing that label. Do not edit the marker/config merely to clear an evidence check.

## Return to the owner

Return a short completion or blocker report with host/time, exact commit/config, backup path, worker run ID, container health, sleeve/context results, timer observation, pre/post position reconciliation, cash bridge, event duplicates/missing records, funding-coverage exceptions and evidence locations. Include exact sanitized verifier/collector output. State separately: installed, activation verified, cash/positions reconciled, full forward parity verified or still UNVERIFIED. Keep full operational evidence private on the host or share it with the owner; do not commit database files, credentials or account snapshots to Git.

## Evidence included

repair_validation.json and historical_replay.json summarize 176 executed passing tests (one inherited private-archive placeholder skipped), 1,026 gates, 374 historical paths, 370 admitted broker paths, 374 funding valuations and 1,480 cash identities. CSVs contain per-path/retest comparisons. Raw 2022–2025 tapes remain in the owner's existing external checkpoint; they are not required to deploy. Hourly L01-long/F111-short admission and policy331 exits remain unchanged. Lower-frequency and initial adaptive-exit challengers were not promoted; no account-risk percentage was selected. Historical 2026 research remains unopened.
