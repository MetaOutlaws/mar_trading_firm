# Exact F111 semantics and acceptance boundaries

## Selection

F111 combines R12 (`compression > 0.50`), E09 (original signal extension `<= 1 prior ATR`), and policy331 (late intended +0.25R floor after +1.25R). All retain the original high-volatility filter `prior_hourly_ATR / original_signal_close >= 0.01`, 60-minute retest, 3ATR initial stop and 4ATR target.

Preserve the existing original hourly compression/BTC-direction/Connors-RSI/low-efficiency strategy and its causal windows. The compression statistic is prior-six true-range mean divided by prior-60 true-range median; verify exact shifts and ATR construction in the inherited signal implementation and private source features. Do not reinterpret this as a 50% price move. Every feature must be available at the original signal time. R12 and E09 apply to the original signal, not to later retest candles/fills.

For direction `s=+1` LONG or `s=-1` SHORT, original extension is `s * (signal_close - boundary) / prior_ATR`. Boundary is the prior-20 hourly high for LONG, prior-20 hourly low for SHORT. Do not replace the inherited low-efficiency rule with the new extension gate: preserve the base rule and add the F111 gates.

## Retest lifecycle

Let `t0` be the original hourly signal's close time / first subsequent minute-open timestamp. Consider the 60 completed minute bars starting at t0 through t0+59 minutes. LONG touch: low <= boundary; SHORT touch: high >= boundary. Remember a touch. A strict reclaim is `s * (minute_close - boundary) > 0`. Touch and reclaim may occur in the same completed minute. Equality at the boundary is not a reclaim.

The first qualifying reclaim schedules entry at the next minute action. The last allowed confirmation can fill at t0+60. Research uses the next minute open; forward paper must use an actually available quote and record latency, never assign a missed past open. Do not scan only every 15 minutes and replay old signals as executable trades. Define and document stale-action behavior before activation, preserving the frozen signal windows.

No opposite-signal cancellation branch is enabled. Independently replay per-token occupancy: one position, admission strictly after the prior exit timestamp, and reject simultaneous opposite eligible entries. An AI/portfolio risk rejection is separately recorded and must not be hidden as a strategy filter.

## Original risk and brackets

With simulated entry fill E and the ORIGINAL prior ATR A:

- initial absolute price risk D = 3A;
- original R as a return = D/E;
- original R in currency = D * quantity;
- initial stop = E - s*D;
- target = E + s*4A.

Retain the target when protection is armed. No partial exits, trailing-distance branch, arbitrary holding cap or monthly/token capital cap is introduced. R is never recalculated from a tightened stop. Existing portfolio safeguards still apply.

## Protection ordering and cost-aware floor

The research simulator samples minute opens starting one minute AFTER entry. On each sample it checks the previously effective stop first, then target. If either exits, no new protection decision occurs on that sample. Otherwise update best favourable move from sampled prices (not future highs or intrabar peaks). Trigger eligibility is best gross move >= 1.25 * original R. Arm only when the current move is strictly above the candidate floor, as in policy331. Newly decided protection becomes effective on the NEXT minute sample; it must not stop out retrospectively on its decision sample.

For equal per-side fee fraction f=0.00055, cumulative signed funding cost F expressed as a fraction of entry notional (debit positive), desired floor g=0.25*D/E, and direction s, the candidate exit-price ratio is:

`candidate_price / E = (s + f + F + g) / (s - f)`

The reference represents this as favourable-move level `s * (candidate_price/E - 1)` and takes the maximum with the prior level. Equivalently solve `s*(exit-E)*qty - entry_fee - exit_fee(exit) - accrued_funding = 0.25*D*qty`. Handle the actual configured fee accounting consistently. Funding credits and debits have different signs. Once armed, the research recomputes and potentially tightens this cost-aware floor as funding evolves; never loosen it. Persist original risk, arming/best-move state, decided/effective stop and funding state across restarts.

Forward sampled quotes, latency and any more frequent stop supervision can change realised exits versus the historical minute-open model. Explicitly version and document these execution differences; do not claim exact tape equivalence. Historical long/short gap/ordering fixtures must still match the frozen simulator. Do not use a minute candle's high/low to invent stop-versus-target order.

## Costs and ledger

Research primary assumptions: entry and market/target exits adverse by 0.002 (20bps), fee 0.00055 (5.5bps) on each notional leg. Alternative base cost 0.003 (30bps). Research stop exits use the sampled actionable price without duplicating the market-exit slip; 0/5/10/20bps extra stop slip was a separate stress. Funding uses historical settlement events at their proper timestamps. Inspect simulator.py's `settle` and `direct_cash` for exact intervals and final valuation handling.

Use observed forward settlement rates where available, recording source and timestamp. If funding/quotes are missing, expose the condition and follow an explicit policy; do not silently substitute zero funding or fabricate liquidity. Paper fills/slippage are modelled, not measurements of orders sent to an exchange. Keep configured stop level, estimated cost-aware exit value, and realised net P&L distinct. Gaps/costs mean +0.25R is NOT guaranteed. Fee/funding stress cases are not liquidity measurements.

## Evidence and scope

F111 is the latest full combination, not a universal winner: F110 had higher primary-cost historical net; F111 performed better under higher base costs. F111's nine changed primary-cost protection exits comprised four saved stops and five reduced targets; the protection component reduced primary-cost net relative to F110. Comparisons with I11 remain uncertain, with paired uplift intervals crossing zero. Core BTC/ETH/SOL support is particularly small. No token-specific optima or calibrated probabilities are established.

All 2022–2025 outcomes and extensive earlier grids have already been viewed. They are development/chronological replication, not pristine out-of-sample. Millions of candles are not millions of independent trades. The owner permits a positive later year without requiring it to beat every control; that does not erase the original R12 failed-replication finding. Keep historical 2026 CLOSED. Forward paper records should retain additional93 and BTC/ETH/SOL separately and include all96 zero-sample cases.
