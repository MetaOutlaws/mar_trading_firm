# Protocol: same-token funding carry

Frozen before any strategy result. Hypothesis count: **1**.

Dataset: `spot_carry_core.tar.xz` sha256 `2157ec16fdacc8d27da2c0f81e644b8887d0e395d455453851755a07c79129c4`. Per-file manifest sha256 `560485b8a73b5dae304329a4d082373e248b9cd687b1e1366d613d7f2b312135`. Window 2022-01-01 00:00:00 through 2025-12-31 23:59:00 UTC. Any timestamp at or after 2026-01-01 00:00:00 UTC is refused. Machine-readable copy: `code/protocol_constants.py`.

## Hypothesis

Long the spot coin and short the same token's USDT linear perpetual, with the base quantities equal after rounding. No short-spot leg. No second rule, and no threshold is fit to profit.

BTCUSDT and ETHUSDT only. 2022–2025 is reused history. No year is a fitting sample. Tables still show 2022, 2023, 2024, 2025 and the full window. 2022–2023 are the earlier block and 2024–2025 the later block; the rule is the same in every block.

## What the audit already fixed

Six one-minute streams, each 2,103,840 rows, no gaps and no duplicates, from 2022-01-01 00:00 through 2025-12-31 23:59. Funding is an exact UTC 8-hour grid, 4,383 settlements each symbol, first 2022-01-01 00:00, last 2025-12-31 16:00. Every settlement minute has a mark open. The archive contains no fee schedule and no margin schedule. Those inputs stay labeled assumptions.

## Costs

Fees are charged in USDT, not in the base coin, so the spot quantity stays equal to the short quantity. The archive does not prove the 2022–2025 fee schedule. The labeled non-VIP schedule is spot taker 10 bp and linear taker 5.5 bp.

| Model | Spot fee per side | Perp fee per side | Slippage per side per leg | Pair round trip | Role |
| --- | --- | --- | --- | --- | --- |
| baseline | 10 bp | 5.5 bp | 1 bp | 35 bp | primary |
| moderate | 10 bp | 5.5 bp | 5 bp | 51 bp | primary |
| desk_031 | 15.5 bp | 15.5 bp | 0 | 62 bp | primary desk |
| severe | 10 bp | 5.5 bp | 10 bp | 71 bp | stress only |

Pair round trip is two sides of two legs. `desk_031` charges the desk's 0.31% round trip on **each** leg (`2 * (5.5 bp + 10 bp)`), split equally across entry and exit, with no extra slippage. Charging 0.31% once for the whole pair would be a lighter cost and is not used.

Slippage moves the fill off the quoted open. A buyer pays `open * (1 + slippage)`. A seller receives `open * (1 - slippage)`. Severe is reported and cannot, by itself, decide the study.

## Capital

One combined account starts at 20,000 USDT. Separate 20,000 accounts are reported for BTC alone and ETH alone.

A pair is one position. The cap is 15 positions. Each leg's quoted notional is at most 10% of marked equity. Gross notional across legs is at most 80% of equity. Leverage is 1.0: the short posts initial margin equal to 100% of its fill notional in cash. Spot coins are not collateral for that wallet. Maintenance margin is 5% of `qty * mark`. Cash that is not margin earns nothing. No borrowed spot.

Marked equity is cash, plus isolated margin wallets, plus spot quantity times spot close, plus short unrealised P&L at the mark. Unrealised on a short is `qty * (entry_fill - mark)`.

The 1% risk ceiling binds before entry. Estimated loss at a 1% adverse basis move, plus entry and exit fees and slippage, must be at most 1% of equity. Quantity is reduced by one perp step until it fits. If it cannot, the entry is blocked.

If marked equity is at or below 30% of its peak, no new entry is allowed. That is the handoff's 70% drawdown entry-stop. Open positions are still exited. `limits.py` is not changed. Its live concurrent-position cap of 5 is not the cap used here; the handoff's 15 is.

## Entry and exit

Decision minute `t` may use spot close, perp close, mark close, and funding settlements with timestamp `<= t`. The discretionary fill is the open of minute `t + delay`. Primary delay is 1 minute. The sensitivity delay is 5 minutes and is not part of the pass rule. Liquidation is not delayed.

Trailing funding is the last three settlements already known. Let `mean3` be their average and `r3` the newest. The hurdle is the model's pair round trip divided by 90. Ninety is 30 days times 3 settlements a day. That horizon was not scanned.

Enter only when flat and all of the following hold:

