# Distinct entry discovery and reverse engineering: frozen protocol

6 October 2026. Brian requests new sources of entry edge through research and/or
reverse engineering. This study supersedes profit protection as the immediate
priority. No result or strategy approval is assumed.

## Scope, chronology and attempt budget

Verified original BTCUSDT/ETHUSDT/SOLUSDT minute candles and funding. Entry clocks
5m, 15m and 60m; long/short separately. Features use complete candles only; fills
use the next minute open. No 2026 data is used for feature fitting or selection.

Development: 2022–23. Selection: 2024. Reused historical evaluation: 2025.
All these years have been viewed in other experiments; none is claimed to be
globally untouched. Refit no feature threshold or model after 2023.

Four fixed event rules plus one learned-rule family. Two controls: every eligible
clock entry and the original reconstructed zone signals. 7 families x 18
token/clock/direction groups x 2 SL/TP arms =252 configurations; 3 periods x
2 cost levels =1,512 result rows, including empty cells. Only the 180 new-family
configurations enter candidate selection. Every result remains visible.

At most three configurations may reach 2026-01-01 through 2026-10-02 inclusive,
and only under the frozen progression below. If none qualifies, do not score
2026. No threshold grid, extra family or winner-based rescue after scoring.

## Common execution lens

Arms: 2% stop / 2.5% target (primary), 3% / 3% (secondary). Stops and targets are
quote-based, as in the existing engine. Fixed SL/TP only; no compulsory 4h-regime
exit and no maximum holding period. The 4h regime remains an available feature.
All families and controls use identical exits. This differs from prior regime-
exit studies; do not attribute differences versus them to entry changes alone.

One position per configuration. No pyramiding; enter only after the prior exit
minute. Same-bar stop wins; adverse gap stops; no favourable target-gap fill;
funding and fees from the unchanged offline engine. Base slippage 0.05% per
side BTC/ETH, 0.10% SOL; double-slippage stress, fee 0.055% each side. Period-end
marks retained; no unknown future exits enter model training. No leverage.

## Fixed features

Entry-clock ATR14 (Wilder), RSI14, true range, prior 20-bar median volume,
close location and signed candle body; completed-hour ATR14; past 1h/4h/24h/7d
returns; BTC 24h return and token-minus-BTC 24h return; 24h path efficiency
(absolute net change divided by summed absolute hourly changes); 4h EMA50/200
direction with three-bar EMA50 slope. Indicators may warm up on prior history.

Funding is the last SETTLED rate, available only from settlement plus one minute.
Use the preceding 90 calendar days, excluding that settlement, for 5th/95th
percentiles; require at least 30 previous rates. Never use a current predicted
rate or later settlement. Record settlement as-of time. No symbol ID, year,
future excursion, exit or winner label is an entry feature.
All new families and the clock control use clocks with finite model features;
an uninitialized 4h regime is missing, not classified as chop. Original zone
signals remain intact as their separate control.

## Four fixed entries (short rules mirror long)

1. Trend-pullback resumption: signed seven-day return >0. During the previous
   six entry-clock bars, signed completed-hour one-hour return / hourly ATR%
   reached <=-1.5. Current candle closes above the preceding candle's high and
   above its own open. No entry on the same bar that first establishes the shock.

2. Volume-shock reversal: a bearish entry-clock candle has body >=2 times the
   preceding entry-clock ATR14, volume >=2 times preceding 20-bar median volume,
   and closes in the bottom quartile of its range. Freeze its midpoint and low.
   Within the NEXT three candles, enter when a bullish close crosses above that
   midpoint. Cancel first if a close falls below the shock low; third bar can
   confirm, otherwise expire. One pending setup per direction, independent of
   open positions; release candle cannot start another setup. Reset at partitions.

3. Funding-crowding breakout: last settled funding <=-0.0001 and <= its prior
   90-day 5th percentile; positive 24h price return; bullish close breaks the
   previous six hours of entry-clock highs. Require the preceding close not
   already beyond its own preceding-six-hour high. At most the first qualifying
   signal per direction per observed settlement. For shorts use positive funding
   >=0.0001 and >=95th percentile, negative price return and downside breakout.
   Funding age must be <=12 hours; no assumption that funding proves liquidation.

