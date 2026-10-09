# Entry discovery: completed findings — 6 October 2026

The strongest new research lead is **compression followed by a directional,
volume-backed expansion**. It produced several positive historical cells, but
**no configuration passed the frozen selection screen**. This is a lead for
replication, not a demonstrated tradable edge. No strategy was promoted.

## What changed and what was tested

We researched primary studies of momentum, reversal, liquidity and perpetual
funding; see RESEARCH.md for sources and limits. Four distinct event entries and
one learned rule replaced the previous cycle of small zone/retest variations.
The hypotheses were fixed before scoring, in commits ebcfe4e and 087a942.

BTC, ETH and SOL; **5m, 15m and 1h entries, both long and short**. Two arms:
2% stop/2.5% target and 3% stop/3% target. 180 new configurations plus 72 controls;
1,512 period/cost rows. Development 2022–23; selection 2024; reused historical
evaluation 2025. **2026 was not scored** because no pre-2025 finalist qualified.

All entries use completed information and the next minute open. Within each
configuration only one position can be open. Exits are stop/target only, without
the previous compulsory 4h-regime exit; both controls use these same exits.
The 4h regime is context. Consequently, differences from older regime-exit
studies cannot be attributed only to entry. No maximum holding period or leverage.
At period boundaries, open positions are marked and explicitly counted.

Fees are 0.055% each side; normal slippage 0.05% each side BTC/ETH and 0.10% SOL.
Stress doubles slippage. Funding is included. Stops/targets remain quote-based,
so a stopped trade loses more than its nominal stop after execution costs.
This is a candle replay, without actual queue position, liquidity capacity,
exchange mark-price triggers or liquidation modelling.

## The useful lead, including the small sample problem

Long entry: the previous six bars have mean true range no greater than 70% of
the previous 60-bar median; the current bar expands to at least 1.5 prior ATR,
has at least 1.5 times prior 20-bar median volume, and closes bullish in the top
quarter of its range above the preceding 20-bar high. Its trailing 24h return
must be nonnegative. Enter next minute. Short rules mirror this.

Thirteen of 180 new configurations had positive mean net in all three historical
partitions at normal costs; eight were compression entries. Six remained positive
in all three partitions at doubled slippage; five were compression entries.
This counts related configurations, not independent discoveries. Pooled 2022–23
profitability also does not imply profitability in each individual year.

Examples below are **descriptive, selected after reviewing all historical cells**.
They are not frozen finalists or a ranked list for deployment. Returns are mean
net return per simulated trade; parenthesized counts are completed trades.

| Compression entry | SL / TP | 2022–23 | 2024 | 2025 | 2025 doubled slippage | 2025 stopped |
|---|---|---:|---:|---:|---:|---:|
| SOL 60m long | 2% / 2.5% | +2.186% (5) | +0.371% (10) | +0.894% (7) | +0.692% | 2/7 (28.6%) |
| ETH 15m short | 2% / 2.5% | +0.404% (26) | +0.257% (11) | +0.615% (8) | +0.516% | 3/8 (37.5%) |
| BTC 60m short | 3% / 3% | +0.661% (14) | +0.926% (6) | +1.346% (4) | +1.247% | 1/4 (25.0%) |

SOL 1h long, 2%/2.5%, was positive in each of 2022, 2023, 2024 and 2025 even at
doubled slippage. However, its annual sample was **4, 1, 10 and 7 trades**.
One winning observation in 2023 does not establish a repeatable edge. The same
SOL entry with 3%/3% fell to **-0.099%** per trade in 2025 under stressed slippage,
versus **+0.692%** with 2%/2.5%; wider stops were not automatically better.
These are coupled stop/target arms, so this does not isolate the stop's effect.

The two SOL arms were the only configurations positive in EACH pre-2025 year
at both cost levels. Both failed the required 20 completed trades per year.
They also received a false PF flag because development had no losses and the
engine stores PF as undefined, not infinity. That reporting convention is
conservative; treating those all-win PFs as infinite would still leave zero
finalists because the count screen independently fails. No result was rescued.

## All entry families, including failures

These are trade-weighted descriptions across token/clock/direction configurations,
not a portfolio. Trades overlap across configurations and cannot be treated as
independent observations or added into an account return. Full cells are in
contrasts.csv; it includes normal/stressed costs, stop counts, boundary marks,
and differences from each matching control. Controls are unpaired and need not
have the same dates or occupancy. Those differences do not establish causation.

2025, normal costs:

