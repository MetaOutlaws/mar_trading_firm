# Deploy the authorized 3R PAPER comparison

The user's “push this live” authorization applies to running the four-book
**paper** experiment. No real-money broker, exchange credentials or order API
is supplied. This release is an isolated companion to the existing application.
PR149 migration/top-up and unrelated research are separate workstreams.

## What runs

- I: hourly L01 long/F111 short + original BL8. IC adds original 3R short;
  IM adds half-size original 3R; IF adds the already-fixed filtered 3R.
- Four independent accounts **per** cost scenario (baseline, moderate, severe):
  twelve funded books, each initially 20,000 USDT. Three independent opportunity
  books track 2,000-USDT-per-signal counterfactuals, including capacity blocks.
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
not every strategy or runtime override in the existing account.

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
credential files are copied. Package versions are pinned; build outputs and the
resulting image ID are retained because the base image tag itself can change.

New state lives only at `/data/state/cipher-forward-v1`. Existing trial books
are reconciled and backed up, never reset. A different release cannot silently
take ownership of existing books. Existing production containers are not
stopped/restarted or resized. Installation logs are under `install-TIMESTAMP`.

Initial preparation runs under `mar-cipher-forward-prepare.service`, so closing
SSH does not interrupt it. Allow roughly 15–30 minutes for public-data warmup;
rate limits or stale L01 context can take longer or fail the preparation. It
persists an absolute UTC seed about 804 hours before preparation and appends
only complete hours made from 60 distinct minute candles with actual turnover.
Missing hours remain missing. Preparation evaluates indicator state only,
never historical trade returns. Failed token requests remain explicit failures;
observed unavailable instruments are retained without ticker aliases.

Successful preparation starts `mar-cipher-forward-paper.service`. Its first
eligible signal cutoff is the next whole UTC hour after the worker starts.
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
the correct release/image/config/seed receipts, reconciled twelve accounts,
fresh heartbeat/execution cycle, first complete future scan, explicit coverage,
no scan errors, scan completion within 110 seconds, current marks and known
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

- `report.html`: self-contained browser view with account comparison; expandable
  year/token/sector/source, costs, R and blocked-opportunity details.
- `report.json`: full machine-readable metrics, I-relative comparisons and
  coverage. `daily/YYYY-MM-DD.json` retains each day's latest snapshot.
- `trial.db`: transactions, raw compressed cycle inputs, first observed hourly
  histories, signals, decisions, funding, protection, positions and equity.
- `status.json`, `deployment.json`, `warmup.json`, `activation_evidence.json`:
  separate heartbeat, installation, seed and runtime evidence.

R uses original price risk. Calendar-year returns are prospective marked-equity
increments; trade R and token/sector/source P&L are attribution, not independent
token portfolio returns. Unknown funding and stale marks remain provisional.
Opportunity totals overlap and have no account ROI. Short samples are descriptive;
the predeclared 30/60-day operational checks and 90-day primary review remain.

Visible depth inputs can grow the ledger substantially. Monitor disk space and
archive consistent SQLite backups to protected storage; never delete active
state. Below 2 GiB free, new funded entries are latched off and exits continue
while space remains. No automatic deletion or automatic halt clearing occurs.

To pause funded **entries** while keeping exits and opportunities supervised:

```bash
touch /data/state/cipher-forward-v1/entries_disabled
```

Only after resolving the recorded cause should an operator remove that manual
flag; it cannot clear drawdown or supervision-gap latches. To stop the isolated
service completely, use `systemctl stop mar-cipher-forward-paper`; this also
stops simulated exit supervision, so preserve the ledger and record the gap.
Do not stop the production containers or run the PR149 account installer here.

## Grokbot/operator handoff

1. Check out the supplied immutable release, read this document, and run the
   installer on the existing Singapore droplet through your authorized session.
2. Keep the production account and PR149 workstream intact. Inspect preparation
   failures (including stale read-only L01 context) rather than bypassing them.
3. After the first future hourly scan, return `deployment.json`,
   `activation_evidence.json`, selected service status and the first report.
   Report pending/error status explicitly; never call a successful install an
   activated trial. No additional historical optimization is requested.
