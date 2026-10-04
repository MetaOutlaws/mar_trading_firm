# Findings — entry diagnostics and trailing exits

Date: 2026-10-04. Status: not scored.

## Conclusion

No candidate from this protocol qualifies, because the protocol has not been run. That is not a market null and it is not evidence of a market edge. The frozen question is still unanswered.

The earlier 48 configurations and 20 alternatives remain non-qualifying under the costs in `independent_review/EMPIRICAL_FINDINGS_2026-10-04.md`. This package does not retune them.

## What is frozen

`EXECUTION_ADDENDUM.md` registers the Stage 1 horizons, the 18 entry configs, and the four exit specs. `experiment_ledger.csv` lists every one of those rows with status `pre-registered` and blank outcome cells. `WAITING_FOR_GARWE_LOCK.md` is the stop on scoring.

## Costs that will be reported, once a locked run exists

- Comparable model: 5.5 bp fee per side; 5 bp slippage per side on BTC and ETH; 10 bp slippage per side on SOL. Round trip before funding is 21 bp on BTC and ETH and 31 bp on SOL.
- Doubled slippage is a full resimulation, not a second candidate.
- Desk disclosure: 10 bp slippage per side on every token, so 31 bp round trip before funding on BTC, ETH, and SOL as well. Funding is extra in both models and is not inside the 31 bp figure.
- Fees apply to every partial fill. Entry fees are charged once. No maker fill is assumed.

## Limitations

Candle paths cannot show order-book depth, queue position, tick order, or the exchange mark. Funding in the engine uses the traded minute open as a mark proxy. Discovery (2022–2024) and validation (2025) were already used by the archived studies, so a later pass is exploratory. 2026 is not a strategy sample in this protocol.

## Next evidence

A parent reply that the Garwe lock is recorded, then one run of `run_study.py` on a cache whose six file hashes match the addendum. That run writes the summary tables and the per-trade `csv.gz` files into a new output directory. Until those files exist, the outcome cells stay blank.
