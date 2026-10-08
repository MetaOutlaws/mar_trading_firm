# H-EXIT-POLLING-01 findings

## Latest completed: sampled-exit audit, 8 October 2026

H-EXIT-POLLING-01 is complete. One-minute quote polling (the prespecified primary
test),five-minute and15-minute scenarios retain positive pooled means in all
three periods at base and doubled-slippage costs. One-minute sampling converts
three former target winners to stops. Historical profit margin remains thin.
No polling-speed,approval,entry,SL/TP or production configuration changed.

The table shows mean NET trade return / stop count with fees,funding and doubled
slippage. All arms use immediate entries and SL2%/TP2.5% from the slipped fill.
Actual sampled exit quotes can be beyond either threshold. Same65 admitted
signals throughout; targets equal trades minus stops. These are exit-polling
intervals, NOT the previous experiment's entry delays.

| Exit model | 2022–24: mean / stops (41 trades) | 2025: mean / stops (15 trades) | 2026: mean / stops (9 trades) |
|---|---:|---:|---:|
| Intrabar benchmark | +0.0702% / 20 | +1.0412% / 4 | +1.7240% / 1 |
| Every1 minute(s) | +0.0681% / 21 | +0.8269% / 5 | +1.3193% / 2 |
| Every5 minute(s) | +0.2586% / 19 | +1.1222% / 4 | +1.4312% / 2 |
| Every15 minute(s) | +0.3724% / 18 | +1.0849% / 4 | +1.3560% / 2 |

Primary1-minute effect:one target-to-stop conversion in EACH period. Across65
trades,25 benchmark stops become28 sampled stops,40 targets become37. No stop
becomes a target in this primary stressed comparison. No new/displaced admissions,
boundary marks or same-minute ambiguities occur. Every sampled stop fills beyond
its nominal2% quote-loss threshold. Worst net stopped loss across periods:
intrabar−2.3271%,1-minute−2.7864%,5-minute−2.9668%,15-minute−3.3014%. A nominal2%
trigger is not a2% realized loss cap when the price is only observed periodically.

All sampled-arm four-week95% mean intervals include zero. Primary intervals:
2022–24 −0.7325% to+0.7697%;2025 −0.3857% to+1.8653%;2026 −0.3295% to+2.4175%.
The point screen passes; independent edge, statistical equivalence, future
certainty and full production execution parity remain unestablished. These are
previously examined periods, not fresh holdouts. No deliberate slower-polling
rule should be inferred from higher averages in selected cells.

Coarser polling sometimes skips stops that later recover, and can capture prices
beyond the target. It can also miss target touches and close later at a loss.
The historical ETH winner entered2023-09-30 14:00 UTC exits at a sampled quote
2.7198 percentage points beyond its2.5% target (net+4.9922%). Such overshoot helps
offset other deterioration; it is not a guaranteed improvement in execution.
Both favorable and adverse overshoot are fully retained in the evidence.

Runtime finding clarified:sampled paper stops, as well as OHLC-resolved stops,
omit the extra adverse exit-slippage tick. This experiment deliberately retains
the original research charge on every exit in every arm to isolate sampling.
Reconciling that convention is the next separate comparison. Targets may be
requoted by the runtime; that extra request latency is not simulated.

Sampling uses observed minute OPEN quotes on fixed global UTC1/5/15-minute
grids, strictly after entry. Funding ends at the known sampled timestamp;
intrabar exits retain their conservative within-minute funding bound. The
15-second runtime waiting-loop constant cannot be reconstructed from minute
candles, and does not prove continuous coverage while workers/scans execute.
These scenarios are neither measured cloud delays nor guaranteed bounds on
actual15-second fills. No candles were interpolated and no missed touch was queued.

Protocol commit a058b599b4b7473260bf90466be231487c327c9a preceded outcomes, with10
exact file readbacks.47 tests passed. preflight_v1 exactly reproduced138 raw and
130 admitted benchmark cost rows. results_v1 is the single treatment run:
552 independent paths/cost rows,24 independent admissions,18 attribution checks;
independent reporting rebuilt592 rows and156 bootstrap intervals.520 trade rows
represent65 signals x4 exit models x2 costs. No failed treatment or retuning.

APPROVED PAPER strategy remains hourly_compression_btc_connors_loweff_v1,
BTC/ETH/SOL LONG+SHORT,1h,SL2%/TP2.5%,no timeout. Keep its existing settings.
Immediate entry with fill-origin brackets remains the research benchmark;
polling scenarios quantify a remaining execution sensitivity, not an approved
strategy replacement. Paper activation/health was not checked in this research run.