4. Compression expansion: mean true range of the previous six entry-clock bars
   <=0.7 times the median true range of the previous 60 bars. Current true range
   >=1.5 times preceding ATR14, volume >=1.5 times preceding 20-bar median volume,
   close breaks the prior 20-bar high, closes in the top quartile and is bullish;
   signed 24h return >=0. No EMA gate or retest/deadline fallback.

## Reverse-engineered fifth family

Fit exactly one pooled DecisionTreeRegressor per clock on both directions and
all three tokens, using 2022–23 eligible opportunities under the primary arm at
doubled slippage. Label = realized net R; omit period-boundary marks and entries
in the last seven days of 2023. No fixed time exit is added by this label purge.
Each token/direction/UTC-entry-day has equal total sample weight. This balances
sampling but does not make overlapping labels independent.

Depth 2, minimum 1,000 observations per leaf, squared-error criterion, seed
20261006; all other defaults recorded. No model or hyperparameter contest.
Inputs: signed 1h/ATRh, 4h, 24h and 7d returns; hourly ATR%; signed BTC24h and
token-minus-BTC24h; direction-adjusted centered RSI14; volume ratio; signed close
location; signed candle-body/ATR; unsigned 24h path efficiency; signed funding;
alignment with the 4h regime. Finite-feature rows only.

Expose all at-most-four leaves per clock. Eligible leaves need >=90 distinct
entry days and >=20 distinct weeks in EACH training year. Select one leaf by
highest minimum annual weighted mean stressed R (tie: pooled weighted mean R, then smaller leaf
ID). Keep the selection even if its training mean is negative and label it as
such; it cannot pass the later positive-return screen. If no leaf meets support,
the learned family produces no entries for that clock. Save conditions, model,
training labels, leaf summaries and frozen selection before 2024/2025 scoring.
Apply the frozen leaf at every later completed eligible candle; occupancy decides
whether it trades. No feature threshold is changed by later performance.

## Selection and confirmation

Using only development and 2024, candidates need >=20 completed trades in EACH
of 2022, 2023 and 2024; positive mean net under both costs in each year; pooled
development PF>=1.10 and 2024 PF>=1.10; and 2024 mean net above the same-clock/
token/direction/arm clock control. This is research triage, not sufficient proof.
Rank by minimum annual stressed mean R, then completed count, then stable ID.
Take at most one per family, at most three total. Save finalists before 2025.

2025 qualification: >=30 completed trades, PF>=1.10, positive base and stressed
mean, and mean above the matching clock control. No post-2025 substitute when a
finalist fails. Report positive non-finalists as exploratory exceptions only.

Only qualifying frozen finalists may be evaluated on the reserved 2026 period,
using the identical model/rules. Report one-/four-week calendar-block mean
intervals, 10,000 draws and Bonferroni 95% intervals covering at most three
finalists. A stronger research candidate needs >=30 completed reserved trades,
positive base/stress mean and positive simultaneous lower bounds under both
block lengths. These remain simulated results, not deployment or profit promises.
Historical source papers and other firm activity may have seen 2026; explicitly
state that limited independence. Preserve any unscored reserved period.

## Evidence and checks

Per-token/clock/direction/arm/period tables: counts, stops and stop rate, targets,
win rate, mean net/R, PF, cost components, average win/loss, duration and additive
closed-trade drawdown. Save chronological ledgers, every signal, causal features,
training opportunity outcomes and all leaves. Do not present overlapping research
configurations as an account return or independently add their trade counts.

Tests: shock confirmation/cancellation/expiry and side symmetry, settled funding
availability, future-prefix independence, frozen tree conditions, and unchanged
execution controls. Verify original six input hashes. Freeze source before
outcomes. Preserve failures. Publish written reports/aggregate tables to GitHub;
retain full code/evidence privately with a verified restoration checkpoint.
No cloud/worker/approved-strategy change.
