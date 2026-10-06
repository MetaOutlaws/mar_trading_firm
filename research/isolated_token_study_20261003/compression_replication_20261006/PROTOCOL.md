# Compression replication: frozen acquisition and evaluation protocol

6 October 2026 UTC. Brian approved broader-token replication of the unchanged
compression entry. Objective: positive, repeatable net expectancy with measured
uncertainty. Low frequency is acceptable. No claim of certainty or leverage
readiness follows from a positive historical cell.

## What is fixed

Reuse entry_discovery_20261006/features.py, without changing its event thresholds
or finite-feature warm-up. Entries on 5m, 15m and 1h; both directions. Primary
stop/target 2%/2.5%; 3%/3% is descriptive sensitivity and cannot rescue failure.
Completed bars; next-minute open; conservative stop-first ambiguity and adverse
stop-gap fills; no maximum hold and no compulsory 4h-regime exit. Funding and
fees charged as in the frozen engine. Each period ends with explicit marks.

Costs: fee 0.055% each side. All NEW tokens use 0.10% slippage each side in the
base case and 0.20% in stress, regardless of the historical winner. Original
BTC/ETH reference cells retain 0.05%/0.10%; SOL retains 0.10%/0.20%.
No calibration of costs to make a result profitable. Actual market impact,
spread, mark-price liquidation and historical risk tiers remain separate work.

## Universe, before outcomes

The unit of expansion is up to 15 additional tokens EACH month, alongside the
three existing reference tokens. Membership may rotate; the distinct historical
union can exceed 15. BTC/ETH/SOL are excluded from the primary replication pool.
Token categories are descriptive, not performance-based quotas.

Acquire the paginated Bybit USDT-settled linear-perpetual catalog for all
documented applicable statuses, retaining failed requests and closed contracts.
Add historical instrument records from a separately sourced registry when
available. Never substitute today's listed tokens for a proven historical
universe. API catalog completeness is UNKNOWN until audited against historical
listing/delisting records. Retrieval success alone cannot clear this flag.

Before each UTC month, select at most 15 new tokens with at least 90 calendar
days since listing/first observed trading, all preceding 30 daily observations,
and prior 30-day median daily USDT turnover >=10 million. Rank by that median,
descending; ties alphabetically. Use only completed days BEFORE that month.
Exclude explicitly identified stablecoin/metal underlyings and noncrypto
instrument types; retain every exclusion. Current instrument classifications
are not a verified historical classification. Record unknowns for review.
Membership changes affect new entries only; existing positions keep their exits.

The catalog and daily turnover panel must be frozen before any new-token trade
outcomes are calculated. Availability is not profitability. Do not backfill a
missing member with the next ranked token after observing data failures.

## Data and chronology

Acquire 2022-01-01 through 2025-12-31 minute candles and all settled funding for
the selected historical union. Use daily candles to form the universe first.
The collector never requests 2026 price/outcome bars. A funding settlement
exactly at the terminal 2026-01-01 00:00 UTC mark is included for boundary cost
accounting; no later settlement is fetched. This clarification was recorded
before new-token acquisition or scoring. Warm-up begins at the observed
listing or 2022-01-01, whichever is later; no invented prelisting candles.
Track launch/delivery timestamps, duplicate contradictions, missing minute
bars, incomplete endpoints, and funding coverage. Funding intervals differ
between instruments and can change; never fill missing funding with zero or
assume a universal eight-hour schedule. A maximum-gap check is only a diagnostic,
not proof of a complete historical funding schedule.

2022-24: historical replication/context, with no threshold tuning.
2025: predeclared cross-token evaluation. This is new-asset evidence if the
assets were not previously scored, but the calendar period and hypothesis have
already been viewed on BTC/ETH/SOL. It is NOT a globally untouched holdout.
2026 stays unscored. Future confirmation requires a separate frozen checkpoint
after reviewing this replication; it will not open automatically.

## One primary pooled test

Pool new-token compression events across all three clocks and both directions.
At a simultaneous same-token signal, prefer 1h, then 15m, then 5m; skip opposing
directions at the same timestamp. At simultaneous different-token signals, use
the prior-turnover rank then symbol. No outcome-based ordering.

One position per token across clocks and directions; at most six open in the
basket and at most three in either direction. A position exiting during minute
t remains occupied until t+1. Full position and rejection logs are required.
Primary expectancy is mean net R of admitted trades, where R is the nominal
initial stop distance. This is a trade-level pooled test, not a levered account
return. Report every clock/token/direction cell separately as descriptive.

The primary configuration is fixed now; no choice among historical winners.
Report calendar-week block bootstrap intervals (1- and 4-week blocks, 10,000
draws, fixed seed 20261006) across ALL tokens together, including no-trade weeks.
This preserves common market episodes within each sampled block. Require
positive lower 95% bounds under base and stress at both block lengths, at least
100 completed 2025 trades across 50 entry dates, 26 entry weeks and eight new
tokens, and positive stressed expectancy when removing any one token. Also
report profitable-token breadth, largest-token profit share and longest loss
streak. Support is pooled; no requirement for 20 trades per token per year.

A candidate can pass only when historical universe and funding completeness
are independently verified. Numeric profitability with missing provenance is
reported as provisional, never silently promoted. Missing symbols/periods remain
in the denominator of coverage; acquisition failures cannot become exclusions
chosen after performance. All valid data remains useful for descriptive work.

## Scaling and leverage

The first target is net expectancy and stability. More tokens can create more
opportunities but also simultaneous correlated losses. Nominal risk reporting
uses 0.25% of starting equity per trade, maximum 1.5% across six positions and
0.75% per direction; these are research scenarios, not production settings.
Gaps/costs can exceed nominal stop risk. Do not report multiplying trade returns
by 5 or 10 as a validated portfolio result.

Leverage testing follows entry confirmation and requires actual mark-price
paths, maintenance-margin tiers, margin mode, funding, cash/margin occupancy,
intratrade drawdown and stressed correlated losses. At fixed position size,
higher selected leverage changes margin use, not the underlying trade P&L.
Increasing notional increases both P&L and loss exposure. No live leverage change
or orders are authorized by this research protocol.

## Status and preservation

At freeze, only the original BTC/ETH/SOL cache is present. Direct Bybit access
from this workspace returned a non-JSON Site Unavailable page. Acquisition must
run where public Bybit market data is accessible. The supplied collector uses
Python's standard library only and public GET endpoints; no account credentials,
trading endpoints, Docker restarts, production config or approval changes.

Save all raw pages, normalized data, selection ranks, exclusions and source
hashes. Interrupted acquisition resumes without discarding partial evidence.
Validate the runner against old reference trades and synthetic occupancy cases
before expanded scoring. The reference check is engineering verification, not
another independent strategy result. Publish protocols/status/aggregates only;
retain source and detailed evidence in the private handover package.

Primary API references, reviewed 6 October 2026:
- https://bybit-exchange.github.io/docs/v5/market/instrument
- https://bybit-exchange.github.io/docs/v5/market/kline
- https://bybit-exchange.github.io/docs/v5/market/history-fund-rate
- https://www.bybit.com/en/help-center/article/FAQ-Order-Execution-and-Liquidation
