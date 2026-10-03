# MAR isolated research package — 2026-10-03

**State: research infrastructure prepared; historical study blocked by missing candles.**
No market backtest has run. No winning strategy, preferred token, forecast return or leverage recommendation has been established. Fourteen synthetic execution tests pass. This package is separate from Grokbot and the deployed application.

## What is ready
- Frozen study protocol for BTCUSDT, ETHUSDT and SOLUSDT.
- Strict 1-minute candle/funding audit with file hashes and coverage checks.
- Descriptive 1/2/3/5% opportunity analysis over 1/4/8/24 hours, with nonoverlapping windows per horizon and direction.
- First-touch 3/5% target versus 1/1.5% stop flags, and adverse excursion through the target minute. A same-minute tie is a stop. Descriptive excursions are quoted-price statistics, not net trade returns.
- Two fixed signal mechanisms; 48 configurations including tokens and directions.
- Discovery/validation selection frozen before reserved evaluation, with fees, adverse slippage, funding approximation, one active trade per configuration, conservative intraminute exit ordering and boundary purging.
- Weekly-block confidence intervals, matched month/hour random entries, multiplicity correction across finalists and doubled-slippage stress.
- Trade-level exports and full discovery/validation table, not just winners.

## Run locally on copied data
Install requirements into a separate environment, then:

    python -m unittest -v test_study
    python study.py --cache /path/to/copied/cache --out /path/to/new/results

The results folder must not exist. Inputs are only read. The runner imports no firm code and has no network or order capability. Use a NEW folder when rerunning. Any protocol or grid change requires a new protocol version; never overwrite the original after seeing returns.

Input layout:

    cache/BTCUSDT_1m.parquet
    cache/ETHUSDT_1m.parquet
    cache/SOLUSDT_1m.parquet
    cache/funding/BTCUSDT_funding.parquet
    cache/funding/ETHUSDT_funding.parquet
    cache/funding/SOLUSDT_funding.parquet

The application's native cache schema is supported. Read PROTOCOL.md for required history and assumptions. Insufficient history produces a blocker, not invented candles or an automatic shorter study.

## One-time existing-data handoff
Upload a ZIP containing the above existing cache files. If a coarse cache is all that exists, include the available 5m/15m/1h/4h files too; they establish available coverage before revising the study. Do not include .env, API keys, SSH keys, trading databases or production configs.

Optional exporter, run where an existing cache resides:

    python export_existing_cache.py --cache /data/state/data/cache --output /tmp/MAR-market-cache.zip

It copies ONLY BTC/ETH/SOL candle and funding Parquet files into a new ZIP and checks each file did not change during its read. It does not call Bybit, start validators or affect trading. Upload the resulting ZIP here. The path is derived from the earlier container mount, not a fresh filesystem verification.

## What remains after data arrives
1. Audit coverage and provenance; resolve timezones, funding gaps and contract identity.
2. Execute the frozen matrix and descriptive opportunity maps.
3. Review month/regime/session stability, adverse excursion, independent episode counts and signal concentration. The raw exports contain hour and an explicitly simple prior-24h trend label; a richer volatility/regime study is not yet implemented.
4. Strengthen random controls to match volatility and trend regime as well as month/hour. These controls are necessary before approval.
5. Add a mark-price liquidation and correlated portfolio simulator before studying realistic 5x/10x capital returns. Current outputs use return per unit notional; sums/drawdowns are additive diagnostic units, not a compounded account curve.
6. Publish evidence for each token, including no-edge outcomes. Use existing F-kit and operator gates; do not promote automatically.

## Material limitations
- Historical data is not yet present, and fees/slippage are assumptions rather than account/fill measurements.
- Funding uses traded candle opens as a mark-price proxy; settlement ordering inside an exit minute is bounded conservatively.
- A 99% weekly bootstrap interval is meaningful only with sufficient independent weeks and trades; it is not proof of stationarity.
- The reserved 2026 period may already have been studied by Grokbot and is not an organisation-wide untouched holdout.
- The candidate rules may overlap historical catalog mechanisms. They are isolated baselines and do not replace Grokbot's active impulse_pullback_continuation.
- The collector is a file export only. The study is not deployed or scheduled and cannot continue while no execution session is running.
