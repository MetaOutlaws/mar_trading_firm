# Three focused entry follow-ups — frozen before scoring

7 October 2026. Brian approved the sequence hourly compression, funding, then trend pullbacks, with explicit hypotheses and decisions. These three diagnostics use the existing BTC/ETH/SOL history. They do not supply independent confirmation or new-token evidence. None of the new comparisons has been scored at this freeze.

## Common design

Reuse the six original minute/funding files and nine frozen causal feature tables from entry_discovery_20261006, checking their hashes against the existing three-token audit. Reuse the fixed monthly eligibility/ranking table from three_token_compression_20261007: 90 observed days, preceding 30 complete days, median turnover >=10 million USDT; all three symbols qualify April 2022 through December 2025. No asset selected using profit.

Historical context is 2022-01-01 through 2024-12-31, continuous within that partition; reused evaluation is calendar 2025. Start each partition flat and mark any remaining position at the end. Annual and 2022–23/2024 summaries are by entry date, without additional forced exits. No 2026 price outcomes. Include funding exactly at 2026-01-01 00:00 only for terminal costs. Prior outcome exposure on these assets/years must remain explicit.

Primary arm 2% stop / 2.5% target. Separate descriptive sensitivity 3% / 3%; it cannot rescue the primary. Completed bars, next-minute open, unchanged fixed quote barriers, adverse gap stops, stop-first same-minute ambiguity, conservative settled-funding timing; no holding cap and no 4h regime exit. Fee 0.055% per side; base per-side slippage BTC/ETH 0.05%, SOL 0.10%; stress doubles slippage. Both directions in every variant.

Each variant is its own alternative basket. Generate every raw candidate before admission. One open position per token across clocks/directions, max six overall and three per direction; conflicting same-token simultaneous directions rejected; same-direction priority 60m >15m >5m; cross-token ties by prior liquidity rank and symbol. Exit minute stays occupied through that minute. Never add trades or returns across alternative variants or cost scenarios. The three-token universe cannot test the six-position limit at scale.

## Hypothesis: hourly compression survives a standalone replay

Treatment `compression_hourly`: all unchanged compression events on 60m only. Comparator `compression_all`: the exact earlier 5m/15m/60m basket. Restricting the entry clock is the only change. Regenerate raw events rather than selecting the previously admitted hourly subset. Reconcile the all-clock comparator against the prior eight pooled results and ledger identities.

The previously observed hourly subset was positive, with wide uncertainty and 27 evaluation trades. Test whether freeing tokens from other-clock occupancy preserves that positive expectancy. Show newly admitted and no-longer-admitted hourly events, and their outcomes, without attributing the entire mean difference solely to them; removing other clocks also changes composition.

Continuation criterion: primary stressed mean >0 in historical context and reused evaluation. Report base means, annual contributions, all token/direction cells, leave-one-token-out means and both confidence intervals. Wide intervals or concentration keep the result exploratory. This is a hypothesis selected after prior outcome review.

## Hypothesis: extreme funding adds value to the breakout

Treatment `funding_extreme`: unchanged original funding-crowding breakout across 5m/15m/60m. Long requires last settled funding <= -0.0001 and <= preceding 90-day 5th percentile; short requires >= +0.0001 and >= preceding 90-day 95th percentile. Both require funding age <=12 hours, signed 24h return >0, directional candle, and a fresh close across the preceding six-hour high/low. Keep the original one qualifying event per settled-funding timestamp, per token/clock/direction/partition.

Comparator `funding_breakout_control`: remove only the extreme-funding predicate. Keep funding age, momentum, breakout/candle confirmation and the same per-settlement de-duplication convention. Without the predicate, a different earlier qualifying breakout can be chosen within a settlement; that is an intended consequence and will be reported. Neither basket proves forced liquidation or order-flow imbalance. No funding threshold sweep or token-specific selection.

Question: does the extreme condition improve mean net expectancy over the underlying breakout AND leave a positive absolute result after costs? Report differences in all costs, funding cost/credit separately, support and uncertainty. This is an observational policy comparison, not randomized or matched proof that funding causes returns.

## Hypothesis: completed 4h trend alignment improves pullbacks

Comparator `trend_original`: unchanged discovery trend-pullback entry. Signed preceding 168-hour return >0; recent opposing shock (previous six entry-clock observations of hourly normalized return include <= -1.5 for longs / >= +1.5 for shorts); directional candle breaking previous candle high/low.

Treatment `trend_aligned`: add only the existing completed 4h regime agreeing with trade direction. Existing regime uses EMA50/EMA200: long when price >slow, fast >slow, and fast >fast three 4h bars ago; short mirror. Neutral and opposing regimes are excluded. The original seven-day-return condition stays. No EMA optimization and no regime-triggered exit.

Question: does the context filter improve net expectancy while accounting for winners removed and changed position availability? Report admitted/rejected events, full raw accepted/excluded cohorts and all descriptive token/clock/direction/year contributions. No outcome-derived threshold selection.

## Inference and decisions fixed now

Primary score is admitted mean net R (net return divided by nominal stop); also report percentage return per trade, completed net win rate, stops/closed fraction, targets, terminal marks, costs, holding time and support. Cumulative trade-return units are not account return or account drawdown.

Use the established 1- and 4-week calendar moving-block bootstrap, all tokens together, including empty weeks, 10,000 draws, seed 20261006 + block length. For treatment-minus-comparator mean-R intervals, draw the same calendar blocks for both baskets and divide each basket's sampled return sum by its own sampled count. Retain draws only when both counts are positive. Samples are not matched individual trades. Mean differences are not improvements in account return; trade frequency also changes.

For funding and trend, the local continuation criterion requires positive primary stressed treatment mean AND positive treatment-minus-comparator stressed mean in BOTH historical context and reused evaluation. Better-but-negative is recorded as relative improvement without profitability. Failing either partition is recorded as no continuation support under this test. A positive point criterion with intervals crossing zero remains exploratory/inconclusive for an established edge. Report how token removal and annual splits affect the conclusion; do not switch to a profitable subgroup after seeing it.

No result in this reused three-token batch qualifies for deployment or substitutes for the original eight-new-token replication gate. Three related hypotheses and multiple descriptive subgroups are being examined; individual 95% intervals do not correct for this selection or prior experiments. Future independent confirmation must predeclare the candidate set and multiplicity handling. No automatic opening of 2026.

Stop after these fixed comparisons and report all outcomes. Volume-shock and learned-rule experiments remain paused pending materially new inputs/hypotheses. Entry-filter sweeps, new RSI/ADX/Connors rules, stop optimization, trailing exits, new-token scoring and leverage simulation are outside this batch.

## Verification and preservation

Before scoring, verify input/feature/membership hashes and freeze protocol/source hashes. Synthetic checks cover filter-only changes, completed-regime alignment, funding de-duplication and common-block contrast identity. After scoring, reconcile original event functions and old all-clock compression; independently check barriers, admission, cost identities and summaries. Save raw events, all opportunities, accepted/rejected ledgers, plain CSV trades, comparisons, decisions and a private restore-verified checkpoint. Publish protocol, findings and aggregates; update the living roadmap and handover.
