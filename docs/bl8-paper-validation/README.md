# BL8 separate paper validation

The owner authorized proper paper testing on15 October2026. This package runs an isolated public-data observer and paper ledger. It cannot submit an exchange order and imports no credentials or existing broker. It does not change or restart the hourly application, API, positions, cash or timers.

## What is fixed

All96 original symbols remain in the scan; unavailable contracts retain explicit reasons and are never aliased. Long-only BL8: hourly bullish re-entry above the lower fixed20-close band, with the trigger and previous hour excluded from that band window; fixed structural stop and fixed mean target; the original1.02%signal-close target-room hurdle; actual simulated fill-to-stop distance>=8%. Four-hour context availability is required; no newly fitted regime filter. Entry action is the minute after the completed hourly signal, within a60-second forward action window. No historical catch-up fills. No holding cap; one position/token in this separate ledger; occupied through exit minute.

The forward observer uses fresh timestamped public bid/ask depth. Entries and target exits add20bp adverse modeled fill cost to depth VWAP; stop exits use observed bid depth with no extra modeled stop slip. Fees5.5bp/leg. This intentionally records the differences from historical minute-open sampling. Quotes older than5seconds or in the future fail. Delayed/unfilled actions remain visible. Instrument minimums, maximum market size and quantity steps are checked.

Position size uses the hourly paper limits on this isolated book: notional is the minimum of equity×1%÷stop distance, equity×10%, remaining room under the 50% exposure cap, and equity×1 leverage. The book starts at 10,000 USDT, the hourly paper default, and then marks its own cash and open positions. It does not read the hourly account. A candidate below 5 USDT after lot rounding is rejected and is never rounded up. Exchange minimums that the cap does not already meet are rejected the same way. All96 are still scanned. These fills are paper evidence under the shared caps. They are not a live-trading approval.

Funding uses observed settlement rates times settlement-minute open times quantity. Both debits and credits are recorded once. Incomplete coverage stays unknown and blocks a final netR label; protective exits continue. Closed positions retry missing funding and accept newly observed settlement events. This proxy is not exact exchange mark-price funding. Changing settlement schedules may be conservatively flagged incomplete.

SQLite transactions persist entry fee, position, close and funding events. Restart does not duplicate an entry or cash event. A process lock excludes a second observer on the same DB. Quote marks, provisional equity, sampled drawdown, missing supervision and failures are visible. No account return percentage is manufactured.

## Local checks and what remains unknown

Read VALIDATION.json and RELEASE_MANIFEST.json. The standard-library test suite covers real SQLite rollback/retry, restarts, duplicate events, fee/funding reconciliation, stale/future quotes, missing depth, minimum-size rejection, frozen config and signal warm-up boundaries. The retained research comparison checks all56,519 B-long candidate signals plus scheduled negative hours, then the actual BL8 fill predicate. Exact counts/status are in the validation file.

These are local checks. Singapore installation, actual public API coverage, worker scan completeness, forward fills/exits and funding reconciliation remain unverified until collected from the host. Zero trades can verify startup but cannot verify a completed forward trade. No claim of future profitability, complete forward path parity or live-trading readiness.

## Operator / Grokbot installation

The paper-limits sizing release has its own stopped-service procedure in [TSURO_INSTALL.md](TSURO_INSTALL.md). Use that file for the pinned SHA. The steps below describe the original isolated install.

Use the full reviewed published commit in the owner's handoff. Do not use a moving branch head as the deployment pin. The installer uses a separate immutable release under /opt/mar-bl8/releases/<commit> and state under /data/state/bl8-paper. No checkout of /data/app is performed.

1. Fetch the published branch into the existing /data/app repository. Record its current HEAD and current hourly container health. Fetching alone does not deploy or restart anything.
2. Extract scripts/deploy_bl8_shadow.sh from the exact reviewed commit into a private path outside /data/app; run it as a child `bash` process with that full SHA as its sole argument. The script checks the Singapore hostname, paper-only hourly configuration, manifest hashes and local tests, then installs the isolated unit and leaves `mar-bl8-shadow.service` stopped.
3. Do not merge PRs, change the hourly marker, relax a guard, reset hourly cash/positions, remove a disabled-entry flag, or restart the hourly container. Retargeting the stopped `mar-bl8-shadow` unit at the reviewed SHA is the BL8 deploy. Diagnose a failed check and preserve its output. The old hourly repair remains a separate operation.
4. Start `mar-bl8-shadow.service` only when the owner asks. After the initial96-symbol scan, run the exact verification command printed by the installer. Save its timestamped JSON privately on the host. Check `systemctl status mar-bl8-shadow.service`, the status.json heartbeat and journal. Return the output to the owner for reconciliation.

The service polls public data and writes only the isolated state directory. It has no exchange order endpoint. Restart uses `systemctl restart mar-bl8-shadow.service` and retains its database. To stop new entries while continuing exits, create /data/state/bl8-paper/entries_disabled. Do not delete this flag automatically. To stop the observer entirely use `systemctl stop mar-bl8-shadow.service`; this also stops simulated exit supervision and must be reported as a gap. Never delete or reset the DB to make a check pass.

## Forward assessment

First establish complete current-universe scans, fresh quotes, reconciled entry/exit events, observed funding, stable persistence, and visible minimum-size/latency rejects. Compare signal timestamps and modeled fills against the frozen rules. Report hourly strategy, rebound observer and any later shared-token portfolio separately; these are not yet a deployed combined book.

Freeze the rule during collection. Daily/weekly PnL, exposure, drawdown, entry episodes, costs and concentration are descriptive until a prospective statistical evaluation window and funded-account sizing are explicitly fixed. Neither a few profitable trades nor elapsed days alone establishes an edge. The worker has no automatic strategy optimization or live-promotion path.

The original hourly execution repair is still independently pending remote cash/position/funding evidence in this research record. Do not transfer the observer's successful checks to hourly or claim the shared deployed portfolio is reconciled.
