# Scan-summary log

The paper worker writes one informational Inbox card after each F111 hourly
pass and each book or cycle pass. The same card is appended, in full, to a
JSONL file in the firm state directory.

Nothing here places an order. Live stays off. A failed write is logged and
ignored; the scan, the gates, and the book are unchanged.

## Path

The file is `data/scan_summaries.jsonl` under the app root
(`PROJECT_ROOT / "data" / "scan_summaries.jsonl"`). That `data/` directory is
the state dir, the same one as `firm.db`, `paper_cash.json`, and
`near_miss_log.jsonl`.

On the SGP1 paper host the state mount is typically `/data/state`, with the
app's `data/` directory inside it. The log is then:

```text
/data/state/data/scan_summaries.jsonl
```

If the bind mount is somewhere else, the file is still `data/scan_summaries.jsonl`
relative to the checkout that process is running. Do not look for a second copy.

## What is in it

One JSON object per line, appended on every publish (insert, update, merge,
or an unchanged republish of the same bar). The line holds the Inbox title,
the rationale text, whether the card is durable, its expiry if it has one,
and the full payload (counts, sleeve rows, near misses, merged scans, and
the summary text).

The file is append-only. It is not rewritten and it is not pruned. Back it
up with `firm.db`. Do not commit it.

## Inbox retention

A card that records an entry, a fill, or an exit has no TTL. It stays in
the Inbox. A no-trade card (signals, rejections, near misses, or pending
retests only) still expires after two hours and is deleted when the Inbox
is listed. A no-trade card that later gains a trade, including one merged
in because the hour was already full, drops its TTL.
