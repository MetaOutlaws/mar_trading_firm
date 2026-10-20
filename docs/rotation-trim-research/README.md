# Grokbot next shift: R03 forward research trial

Owner request: prepare and activate the trimmed-rotation strategy for research, monitor it, and leave these instructions in Git.

**Status: research authorized; implementation pending; activation NOT verified.** This document does not start a worker. Do not report "running" without the evidence below.

## Required trial

Create three isolated persistent simulated accounts, each with 20,000 USDT:
1. Reference: original hourly + BL8 with fixed 24-hour recovery.
2. Control: reference plus original rotation.
3. Candidate: reference plus rotation with the frozen exposure-trim rule.

Use separate account namespaces, positions and capacity for each book, with identical data and cost assumptions. Record every eligible opportunity and its subsequent shadow path, including those rejected by account limits. Shadow opportunities are not account trades or extra independent samples.

Each research account: max15 open positions,1% cost-aware entry-risk ceiling,10% entry notional cap,50% gross admission cap,2 positions per sector,20 new entries per UTC day,3% daily closed-loss rule, and the existing six-loss/24-hour recovery policy. Use the owner's70% drawdown entry-stop for these isolated research accounts only. Existing holdings retain their exits after an entry halt, while shadow opportunity recording continues.

Do not reset or alter the current execution account. PR149 deployment/reconciliation remains a separate operational track. Verify its actual status. Do not substitute a different running strategy for the specified reference.

## Candidate behavior

Preserve original rotation signals, protection, daily membership exits, universe and ordering. No new token whitelist or retuning. At each four-hour checkpoint +1minute, before new entries, a price-profitable rotation position exceeding20% of marked account equity schedules a reduction to leave10% at the decision quote. Execute the fixed quantity at the next minute quote, with fees and slippage. Keep both slices above the execution minimum. Full original exits take priority. Keep the remaining core until its original exit; no re-expansion.

Use the frozen research specification for implementation parity. Obtain the approved private research package through the existing authorized channel; do not infer missing rules or publish private artifacts here. If unavailable, record that specific dependency block. This ticket intentionally contains no private research tables, datasets or source archive.

Partial reductions must allocate entry fees and accrued funding, update daily closed PnL immediately, and count the whole lifecycle once for loss-streak recovery. They do not free a position/token/sector slot or reset recovery.

## Implementation and verification

Implement in a dedicated reviewed PR. Reuse the existing market-data cache/poller; separate research ledgers, identifiers, locks and services. The research worker must have no live-order capability. Preserve source/config fingerprints and all blocked-opportunity reasons.

Verify strict20% boundary, long/short behavior, fixed-quantity next-minute fills, full-exit priority, repeated trims, funding/fees, lifecycle recovery and restart deduplication. When no trim triggers, original and trimmed books must match.

Before starting: validate fresh data, eligible universe, exact approved source versions, initial balances and effective limits. Do not backfill historical trades as forward fills.

After starting: write a sanitized activation record containing UTC time, code SHA, config hash, worker/run ID, heartbeat, latest market timestamp, all three account balances and actual new scan/decision evidence. Restart once and verify no duplicates or balance/position changes. Reconcile cash plus marked PnL to equity. Zero fills is acceptable when genuine scans and no-signal/rejection reasons are recorded.

Only then set activation_verified=true. Until then label the exact stage: implementation pending, preflight failed, or runtime verification pending.

## Monitoring and decision

Maintain normal source timing, minute health heartbeat, daily rotation and four-hour trim checks. Produce hourly health summaries and daily three-account comparisons: net return, marked drawdown, costs/funding, source/token/sector PnL, positions, accepted and blocked opportunities, data gaps and trim activity. Compare matched cost assumptions; severe cost stress remains secondary.

Review operation after24hours and research after14days of verified runtime. Report unique completed lifecycles and unique positions trimmed; sparse evidence means continue collecting, not declare superiority. Research authorization does not mean the historical advancement gates passed or that returns are proven better. No automatic promotion or real-money deployment.

On integrity failure, suspend new research admissions, preserve the ledgers and continue original exits/valuation. Never erase failures or reset balances to improve results.

Publish the implementation PR and sanitized activation evidence in Git. Update this status only when supported. No separate outbound message is requested.
