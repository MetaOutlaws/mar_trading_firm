# Recovery paper implementation — 17 October 2026

Owner authorization: implement the recovery comparison and full opportunity
recording; raise the current paper cash balance to 20,000 USDT and its open
position ceiling to 15. Keep the 1% risk and 10% position settings.

## What runs

| Book | Starting paper capital | Position ceiling | Rule |
|---|---:|---:|---|
| Existing current account | One capital top-up to 20,000 USDT cash | 15 | Existing strategies and exits continue |
| NONE comparison | 20,000 USDT | 15 | Original-order hourly + BL8, no timed streak reset |
| C24 comparison | 20,000 USDT | 15 | Same signals, execution and limits; fixed 24-hour streak recovery |
| Opportunity recorder | No shared capital balance | No portfolio cap | Independent 2,000 USDT notional per executable strategy signal |

The comparison books are separate from the current account and from the old
BL8 observer. Each comparison account has its own cash, positions, streak,
daily losses and drawdown latch. Neither can consume another account's slots.
Both use L01 longs, unchanged F111 shorts, and original BL8 rebound longs.
They do not copy every unrelated strategy in the current account.

All 96 original symbols remain in scope. Unavailable exchange instruments
are recorded without alias substitution. No profitable-token filter, target-room
ranking, added entry delay or changed exit rule is introduced. Historical 2026
backtests remain closed; completed history is read only to warm indicators.
New entries start with the first complete hourly signal after activation.

## The limits still matter

Both funded comparison books retain 1% cost-aware planned stop risk, 10%
position notional, 50% marked gross exposure, 1x leverage, two positions per
sector, one per symbol, 20 entries per UTC day, and exchange minimums. A 15-slot
ceiling does not promise 15 simultaneous positions: the other limits can bind
earlier. The current account keeps its existing sizing implementation; only
its paper position-count declaration changes.

Daily closed-loss pause is 3%, six nonpositive closes pause entries, and a 15%
marked drawdown permanently latches the comparison account's entry stop.
Already-open positions continue their exits after an entry halt. Consequently,
15% is not a guarantee that the eventual drawdown cannot exceed 15%.

C24 clears only the effective six-loss streak when a candidate arrives at least
1,440 completed minutes after the latest nonpositive close. Another loss extends
the clock; a positive close clears the streak as before. Raw streak history,
manual stops, daily limits and drawdown latches are retained. It never resets
the current account's kill switch.

## Execution and durable evidence

The worker only makes public market-data GETs through an explicit four-endpoint
allowlist. Its container receives no exchange credentials or production `.env`.
The production L01 context is mounted read-only; bounded additional context is
continued from the same seed in memory when a valid long needs it.

Hourly retests use completed one-minute bars and schedule the next minute.
Candidates are batched by action time, hourly before BL8, then symbol/UID.
Fresh visible depth supplies actual forward paper fills; adverse entry and
target slippage is 0.20%, both-leg fees are 0.055% per leg, and stop gaps remain
in the fills. Exits and profit-floor steps use the first usable quote sample in
each minute, rather than hindsight candle extremes. This differs from an exact
historical minute-open fill; stored timestamps and quotes make it inspectable.

Funding uses observed signed rates and the settlement-minute opening price
proxy. A missing settlement is unknown, never zero. A position can execute
its exit while its final net result awaits funding reconciliation. The funded
books pause new admissions until their required funding is known. The
opportunity stream continues independently.

SQLite WAL/FULL commits positions, fees, cash, decisions and recovery state in
one transaction. Exact duplicates cannot fill twice; conflicting identities are
refused. Missing complete account-mark minutes latch a reconciliation hold on
entries while exits and opportunity observations continue. The worker does not
automatically clear this hold. Missing/corrupt/changed-rule databases never
silently become a new book. One lock prevents duplicate workers.

Each rejected signal records its account reason. If market data and strategy
fill conditions permit, the recorder follows an independent hypothetical trade
through its exit, even when the account was full, halted, exposed or occupied.
It does not bypass stale/missing prices, exchange availability or liquidity.
Missing exit-sample minutes are counted. These overlapping fixed-notional
outcomes are not attainable account ROI and cannot be added to account profit.

## Current-account migration

`scripts/resize_paper_account.py` supports a read-only preview. The installer
first checks the actual mounted source/data, paper mode, cash reconciliation,
existing positions, known settings, and dependencies. It finishes the build,
tests and dry run before briefly stopping the current paper and API containers.
It backs up the database, cash journal, risk limits and protective files.

