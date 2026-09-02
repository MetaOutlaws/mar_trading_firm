# MAR Trading Firm

A deterministic crypto trading core with AI employees around it — not instead of it.

The previous bot never placed a trade, its backtests contradicted each other, and
its risk limits were not enforced. This rebuild separates three things that were
mixed together:

1. **Research** decides whether a strategy has an edge.
2. **Risk + execution** (no LLMs) decide whether a signal may become an order.
3. **Employees** advise, veto, and research. They cannot raise a limit.

## Phase 1 verdict

The legacy RSI + golden-cross strategy is **rejected**. Full-history baseline
expectancy is negative on every major pair after fees, slippage, and funding.
See `research/artifacts/PHASE1_VERDICT.md`. Nothing is approved to trade live.

## Safety

- Keys live in `.env` only. Never in source.
- `TRADING_MODE=paper` by default. Live also requires `GO_LIVE_CONFIRMED=I_ACCEPT_THE_RISK`.
- Kill switch is file-backed and human-reset-only.
- Agents start at L1 Advisor. Promotion needs scored decisions, auditor sign-off, and you.

## Run

```bash
pip install -e .
copy .env.example .env
python scripts/validate_strategy.py --baseline-only
python scripts/run_paper_trading.py --cycles 1
python scripts/run_api.py
```

Dashboard: http://127.0.0.1:8000 — operator desk with equity, blotter, positions,
employee floor, inbox, research, sentiment, and go-live gates.

Go-live check (does not start live trading):

```bash
python scripts/check_go_live.py
```

If any gate fails, stay in paper. The gates are the product.
