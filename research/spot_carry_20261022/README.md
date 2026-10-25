# Same-token funding carry: executable data handoff

22 October 2026 (Asia/Dubai). Read **HANDOFF_GROKBOT.md** for the complete assignment.

This is a code-only handoff. It contains two public-data collectors, synthetic tests and instructions. It includes no private research data, account records, large market archives or prior strategy results. The collectors obtain the historical inputs directly from the exchange.

**A full strategy backtester is not included or claimed to have run.** After data readiness is established, Grokbot must document and commit the exact protocol before implementing and running the strategy test, as specified in the handoff.

## Isolated checkout

Use an existing authorized clone of `MetaOutlaws/mar_trading_firm`. Fetch branch `codex/spot-carry-handoff-20261022` and verify the exact commit supplied in the owner's prompt. Create a separate research worktree or clone. Do not switch, reset, merge into or restart the running application checkout. Inspect an existing research worktree before reusing it.

From this directory, with Python 3.10+ (standard library only):

```bash
python3 -m unittest discover -s code -p 'test_*collector.py' -v
python3 code/collect_matched_history.py --output downloads
python3 code/collect_funding_history.py --output downloads
```

Review both probe summaries. Candle/mark probe: `failure` null, six distinct stream/token results, ten rows each. Funding probe: `failure` null, both symbols, nonempty correctly bounded settlements; investigate interval/coverage rather than assuming a fixed funding schedule. Empty/partial/unavailable responses are not readiness.

After the probe review:

```bash
python3 code/collect_matched_history.py --download --output downloads
python3 code/collect_funding_history.py --download --output downloads
```

The candle collector requests BTCUSDT and ETHUSDT spot/perpetual/mark one-minute history for 2022-01 through 2025-12: 288 monthly stream/token units. The funding collector adds 96 token/month units and handles backward pagination, including changes in funding frequency. Both need no API key and use public GET requests only.

Completed months resume after checksum verification. Interrupted months are fetched again. Missing candles/settlements are recorded, never filled. Raw response pages, retrieval timestamps, exact bounded URLs and hashes are retained. A successful process exit does not establish complete data or strategy readiness. All summaries deliberately retain `strategy_ready=false` pending independent audit and an explicit cost/collateral model.

The funding collector's eight-hour calendar comparison is only a diagnostic. Validate the actual historical settlement schedule; a different interval is not automatically erroneous, and a matching grid is not proof of authenticity/completeness.

Collectors stop on unavailable/denied/rate-limited or malformed responses. Respect exchange limits and do not rotate domains/proxies to bypass access controls. Do not purchase data or use private account credentials. No 2026 market outcomes are requested. Publication does not start any job.

Store `downloads/` outside Git; it is ignored here. Return durable data/artifact locations, hashes and logs. Do not commit credentials, account databases or raw price archives. Use a normal research session/job runner if a download is long, and record the actual job status rather than claiming completion at launch.

## Public interface references

- Candles: https://bybit-exchange.github.io/docs/v5/market/kline
- Mark prices: https://bybit-exchange.github.io/docs/v5/market/mark-kline
- Realized funding: https://bybit-exchange.github.io/docs/v5/market/history-fund-rate
- Funding cash mechanics: https://www.bybit.com/en/help-center/article/Funding-fee-calculation
- Margin parameters: https://bybit-exchange.github.io/docs/v5/market/risk-limit

Current documentation is not proof that historical fees, contract terms or margin rules were unchanged. Use effective-dated records where available and disclose defensible assumptions and sensitivities where unavailable. A minute-open mark is a proxy for settlement cash until shown otherwise.

## Validation

The handoff contains 15 offline tests. They cover candle market/time/price validation, gaps, unavailable HTML, date limits, full synthetic month/resume/checksum corruption, signed funding, duplicate/out-of-window funding, changing-interval pagination and funding resume behavior. Historical live API downloads have not been verified in the publishing environment.
