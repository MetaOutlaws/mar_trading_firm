# Independent data audit

The monthly files in `spot_carry_core.tar.xz` were checked without a strategy backtest. Raw HTTP bodies were not in this delivery (`spot_carry_raw.tar.xz`, sha256 `6ad48a8abfb332f8aabb0043468ad20d34a5ad4743f86a7dcc8f0d9e6001da55`). They are not required to recount the monthly series. They would be required only to re-hash the original response pages.

## Archive checks

| Check | Result |
| --- | --- |
| 12 split parts vs `PARTS.sha256` | all match |
| Reassembled `spot_carry_core.tar.xz` | `2157ec16fdacc8d27da2c0f81e644b8887d0e395d455453851755a07c79129c4` |
| Files listed in `SHA256SUMS` and present | 832 match, 0 mismatches |
| `SHA256SUMS` entries absent | 12,870, all under `downloads/raw/` |
| `SHA256SUMS` entries missing outside `raw/` | 0 |
| Sidecar sha256 vs monthly gzip bytes | 0 mismatches |
| Rows at or after 2026-01-01 | 0 |

`SHA256SUMS` itself hashes to `560485b8a73b5dae304329a4d082373e248b9cd687b1e1366d613d7f2b312135`.

Brian's probe summaries, stored beside the data, have `failure: null`, six candle streams of 10 rows, and two funding probes of 3 settlements. `strategy_ready` in those collector summaries is still false, which is what the collector writes. This audit is the separate readiness decision.

## Series

Each of spot, perpetual and mark, for BTCUSDT and ETHUSDT:

- 48 months, 2,103,840 minute rows
- first bar 2022-01-01 00:00:00 UTC, last bar 2025-12-31 23:59:00 UTC
- 0 missing minutes, 0 duplicates, 0 out-of-order rows, 0 bad OHLC, 0 bad volume
- month boundaries connect by exactly one minute

Funding, each symbol:

- 4,383 settlements, every interval exactly 8 hours, every stamp on the UTC 00:00/08:00/16:00 clock
- months that are not an exact calendar grid: none
- first 2022-01-01 00:00, last 2025-12-31 16:00 (the next stamp would be 2026-01-01 00:00 and is absent)
- every settlement minute has a mark open
- BTC rates from -0.00090728 to 0.00112788 (720 negative, 3,662 positive, 1 zero)
- ETH rates from -0.00330495 to 0.00097166 (831 negative, 3,552 positive, 0 zero)

Those rate counts describe the series. They are not a strategy result, and the entry hurdle was not set from them.

## Basis

Close-to-close `(other - spot) / spot` on all 2,103,840 common minutes. Spot was not copied into the perpetual: BTC closes match on 595 minutes, ETH on 2,300.

| Symbol | Perp vs spot mean | Perp vs spot min | Perp vs spot max | Minutes with abs basis > 2% | One-minute jumps > 50 bp |
| --- | --- | --- | --- | --- | --- |
| BTCUSDT | -2.6 bp | -4.12% | +2.30% | 4 | 21 |
| ETHUSDT | -3.1 bp | -3.13% | +2.34% | 6 | 48 |

Mark versus spot is similarly tight on average, with a few single-minute jumps above 2%. Those minutes stay in the series. Nothing was interpolated.

## Costs and margin

The files do not contain a historical fee, tick, lot, or margin table. The protocol labels spot taker 10 bp, linear taker 5.5 bp, 1x isolated margin, and 5% maintenance. Quantity steps 0.001 BTC and 0.01 ETH are the same kind of label. Current Bybit pages were not used as proof that those numbers held for all of 2022–2025.

## Readiness

The monthly price and funding series are usable for the frozen protocol. Raw response bytes remain unloaded. No strategy P&L has been computed from this audit.
