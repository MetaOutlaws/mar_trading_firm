# Owner approval — BTC + Connors + conditional extension cap

Brian's instruction on 8 October 2026 at 08:39 Dubai approves the low-efficiency-only
extension cap for PAPER deployment. It supersedes the 08:11 BTC + Connors selection
without a cap and all earlier hourly deployment preferences.

Strategy ID: `hourly_compression_btc_connors_loweff_v1`.
Scope: BTCUSDT, ETHUSDT, SOLUSDT; LONG and SHORT; completed 1h bars.
Initial stop 2%, target 2.5%, no timeout. Original compression and Connors
CRSI(3,2,100), LONG <=90 / SHORT >=10, remain fixed. ETH/SOL require matching
completed BTC24 direction; BTC retains its existing own-direction predicate.

Apply the one-prior-ATR extension cap ONLY when own-token prior24h efficiency
is below 0.30. ER >=0.30 has no extension cap. ER excludes the signal hour:
abs(C[T-1h]-C[T-25h]) divided by the 24 absolute hourly changes between these
endpoints, with closes labelled by close time and T the entry time. A flat path
has ER zero. No interpolation or missing-context fallback.
Extension = side*(signal close - prior20bar breakout boundary)/priorATR14.
Boundary is prior20 highs for LONG, prior20 lows for SHORT. Extension <=1 passes.
This is a causal market-state rule shared across years, not a calendar switch.

The owner selects study `hourly_extension_regime_20261008/results_v1`, arm
`combo_loweff`. Stressed results (average per-trade notional return):

| Period | No cap trades / stops / mean | Approved conditional cap trades / stops / mean |
|---|---|---|
| 2022–2024 | 56 / 22 / +0.3849% | 41 / 15 / +0.5003% |
| 2025 | 19 / 5 / +0.9205% | 15 / 3 / +1.1993% |

It removes 7 stops and 8 target winners historically, and 2 stops and 2 target
winners in 2025; no added/displaced admissions. Historical additive return sum
falls slightly despite higher mean. Incremental confidence intervals include
zero and 2025 has been reused, so this is an owner-approved exploratory paper
pilot, not an independently established edge or guaranteed profit.

Install six PAPER overrides (approved=false,paper_override=true). Retire only
exact known original / standalone Connors / BTC+Connors hourly entry records.
Preserve unrelated records, open positions, their exits, risk sizing and trading
mode. No live trading, leverage increase or additional-token deployment approved.

Runtime and a pinned host installer are prepared in PR101. Cloud installation
and scanning are NOT verified here; Grok must deploy with existing cloud access
and record a fresh healthy completed scan after activation. Read the latest
root GROK_START_HERE.md. Historical protocol/results/decision files remain frozen.
