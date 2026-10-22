# Same-token funding carry — data audit

Research date: 22 October 2026 (UTC). Base commit: `2732dec7029ae96fb0601a1ce55ce068f054a358` on `codex/spot-carry-handoff-20261022`. This audit does not change that handoff. `MANIFEST.json` still matches the eight handoff files byte for byte.

**Readiness: not established.** `strategy_ready` stays false. No strategy protocol was frozen. No strategy outcome was computed. No 2026 market data was opened.

## Prompt versus handoff

The owner prompt and `HANDOFF_GROKBOT.md` agree on scope (BTCUSDT and ETHUSDT, long spot versus short linear perpetual, 2022-01-01 through 2025-12-31 UTC), on the collector path, on committing the protocol before any outcome, and on not imposing an arbitrary maximum holding period.

They differ on which cost model is primary. The handoff governs:

- Handoff: baseline and moderate costs are the primary economic views. Severe cost is a secondary stress, not the sole veto. Measured BTC/ETH execution must be distinguished from inherited 20/30 bp assumptions.
- Owner prompt: the desk's official cost is 0.31%, and that model should be stated as primary, with the severe case kept as a secondary stress.

The 0.31% figure is the inherited perpetual round trip in `research/costs.py`: `2 * (taker fee 0.055% + slippage 0.10%) = 0.31%`, funding excluded from that percentage (`CostModel.round_trip_cost_pct`). It is not a measured spot-plus-perpetual execution cost, and it was not applied. No backtest ran, so no cost model became the study primary. Had acquisition succeeded, the handoff's baseline and moderate views would have been primary, severe would have stayed a stress, and 0.31% would have been labeled as this inherited perpetual schedule rather than as measured carry friction.

## What was verified

| Check | Result |
| --- | --- |
| Handoff manifest SHA256 | 8/8 files match `MANIFEST.json` |
| Offline collector tests | 15/15 passed (`audit/OFFLINE_TEST_LOG.txt`) |
| Candle/mark probe | Failed. `failure` is HTTP 403. `results` is empty. Not six streams of ten rows. |
| Funding probe | Failed. `failure` is HTTP 403. `results` is empty. Not two nonempty bounded settlement lists. |
| Full `--download` | Not started. A failed probe is not readiness. |
| 2026 outcomes | Not opened. Collector window remains `[2022-01-01, 2026-01-01)`. |
| Running paper book, `core/risk/limits.py`, deploy configs | Not modified. |

The 15 tests are the handoff suite: candle market, time and price validation, gaps, unavailable HTML, date limits, full synthetic month resume and checksum corruption, signed funding, duplicate and out-of-window funding, changing-interval pagination, and funding resume.

## Blocker

`api.bybit.com` answers the collector's public GET with HTTP 403 before any candle or settlement body is returned. CloudFront pop `HIO52-P4` (Hillsboro, Oregon) returns:

```text
{ error:The Amazon CloudFront distribution is configured to block access from your country }
```

This host's public address at the time of the probe was `54.184.235.255` (`ec2-54-184-235-255.us-west-2.compute.amazonaws.com`, Boardman, Oregon, US, AS16509). Workspace egress is allow-all, so this is Bybit's country control, not a local deny. The same body was returned for spot kline, mark-price kline, funding history, and `/v5/market/time`. A second request of server time was also 403. The collector user agent was `MAR-public-research-audit/1`, which is the handoff's own header.

The collectors stop on a denied response and do not rotate host or proxy. That rule was followed. These were not tried: `api.bytick.com`, a proxy, a VPN, a paid vendor, or account credentials.

`https://public.bybit.com/` returned HTTP 200 and an S3 directory index. No object under that host was downloaded. It was not used as a substitute. The probes were invalid, and switching host to get around the API denial is the bypass the handoff forbids.

## Coverage that could not be audited

None of the 288 stream/token/month candle units or the 96 funding token/month units were fetched. There is therefore no SHA256, timestamp, gap, settlement-count, basis, or mark-price audit of historical series. Missing fields, all unresolved:

- Common usable spot / perpetual / mark coverage by token, month and year
- Funding settlement count, timestamps and interval changes
- Spot versus perpetual and mark-price differences
- Historical fee schedule, size and tick rules
- Historical margin and collateral rules
- Measured spread and slippage

Current documentation links in the handoff README are references only. They are not evidence that 2022–2025 fees or margin rules were constant, and they were not fetched as data.

## Official source and how to resume

The reproducible fetch is the handoff collectors. From `research/spot_carry_20261022` on a host that Bybit does not country-block:

```bash
python3 -m unittest discover -s code -p 'test_*collector.py' -v
python3 code/collect_matched_history.py --output downloads
python3 code/collect_funding_history.py --output downloads
```

Review both summaries before any download. Candle probe: `failure` null, six distinct stream/token results, ten rows each. Funding probe: `failure` null, both symbols, nonempty correctly bounded settlements. Only then:

```bash
python3 code/collect_matched_history.py --download --output downloads
python3 code/collect_funding_history.py --download --output downloads
```

Public endpoints, unchanged:

- Candles: `https://api.bybit.com/v5/market/kline`
- Mark prices: `https://api.bybit.com/v5/market/mark-price-kline`
- Realized funding: `https://api.bybit.com/v5/market/funding/history`

`downloads/` stays outside Git. A later successful run must publish file hashes, source URLs and retrieval logs. This audit's hashes cover the failure evidence only.

## Decision

Data readiness is not established. Phase B (freeze the protocol) and Phase C (implement, run, report outcomes) do not start. Inventing coverage or performance would violate the handoff.
