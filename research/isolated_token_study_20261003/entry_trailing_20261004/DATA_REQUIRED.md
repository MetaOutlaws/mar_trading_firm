# DATA_REQUIRED

No market result was computed in this cloud VM.

Two independent stops are in force:

1. Garwe lock. `WAITING_FOR_GARWE_LOCK.md` blocks scoring until a parent reply records the lock. The runner was not pointed at a cache.
2. The one-minute cache is not on this machine. A search found no `BTCUSDT_1m.parquet` and no copy of the study archive.

When a parent runs the study, verify the archive before extraction:

`344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc`

Cache layout, same as the prior study:

```text
cache/BTCUSDT_1m.parquet
cache/ETHUSDT_1m.parquet
cache/SOLUSDT_1m.parquet
cache/funding/BTCUSDT_funding.parquet
cache/funding/ETHUSDT_funding.parquet
cache/funding/SOLUSDT_funding.parquet
```

The six file SHA256 values are frozen in `EXECUTION_ADDENDUM.md`. The runner checks them and then drops every price bar at or after 2026-01-01 UTC. Raw candles must not be committed.