NEXT: reconcile the stop-exit cost convention on frozen paths, separately from
sampling or entry delay. Then return to winner/loser diagnostics under the
reconciled execution model before proposing new entry/risk filters. Actual
15-second reliability needs quote/cycle/worker timestamps;minute OHLC cannot
supply it. H-HOURLY-EXPANSION-01 remains frozen,with no new-token results opened.

Read hourly_exit_polling_20261008/FINDINGS.md and PROTOCOL.md in research PR99.
Newest cumulative archive:MAR_exit_polling_checkpoint_20261008.zip,restored over
MAR_hourly_compression_checkpoint_20261007.zip. It carries all earlier increments,
code,ledgers,attempt logs and the runtime snapshot;raw inputs remain separately
saved. Earlier status sections below are historical and do not override this one.

## Complete cost comparison

| Period | Poll minutes (0=intrabar) | Costs | Trades | Stops | Targets | Mean net | Four-week95% interval |
|---|---:|---|---:|---:|---:|---:|---|
| 2022–24 | 0 | Base | 41 | 18 | 23 | +0.3529% | -0.3315% to +0.9607% |
| 2022–24 | 0 | Doubled slippage | 41 | 20 | 21 | +0.0702% | -0.6258% to +0.6902% |
| 2025 | 0 | Base | 15 | 3 | 12 | +1.4097% | +0.3875% to +2.3048% |
| 2025 | 0 | Doubled slippage | 15 | 4 | 11 | +1.0412% | +0.1309% to +1.8958% |
| 2026 Jan–2 Oct | 0 | Base | 9 | 1 | 8 | +1.8015% | +0.0484% to +2.3103% |
| 2026 Jan–2 Oct | 0 | Doubled slippage | 9 | 1 | 8 | +1.7240% | -0.0125% to +2.2352% |
| 2022–24 | 1 | Base | 41 | 19 | 22 | +0.3819% | -0.4341% to +1.1085% |
| 2022–24 | 1 | Doubled slippage | 41 | 21 | 20 | +0.0681% | -0.7325% to +0.7697% |
| 2025 | 1 | Base | 15 | 3 | 12 | +1.4942% | +0.4558% to +2.3741% |
| 2025 | 1 | Doubled slippage | 15 | 5 | 10 | +0.8269% | -0.3857% to +1.8653% |
| 2026 Jan–2 Oct | 1 | Base | 9 | 1 | 8 | +1.8227% | +0.0528% to +2.3464% |
| 2026 Jan–2 Oct | 1 | Doubled slippage | 9 | 2 | 7 | +1.3193% | -0.3295% to +2.4175% |
| 2022–24 | 5 | Base | 41 | 18 | 23 | +0.4303% | -0.4216% to +1.1893% |
| 2022–24 | 5 | Doubled slippage | 41 | 19 | 22 | +0.2586% | -0.5791% to +1.0045% |
| 2025 | 5 | Base | 15 | 3 | 12 | +1.5569% | +0.4549% to +2.4964% |
| 2025 | 5 | Doubled slippage | 15 | 4 | 11 | +1.1222% | -0.2661% to +2.1478% |
| 2026 Jan–2 Oct | 5 | Base | 9 | 1 | 8 | +1.9805% | +0.1916% to +2.6042% |
| 2026 Jan–2 Oct | 5 | Doubled slippage | 9 | 2 | 7 | +1.4312% | -0.2041% to +2.4790% |
| 2022–24 | 15 | Base | 41 | 18 | 23 | +0.4321% | -0.4664% to +1.2389% |
| 2022–24 | 15 | Doubled slippage | 41 | 18 | 23 | +0.3724% | -0.4994% to +1.1575% |
| 2025 | 15 | Base | 15 | 3 | 12 | +1.5187% | +0.3352% to +2.5160% |
| 2025 | 15 | Doubled slippage | 15 | 4 | 11 | +1.0849% | -0.3982% to +2.2029% |
| 2026 Jan–2 Oct | 15 | Base | 9 | 2 | 7 | +1.4538% | -0.3066% to +2.5809% |
| 2026 Jan–2 Oct | 15 | Doubled slippage | 9 | 2 | 7 | +1.3560% | -0.3467% to +2.4597% |

## Primary paired mean differences

| Period | Difference (percentage points) | Four-week95% interval (percentage points) |
|---|---:|---|
| 2025 | -0.2143 | -0.9757 to +0.1461 |
| 2022–24 | -0.0021 | -0.3446 to +0.2445 |
| 2026 Jan–2 Oct | -0.4047 | -1.4651 to +0.2204 |

## Stopped-trade losses at doubled slippage