Legacy cash compatibility (20 October 2026 Dubai): a durable database row may
have an `event_id` while its older JSON payload lacks that field. The preview
now accepts this when the database ID matches an existing journal entry with
identical economic fields. If the journal entry also lacks an ID, the entire
payload, including its timestamp and any other metadata, must match exactly;
each journal occurrence can cover only one durable row. Missing IDs are not
assigned, history is not rewritten, and explicit ID conflicts, unmatched rows,
duplicate IDs and economic differences still stop the migration. Preview and
apply receipts include `durable_cash_reconciliation` counts for inspection.
The reported seven October 9 records were reproduced with synthetic fixtures;
their actual server payloads have not been independently inspected here.

The increase is one identified capital event: `max(0, 20000 - current cash)`.
It is not trading profit. An account already above 20,000 is not reduced.
Unrealised P&L on existing positions remains additional to this cash balance.
A repeated install does not replenish subsequent losses. No position, stop,
closed trade, earlier cash event or kill state is rewritten. The source change
is limited to `PAPER_LIMITS = RiskLimits(max_concurrent_positions=15)`; live
limits and the rest of the current checkout stay intact. The installer then
restarts the existing containers and starts the isolated comparison service.

## Install and inspect

Run the pinned installer from the existing Singapore operator session:

```bash
set -euo pipefail
umask 077
test "$(hostname)" = mo-paper-vm-sgp1
# Set RELEASE to the full reviewed commit from the latest operator handoff.
# Use the legacy-cash fix commit, not the original October 17 release.
RELEASE='FULL_REVIEWED_COMMIT_SHA'
git -C /data/app fetch origin codex/recovery-paper-20261017
test "$(git -C /data/app rev-parse FETCH_HEAD)" = "$RELEASE"
git -C /data/app show "$RELEASE:scripts/deploy_recovery_paper.sh" > /root/deploy_recovery_paper.sh
bash /root/deploy_recovery_paper.sh "$RELEASE"
```

Replace the placeholder before running. Fetch downloads the reviewed code
history; it does not change the current checkout or running containers. The
installer is the separate step that previews, backs up and applies the change.

Do not checkout this branch over `/data/app`: newer unrelated repairs may be
running there. The installer extracts this immutable release under `/opt`.

Service: `mar-recovery-paper.service`. State: `/data/state/recovery-paper-v1`.
The reporting timer renders `report.html` and `evidence.json` every five minutes.
The report includes NONE versus C24 equity/return/drawdown, recoveries, rejected
opportunities, and closed-trade year/token/sector/source/regime attribution.
No closed trades is a valid initial result; it is not evidence of profitability.

```bash
systemctl status mar-recovery-paper.service --no-pager
systemctl start mar-recovery-report.service
cat /data/state/recovery-paper-v1/evidence.json
cat /data/state/recovery-paper-v1/resize-applied.json
```

Activation requires a fresh heartbeat, matching release/configuration, a
completed forward-hour scan, complete marks/funding, reconciled cash and no
unresolved halt/gap. `activation_verified` stays false until those checks pass.
`profitability_verified` is always false in this operational verifier; adoption
of recovery as the standard policy requires a separate evidence decision.

To pause new comparison entries while preserving exits/recording:

```bash
touch /data/state/recovery-paper-v1/entries_disabled
```

Do not stop the entire service to pause entries while positions are open. Do
not delete a ledger, remove a drawdown/gap state, or restore an old cash journal
over newer trades. Backups and immutable events support an explicit repair.

## Verification and rollout status

Local verification: 48 recovery checks and 43 inherited BL8 checks pass.
The recovery suite includes 12 added legacy-cash regression tests covering
seven old payloads, mixed formats, exact-match multiplicity, conflicting IDs,
economic differences, read-only preview, preservation and top-up retry.
They cover fee-aware sizing, all major gates, C24 timing, shared ordering,
short/funding accounting, partial quote/close ordering, restart/idempotence,
an actual abrupt process interruption inside the transaction, report
reconciliation and current-account migration preservation. Python compilation,
shell syntax and diff whitespace checks pass.

The Docker build and real exchange/server runtime are not verified from the
authoring workspace. The installer runs the focused checks in its actual
image before touching the current account. There is no server shell connection
in that workspace: publication is not activation. The operator must run the
pinned installer and return runtime evidence. The prior 10,000 USDT/five-slot
historical returns have not been recomputed for the newly authorized settings
and must not be presented as expected performance for these books.
