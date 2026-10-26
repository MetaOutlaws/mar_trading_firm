# Deploy the authorized 3R paper comparison

This release runs one paper service. It does not authorize real-money trading,
a broker, exchange order credentials, or an order API. The process refuses to
start unless `TRADING_MODE` is paper and `GO_LIVE_CONFIRMED` is unset. It is an
isolated companion to the existing application. PR149 migration/top-up and
unrelated research are separate workstreams. This is a non-promotional
experiment. Its own pass rule is REPORT-ONLY. It cannot size up, join the book,
or feed walk-forward. Promotion requires a filing, a Garwe LOCK, the desk gates
in `protocol.json`, and a holdout. BL8 and the filtered W11S variant are covered
by that clause.

## What runs

- I: hourly L01 long/F111 short + original BL8. IC adds original 3R short;
  IM adds half-size original 3R; IF adds the already-fixed filtered 3R.
- One paper service holds 16 internal simulated portfolios: the four strategy
  variants I, IC, IM, and IF, each at desk031, baseline, moderate, and severe
  costs. These are not exchange accounts, testnet accounts, or subaccounts. They
  do not add capital and they do not use an API key per portfolio. Each portfolio
  record starts with 20,000 USDT of simulated cash. The 16 portfolios are 16
  looks at one idea, not 16 tests. Reports do not rank them or crown a config
  or cost. Four opportunity records track 2,000-USDT-per-signal
  counterfactuals, including capacity blocks.
- PRIMARY is IC: incumbent L01/F111 plus original BL8, plus the original
  unfiltered 3R short at full size. Only IC at desk031 is labelled BINDING.
  Every other cell is REPORT-ONLY. Interim reviews are veto-only. An interim
  review can stop or void the run. It cannot promote, re-pick PRIMARY, or
  change any config. No config is swapped after LOCK. Freeze and start refuse
  an empty PRIMARY. `docs/cipher-forward/config_freeze.json` carries the same
  PRIMARY id and the same config hash the runtime freeze writes.
- 15 positions, 50% gross admission, 1% planned cost-aware risk/10% notional;
  IM challenger alone is 0.5%/5%. Two per sector, one per token including exit
  minute, twenty daily entries, 3% daily closed loss/current equity, C24 after
  six nonpositive closes. The independent 15% drawdown entry latch persists.
- No holding-time cap, token profit whitelist, new parameter search or 2026
  outcome backtest. The 70% drawdown guard was historical simulation only.
- Stop/target checks at 15-second observed-quote ticks, maximum quote age 5s.
  Hourly protection decisions take effect on the next minute. No intrabar
  reconstruction, old-open backfill or manufactured liquidity. Triggered exits
  remain pending until fresh sufficient depth exists. Data gaps are recorded.
- Public signed funding rates, explicitly labelled minute-open price proxy;
  unknown funding holds funded entries while exits continue. Fees and extra
  slippage are assumptions, not measured exchange execution.

Signal/risk code is frozen; the prospective execution bridge is intentionally
observable. Historical 2022–25 returns are not forecasts under the 15% guard or
this quote-sampled execution. I represents the named incumbent combination,
not every strategy or runtime override on the existing production paper book.

## Install from an existing authenticated root SSH session

Use the **full release SHA supplied with this PR**, never a moving branch name:

```bash
set -euo pipefail
release=FULL_40_CHARACTER_RELEASE_SHA
git -C /data/app fetch origin "$release"
git -C /data/app show "$release:scripts/deploy_cipher_forward_paper.sh" | bash -s -- "$release"
```

Fetching adds code history only; the working checkout is not switched. The
installer checks the hostname `mo-paper-vm-sgp1`, root, running paper container
and its paper-mode assertion. It resolves the real mounted L01 context path
from Docker mounts and mounts that directory **read-only**. It records selected
non-secret source/settings observations; it does not read or print credentials.

It extracts the pinned commit into `/opt/mar-cipher-forward/releases/SHA`, builds
`docker/cipher-forward.Dockerfile`, runs the candidate/runtime tests inside that
image with networking disabled, and records the image ID. The image deliberately
uses a minimal `research` package initializer to avoid importing the historical
backtester or unrelated execution code. No production execution modules or
credential files are copied. Package versions are pinned. The `python:3.11-slim`
base is pinned by digest in `docker/cipher-forward.Dockerfile` (tag last updated
2026-10-22). Build outputs and the resulting image ID are retained.

