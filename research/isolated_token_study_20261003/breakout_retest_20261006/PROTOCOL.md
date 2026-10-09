# Standalone breakout/retest: frozen experiment

6 October 2026. User authorizes continuation after failed standalone-zone entry
prediction audit. This new mechanism was queued before that audit. One fixed
rule set; no threshold grid, no winner-based selection, no deployment.

## Scope and fixed inputs

BTCUSDT, ETHUSDT, SOLUSDT; long and short; 5m, 15m, 60m completed candles.
Discovery 2022–2024 and reused historical evaluation 2025. No 2026 scoring.
Use the same six SHA256-verified minute-candle/funding inputs, same completed
4h EMA50/200 directional regime and three-bar fast-EMA slope, same funding,
taker fee and base/doubled slippage. No maximum trade holding period.

Stop/target arms: 2%/2.5% (primary) and 3%/3% (secondary robustness comparison).
Compare entry methods only within an identical arm. Do not attribute a
difference between those arms solely to stop width or solely to target size.

## One causal setup, two entry policies

When no pending setup exists in that direction, a completed candle in the
matching 4h regime starts a setup when it closes strictly above the highest
high of the PREVIOUS 20 completed entry-clock candles (long), or below their
lowest low (short). Candle high/low from the current breakout is excluded from
that rolling level. A valid completed-candle Wilder ATR14 is required.

Freeze that breakout level and a band of +/-0.25 entry-clock ATR14 measured
at breakout close. Retest may occur only in the NEXT six completed entry-clock
candles; breakout candle cannot qualify. Long confirmation overlaps the frozen
band and closes strictly above its upper edge AND above its own open. Short
confirmation mirrors it. Fill at the next minute open with actual gaps/costs;
do not chase or enter automatically when no retest occurs.

Cancel before testing confirmation if the regime no longer matches or if a
long candle closes below the lower edge (short above upper edge). The sixth
candle may still confirm; otherwise expire at its close. After a confirmation,
cancellation or expiry, allow a new setup starting on the following candle.
Do not reuse the release candle to start another setup. Reset pending setups
at the evaluation partition boundary. Historical bars may warm up indicators.

Signal-generation state is independent of position occupancy. Preserve all
setups and confirmed candidates, including those arising while a trade is open;
the chronological execution scheduler independently rejects busy entries. No
capital reservation for pending setups. One pending setup per direction.

The immediate-breakout control enters at the next minute open after each SAME
parent breakout. It uses exactly the same parent-setup cohort, so the retest
comparison is not confounded by independently generating more breakout setups.
Keep setup id, level, band, confirmation/cancel/expiry time and reason.

## Other controls and execution

Also replay the original EMA20 reclaim and reconstructed standalone-zone
entries under the identical two arms. Zone sources remain explicitly
reconstructed; original individual row identity is not proven. Reconcile all
72 selected zone configuration-period rows against reconstruction_v1 before
interpreting any breakout result. Reconcile EMA 2%/2.5% rows against the fixed
stop archive when those reference rows exist, at both cost levels.

Each of four entry families independently admits one position per token,
clock, direction and arm. A new position can enter only AFTER the prior exit
minute. Same-minute stops take precedence over targets; stop gaps use adverse
open quotes. Reuse the unchanged prior execution engine, including regime
open handling and conservative intrabar funding. Boundary marks retained.

18 token/clock/direction groups x 4 entry families x 2 arms =144 configurations;
two periods x two costs =576 chronological result rows. These are overlapping
research configurations, not independent portfolio bets. Save every trade,
source candidate, parent setup, annual result, summary and reference check.

## Gate and decisions

For a retest configuration to merit fresh confirmation: >=50 completed trades
in EACH period, mean net>0 and PF>=1.15 in each base-cost period, and mean net>0
under doubled slippage in each period. Also report its incremental difference
against immediate parent breakout, EMA and zone controls within the same arm.
No conditional retuning if the screen fails. A passing reused-history screen
would still be exploratory and require fresh confirmation.

Report net/trade, average win/loss, win rate, trades, stops and stop-out rate,
target/regime/boundary counts, fees/funding, holding times, equal-initial-risk
mean R, and closed-trade plus minute-close MTM drawdown. Drawdowns are additive
unit-notional/initial-R research measures, not compounded account returns.

Test setup direction symmetry, exclusion of breakout candle, frozen level,
sixth-bar expiry, regime cancellation, future-prefix independence and no
automatic fallback. Preserve failed implementation invocations separately.
Freeze protocol/code commits before outcome scoring. Do not change cloud
settings or research-approved flags.
