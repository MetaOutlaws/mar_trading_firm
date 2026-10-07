# Hourly RSI exhaustion exclusion: historical improvement, no consistent benefit

Completed 8 October 2026 Dubai (7 October UTC). The fixed RSI exclusion is
positive after stressed costs in both periods, but fails the required improvement
in BOTH periods. It improves historical 2022–24 and removes only a target winner
in reused 2025. Do not adopt the unconditional replacement or retune the cutoff.
Preserve its historical improvement as an observation, not a proven regime rule.
The owner-approved preferred paper variant remains BTC24 confirmation.

## One isolated question and prior work

Does avoiding an already extreme breakout improve entries? Retain LONG only
with own-token completed-hour RSI14<=70 and SHORT with RSI14>=30; equality
passes. No other RSI bound, crossover, direction alignment or setup-memory rule.
No BTC, ADX, extension or Connors filter. ORIGINAL hourly BTC/ETH/SOL control,
both sides, same 2% SL/2.5% TP, fees, fills, actual funding and occupancy.

The conventional levels are motivated by [Fidelity's RSI guide](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/RSI).
Its observation that RSI can stay extreme during trends supports the competing
hypothesis that this rule may exclude continuation winners. It is educational
context, not evidence of a crypto edge. All period results below are from our
saved data and code, not that reference.

RSI was already studied in the EMA-reclaim anatomy, exposed to learned models
and included in failed BTC4h combinations in PR96. No exact isolated hourly
compression exhaustion exclusion was found in inspected evidence. Those older
systems are not rerun or relabeled. External Grokbot runtime completeness is
unverified. See NOVELTY_AUDIT.md for the overlap and search limits.

Initial protocol 28c3da989a518dbf161c108893cbffbd2bb957d4 was corrected BEFORE
freezing/scoring at 0d86fcd168518e405d26835e2749b5537a3ea72c: source inspection
showed original discovery RSI already uses the same arithmetic seeds. The
correction fixed provenance wording and added an equality check, changing no
predicate or result. Independent RSI matches the original 143 signal values.
Exact seeds, zero-gain/loss conventions and entry timestamps are in PROTOCOL.md.

## Chronological full-basket comparison

| Period | Rule | Trades | Stops / rate | Targets | Win rate | Mean net base | Mean net stress | Stress PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022–24 | baseline | 97 | 44 (45.36%) | 53 | 54.64% | +0.2268% | +0.1037% | 1.098 |
| 2022–24 | rsi14_not_exhausted | 69 | 29 (42.03%) | 40 | 57.97% | +0.3727% | +0.2445% | 1.247 |
| 2025 | baseline | 36 | 14 (38.89%) | 22 | 61.11% | +0.4992% | +0.3685% | 1.400 |
| 2025 | rsi14_not_exhausted | 35 | 14 (40.00%) | 21 | 60.00% | +0.4480% | +0.3164% | 1.334 |

All trades close at stops or targets; no terminal marks. All stops lose and
targets win after costs. Stress doubles slippage without changing paths or
counts. Net returns include fees, slippage and funding, so they differ from
quoted barriers. Point screen: positive stressed mean both periods PASS;
improvement both periods FAIL; nonempty both PASS. No independent qualification.

## Stops avoided, winners sacrificed and occupancy

Historical baseline has 97 trades. RSI directly excludes 29: **16 stop-outs and
13 target winners**. Shared 68 trades retain identical paths/costs. Freed
occupancy admits one extra ETH SHORT on 2023-09-15 at 12:00 UTC; it hits its stop.
Thus actual RSI totals are 69 trades, 29 stops and 40 targets. There are no eligible
baseline trades displaced by changed occupancy. Direct 16 avoided stops become
a net reduction of 15 actual stops after including the new loss.

The excluded historical trades average -0.3147% stressed. Removing their
-0.091252 additive return units and adding the new -0.023206 stop improves total
additive return by 0.068046 units. The shared 68 average +0.2822% stressed, falling
to +0.2445% with the new loser. Additive units are not funded account returns.

In 2025 the rule excludes just ONE original admission: BTC SHORT at
2025-03-09 11:00 UTC, completed-hour RSI 28.4743. That trade reaches its target
and earns +2.1929% after stressed costs. **Zero stops avoided, one target winner
lost**, no new or displaced admissions. Stop count stays 14; stop rate increases
38.89% to 40.00%, and win rate falls 61.11% to 60.00%. ETH/SOL admissions are
unchanged. Total additive return decreases by 0.021929 units.

Before occupancy, 143 raw opportunities comprise 104 historical and 39 evaluation.
The filter retains 73 historical and 37 evaluation. Raw historical exclusions
are 16 stops/15 targets; raw evaluation exclusions are 0 stops/2 targets.
Raw opportunities can overlap and are not an executed portfolio. Both raw and
admitted scopes are saved explicitly to avoid mixing those counts.

## Tokens, years and uncertainty

| Period | Token | Baseline trades / stops | RSI trades / stops | Baseline stress mean | RSI stress mean |
| --- | --- | --- | --- | --- | --- |
| historical | BTCUSDT | 39 / 16 | 25 / 9 | +0.3442% | +0.5760% |
| historical | ETHUSDT | 36 / 20 | 25 / 13 | -0.3040% | -0.1466% |
| historical | SOLUSDT | 22 / 8 | 19 / 7 | +0.3446% | +0.3227% |
| evaluation | BTCUSDT | 17 / 7 | 16 / 7 | +0.3247% | +0.2080% |
| evaluation | ETHUSDT | 8 / 3 | 8 / 3 | +0.4909% | +0.4909% |
| evaluation | SOLUSDT | 11 / 4 | 11 / 4 | +0.3472% | +0.3472% |

Historical benefit is concentrated in BTC and ETH; ETH remains negative.
Historical SOL slightly worsens. Filtered 2022 stressed mean +0.8114% and 2024
+0.3279% improve their baselines, but 2023 worsens from -0.4624% to -0.4942%.
The 2022–24 aggregate must not be described as improvement in every year/token.
In 2025 only BTC changes, worsening; ETH and SOL are identical to baseline.

| Period | Rule | Stress mean | 95% four-week block interval |
| --- | --- | --- | --- |
| historical | baseline | +0.1037% | [-0.3772%, +0.5817%] |
| evaluation | baseline | +0.3685% | [-0.2725%, +1.0038%] |
| historical | rsi14_not_exhausted | +0.2445% | [-0.2806%, +0.7268%] |
| evaluation | rsi14_not_exhausted | +0.3164% | [-0.3094%, +0.9545%] |

| Period | Stressed mean difference (pp) | 95% four-week difference interval (pp) |
| --- | --- | --- |
| evaluation | -0.0521 | [-0.1609, +0.0000] |
| historical | +0.1407 | [-0.1835, +0.4409] |

Absolute intervals span zero in both periods. Historical difference spans zero;
the 2025 difference interval is nonpositive and touches zero because some
calendar resamples omit the single excluded winner. It supplies no evidence of
improvement. Both one-week and four-week versions use 10,000 valid shared-calendar
draws, including empty calendar weeks. The 2025 result has 35 entries; the filter's
difference depends on just one observation. Repeated inspection of 2025 prevents
calling it untouched out-of-sample confirmation. Reserved 2026 stays unscored.

The RSI exclusion affects 29/97 original historical admissions but only 1/36 in
2025. That is a difference in observed signal composition, not proof that 2025
was choppy or that a calendar-dependent switch would be profitable. No causal
regime was tested. Preserve both the historical improvement and later failure.

## Verification, files and decision

15 focused synthetic tests passed before scoring. Independent raw-minute close
aggregation and scalar RSI matched all143 contexts and original RSI features;
143 raw barrier checks and eight chronological admission checks passed. Baseline
286 raw/266 admitted cost rows reconcile exactly, and shared executions match.
All 152 report rows reconcile. Frozen 92 sources, 9 feature files, 6 raw inputs,
4 baseline references and 19 output hashes verified. One successful run results_v1.

The ordinary CSV has 474 scenario rows: 133 baseline plus 104 RSI admissions,
each under two cost assumptions. Overlapping arms are not 474 independent trades.
Excluded CSV has 30 original admissions under two costs, 60 rows. Returns are
fractions (0.005=0.5%); side 1 LONG/-1 SHORT; stress 1 base/2 doubled slippage.
filter_rsi14 is causal entry context; exit/path columns are outcomes. Legacy
entry_rsi14 is preserved and equals the recomputed value to checked tolerance.

Close this unconditional RSI exclusion as unsuccessful under its predeclared
screen. Label it HISTORICAL IMPROVEMENT (2022–24), REGIME EXPLANATION UNVALIDATED.
No post-result cutoff, token selection, side selection or filter stacking.
BTC confirmation remains the owner-approved preferred PAPER variant; its cloud
activation is still PENDING / NOT VERIFIED. This study changes no runtime,
approval book, positions, trading mode or leverage.

Next: audit and preregister one independent Connors RSI predicate against the
ORIGINAL hourly baseline. Its exact rule is not yet frozen/scored. Then review
H-EXT-REGIME-01 and whether a separately motivated common-state comparison can
explain retained historical observations; do not infer that explanation now.
Broader-token and prospective confirmation remain necessary for independent
evidence. No background study is running.