New state is stored only at `/data/state/cipher-forward-v1`. Existing trial books
are reconciled and backed up, never reset. A different release cannot silently
take ownership of existing books. Existing production containers are not
stopped/restarted or resized. Installation logs are under `install-TIMESTAMP`.

The installer does not enable the service, does not start it, and does not
initialize the ledger. It writes `entries_disabled` before fetch and build, so
a later manual start still admits no funded entries until an operator removes
that file. `--no-start` is the explicit dry run and does the same non-starting
work: fetch, archive, build, in-container tests, and unit-file write, then it
prints the manual next steps. Those steps stay manual and need the operator's
deploy OK via Tsuro. `docker exec` audits of `mo-paper-paper-1` run only with
`--audit-production`, which is off by default.

Initial preparation, once an operator starts it, runs under
`mar-cipher-forward-prepare.service`, so closing
SSH does not interrupt it. Allow roughly 15–30 minutes for public-data warmup;
rate limits or stale L01 context can take longer or fail the preparation. It
persists an absolute UTC seed about 804 hours before preparation and appends
only complete hours made from 60 distinct minute candles with actual turnover.
Missing hours remain missing. Preparation evaluates indicator state only,
never historical trade returns. Failed token requests remain explicit failures;
observed unavailable instruments are retained without ticker aliases.

The installer does not start `mar-cipher-forward-paper.service` after
preparation. An operator starts it only after the deploy OK. Its first
eligible signal cutoff is the next whole UTC hour after the worker starts.
Funded quote requests peak at 4/s (0.25s spacing, concurrency 2). The hourly
scan keeps a separate 10/s pacer and is requested 6 minutes after the hour.
The scan as-of time stays the hour boundary. The 110-second completion budget
is measured from that delayed request, not from the top of the hour.
After reboots, existing books resume exit supervision immediately; warmup does
not block exits on restart. Missing/corrupt indicator state blocks new signals
without disabling existing exits. One worker lock prevents duplicate supervisors.

## Verify actual operation

```bash
systemctl status mar-cipher-forward-prepare mar-cipher-forward-paper --no-pager
journalctl -u mar-cipher-forward-prepare -u mar-cipher-forward-paper -n 60 --no-pager
cat /data/state/cipher-forward-v1/activation_evidence.json
```

The worker writes technical evidence and a complete report each minute. It
does **not** mark activation verified merely because a container starts. Require
the correct release/image/config/seed receipts, reconciled sixteen internal simulated portfolios,
fresh heartbeat/execution cycle, first complete future scan, explicit coverage,
no scan errors, scan completion within 110 seconds of the request at minute 6, current marks and known
funding, and no entry holds. Zero fills can be valid. Pending funding or temporary
data gaps can make a later check incomplete; inspect the reasons, never reset
the ledger or relax a gate to turn the indicator green.

The local environment used for development has no Docker binary or server SSH
key. Local Python tests and installer syntax validation do **not** establish a
successful image build, available server data, measured scan latency, or an
activated trial. These checks intentionally run on the destination before and
after starting the service. Do not mark `paper_trial_started` or
`activation_verified` in project state without the actual remote receipt.

The SSH key previously configured is held on the owner's Windows PC. Use that
existing operator session or an already-authorized operator such as Grokbot.
Do not paste a private key into Git, logs or chat. No external operator message
has been sent by this release.

## Reports and operation

- `report.html`: self-contained browser view of four strategy comparisons, in
  fixed order I, IC, IM, IF. desk031, baseline, and moderate are prominent,
  with desk031 first. Severe is secondary, collapsed, and display only. Only
  IC at desk031 is labelled BINDING. Every other cell is REPORT-ONLY. The page
  states that the 16 portfolios are 16 looks at one idea, not 16 tests. It
  does not rank them.
  Year, token, sector, source, costs, R, and blocked-opportunity details stay
  expandable.
- `report.json`: full machine-readable metrics, I-relative comparisons and
  coverage. `daily/YYYY-MM-DD.json` retains each day's latest snapshot.
- `trial.db`: transactions, raw compressed cycle inputs, first observed hourly
  histories, signals, decisions, funding, protection, positions and equity.
- `status.json`, `deployment.json`, `warmup.json`, `activation_evidence.json`:
  separate heartbeat, installation, seed and runtime evidence.

R uses original price risk. Calendar-year returns are prospective marked-equity
increments; trade R and token/sector/source P&L are attribution, not independent
token portfolio returns. Unknown funding and stale marks remain provisional.
Opportunity totals overlap and are not simulated-portfolio returns. Short samples
are descriptive. The 30/60/90-day reviews are report and veto only.

