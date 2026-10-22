#!/usr/bin/env python3
"""Run the frozen carry protocol. Writes summaries under the output directory.

No threshold is changed here. A cash mismatch larger than one cent stops the run.
"""
from __future__ import annotations

import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from carry_sim import CarryAccount, Cost, SymbolBook, prepare, roll_funding
from load_series import load
from protocol_constants import (
    COST_MODELS,
    NULL_SHIFT_MAX_DAYS,
    NULL_SHIFT_MIN_DAYS,
    NULL_SHIFTS,
    PRIMARY_DELAY_MINUTES,
    SENSITIVITY_DELAY_MINUTES,
    STARTING_EQUITY_USDT,
    SYMBOLS,
    funding_hurdle,
)
from score_carry import bootstrap_interval, gates, summarise


def _books(raw, names):
    books = []
    for name in names:
        item = raw[name]
        book = SymbolBook(
            name=name,
            spot_o=item["spot_o"],
            spot_c=item["spot_c"],
            perp_o=item["perp_o"],
            perp_c=item["perp_c"],
            mark_o=item["mark_o"],
            mark_c=item["mark_c"],
            fund_flag=item["fund_flag"],
            fund_rate=item["fund_rate"],
            step=item["step"],
            min_qty=item["min_qty"],
        )
        prepare(book)
        books.append(book)
    return books


def _cost(model: str) -> Cost:
    spec = COST_MODELS[model]
    return Cost(spec["spot_fee"], spec["perp_fee"], spec["slippage"], funding_hurdle(model))


def _execute(books, cost, delay, passive, timestamps, year_ends):
    account = CarryAccount(books, cost, delay, passive, complete=True)
    result = account.run(timestamps, year_ends)
    if result["open_positions"]:
        raise RuntimeError(f"positions left open: {result['open_positions']}")
    pnl = sum(trade["pnl"] for trade in result["trades"])
    change = result["ending_equity"] - STARTING_EQUITY_USDT
    if abs(pnl - change) > 0.01:
        raise RuntimeError(f"cash conservation failed: trade pnl {pnl} vs equity change {change}")
    return result


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


_STATE = {}


def _null_pnl(days: int) -> float:
    books = [roll_funding(book, int(days) * 1440) for book in _STATE["books"]]
    result = _execute(books, _STATE["cost"], PRIMARY_DELAY_MINUTES, False, _STATE["timestamps"], _STATE["year_ends"])
    return result["ending_equity"] - STARTING_EQUITY_USDT


def main() -> None:
    root = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    raw, timestamps, year_ends = load(root)
    print(f"loaded {len(timestamps)} minutes in {time.time() - t0:.1f}s", flush=True)
    names = {
        "BTC": ["BTCUSDT"],
        "ETH": ["ETHUSDT"],
        "combined": list(SYMBOLS),
    }
    prepared = {key: _books(raw, value) for key, value in names.items()}
    jobs = []
    for model in ("baseline", "moderate", "desk_031", "severe"):
        for book_name in ("BTC", "ETH", "combined"):
            jobs.append((model, book_name, PRIMARY_DELAY_MINUTES, False))
            jobs.append((model, book_name, PRIMARY_DELAY_MINUTES, True))
        if COST_MODELS[model]["role"] != "stress":
            jobs.append((model, "combined", SENSITIVITY_DELAY_MINUTES, False))
    summaries = {}
    trade_pnls = {}
    for model, book_name, delay, passive in jobs:
        label = f"{model}_{book_name}_d{delay}_{'passive' if passive else 'selective'}"
        started = time.time()
        result = _execute(prepared[book_name], _cost(model), delay, passive, timestamps, year_ends)
        summary = summarise(result, timestamps, label)
        if not passive and delay == PRIMARY_DELAY_MINUTES and book_name == "combined":
            low, high = bootstrap_interval([t["pnl"] for t in result["trades"]])
            summary["bootstrap_low"] = low
            summary["bootstrap_high"] = high
            trade_pnls[model] = [t["pnl"] for t in result["trades"]]
        _write(out / f"{label}.json", summary)
        summaries[label] = summary
        print(
            f"{label} equity {summary['ending_equity']:.2f} trades {summary['trades']} "
            f"in {time.time() - started:.1f}s",
            flush=True,
        )
    rng = np.random.default_rng(20261022)
    offsets = rng.integers(NULL_SHIFT_MIN_DAYS, NULL_SHIFT_MAX_DAYS + 1, size=NULL_SHIFTS)
    workers = min(4, mp.cpu_count())
    for model in ("baseline", "moderate", "desk_031"):
        _STATE["books"] = prepared["combined"]
        _STATE["cost"] = _cost(model)
        _STATE["timestamps"] = timestamps
        _STATE["year_ends"] = year_ends
        started = time.time()
        # Fork after the arrays exist so workers share the price pages.
        with mp.get_context("fork").Pool(workers) as pool:
            nulls = pool.map(_null_pnl, [int(days) for days in offsets], chunksize=5)
        summary = summaries[f"{model}_combined_d1_selective"]
        summary["gates"] = gates(summary, nulls)
        summary["null_pnl_mean"] = float(np.mean(nulls))
        _write(out / f"{model}_combined_d1_selective.json", summary)
        _write(out / f"{model}_nulls.json", {"offsets": offsets.tolist(), "pnls": nulls})
        print(f"gates {model} pass={summary['gates']['pass']} in {time.time() - started:.0f}s", flush=True)
    _write(out / "INDEX.json", {"labels": sorted(summaries)})
    print(f"done in {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
