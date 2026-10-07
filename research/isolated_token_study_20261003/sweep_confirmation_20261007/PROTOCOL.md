# Previous-day sweep: one-candle confirmation experiment

Pre-scoring protocol, 7 October 2026. Read NOVELTY_AUDIT.md first.
Research-only variant of an existing family; one comparison, zero fitted parameters.

## Hypothesis
After a previous-day extreme is swept and reclaimed, a close beyond the reclaim
candle's opposite extreme on the immediately next candle may reject false
reversals sufficiently to offset missed winners and a later, potentially worse fill.

## Fixed entries and comparator
BTCUSDT, ETHUSDT, SOLUSDT; 15-minute completed candles; LONG and SHORT pooled.
Define the setup's UTC day from its candle OPEN, not its close label. Use the
raw high/low of the preceding completed UTC calendar day, never the forming day.
Both arms use the FIRST strict reclaim per token/day/side (calendar deduplication
inherited from the old family; no retry after failed confirmation). Deduplication
happens before occupancy or outcomes. No minimum sweep depth or ATR tolerance.
LONG: low < prior-day low, close > prior-day low, close <= prior-day high.
SHORT: high > prior-day high, close < prior-day high, close >= prior-day low.

Control immediate: enter at the minute open immediately after setup completion.
Treatment confirmed: ONLY the immediately following 15m candle may confirm:
LONG close > setup high; SHORT close < setup low. Enter at the following minute
open. Equality fails. No intrabar confirmation, extra wait, body-colour requirement,
additional sweep-extreme invalidation, or later retry. A midnight confirmation
keeps its parent setup's fixed levels. Two-sided signals follow existing
opposing-simultaneous rejection; each arm replays its actual entry times.
Require setup open and both potential entry times inside the same partition,
independent of whether confirmation succeeds; no cross-partition parents.
Document every first setup, including failed confirmations and membership rejects.

## Fixed exits, costs, admission
SL2%, TP2.5%, no timeout; brackets anchored on quoted entry open exactly as
the current isolated-study execution contract. Conservative stop-first minute
ties, worse opening-gap stop, no improved target gap fill. Terminal positions
marked at final pre-boundary close, labelled boundary_mtm, excluded from closed
win/stop denominators. Quote brackets stay fixed under slippage stress.
Fees0.055% per fill; base slippage0.05% BTC/ETH and0.10% SOL per side, stress
doubles slippage. Actual funding with existing conservative minute convention.
No leverage, margin, maker assumption or account-return interpretation.

Use unchanged monthly eligibility/rank from the three-token membership audit:
90 observed days and prior30-day median daily turnover >=10m; no outcome filter.
One position/token across sides, six basket/three direction slots, same-exit-minute
reentry blocked. Replay each arm separately; raw overlapping paths are diagnostics.

## Data and diagnostics
Verify six original raw hashes, existing frozen features and membership hash.
Historical2022–24 and reused evaluation2025, reset flat between them; also report
individual entry years, tokens and directions without selecting a winning cell.
No 2026 candle used in entries/exits/features or scored returns. Funding at the
boundary retained only for existing conservative last-minute convention.
Use complete15m features with asof <= entry. No feature-eligibility gate:
only defined levels, complete candles and fixed monthly membership gate entries.
Record entry-time 15mRSI14, volume ratio against prior20 median, ADX14 and hourly
24h/168h returns, plus setup/confirmation geometry. ADX14 uses causal Wilder-style
ewm(alpha=1/14,adjust=False,min_periods=14) on TR,+DM,-DM then DX, seed convention
explicit; zero directional sum gives DX0. Indicators are descriptive, not filters.
Report winners and losers including stop trades; never choose thresholds here.

## Comparison and decision
Exactly two pooled arms, both cost scenarios and both partitions; no SL/TP,
timeframe, token or indicator search. Compare chronological count, actual stop
hits/rate, targets, boundary marks, net win rate, mean net, PF, initial-risk R,
holding time, additive return sum and annual/token/side detail. Weekly and
four-week paired calendar-block bootstrap (10,000 draws, prior fixed seeds),
including empty weeks and shared token days. Reused history is exploratory.

For every shared parent, show immediate outcome and confirmation disposition.
Count skipped immediate stops and skipped target winners; compare returns of
confirmed parents with their immediate counterparts. Decompose confirmation
selection versus delayed entry on raw opportunities. Separately decompose
chronological total change into shared-parent differences, dropped control
admissions and new treatment admissions caused by occupancy. Reject attributing
all skipped stops to confirmation if occupancy caused the change.

Exploratory continuation requires >=50 CLOSED trades in EACH partition, positive
base means and PF>=1.15 in each, positive stressed means in each, AND positive
stressed difference in mean versus immediate in each. Report absolute and
difference block intervals; passing point criteria does not establish an edge.
No automatic deployment or reserved2026 scoring. Failure closes this budget;
no threshold rescue or token-only cherry-pick. A pass queues independent-token
and prospective confirmation, preserving the existing frozen broader-token gates.

## Verification and preservation
Commit this protocol and duplicate audit before market scoring. Freeze code,
input, feature and membership hashes. Test strict/equal boundaries, both sides,
first/day behaviour, failed/late confirmation, midnight and partition boundaries,
and future perturbation/truncation. Independently reconstruct all first setups
and confirmations from minute candles and every raw exit path; replay admissions,
reconcile costs and report totals. Publish findings and aggregate contrasts on
existing draft PR99, retain downloadable uncompressed per-trade CSV and a private
restorable checkpoint. Do not modify the approved hourly paper pilot.
