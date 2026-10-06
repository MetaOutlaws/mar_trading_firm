# Next test design: top-down structure and pullback location

5 October 2026. DESIGN ONLY, NOT RUN. The current experiment has superseded this broad proposal with one incremental daily-trend test and non-blocking zones; see ../incremental_context_20261005/PROTOCOL.md and FINDINGS.md. Prepared from Brian's questions and the archived negative results. This document is a reviewable proposal; it does not claim a new profitable setup or amend completed studies. Grokbot review can occur when Brian requests it. No message or job has been sent to Grokbot.

## Questions

1. Does confirmed 4h structure improve the existing EMA regime entry?
2. Does adding daily alignment help or merely remove trades?
3. Does buying a pullback near known support, or shorting a rally near known resistance, improve returns relative to EMA reclaim alone?
4. Does a rejection or break/retest trigger improve those entries?
5. Which effects persist independently for each token, direction and entry timeframe?

We cannot know a true bottom/top at entry. Test observable pullback location and subsequent confirmation, and record confirmation delay and distance traveled before entry. Never label a historical extremum as tradable before its confirmation.

## Fixed reporting cells and budget

BTC/ETH/SOL × long/short × 5m/15m/1h = 18 separate cells. No direction or timeframe is dropped by a global top-two selector. All cells remain visible, including zero-trade and losing cells.

Six variants per cell = 108 configurations, with the same risk/exit shell. Base and doubled-slippage cost scenarios are not extra signal configurations. Report 2022–2024 and 2025 separately: 432 configuration/period/cost rows, with annual-entry attribution tables. These periods have already been reused; all historical findings remain exploratory. No 2026 outcomes or prospective data are opened as part of this design.

| Variant | Entry permissions and trigger | Main comparison |
|---|---|---|
| T0 | Original completed 4h EMA50/200 regime + lower-timeframe EMA20 reclaim | Reconcile archived reference |
| T1 | T0 + confirmed 4h directional structure | T1 vs T0: structure filter |
| T2 | T1 + daily alignment | T2 vs T1: daily filter |
| T3 | T2 + pullback/rally location near known hourly support/resistance | T3 vs T2: location filter |
| T4 | T3 context/location, replace EMA reclaim with support/resistance rejection | T4 vs T3: rejection trigger |
| T5 | T3 context/location, replace EMA reclaim with break-and-retest trigger | T5 vs T3: retest trigger |

T1–T3 are subsets of original opportunities: report paired accepted/rejected comparisons and separately chronological one-position results. T4/T5 generate different opportunities: do not describe their difference as a pure causal filter effect. The conclusions apply to this sequence of definitions; a factorial interaction claim is not justified.

## Proposed definitions to freeze before running

All timestamps UTC. One-minute bars aggregated with explicit close timestamps. Use only completed daily, 4h, hourly and entry bars; enter on the next available minute open after the entry bar closes. Warm-up bars may precede the scoring interval. No forward-filled incomplete higher-timeframe bar.

**Base regime:** long when completed 4h close > EMA200, EMA50 > EMA200 and EMA50 > its value three completed 4h bars earlier. Short reverses these inequalities. Otherwise neutral.

**4h structure:** strict swing high/low requires two bars on each side; available only after the second confirmation bar closes. Last two confirmed highs AND lows rise for long, fall for short. No entry while ambiguous. Invalidate the current long structural permission on a completed 4h close below the latest confirmed swing low, or short permission above its latest swing high, until newly confirmed structure restores direction. Log that this immediate close-break rule differs from PR97's pivot-only state.

**Daily alignment:** completed daily close above EMA50 with EMA50 rising over three completed days for long, reversed for short. Daily confirmed structure uses the same two-bar pivot convention, with both latest highs and lows rising/falling. Require both daily trend and structure to agree with the 4h direction. Neutral/conflicting states block entry. This strict daily rule could starve the sample; that is an outcome to report, not a reason to relax it mid-run.

**Location (T3–T5):** at setup activation, freeze the range high/low from the 20 fully completed 4h bars preceding activation. Position = (setup close − range low)/(range high − range low). Long position must be within [0, 0.35]; short within [0.65, 1]. Zero-width ranges are invalid. The relevant known hourly support/resistance is a strict pivot confirmed by two hourly bars. Keep pivots no older than 30 days, invalidate support after an hourly close below pivot − 0.25 ATR14 and resistance after a close above pivot + 0.25 ATR14. ATR uses the simple mean of 14 true ranges, known at setup. Zone width is frozen at confirmation. Select the closest valid support below/around price for a long and resistance above/around price for a short, with distance to its band <= 0.5 completed-hour ATR14; ties choose the most recently confirmed. Log all component passes separately. This is a candle-derived support/resistance proxy, not observed supply/demand liquidity.

