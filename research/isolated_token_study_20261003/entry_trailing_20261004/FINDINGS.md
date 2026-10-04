# Findings — entry diagnostics and trailing exits

Date: 2026-10-04. Status: CLOSED_NULL. Complete for this budget.

## Conclusion

No qualifying candidate. All 18 pre-registered entry configs failed validation. The box run and Munha's independent score agree. Stage 3 exits were not applied, because nothing froze. 2026 strategy returns were not scored.

This is a null for this budget. It is not a claim that every future rule on these tokens loses money, and it is not a prompt to retune these 18 configs against 2025.

The earlier 48 configurations and 20 alternatives remain non-qualifying as well. Those families were not rerun here.

## What was decided

| Question | Result |
|---|---|
| Stage 2 screen, 18 configs | All fail validation |
| Frozen entry per token | None |
| Stage 3 exits | Skipped |
| 2026 | Not scored |
| Promotion | None |

Discovery and validation here are the windows already used by the archived studies: 2022–2024 and 2025. A pass would still have been exploratory. There was no pass.

## Numbers not in this commit

This workspace did not contain the box output directory or Munha's score file. Trade counts, means, profit factors, stress means, and the desk 31 bp column are therefore blank in `experiment_ledger.csv`. They are not guessed. Attach the files named in `results/TABLES_TO_ATTACH.md` if the archive should hold the path as well as the decision. Attaching them does not reopen the budget.

## Limitations

Candle fills are not the book. The comparable cost model is 5.5 bp fee per side, 5 bp slippage per side on BTC and ETH, and 10 bp slippage per side on SOL. The desk 31 bp round trip, before funding, is the disclosure column and was not a second search. Funding uses the traded minute open as a mark proxy. Same-bar trails are conservative: a high on a bar cannot tighten the stop that same bar is tested against. None of that was enough to produce a validation pass on these entries.

Fixed unit notional is not account equity. No leverage was applied.

## Next evidence

Do not search this budget again. A later question needs its own registered design, written down before the run, and it should change the information or the execution evidence rather than nudge these thresholds. Prospective paper observations would be new evidence. Another pass on 2022–2025 with the same 18 configs would not be.
