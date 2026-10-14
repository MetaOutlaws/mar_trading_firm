# Offline staging plan: paper books on nyc3 and sgp1

**Plan only.** This note specifies how a later, human-run staging pass
must treat paper-book identity. It is not a migration. Nothing in this
change connects to SQLite, Postgres, or either droplet. Do not run the
SQL sketches below. Live trading stays off. `config/approved_strategies.json`
is not part of this change, and no strategy is marked approved.

The checker that matches this note is `core.ledger.host_identity`. It
classifies rows that are already in memory. It does not open a database
and it does not return a merged book.

## Hazard

`Position.id`, `TradeRecord.id`, and `EquitySnapshot.id` are integer
primary keys (`core/ledger/models.py`). Each process that owns a
database allocates those integers itself. The nyc3 droplet and the sgp1
droplet do not share a sequence. `positions.id = 1` on nyc3 is a
different position from `positions.id = 1` on sgp1.

A later merge that treats `id` as a global key corrupts the book:

- SQLite `INSERT OR REPLACE` is a delete of the conflicting row followed
  by an insert. The sqlite3 CLI leaves `foreign_keys` off unless a
  session turns them on, so the delete of nyc3's position succeeds and
  sgp1's row reuses the same integer. nyc3's `trades.position_id` still
  says that integer, and now describes the other host's position.
  `core/db.py` does turn foreign keys on for the application engine;
  a dump/restore tool will not, unless someone sets the pragma. Do not
  rely on the pragma to save a bad merge.
- Postgres `INSERT ... ON CONFLICT (id) DO UPDATE` overwrites one host's
  row in place. `ON CONFLICT DO NOTHING` and SQLite `INSERT OR IGNORE`
  drop the other host's row. Both throw a book away.
- A naive row copy (`INSERT INTO positions SELECT * FROM other.positions`,
  or copying pages between SQLite files) either hits the primary key or,
  if the id column is omitted, leaves `trades.position_id` pointing at
  the wrong parent.

Cash is a second, independent hazard. The paper journal is
`data/paper_cash.json`, replayed by `replay_events` in
`core/execution/paper_cash.py`. Events have no id, no host, and no
epoch. Concatenating a September journal with an October journal sums
capital, fees, funding, and realised P&L into one account.
`PaperCashStore` then atomically replaces the file with that replay.
Doing that on the running droplet replaces the live journal.

September and October are accounting epochs (book generations), not a
hint to re-bucket each row by `opened_at`. A position opened in one
epoch and closed in the next, if that ever exists inside a single file,
stays in the file's epoch. Splitting a file by timestamp would break
the trade/position link and is out of scope.

## Composite identity

Inside one table the identity is:

```text
source_server + epoch + id
```

| Field | Allowed values | Meaning |
|---|---|---|
| `source_server` | `nyc3`, `sgp1` | Which droplet the file was copied from |
| `epoch` | `2026-09`, `2026-10` | Which accounting generation that copy is |
| `id` | integer, `>= 0` | The primary key in that file, unchanged |

`table` is not part of the key inside a table. It is part of the check
so `positions.id = 1` is not compared with `trades.id = 1`. Both
sequences start at 1 on every host.

The two axes are independent. This plan does not claim that nyc3 is
September and sgp1 is October. The operator stamps both labels when the
copy is made, from which machine and which generation the file is. A
merge that keeps the host but drops the epoch, or keeps the epoch but
drops the host, is still a bad merge.

If the operator cannot say which epoch a file belongs to, that file
stays quarantined. Do not guess from `max(opened_at)`, from a filename
date, or from the other host's labels.

Cash events have no id in the JSON. For the checker, `id` is the
0-based index of the event in **that** file's `events` array. Do not
renumber when two files are placed side by side.

`trades.position_id` is not an identity. It is a foreign key back to
`positions.id` **of the same** `source_server` and `epoch`.

## How to detect collisions

Load copied rows into memory and call `detect_book_collisions`. Do not
point it at a database. The report is the decision record.

