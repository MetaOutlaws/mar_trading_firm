# Independent review of PR92 — 2026-10-03

## Conclusion
The reported results reject two baseline entry mechanisms under the tested exits and costs. They do not reject all ways of trading BTC/ETH/SOL. There were 48 configurations but only two signal families, with strongly overlapping trades and parameter variants. Searching more variants without diagnosing the failure is a poor next step.

This review independently checked the code and arithmetic in the published report. It did NOT independently rerun the historical backtest: the 218 MB candle ZIP and exact results CSV are in a different execution workspace and have not been uploaded here. The Windows path is not an accessible URL. Neither /workspace/uploads/isolated_token_study_1m_2022_20261002_v2.zip nor /workspace/pr92_results_20261003_v2/all_discovery_validation.csv exists here. Exact-name and shorter Library searches found no matching uploaded dataset.

## Evidence verified here
Source commit: 97a6d25, research branch codex/isolated-token-research-20261003. Simulator SHA256 a5e4bf7f29c047b287af773275c12df59855d5dca8221f6c4da7e6dec2bca6f9, matching FINDINGS.

- Parsed all 48 published configuration rows, yielding 96 partition results. All 96 rounded means are negative; all PFs are below 1. This checks the report's internal arithmetic, not its source candles.
- Independently implemented a scalar execution calculator and compared it with Tape.run across 800 synthetic random-path cases: 100 paths × 2 directions × 2 targets × 2 slippage levels. All matched net P&L and funding to 12 decimal places, plus exit reason/time.
- Additional tests verify microsecond/nanosecond clock equivalence, funding-window count boundaries, a short-funding-cadence coverage blind spot, and losses from friction on a flat market. Five test methods passed, including the 800-case test. These are execution checks, not profitable trades.

Published ranges, copied/parsed from rounded report values:

| Token | Discovery net mean/trade | Validation net mean/trade | Best validation PF |
|---|---:|---:|---:|
| BTC | -0.217% to -0.138% | -0.291% to -0.111% | 0.857 |
| ETH | -0.280% to -0.126% | -0.318% to -0.017% | 0.978 |
| SOL | -0.455% to -0.281% | -0.447% to -0.260% | 0.729 |

SOL's larger excursions did not translate into profitable entries. ETH's near-break-even validation cell is not a survivor because its discovery period also lost money. These ranges should not be averaged into a portfolio; candidate trades overlap.

## Findings and their practical effect

### 1. Funding count discrepancy has a reproducible explanation
study.audit counts funding in [START - 8h, END], while the report's independent audit counts in-window events. A toy daily tape with three in-window 8h settlements yields four events in study.audit when the preceding settlement is included. This explains how the one-event discrepancy can arise, without assuming missing or duplicated funding. Confirm the actual leading timestamp when the Parquets arrive; do not silently delete an event to force matching counts.

### 2. Funding cadence audit is weaker than claimed coverage
The maximum-gap check only rejects gaps larger than 8h. During SOL's reported 2h settlement regime, one missing event leaves a 4h gap and passes. The independent test demonstrates that weakness. It does NOT demonstrate a missing event in the supplied data, whose separate audit reportedly checked all prints. Final verification should compare against historical instrument settlement schedules, not just a global maximum gap.

### 3. Costs cannot yet be blamed or dismissed
Net means alone do not reveal whether the entry rule had positive gross edge. Fees and assumed slippage sum approximately to 0.21% round trip for BTC/ETH and 0.31% for SOL before funding, while many reported net losses are of similar magnitude. That motivates attribution, not the conclusion that gross profitability exists.

diagnose_baselines.py reruns the same discovery/validation matrix and exports every trade, gross quoted-path movement, slippage drag, actual modeled fees, funding, stop/target/time fractions and quarterly results. The identity is checked per trade. Quoted-path return uses the ORIGINAL exit path: it is not a hypothetical zero-cost strategy whose exit barriers might differ.

### 4. Target size and unconditional volatility are mismatched
The reported median 24h favourable excursion is below 3% for all three tokens, from fixed start grids. A fixed 3–5% target therefore often asks for a tail event while a 1–1.5% stop can be reached first. This observation motivates testing volatility-normalized exits and conditional opportunity selection. It does not prove those changes will improve expectancy, nor establish how often actual signal entries reach a target.

### 5. Reversing every losing signal is not an automatic edge
For identical entry/exit timestamps and approximately symmetric friction C, original net is G-C and reversed net is -G-C. Their sum is -2C. A strategy losing roughly its transaction costs can lose on both sides. A reversed-barrier strategy also follows a different path and requires a full rerun. No reversed historical result has been computed here.

### 6. Some evaluation data is now exposed
2026 strategy return tests were not run because no finalist qualified. However, opportunity() processes the entire tape, including 2026, and its summaries were published. Therefore 2026 is not wholly unseen for subsequent research design, even aside from Grokbot's other studies. Treat next experiments as adaptive research with recorded dataset reuse; use locked temporal folds and prospective paper confirmation.

### 7. Reported bars are not a liquidation/portfolio test
No observed bid-ask/impact, queue, mark-price liquidation or correlated portfolio simulation was performed. Additive return-unit sums are not account returns. Running the same negative edge with 5x/10x leverage does not change its sign before capital constraints. Do not turn assumed passive fees into guaranteed passive fills.

## Next work prepared
See NEXT_EXPERIMENTS.md for a staged diagnostic study and a capped 20-candidate proposal: volatility-normalized continuation, followed by cross-asset residual reversion with BTC hedges and explicit costs on both legs. Both are hypotheses only; catalog overlap must be checked. Nothing is queued with Grokbot or promoted.

Run the existing-cell diagnostic once the copied cache is available:

    python3 research/isolated_token_study_20261003/independent_review/diagnose_baselines.py --cache /path/to/copied/cache --out /path/to/new/diagnostics

The diagnostic validates full data coverage but excludes 2026 candles/funding before signal construction or return calculations. It reads no account credentials, imports no production application and writes only its new output folder. It is prepared and syntax-checked; its historical output is pending data.

## Required handoff
Upload isolated_token_study_1m_2022_20261002_v2.zip here, or provide an accessible download URL, plus the small v2 results folder if possible. Expected ZIP SHA256: 344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc. Alternatively upload BTC first with its funding file and results for a sequential study. A filesystem path in another assistant's workspace is not shared storage.

No changes to production, approval book, worker instructions, live flags or Grokbot's ongoing tests. This is an independent research review, not a merge/deployment request.
