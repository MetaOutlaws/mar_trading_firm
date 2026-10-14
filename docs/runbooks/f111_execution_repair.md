# F111/L01 execution repair v2

Base: deployed commit 868f1c9a7a34c240dd81fb0c4b2f25b02455d4a4. This repair keeps the hourly strategy, directional filter, original risk, target, floor and no-holding-cap rules. It changes execution mechanics and therefore has a new configuration hash and execution model version.

## What changes

- Completed candles confirm retests; a fresh quote executes the scheduled next-minute action immediately within its existing 60-second window. Slow fetches recheck the clock. Future bars and missing minutes cannot manufacture an entry.
- Protection samples once per UTC minute, with a persisted cursor. A floor decision takes effect on the next minute. Existing stop supervision continues between samples and while entries are disabled.
- Entry and exit use their explicit triggering quote. The target pays one modeled slippage charge. SQLite commits the close/trade together before RAM and JSON cash are updated.
- F111/L01 cash and protection use the same validated observed funding balance: settlement rate × settlement-minute open proxy × fixed quantity. This matches the research valuation proxy; it is not exact exchange mark-price settlement. Full pages are paginated, malformed/nonfinite/incomplete responses remain unknown, and observed payments cannot be erased by an incomplete later response.
- Missing funding never becomes an elapsed-time baseline estimate for these positions. Stops still execute. A close with incomplete observations is labeled `incomplete_at_exit` in its durable event; the saved observed-through timestamp states the coverage. Such closes need follow-up reconciliation, and this patch does not invent or rewrite missing historical settlements.
- New entries share a single opening timestamp across the runtime, broker and ledger. Existing F111 positions retain their original opening time. Their next observed cumulative balance can correct previously estimated funding on that still-open hold through an explicit new journal event. Closed history remains intact.

## Validation

Local results: 176 passed, one inherited archive placeholder skipped; 1,026 gate checks, 374 costed paths, 370 admitted broker paths, 374 observed-funding valuations and 1,480 independent cash identities all pass. See [validation evidence](../mar-f111-execution-repair/VALIDATION.json).

The repair suite covers both directions, offsets 0/15/59/61 seconds, missing/current/future quotes, repeated polls, restart, price changes during target close, funding pagination/valuation/unknown responses, real SQLite stop updates and close rollback/recovery, and the attached worker path. The original private 2022–2025 replay is run separately; its raw candles are not stored in Git.

Passing local tests does not establish fresh Singapore deployment or actual forward fills. The configuration deliberately retains `saved_path_parity: UNVERIFIED` until the server evidence is reconciled.

## Deploy through the existing SSH session

Use only the existing Singapore host, repository and containers. The operator script below requires the pinned reviewed repair SHA as its sole argument; it refuses a different host/base commit, dirty production files, unexpected mounts or an existing entry-disable flag. It preserves a private consistent SQLite backup and the cash/runtime/marker files after stopping the paper worker. It does not create another trading worker or change sizing/capital.

Fetch the reviewed branch first, inspect the pinned commit and invoke its deployment script through `git show` or from a temporary private path. Do not invoke the old checkout's nonexistent script. The operator script then checks out the exact repair commit, migrates only the guarded L01 configuration marker using the existing API container, and restarts the existing containers. It never merges a PR.

After startup, run:

```sh
docker exec -w /app mo-paper-paper-1 python scripts/verify_f111_paper_scan.py --output data/l01_registry_check.json
docker exec -w /app mo-paper-paper-1 python scripts/verify_l01_paper.py --expected-commit REPAIR_SHA --output data/l01_activation_evidence.json
```

Replace REPAIR_SHA with the full reviewed repair commit. Wait for the worker's own first hourly scan if verification reports that it has not produced one. Collect the existing read-only forward audit and reconcile cash, open positions, funding and fills against the new pre-upgrade backup. Observe the existing four-hour context timer; do not install a duplicate timer.

## Failure and rollback

If the deployment script fails after stopping the paper worker, it leaves a clear stopped-worker message. Inspect the failure before restarting. The backup path is printed before changing code. Never overwrite a current ledger or cash journal with an old snapshot after trading has resumed.

To roll back code before any resumed trading, restore only the backed-up L01 marker, check out the recorded base commit and stamp its GIT_SHA, then restart the same containers. If trading has resumed, first preserve the current book and reconcile any new fills; do not blindly restore state. Keep all cash/position history and stop supervision.