1. **Integer-id collision.** Group by `(table, id)`. If more than one
   `(source_server, epoch)` appears in a group, those rows collide.
   Overlapping ids are expected: both hosts autoincrement from 1. The
   finding means "keep every identity." It does not mean "pick a
   winner" or "delete the older id."
2. **Host mix.** More than one `source_server` in the set. Disjoint
   integers are not a free pass. An `INSERT` of both sides into one
   `positions` table would succeed and still union two books.
3. **Epoch mix.** More than one epoch in the set. September and October
   cash must not be passed to one `replay_events` call. September and
   October equity snapshots must not become one curve ordered by `id`
   or `recorded_at`.
4. **Payload conflict.** The same composite identity appears twice with
   different bodies. The copies disagree. Stop. Do not `REPLACE`.
5. **Duplicate export.** The same composite identity appears twice with
   the same body. That is one file copied twice. Deduping that pair
   does not authorize a host merge.
6. **Banned statement.** The SQL text contains `INSERT OR REPLACE`,
   `REPLACE INTO`, `INSERT OR IGNORE`, or `ON CONFLICT ... DO UPDATE`,
   `DO NOTHING`, or `DO REPLACE`. A column list between `ON CONFLICT`
   and `DO UPDATE` still matches. The checker does not execute the text.
7. **Destructive statement.** The text contains `DROP`, `TRUNCATE`, or
   `DELETE FROM`. Those are banned against nyc3, against sgp1, and
   against the staging file. nyc3 is not cleaned up to make a merge
   easier.
8. **Banned destination.** The only write labels the checker accepts
   are `staging` and `offline-staging`. `nyc3`, `sgp1`, `live-sgp1`,
   a filesystem path, and any unrecognised label are banned. Empty
   destination means "inventory only."

`CollisionReport.blocks_naive_merge` is true when any of 1–3, a payload
conflict, a banned statement, a destructive statement, or a banned
destination is present. Duplicate exports alone do not set it.

A single host and a single epoch, with no statement and an empty
destination, does not block. That result is an inventory of one book.
It is not permission to copy that book onto the other droplet.

## Explicit bans

These are hard stops. A staging pass that needs one of them is the
wrong pass.

1. **No `INSERT OR REPLACE`.** Also no `REPLACE INTO`, no
   `INSERT OR IGNORE`, and no `ON CONFLICT DO UPDATE` / `DO NOTHING`.
   Those statements resolve a primary-key clash by deleting,
   overwriting, or dropping a row. The clash is two positions, not a
   duplicate.
2. **No merge onto the live sgp1 book.** Do not copy rows, a staging
   file, or a concatenated `paper_cash.json` onto the sgp1 droplet's
   database, its `-wal` / `-shm` files, or its `data/paper_cash.json`.
   Do not change sgp1's `DATABASE_URL` to point at a merged file. Do
   not restart the paper process there against imported rows. sgp1
   remains the running book, untouched.
3. **No destruction of nyc3.** Copy out, do not move. Do not `DROP`,
   `TRUNCATE`, `DELETE`, vacuum-into, or replace nyc3's `firm.db`,
   WAL, SHM, or `paper_cash.json`. Do not unlink them after a "successful"
   copy. A later staging file is a third artifact.
4. **No silent epoch combine.** Do not concatenate September and
   October `events` arrays. Do not sum their snapshot headers
   (`contributed_capital`, `cash`, `realised_pnl`, `total_fees`,
   `total_funding`). Do not stitch `equity_snapshots` into one series.
5. **No application schema change on a live book.** Do not add
   `source_server` or `epoch` columns to the running `positions` table
   via `core/db.py` or an `ALTER` against either droplet. The composite
   key lives only on the offline staging copy described below.
6. **No live trading and no new approvals.** `TRADING_MODE` stays
   paper. This plan does not set `approved=true` and does not edit
   `config/approved_strategies.json`.

## Offline staging procedure

