# Prior-use audit, performed before new 2026 strategy scoring

Verdict: usable for a fixed-strategy temporal replication; not an untouched holdout.

1. Original `study.py` loads 2022-01-01 through 2026-10-03. `run()` calls
   `opportunity(tape.c)` over that entire tape before checking whether a finalist
   exists. It also calculates full-span signal timestamps. Strategy scoring loops
   use discovery/validation only unless a finalist qualifies; none did.
2. Published `FINDINGS_2026-10-03.md`, confirmed on research branch head
   `36bc259436c1f6806efd18f5fba4d38c2b2264e6`, reports 1,736 24-hour descriptive
   windows per token/side, covering the full tape including 2026. It says reserved
   strategy evaluation was not run, and explicitly disclaims an organisation-wide
   untouched holdout because Grokbot may already have used it.
3. PR93/94 and later compression/filter protocols and recorded manifests exclude
   2026. The recent loader truncates candles before 2026-01-01. A date-only scan of
   58 available research Parquet ledgers finds zero 2026 entry rows. See inventory.
   This scan excludes files without an `entry` field and is not proof about missing
   archives, external workers, unrelated strategies, or unrecorded experiments.
4. Personal-context search recovered the same no-2026 scoring declarations for
   the recent sequence; it did not establish what external Grok sessions accessed.
5. Coverage checks find continuous valid minute OHLCV/turnover for all three tokens
   and 825 funding timestamps each in 2026 through 2 October 16:00 UTC. Raw hashes
   match the current compression research. The old PR92 report's historical funding
   counts differ from these recovered files, so no claim of original PR92 funding
   identity or independently verified exchange settlement schedules is made.

Scope of new result: first documented scoring of this exact approved combination
on 2026 in the recovered sequence, conditional on these data and execution proxies.
No new strategy outcomes were viewed to choose the interval or this classification.
