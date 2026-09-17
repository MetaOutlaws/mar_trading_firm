# F04 execution contract (research ↔ paper)

CEO LOCK / Option B / 1-week DONE. This is the comparison contract, not a
go-live unlock. Live stays off. `approved=true` is not granted here.

Full rules live in `core/execution/contract.py` (`EXECUTION_CONTRACT_VERSION`).
This note is the desk-readable copy.

## What was true on HEAD (verified, not hypothesized)

| Rule | Research `BacktestEngine` | Live paper `TradingEngine` / `PaperBroker` |
|---|---|---|
| Entry | Next-bar **open**, then `CostModel.entry_price` | Signal on just-closed bar; submit later at **sampled last price** |
| TP/SL origin | Slipped **fill** | Was signal-bar **close** (F04 repair: rebuilt from fill after the order) |
| `max_holding_bars` | Timeout at last holding bar's close | Was **not** checked (F04 repair: `expiry_at` on the position; timeout after stops) |
| Stop path | Full OHLC: gap at open, then stop, then target | **One sampled last price** per poll (F15; not this ticket) |
| Stop extra slip | **None** — stop/gap quote is the fill | Live SL poll now `close_at_fill` at the last mark (no second slip). Replay uses the research quote |
| Fees / funding | `CostModel` both legs + `funding_cost` | Same model after F03 |
| Conflicts | One position per symbol; no pyramiding | Same on the paper broker; runtime also competes approved sleeves for the slot |

Fees/funding application was **not** the remaining F04 hole (F03 closed it).
Fill timing, TP/SL origin, holding expiry and sampled-vs-OHLC path **were**.

## Canonical comparison rules

Identical candles must produce identical signals, fills, exits, costs and P&L
between `BacktestEngine` and `run_paper_replay` (a `PaperBroker` driven by the
same tape).

1. Signal on bar `t` fills at bar `t+1` open.
2. TP/SL from the slipped fill.
3. Intrabar: gap-stop at open, then pessimistic stop-vs-target, then stop, then target.
4. Timeout at `max_holding_bars` (fill at that bar's close). `END_OF_DATA` if the series ends first.
5. Stop fills take **no** extra `exit_price` slippage. TP / timeout / EOD do.
6. Taker fees both legs; funding over `[entry_time, exit_time]` on entry notional.
7. One position per symbol.
8. Every paper position stores `execution_contract`, full params, timeframe, `max_holding_bars`, `expiry_at`.

Live paper still cannot see wicks between polls. That limitation is explicit.
The golden tape does not pretend a sampled mark equals an OHLC path.

## Golden tape

Fixtures: `tests/fixtures/golden_tapes/*.json`.

```bash
python -m pytest tests/test_f04_execution_contract.py tests/test_engine.py -q
```

Both `BacktestEngine.run` and `core.execution.replay.run_paper_replay` must
match each fixture's `expected.trades`. If research and paper drift on the
taped scenario, those tests fail.

Bump `EXECUTION_CONTRACT_VERSION` when the numbered rules change. Do not
stamp `approved=true` from this work.