For T3/T4 setup activation is the just-completed entry bar. Freeze its range/zone before constructing the order. For T5 activation is the break close described below; freeze the range and flipped level then. Recheck daily/4h permissions at the eventual trigger. Do not require a later retest to be near a newly selected level or recalculate a more favorable range after the setup.

**T3 EMA trigger:** same EMA20 reclaim as T0, with location permission.

**T4 rejection:** the completed entry candle overlaps the pre-existing hourly support band, closes above the band and above its open for a long. Short mirrors at resistance. A zone first confirmed at that candle close cannot count as pre-existing for that candle; it must have been known at candle open. One entry per zone until a new hourly zone forms or the existing zone is invalidated. Rejection is not a claim of an absolute market bottom/top.

**T5 break/retest:** long: an entry candle closes above a pre-existing hourly resistance band's upper edge by at least 0.1 hourly ATR; that level becomes candidate support. Short mirrors a support break. Apply the frozen range-location rule at break close; use the flipped band for the proximity condition. Only a subsequent entry candle may retest (not the break candle), within the next six completed entry bars. It must overlap the band and close back beyond the breakout edge in the trade direction with a directional body. Invalidate on a close through the opposite edge or loss of higher-timeframe permission. Enter once per breakout. Six bars is a setup expiry, never a position holding cap. Breakouts too far from pullback location are recorded as blocked; do not loosen location to create trades.

**Common risk/exit shell:** fixed 1% quote stop, 2.5% quote target and original deterministic 4h EMA-regime exit for every variant. This deliberately preserves T0 comparability; structural stops, trailing stops and AI-managed exits are separate hypotheses. No fixed holding period. Use historical funding, original fees/slippage, pessimistic stop-first same-minute ambiguity and documented gap treatment. Start each historical partition flat; mark still-open positions at its boundary with liquidation costs and flag them. One position per token/side/timeframe/variant, no pyramiding. These separate research sleeves do not constitute a jointly tradable portfolio.

For T3–T5, log stop distance relative to ATR and selected support/resistance, opposing-zone distance and available reward/risk; initially do NOT block every target crossed by any opposing zone. PR97's severe sample attrition makes that a separate diagnostic. This does not claim target room is irrelevant.

## Reporting and decision rules

Publish a table for every token × side × timeframe × year × variant, with total/closed/boundary counts, opportunity retention, gross/net expectancy, win rate, conventional PF, net R, fees/slippage/funding, stop/target/regime exit counts, holding-duration distribution, and minute-close mark-to-market drawdown. Show base and stressed costs. Never pool sides or average overlapping configurations into an apparent portfolio return.

Entry audit: higher-timeframe closes and values, confirmation timestamps, directional states, range anchors/position, zone ID/bounds/age, trigger type, spread assumption, distance from known swing at entry, and reason for each rejection. Give stage-by-stage and intersecting rejection counts to identify whether daily context, location or triggers remove most opportunities.

Training/pre-evaluation period is 2022–2024; 2025 is the reused chronological evaluation period. Annual breakdowns do not create fresh holdouts. Keep all 108 results, but rank any candidate for later confirmation using training information alone. Minimum exploratory screen: >=50 completed trades in each period, positive net expectancy in both, PF >=1.15 in both, and positive doubled-slippage expectancy in both. Insufficient counts mean inconclusive, not successful. Do not alter thresholds after viewing returns. Report weekly-block uncertainty and the limitations of correlated tests and prior historical reuse; do not claim that an unadjusted interval corrects the whole search history.

Only after the comparison is complete consider a separately registered stop/target study on a limited number of training-selected cells. Keep long and short selection independent; either can remain inactive. A prospective evaluation or deliberately reserved period is required before promotion. No deployment is implied by historical screening.

## Verification before execution

- Reconcile T0 to existing 18 reference configurations in both historical partitions.
- Perturb future daily/4h/hourly/entry candles: earlier decisions must not change.
- Test pivot confirmation delays, structure invalidation, daily rollover, stale/invalid zones, neutral states, mirrored long/short logic, trigger timing, setup expiry and no-trade handling.
- Verify no same-bar retrospective pivot or break/retest entries; account for the next-open gap.
- Freeze protocol, code version, input hashes and run budget before computing outcomes.
- Retain every row and error. Stop at the declared budget.

Implementation and results are pending. No claim is made that these proposed definitions will improve profitability.
