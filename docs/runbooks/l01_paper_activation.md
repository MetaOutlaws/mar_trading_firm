# L01 longs / F111 shorts: activate the existing paper worker

Owner authorized this directional PAPER change and Git/deployment on 14 October
2026. See [the specification](../mar-l01-paper-handoff/README.md). Publication
alone does not activate it. Live trading is not authorized.

## 1. Inspect and preserve the current deployment

Use the existing **Singapore** host and its existing paper/API containers. Do
not start the old NYC worker or a second trading process. Inspect the current
Compose project, image, command, and mounts before applying commands below;
do not assume the repository's development Compose file matches production.
Do not print `.env` or API credentials. Verify only `TRADING_MODE=paper` and an
empty `GO_LIVE_CONFIRMED`. Confirm exactly one paper process is running.

Record the deployed commit, approval-book hash, open position IDs/stops,
pending retests and paper cash. Preserve the host's authoritative data mounts.
Back up `approved_strategies.json`, `f111_paper_state.json`, `paper_cash.json`
and existing L01 marker/context if present. Use SQLite's backup API for
`firm.db` while it is running; a copy of its main file alone can miss WAL data.
Keep those backups private. Never restore an old ledger over newer trades.

## 2. Install the reviewed commit and prepare indicator data

Deploy the pinned reviewed Git commit through the existing image/mount
procedure. Preserve local changes; do not use a blind hard reset. Ensure the
same code reaches paper and API containers and stamp its full 40-character
commit in `GIT_SHA`/`data/DEPLOYED_SHA` as used by the current deployment.
Preserve the existing approved sizing, risk limits, costs and exit polling.

Commands below run **inside the existing paper container** at its application
root, with its current Python environment and persistent `data` mount:

```sh
python scripts/prepare_l01_context.py
python scripts/enable_l01_paper.py
```

The first command prepares indicators only. It continues the verified
2022–2025 EMA seed using complete blocks of 240 distinct minute candles up to
the latest closed UTC 4-hour interval. It reuses minute caches and fetches
missing data in restartable seven-day chunks. It can take substantial time
on the first run. It does not score 2026 strategy outcomes, place orders or
start a trading worker. Let the existing worker supervise positions during
preparation. Both commands must exit zero before enabling; a bearish trend
is valid prepared context, while a stale or missing feed is not.

Schedule the same data-only preparation command every four hours, at least
two minutes after the UTC boundary. For the established container name, an
example root cron entry on the **existing** host is:

```cron
CRON_TZ=UTC
2 */4 * * * flock -n /var/lock/mar-l01-context.lock docker exec -w /app mo-paper-paper-1 python scripts/prepare_l01_context.py >> /var/log/mar-l01-context.log 2>&1
```

Confirm that container name and `/app` workdir against inspection first.
Install one such refresh job only, with log rotation and failed-exit monitoring
through the host's existing operational mechanism. Verify its first successful
run. This job is not a trading worker. The worker permits at most eight hours
of inline indicator catch-up; older context rejects new longs explicitly so a
large initial backfill cannot occupy the trading loop. Short admission and
existing exit supervision do not require this new indicator.

If F111 has not actually been deployed, first complete the entry-retirement
and persistent-mount steps in [the F111 runbook](f111_paper_activation.md).
Do not add L01 or F111 as a generic immediate-entry approval: the attached
F111 runtime owns the retest/reclaim flow. Do not restore superseded hourly
entry rows just because the old start-here document used to name them.

## 3. Enable and restart the same worker

```sh
python scripts/enable_l01_paper.py --apply
```

This writes `data/l01_paper_enabled.json`, recording the exact configuration
hash. It does not claim activation or start/restart a process. Restart the
same paper container through its existing deployment mechanism, followed by
the existing API container if needed to load the matching code/config.
Ensure `data/f111_paper_scan_disabled` is absent before activation; if it
exists, inspect why it was set before removing that operational pause.

At restore, unfiltered pre-upgrade pending LONG entries are cancelled with
`l01_upgrade_requires_new_long_signal`. Pending SHORT entries and all open
positions retain their original state and exits. New L01 pending entries
survive subsequent restarts. The ledger strategy ID deliberately remains
the inherited F111 ID; version, entry case and configuration hash distinguish
new L01 fills. Historical/open F111 positions are not relabelled as L01 entries.

## 4. Require evidence from the running worker

After its first real scan, run in the **same paper container/PID namespace**:

```sh
python scripts/verify_f111_paper_scan.py --output data/l01_registry_check.json
python scripts/verify_l01_paper.py --expected-commit FULL_40_CHARACTER_DEPLOYED_SHA --output data/l01_activation_evidence.json
```

The registry command must report 192 evaluated sleeves, no transport failure
and zero orders from the check itself. The activation command must exit zero
and report `activation_verified: true`. It requires the actual latest worker
restart to match the config and runtime source hash, a matching live paper
process/start identity, the worker's own recent 192-sleeve census, an hourly
decision from that run, fresh context, paper mode and the full expected commit.
A separate scan or a hash written into an approval file is insufficient.

Compare pre/post cash and positions, allowing only ledger-explained genuine
paper activity. Confirm each existing position retained exit supervision.
Record the process/container identity and verified source commit privately.
If no entry qualifies, report zero fills; never manufacture a demonstration
trade. Gate checks do not certify the inherited engine's complete fill-path
parity, future profitability, or live suitability.

## 5. Roll back the directional gate without resetting the book

Remove only `data/l01_paper_enabled.json` after preserving a copy, then restart
the same worker with this reviewed code. This selects the original F111
configuration. Leave the current ledger, cash and protection state in place;
do not flatten positions or overwrite them from a backup. Existing L01
positions retain their exits. The data-only refresh job can be disabled if
L01 is no longer being evaluated. Use the F111 runbook only for a separate
rollback of the inherited entry engine itself.