| Period | Poll minutes (0=intrabar) | Stops | Mean stopped net | Worst stopped net | Worst quote loss beyond2% (percentage points) |
|---|---:|---:|---:|---:|---:|
| 2025 | 0 | 4 | -2.2386% | -2.3195% | -0.0000 |
| 2022–24 | 0 | 20 | -2.2219% | -2.3271% | -0.0000 |
| 2026 Jan–2 Oct | 0 | 1 | -2.2686% | -2.2686% | 0.0000 |
| 2025 | 1 | 5 | -2.3038% | -2.4060% | 0.1005 |
| 2022–24 | 1 | 21 | -2.3070% | -2.7864% | 0.5090 |
| 2026 Jan–2 Oct | 1 | 2 | -2.3002% | -2.3235% | 0.0723 |
| 2025 | 5 | 4 | -2.4757% | -2.6500% | 0.4068 |
| 2022–24 | 5 | 19 | -2.4085% | -2.9668% | 0.6897 |
| 2026 Jan–2 Oct | 5 | 2 | -2.3571% | -2.4124% | 0.1612 |
| 2025 | 15 | 4 | -2.7105% | -3.1672% | 0.8006 |
| 2022–24 | 15 | 18 | -2.4746% | -3.3014% | 1.0248 |
| 2026 Jan–2 Oct | 15 | 2 | -2.4811% | -2.6603% | 0.4096 |

## Three missed primary target winners

| Original signal UTC | Token | Side | Intrabar exit UTC | Sampled exit UTC | Sampled net |
|---|---|---|---|---|---:|
| 2024-03-08 15:00:00+00:00 | BTCUSDT | LONG | 2024-03-08 15:31:00+00:00 | 2024-03-08 16:03:00+00:00 | -2.7864% |
| 2025-10-05 03:00:00+00:00 | SOLUSDT | LONG | 2025-10-05 08:01:00+00:00 | 2025-10-05 19:57:00+00:00 | -2.3348% |
| 2026-09-05 17:00:00+00:00 | ETHUSDT | LONG | 2026-09-07 02:39:00+00:00 | 2026-09-10 12:48:00+00:00 | -2.3235% |

All three are target-to-stop transitions:BTC LONG8 March2024,SOL LONG5 October2025,
ETH LONG5 September2026. The ETH target touch precedes its sampled stop by over
three days. This illustrates missed transient protection, without establishing
what15-second polls would have observed. No post-entry information was used to
change the entry rules or cancel trades.

Primary stressed token means:historicalBTC+0.5916%(15),ETH−0.4619%(17),
SOL+0.1967%(9);2025BTC+0.3656%(7),ETH+2.3949%(2),SOL+0.8426%(6);
2026BTC+0.8500%(3),ETH−2.3235%(1),SOL+2.3295%(5). No token exclusion is selected
from these small descriptive cells. Calendar years are not entry-time regimes.

The5/15-minute arms recover some benchmark stops but lose other target winners.
Risk tails worsen even where a mean improves. Do not tune polling to this path
history or infer that worker interruptions are desirable.

Data dictionary:poll_minutes0 denotes the intrabar comparator;1/5/15 denote
sample intervals,not entry delays. side1 LONG/−1 SHORT;stress1 base/2 doubled
slippage;returns/overshoot are fractions,UTC timestamps. All entry timestamps and
frozen feature values are unchanged. signal_i is the original identity.
Raw exit_bar is a minute start:sampled exits with fund_mode=open occur exactly
there;intrabar exits with fund_mode=bar lie within that minute;boundary marks
with fund_mode=close occur at minute end. The user-facing individual-trade export
adds explicit lower/upper exit timestamps and clock precision. No intra-minute
time is fabricated. Intrabar holding minutes are upper bounds;sampled holding
minutes are exact for the scenario.

stop_quote_overshoot=max(0,side*(stop_price−observed_exit_quote)/entry_fill),only
on stops;target_quote_overshoot=max(0,side*(quote−target_price)/entry_fill),only
on targets. These exclude fees,exit slippage and funding. Worst net stopped
returns include them. Nominal trigger percentages and realized net losses are
different quantities. Original benchmark targets fill at the target,not beyond it.

All69 raw signals are retained;65 admitted under each arm/cost. Matched-original
and full replay views coincide here because admission identities do not change.
Exit minute remains occupied in every arm;runtime exits-before-entries can differ.
Additive sums are attribution units,not compounded account returns. Circular
calendar-week bootstrap intervals retain zero-trade weeks and are descriptive
after repeated research. No independent holdout,multiplicity correction or
leverage qualification is implied.
