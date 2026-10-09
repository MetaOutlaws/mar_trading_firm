# Entry discovery: evidence and hypothesis rationale

6 October 2026. This changes the research priority from profit protection to
finding an entry mechanism. Previously failed zone/retest variants remain in
the record. None of the papers below establishes profitability for our rules,
our Bybit data, current execution costs or our selected assets.

| Primary source | Evidence reviewed | Implication for this study |
|---|---|---|
| Liu & Tsyvinski, Risks and Returns of Cryptocurrency, NBER w24877, 2018; https://www.nber.org/papers/w24877 | Abstract reports time-series momentum and attention-related predictability | Multi-day direction is a candidate context; a moving-average reclaim is not the only possible entry |
| Zaremba et al., Up or down? Short-term reversal, momentum, and liquidity effects in cryptocurrency markets, 2021; https://doi.org/10.1016/j.irfa.2021.101908 | Publisher abstract reports broad-coin daily reversal but daily momentum among the largest/liquid coins | Separate trend pullbacks from exhaustion reversals; do not transfer illiquid-alt findings uncritically to BTC/ETH/SOL |
| Wen et al., Intraday return predictability in the cryptocurrency markets: Momentum, reversal, or both, 2022; https://doi.org/10.1016/j.najef.2022.101733 | Publisher abstract reports momentum and reversal varying with jumps, liquidity and market conditions | Test volatility/volume events as distinct setups rather than impose one universal trend gate |
| Shen, Urquhart & Wang, Bitcoin intraday time series momentum, Financial Review, 2022; https://doi.org/10.1111/fire.12290 | Publisher abstract associates stronger session predictability with high initial volume/volatility | Volume is a conditioning variable; this study is not a replication of that paper's session-timing rule |
| He et al., Fundamentals of Perpetual Futures, December 2022; https://arxiv.org/abs/2212.06888 | Full paper explains funding, futures/spot deviations and arbitrage under transaction costs | Settled funding supplies information beyond OHLCV, but funding alone is not a demonstrated directional predictor; our crowding-plus-price rule is a new hypothesis |

The recent SSRN abstract “Conditional Arbitrage Capacity” (7520320) was also
encountered. Its full text was inaccessible and it uses 2021–2026 observations;
we do not treat its reported directional returns as validation or use them as
parameter estimates. General external exposure to 2026 information means any
reserved period here is reserved within this experiment, not globally unseen.

## Deliberate change in approach

Earlier experiments repeatedly conditioned entries on the same slow 4h EMA
regime. That narrowed the opportunity set and could exclude reversal setups.
Here the 4h regime is recorded as context rather than a compulsory entry gate.
The new study uses a common stop/target-only exit for ALL tested families and
controls. It therefore evaluates a new research framework; differences against
the old regime-exit results cannot be attributed solely to the entry change.

The four fixed hypotheses are trend-pullback resumption, volume-shock reversal,
funding-crowding breakout and compression expansion. Precise rules are frozen in
PROTOCOL.md. These are proposals informed by the evidence, not copied paper
strategies or named proven edges. No liquidation or order-flow claim is made
from candle volume: we do not have historical liquidation/OI/order-book data.

A fifth family reverse-engineers a small, interpretable decision rule from
entry-time features and BOTH winning and losing opportunities. It uses only
2022–23 labels, chooses one leaf per clock, then remains fixed. Later years
evaluate the rule rather than train it. Report every leaf and the exact learned
conditions; do not search until a profitable 2025 cell appears.

Funding/basis arbitrage and order-flow models remain separate possibilities.
The current cache has perpetual candles and settled funding, not matched spot,
historical mark/basis, depth or open interest, so it cannot establish those edges.

Implementation documentation: scikit-learn DecisionTreeRegressor API,
https://scikit-learn.org/stable/modules/generated/sklearn.tree.DecisionTreeRegressor.html.
Installed version is recorded in the run manifest; no hyperparameter search.