desk031 is 0.31% on entry, on a non-stop exit, and on a stop exit. Only IC at
desk031 is labelled BINDING. Every other cell is REPORT-ONLY. Baseline,
moderate, and severe were not repriced. Baseline is 0.255% on entry and on a
non-stop exit, and 0.055% on a stop exit, and stays prominent. Moderate is
0.355% on entry and on a non-stop exit, and 0.255% on a stop exit, and stays
prominent. Severe is 1.055% on entry and on both exits. It stays secondary
display only. I, IM, and IF at desk031 are REPORT-ONLY.

Before warmup fetches a bar, the service writes `config_freeze.json` with a
hash of every portfolio config and the code SHA. Startup and every cycle
recheck those hashes. A missing freeze, or any mismatch after warmup has begun,
writes `void.json`, prints a VOID line, shows VOID at the top of the report,
and disables entries. The run stays VOID. Warmup bars compute indicator state
only. A trade, signal outcome, or P&L on a warmup bar is not written as
performance and is left out of the report.

Cycle events store a hash of each full quote. Level arrays are the top 25,
and they are written at most every 15 minutes; other cycles store the hash
without the levels. Fills still use the full in-memory book. Position
entry and exit quotes stored on the book are the top 25 plus that hash.
The worker drops quote cache entries that are not an open position or a
signal still inside its entry minute. A synthetic day of 96 symbols at 200
levels, with no exchange bars, measures quote-event payloads at 26,403,744
bytes/day (about 25.2 MiB). Sixteen equity-sample rows add about 2.7 MiB/day.
The capacity review's history figure, not remeasured here, is 51 MiB/day.
The sum is about 79 MiB/day. Fourteen days of that sum is about 1.08 GiB, so
the 1 GiB write cap remains the backstop if history stays at that quoted size.
Sixteen portfolios do not multiply the shared quote feed or the history
snapshots. The size cap stops ledger writes: `block_writes` makes the next
transaction raise `StorageWriteBlocked`, and the worker skips the cycle while
writes are blocked. It does not merely stop new entries. Archive consistent
SQLite backups to protected storage. Do not delete open positions, cash,
decisions or signals to make room.

The service measures free space on the volume that holds the main paper
database (`/data/state/data/firm.db`, mounted read-only at `/main-paper` in
the container) and on its own state directory. Below 2 GiB free on either
volume it stops ledger writes, disables entries, and logs
`ERROR cipher-forward storage guard` about once a minute. It does not clear
that entry halt when space returns. While free space stays under the
threshold, writes stay off even if `entries_disabled` is removed.

Append-only history is retained for 14 days, and the SQLite files (database,
WAL and shared memory) are kept at or under 1 GiB. Cycle and history payloads
older than that can be dropped; their identities and hashes stay, so a replay
cannot trade twice. If the active book itself is still over 1 GiB, writes stop
rather than growing without a bound. `VACUUM` runs only when the free-space
reserve would survive a second copy of the file.

`CIPHER_FORWARD_MIN_FREE_BYTES` defaults to 2147483648,
`CIPHER_FORWARD_LEDGER_MAX_BYTES` to 1073741824, and
`CIPHER_FORWARD_LEDGER_MAX_AGE_MS` to 1209600000.
`CIPHER_FORWARD_MAIN_PAPER_DB` is the book whose volume is protected.

To pause funded **entries** while keeping exits and opportunities supervised:

```bash
touch /data/state/cipher-forward-v1/entries_disabled
```

Only after resolving the recorded cause should an operator remove that manual
flag; it cannot clear drawdown or supervision-gap latches. To stop the isolated
service completely, use `systemctl stop mar-cipher-forward-paper`; this also
stops simulated exit supervision, so preserve the ledger and record the gap.
Do not stop the production containers or run the PR149 resize installer here.

## Grokbot/operator handoff

1. Check out the supplied immutable release, read this document, and run the
   installer on the existing Singapore droplet through your authorized session.
2. Keep the production paper book and PR149 workstream intact. Inspect preparation
   failures (including stale read-only L01 context) rather than bypassing them.
3. After the first future hourly scan, return `deployment.json`,
   `activation_evidence.json`, selected service status and the first report.
   Report pending/error status explicitly; never call a successful install an
   activated trial. No additional historical optimization is requested.
