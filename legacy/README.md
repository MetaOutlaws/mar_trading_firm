# Legacy reference code

Read-only snapshots from the predecessor project (`../../mar_trading_bot`), kept
so the rebuild can be checked against the original intent. **Nothing here is
imported by the running system.**

## Why each file is here

| File | Why kept |
|---|---|
| `new_multi_indicator.py` | The 3,334-line live bot. The authoritative record of what the deployed entry logic actually was (`check_entry_conditions`, ~L2588). |
| `enhanced_indicators.py` | The backtest-side signal generator. Diverged from the live bot, which is the root cause of the contradictory backtest results. |
| `backtest_engine.py` | Fee/slippage-aware simulator. Its cost assumptions were sound; it lacked funding costs. |
| `long_strategy_config.py` / `short_strategy_config.py` | Source of the per-asset parameters, extracted to `../config/asset_params.json`. |
| `bigquery_connector.py` / `bigquery_config.py` | The Q1/Q4 2024 history access pattern. |

## Known defects (do not reproduce)

1. **Live keys hardcoded** with `testnet=False` (`new_multi_indicator.py` ~L3313).
   See `../SECURITY.md`.
2. **Two competing strategy implementations.** The live bot used asset-specific
   RSI ranges plus golden cross; the backtester used MACD crossover plus ADX
   scoring. They were never the same strategy, so their results could not agree.
3. **Declared risk limits unenforced.** `MAX_POSITIONS = 5` and
   `MAX_DAILY_TRADES = 30` (L393-394) are never checked in `execute_strategy`.
   No daily loss limit, no kill switch, no portfolio exposure cap.
4. **No funding cost in backtests.** Positions held up to 24h on perps incur up
   to three funding settlements, worth ~22% annualised for a long in Q1 2024.
5. **Unbounded logging.** `trading_bot_2.log` reached 473 MB.
6. **`enabled=True` in a Python file was sufficient to trade real money.** No
   validation gate stood between a hand edit and order placement.
7. **Never executed a trade.** Zero order placements across the entire 473 MB
   log, so none of the strategy claims were ever tested against a real fill.

## What was carried forward

- Per-asset parameters -> `config/asset_params.json` (with performance figures
  quarantined under `legacy_claims`)
- Asset universe and sector groupings -> `config/universe.py`
- Fee and slippage assumptions -> `research/costs.py` (plus funding)
- Indicator definitions -> `core/strategy/indicators.py` (single implementation)