| Entry family | 2% SL / 2.5% TP: mean net; stops / closed | 3% SL / 3% TP: mean net; stops / closed |
|---|---:|---:|
| Compression expansion | -0.095%; 139/266 stops (52.3%) | -0.373%; 132/253 stops (52.2%) |
| Funding-crowding breakout | -0.404%; 291/493 stops (59.0%) | -0.321%; 230/449 stops (51.2%) |
| Trend-pullback resumption | -0.140%; 388/729 stops (53.2%) | -0.082%; 301/638 stops (47.2%) |
| Volume-shock reversal | -0.278%; 567/1004 stops (56.5%) | -0.299%; 458/897 stops (51.1%) |
| Learned two-condition rule | -0.159%; 3710/6930 stops (53.5%) | -0.123%; 2088/4360 stops (47.9%) |
| Every eligible clock | -0.259%; 8822/15885 stops (55.5%) | -0.260%; 4632/9264 stops (50.0%) |
| Legacy zone control | -0.407%; 1340/2274 stops (58.9%) | -0.381%; 849/1629 stops (52.1%) |

Every pooled family remained negative. Compression's positive exceptions justify
replication of the precise event, not a claim that all compression trades work.
Funding exceptions were sparse; one stressed survivor had only one trade in
2024 and one in 2025. Trend pullbacks had some encouraging 2025 cells but failed
earlier periods. Volume-shock reversal did not show a robust net edge.

## What reverse engineering found

Three shallow decision trees examined **1,688,248 overlapping training
opportunities**, including winners and losers, using only 2022–23 outcomes.
Fourteen entry-time inputs covered RSI, volume, volatility, returns, relative
strength, candle shape, path efficiency, settled funding and 4h-regime alignment.
This is a large opportunity table, not 1.69 million independent trades.

The chosen region was almost identical across clocks: avoid a signed seven-day
return worse than roughly -4.1% to -4.2%, and require signed settled funding no
higher than roughly 0.16825 basis points. The best minimum annual training mean
was still about **-0.125 R** after stressed costs. These are least-bad regions,
not profitable entry rules. RSI was available but was not chosen by these small
trees; this does not prove RSI is useless. ADX and Connors RSI were not included
in this experiment and must not be claimed as tested here. All leaves and exact
conditions are saved, including negative ones.

## Next research priority

1. Replicate the frozen compression event across a broader, point-in-time liquid
   perpetual universe. Fix eligibility using only past turnover/listing age;
   retain delisted tokens and explicitly report unavailable history. Do not
   select today's winners or loosen thresholds to manufacture sample size.
   Pre-register a pooled family test and reserve future data before opening it;
   token/direction subgroups are exploratory until independently replicated.
2. Gather historical open interest, liquidations and spread/depth or trade-flow
   data. A separate liquidation-exhaustion hypothesis should require aggressive
   flow, falling OI and a confirmed price reclaim; ordinary candle volume alone
   cannot establish forced liquidation. Freeze any such rule only after checking
   timestamp availability and completeness. Matched spot/perpetual basis is a
   separate market-neutral research path, with its own costs and execution risks.
3. Use forward paper observations for any frozen candidate, recording rejected
   setups as well as trades. Do not tune on each new loss. Only then investigate
   stop/target changes against the same entry set and execution constraints.

The cache presently covers three tokens, not the requested expanded universe.
That replication/data collection has not run and nothing is running in the
background. Profit protection is deferred by the user's change of priority.
No cloud, approval-book, worker, order or production setting was changed.

## Reproduction and evidence

PROTOCOL.md is the frozen specification. results_v1/manifest.json pins five
source files, six original data hashes and every frozen output. REPORT_VERIFICATION.json
records ledger/summary/occupancy checks, annual checks and training date checks.
Four focused tests passed: prefix causality, tree/execution consistency, settled
funding availability and shock confirmation/cancellation/expiry/side symmetry.
Detailed private evidence includes causal feature tables, training labels,
all model leaves, all signals, ledgers and annual results. Public GitHub contains
the protocol, rationale, findings and aggregate tables only.

Reproduce after restoring the checkpoint and the separately preserved data ZIP:

```bash
python research/isolated_token_study_20261003/entry_discovery_20261006/run_discovery.py --cache data_cache --reconstructed research/isolated_token_study_20261003/entry_quality_audit_20261006/reconstruction_v1 --out rerun_entry_discovery
```

Python 3.12.14, numpy 2.3.5, pandas 2.2.3, pyarrow 25.0.1 and scikit-learn 1.8.0
were used. The report builder reads frozen results_v1 and never changes scoring.
2025 is reused research history, and the positive cells above were highlighted
after reviewing it. 2026 is unscored within this experiment, not globally unseen.