- at least three known settlements
- `mean3` is strictly above the hurdle
- `r3` is strictly positive
- basis `(perp_close - spot_close) / spot_close` is strictly above -1%
- the drawdown stop is not active
- the position, gross, cash, minimum-quantity and risk checks pass

Basis uses the decision minute's closes. Quantity is chosen from those known closes, not from the later fill:

`floor(min(0.10 * equity, cash that the decision-minute quote can afford) / quoted_spot_buy / step) * step`

`quoted_spot_buy` is the decision-minute spot close times `(1 + slippage)`. The delayed open is used only when the order fills. If that open is worse and the reserved cash cannot pay for the original quantity, quantity is reduced by whole steps at fill time or the fill is skipped and counted as blocked. It is not resized from a future close.

Steps are 0.001 BTC and 0.01 ETH. Those steps are labeled instrument rules, not observed in the archive. Within a minute, BTC is handled before ETH. Exits and liquidations happen before entries, so freed cash can fund a later symbol in that same minute.

Exit on the next delayed open when any of these is true on the decision minute:

- `r3` is not strictly positive
- `mean3` is not strictly above the hurdle
- basis is at or below -1%

There is no maximum holding time and no rebalance. Quantity stays fixed until the pair is flat.

A settlement is paid only if the position was opened on a strictly earlier minute. Payment is `rate * qty * mark_open` added to the isolated wallet. A positive rate pays the short. The mark open is a proxy for the exchange settlement price, not a printed settlement print.

Liquidation, checked at the mark open before a discretionary exit: if `wallet + qty * (entry_fill - mark_open) <= 0.05 * qty * mark_open`, cover the short at `mark_open * (1 + slippage + 0.0025)` and sell the spot at the spot open with the usual exit slippage and fee. The 25 bp penalty is labeled and was not fit.

If the sample ends while a pair is open, flatten at the last minute's close with exit costs. That trade is tagged `end_of_sample`. A missing spot, perp or mark bar is not filled; an open pair is flattened at the last complete minute and tagged `missing_data`. This archive has no such gap. The simulator still refuses a timestamp on or after 2026-01-01.

## Controls

- Cash: no orders. Ending equity 20,000.
- Passive carry: same size, costs, margin and liquidation, but enter at the first legal fill and re-enter on the next legal fill after any liquidation. No funding hurdle and no basis exit. Hold to the sample end.
- Approved hourly sleeves and BL8 are compared only if the same dates, the same 20,000 capital and the same cost model can be reproduced from this archive and the repo code. Otherwise the comparison is unavailable. Their old research R is not placed next to this return.

## Pass rule

A cost view passes only when the **combined** account meets every item below. Baseline, moderate and `desk_031` each have to pass. Severe does not have to pass. One failure is a study fail. Nothing here authorises live trading.

- At least 30 closed pair trades.
- Profit factor at least 1.15. Profit factor is the sum of positive trade P&L divided by the absolute sum of negative trade P&L.
- Mean trade P&L greater than 0.
- Maximum drawdown of marked equity at most 25%.
- At least half of the four calendar years have a positive change in marked equity.
- A 2,000-draw bootstrap of closed-trade P&L, seed 20261022, has a 95% percentile interval for the mean that lies entirely above 0.
- Beats a 200-shift null. Each shift rotates the funding series by a whole number of days drawn uniformly from 7 through 1454, seed 20261022, and reruns the combined account. The study P&L must be strictly above at least 190 of the 200 null P&Ls.
- Concentration: if combined P&L is positive, neither token's trade P&L may exceed 80% of it, and no single year's marked equity change may exceed 70% of the full-sample equity change.
- There is no fitted parameter, so the parameter-stability gate is recorded as not applicable. It is not a pass awarded to an unstable fit.

Go-live portfolio gates (300 trades, profit factor 1.3, drawdown under 15%) are a higher bar and are not claimed.

## Reports required after this file is committed

For each cost model, for BTC, ETH and the combined account, for 2022, 2023, 2024, 2025 and the full window: net return on starting equity, ending equity, maximum drawdown, utilisation, trade count, win rate, profit factor, average win, average loss, expectancy, total fees, slippage, funding, liquidation penalties, and R. R uses the ex-ante 1% of equity at entry as the denominator for each trade. A funding-rate sum is not an R.

Also report blocked entries, end-of-sample closes, missing-data closes, the 5-minute delay on the three primary models, and the passive and cash controls.

A bug that makes the code disagree with this file may be fixed and must be logged. A losing result is not a reason to edit the rule.