Human steps, on copies, on a machine that is neither droplet. There is
no script in this repo that performs them, on purpose.

1. **Quiesce nothing by force.** Do not stop nyc3 in order to snapshot
   it if stopping it is someone else's production decision. A copy
   taken under WAL still needs the matching `-wal` file in the same
   directory as the copied db, or the copy is a partial book. If the
   WAL cannot be copied consistently, quarantine and stop. Do not
   repair the source.
2. **Copy, do not move.** Place each copy in its own directory named
   with the server and the epoch, for example `nyc3/2026-09/` and
   `sgp1/2026-10/`. The directory is on the staging machine. Record
   who assigned the epoch and why, in a text file next to the copy.
3. **Leave the originals in place** on both droplets, including WAL,
   SHM, and `paper_cash.json`.
4. **Stamp rows in memory** with `source_server`, `epoch`, `table`,
   and `id` before any shared file exists. Cash uses the event index
   as `id`.
5. **Run `detect_book_collisions`** on those mappings. Expect integer
   collisions wherever both books have traded. Expect `host_mix` and,
   when both generations are in the inventory, `epoch_mix`. Save the
   report. If `payload_conflicts` is non-empty, stop for that identity;
   the two copies are not the same export.
6. **Create a new local file** that is not named `firm.db` and is not
   inside a checkout that either droplet runs. Suggested shape, as a
   sketch, not a migration to execute against either host:

   ```text
   staging_positions
     staging_id          new integer, only in this file
     source_server       nyc3 | sgp1
     epoch               2026-09 | 2026-10
     source_id           original positions.id
     ... remaining position columns, unchanged ...
     UNIQUE (source_server, epoch, source_id)

   staging_trades
     staging_id
     source_server
     epoch
     source_id           original trades.id
     source_position_id  original trades.position_id (nullable)
     staging_position_id lookup of (source_server, epoch, source_position_id)
     ... remaining trade columns ...
     UNIQUE (source_server, epoch, source_id)

   staging_equity_snapshots
     same composite unique key
     do not order a cross-host curve by source_id

   staging_cash_events
     staging_id
     source_server
     epoch
     source_index        index in that file's events array
     payload             the original event object
     UNIQUE (source_server, epoch, source_index)
   ```

   Inserts into that new file are plain `INSERT` of rows whose unique
   key is the composite identity. A unique conflict means the load is
   wrong. Stop. Do not switch the statement to `INSERT OR REPLACE`.
7. **Resolve trade parents by the composite key**, never by
   `source_position_id` alone. A missing parent inside the same server
   and epoch is a quarantine, not a reason to attach the trade to the
   other host's position with that integer.
8. **Replay cash per group only.** For one `(source_server, epoch)` at
   a time, `replay_events` on that group's events must match the
   snapshot header stored in that copy of `paper_cash.json`
   (`cash`, `realised_pnl`, `contributed_capital`, `total_fees`,
   `total_funding`). Do not concatenate groups and then replay.
   `replay_events` has no epoch filter; the separation has to happen
   before the call.
9. **Do not point the application at the staging file.** Do not set
   `DATABASE_URL` to it. Do not start `scripts/run_paper_trading.py`
   or `scripts/run_api.py` against it. Staging is an archive for
   reconciliation, not a book the engine trades.
10. **Do not copy the staging file back** to nyc3 or sgp1.

Other integer-keyed tables (`agent_runs`, `proposals`, `risk_events`,
`rejected_signals`, and the rest of `firm/memory_models.py`) have the
same class of primary-key hazard. They are out of this pass. Do not
"finish the merge" by copying the rest of `firm.db` with a replace.

## What this change does not do

- It does not add a migration, a CLI, or a connection string.
- It does not read or write `data/firm.db` or `data/paper_cash.json`.
- It does not alter `core/db.py`, the ledger models, or the cash store.
- It does not stop, delete, or rewrite anything on nyc3.
- It does not import, overlay, or replace the live sgp1 book.
- It does not enable live mode and does not approve a strategy.
