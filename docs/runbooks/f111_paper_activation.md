# F111 paper activation (existing SGP1 worker)

Paper only. This runbook is for the existing Singapore paper worker. It does
not start a second process, does not start the New York worker, does not reset
cash, and does not close or convert an open position.

F111 (`mar_f111_r12_extension_latefloor_v1`) is not an engine-plan sleeve. The
hourly close is not an order. Entries are minute retests inside the existing
paper loop. Live plans cannot select it.

The private checkpoint `MAR_R12_I11_factorial_checkpoint_20261010.zip` was not
in this implementation. Saved-path parity stays **UNVERIFIED**. Do not treat
the unit tests as a replay of the research tape.

## What this changes

- New F111 paper scan: 96 supplied symbols, LONG and SHORT (192 sleeves).
- Superseded hourly **entry** sleeves are removed from the scan book:
  - `hourly_compression_v1`
  - `hourly_compression_connors_v1`
  - `hourly_compression_btc_connors_v1`
  - `hourly_compression_btc_connors_loweff_v1`
- Positions those sleeves already opened keep their strategy name, their
  stops, and the existing exit poll. They are not moved onto the F111 floor.

## 1. Look before touching anything

On the existing SGP1 host, confirm there is one paper worker (the container
already used for paper, historically `mo-paper-paper-1`). Confirm
`TRADING_MODE=paper` and that `GO_LIVE_CONFIRMED` is empty.

Verify the real paths. Earlier notes say code at `/data/app` and state at
`/data/state`. If a bind mount points elsewhere, use the mount you find. Do
not create a new VM.

Record, privately, the worker commit, the approval-file sha256, whether
`data/paper_trading.pid` names a live process, open-position count, and cash.
Do not copy keys, host addresses, or trade logs into git.

Do not run a 2026 backtest. Do not change thresholds.

## 2. Backup

Back up, with the same tool you already use for this host:

- the approval book (often a bind-mounted `config/approved_strategies.json`)
- `data/firm.db` (and its wal/shm if present)
- `data/paper_cash.json`
- `data/killswitch.json` if it exists
- the current git commit / image id

Preserve symlinks. Copy the link target if you need a byte backup; do not
replace a mounted file by truncating it. Do not delete the cash journal.

## 3. Deploy onto the existing worker

Check out this commit in the existing app tree. Restart **that** paper
process so it loads the code. Do not `docker run` a second paper container.
Do not start a New York worker. Do not call any cash-reset or capital script.

F111 turns on when all of the following are true:

- `TRADING_MODE=paper`
- `GO_LIVE_CONFIRMED` is empty
- `config/sleeves/mar_f111_r12_extension_latefloor_v1.json` has
  `paper_scan_enabled` true and `live_authorized` false
- `data/f111_paper_scan_disabled` does **not** exist

The config file's sha256 is logged on every F111 line as
`configuration_sha256`. Quote that hash in the activation note.

Then retire hourly entries, from the app tree:

```bash
python scripts/enable_f111_paper.py
python scripts/enable_f111_paper.py --apply
```

The dry run prints the keys it would remove. `--apply` writes a sibling
backup named `approved_strategies.json.before-f111-<timestamp>` and then
removes those entry rows. It does not add F111 to the book.

## 4. Verify the 192-sleeve scan

Inside the same paper container, after one loop has started (the existing pid
file should still be the same process):

```bash
python scripts/verify_f111_paper_scan.py
```

You want:

- exit 0
- `sleeves_evaluated` 192
- `orders_placed` 0 from the scan itself
- `saved_path_parity` `UNVERIFIED`
- every symbol either `Trading` (available) or an explicit UNAVAILABLE reason
- no renamed ticker traded under another symbol

Exit 2 means the scan ran but `instruments-info` did not answer. Those rows
are UNAVAILABLE with an unreachable reason. Do not treat them as tradable and
do not substitute an alias. Fix network access and run the command again.

Pending retests are stored in `data/f111_paper_state.json` and survive a
restart of this same process. A missed minute is a rejection, not a fill at
an old open.

If the first sessions produce no signal, say zero signals. Do not manufacture
a trade.

## 5. Rollback that keeps exit supervision

1. Create `data/f111_paper_scan_disabled`. That stops new F111 entries and
   new F111 protection decisions. It does not flatten the book.
2. Restore the approval backup from step 3 so the retired hourly entry rows
   return. Restoring the book does not rewrite open positions.
3. Restart the **same** paper process only.
4. Leave `data/firm.db` and `data/paper_cash.json` in place. Do not restore
   an older ledger over a newer one, and do not close positions by hand.

The engine still polls stops for every open paper position, including the
hourly sleeves that were retired and any F111 position that already filled.
The stop on a filled F111 position stays at the last effective level.

To roll the code back as well, check out the previous commit in the same
tree and restart that same process after the flag file and the approval
restore. Still do not reset cash.
