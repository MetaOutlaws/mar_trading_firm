# Broader-token replication: ready, awaiting data acquisition

6 October 2026 UTC. The approved plan is implemented and frozen. **No additional
token has yet been scored. No new profitability result or known edge is claimed.**

## Completed

- Frozen entry thresholds, costs, historical universe selection, pooled primary
  test, simultaneous-position rules and evidence requirements in PROTOCOL.md.
- Standard-library public-data collector, resuming cached requests after an
  interruption. Captures instrument status/launch/delivery, historical daily
  turnover, monthly selection ranks, minute candles and actual funding events.
- Offline input validator and replication runner. Missing execution data blocks
  scoring; incomplete historical-universe or funding provenance blocks promotion.
- Four focused tests passed: strictly prior-month selection, request pagination,
  token/clock/direction occupancy, and failure of empty/unverified qualification.
- All **216 previous compression result cells** reproduced exactly in trade and
  stop/target counts, and within 1e-12 in mean net returns. Six original input
  hashes and nine frozen feature hashes verified. Shared occupancy was exercised
  using old reference opportunities. These are engineering checks, not fresh evidence.

## Blocker observed

Only BTC/ETH/SOL histories were found in the saved research cache. The saved
archives include that original data and the research checkpoints, not the new
token minute histories. Direct Bybit requests and the new collector's preflight
both returned HTTP 200 containing a non-JSON **Site Unavailable / Unable to access
this site** page. The failed acquisition attempt and response prefix are retained.
No exchange access restriction was bypassed. No Singapore SSH session is attached
to this workspace, so the collector has not been launched on the droplet.

The private MAR_compression_replication_kit_20261006.zip contains the collector,
offline runner, supporting source, frozen protocol, test results and exact
Windows PowerShell/Singapore instructions. It requires no API key and the
collector requires no extra Python packages. It writes only to its chosen
research directory. It does not restart containers, modify approvals or place orders.

## What will run when the data is available

Each month: up to 15 additional eligible tokens ranked by prior 30-day median
turnover, subject to 90 days of listing/history and the frozen liquidity floor.
The historical union can contain more than 15 names. BTC/ETH/SOL remain references
and cannot count as new-token evidence. No token is substituted after a failed
download or after observing a loss. The catalog's historical completeness must
be audited, including delisted contracts and classifications.

The primary strategy pools the unchanged 5m/15m/1h compression entry, both sides,
with 2% stop and 2.5% target. One position per token; maximum six overall and
three per direction. The 3%/3% arm is descriptive sensitivity, not a substitute
winner if the primary fails. Report every token/clock/direction, costs, stops,
occupancy rejections, concentration and synchronous calendar-block uncertainty.

There is no minimum trade count per token per year. Evidence is pooled, while
requiring enough distinct dates, weeks and tokens to avoid mistaking one market
episode for many independent wins. A positive backtest can support an estimated
edge; it cannot create certainty about future trades.

## Leverage decision

Leverage is not enabled or tested by this stage. At fixed position size, selecting
higher leverage reduces initial margin rather than increasing trade P&L. To
amplify returns one must increase notional exposure, which also amplifies losses.
As a simple illustration, $25 nominal stop risk with a 2% stop implies $1,250
notional before costs, regardless of whether the selected margin leverage is 1x
or 5x. Costs and gaps can make the actual loss larger than $25.

After entry confirmation, evaluate margin mode, mark-price liquidation paths,
maintenance-margin tiers, actual funding, liquidity and correlated account
drawdowns. Bybit states that liquidation uses mark price, while a stop may use
last traded price: a stop is not itself proof against liquidation.

Sources reviewed: official Bybit instrument, kline and funding API documentation;
https://www.bybit.com/en/help-center/article/FAQ-Order-Execution-and-Liquidation.

## Current state

Prepared and verified: acquisition/replication code and protocol.
Blocked: additional-token data download from this workspace.
Pending: historical-universe/cadence audit and broader-token scoring.
Running in background: none.
2026 outcome bars scored: none. No production or trading settings changed.
