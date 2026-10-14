"""Read-only replay of the saved 2022–2025 L01 gate and admission decisions.

Requires the owner's restored checkpoint; does not download candles, open a
new evaluation period, simulate new exit paths, or activate a paper worker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.strategy.l01_context import SEED_PATH, SEED_SHA256, decision


def verify(root: Path) -> dict:
    study = root / "mar_structure_direction_20261014"
    freeze = json.loads((study / "FREEZE.json").read_text())
    checked_hashes = {}
    for name in ["mar_structure_entry_20261014/causal_features.parquet",
                 "mar_protection_surface_20261010/sources.parquet",
                 "mar_protection_surface_20261010/entries.parquet",
                 "mar_protection_surface_20261010/results/opportunities.parquet"]:
        checked_hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
        assert checked_hashes[name] == freeze["source_sha256"][name], name
    features = pd.read_parquet(root / "mar_structure_entry_20261014/causal_features.parquet")
    seed = json.loads(SEED_PATH.read_text())["records"]
    assert hashlib.sha256(SEED_PATH.read_bytes()).hexdigest() == SEED_SHA256
    assert len(features) == 1026 and features.symbol.nunique() == 96
    passed, comparisons, stale = {}, 0, 0
    for symbol, group in features.groupby("symbol"):
        bar_path = root / "mar_structure_entry_20261014/bars" / f"{symbol}_4h.parquet"
        assert hashlib.sha256(bar_path.read_bytes()).hexdigest() == seed[symbol]["source_4h_sha256"]
        bars = pd.read_parquet(bar_path)
        ema = bars.close.ewm(span=50, adjust=False, min_periods=1).mean()
        np.testing.assert_allclose(ema.iloc[-4:], seed[symbol]["ema_tail"], rtol=0, atol=1e-12)
        assert len(bars) == seed[symbol]["complete_bars"]
        for row in group.itertuples():
            j = int(bars.index.searchsorted(row.signal_time, side="right") - 1)
            state = None if j < 0 else {
                "processed_through": row.signal_time.floor("4h").isoformat(),
                "available_at": bars.index[j].isoformat(), "complete_bars": j + 1,
                "close4": float(bars.close.iloc[j]), "ema_tail": list(ema.iloc[max(0, j-3):j+1]),
            }
            ok, reason, info = decision("LONG" if row.side == 1 else "SHORT", state, row.signal_time)
            expected = row.side == -1 or bool(row.trend4)
            assert ok == expected, (symbol, row.sid, reason, expected)
            passed[row.sid] = ok
            stale += int(reason == "l01_context_stale")
            if row.side == 1 and row.trend4_available and info.get("l01_ema50") is not None:
                np.testing.assert_allclose([info["l01_ema50"], info["l01_slope4"]],
                                           [row.ema4, row.slope4], rtol=1e-11, atol=1e-11)
                comparisons += 2
    source = pd.read_parquet(root / "mar_protection_surface_20261010/sources.parquet")
    source = source.sort_values(["symbol", "signal_time", "side"]).reset_index(drop=True)
    source["sid"] = np.arange(len(source))
    assert list(source.symbol) == list(features.sort_values("sid").symbol)
    base = (source.prior_atr/source.close >= .01) & (source.compression > .5) & (source.extension_atr <= 1)
    valid = set(source.loc[base & source.sid.map(passed), "sid"])
    entries = pd.read_parquet(root / "mar_protection_surface_20261010/entries.parquet")
    entries = entries.merge(source[["symbol", "signal_time", "side", "sid"]],
                            on=["symbol", "signal_time", "side"], validate="one_to_one")
    paths = pd.read_parquet(root / "mar_protection_surface_20261010/results/opportunities.parquet",
                            filters=[("policy", "==", 331)])
    paths = paths.merge(entries[["eid", "sid"]], on="eid", validate="many_to_one")
    books = pd.read_parquet(study / "books.parquet")
    admissions = []
    for slip in [.002, .003]:
        candidates = paths[paths.slippage.eq(slip) & paths.sid.isin(valid)]
        kept, busy = [], {}
        for (symbol, at), group in candidates.sort_values(["symbol", "entry", "signal_time", "side"]).groupby(["symbol", "entry"], sort=False):
            if group.side.nunique() > 1:
                continue
            for idx, row in group.iterrows():
                if at.value > busy.get(symbol, -1):
                    kept.append(idx)
                    busy[symbol] = int(row.exit_ns)
        actual = candidates.loc[kept].sort_values("sid")
        expected = books[books.case_id.eq("L01") & books.slippage.eq(slip)].sort_values("sid")
        assert list(actual.sid) == list(expected.sid)
        for col in ["entry_i", "exit_i", "entry_price", "exit_price", "net_R", "net_return", "funding"]:
            np.testing.assert_allclose(actual[col], expected[col], rtol=0, atol=1e-12)
        short_control = books[books.case_id.eq("S00") & books.slippage.eq(slip) & books.side.eq(-1)]
        assert set(actual.loc[actual.side.eq(-1), "sid"]) == set(short_control.sid)
        admissions.append({"slippage_per_side": slip, "all96_trades": len(actual),
                           "additional93_longs": int((actual.population.eq("additional93") & actual.side.eq(1)).sum()),
                           "additional93_shorts": int((actual.population.eq("additional93") & actual.side.eq(-1)).sum())})
    return {"status": "pass", "signals": len(features), "tokens": 96,
            "long_signals": int(features.side.eq(1).sum()), "short_signals": int(features.side.eq(-1).sum()),
            "ema_and_slope_comparisons": comparisons, "stale_context_rejections_in_saved_sample": stale,
            "research_seed_records_verified": len(seed), "seed_sha256": SEED_SHA256,
            "admission_replays": admissions, "input_sha256": checked_hashes,
            "historical_2026_backtest_opened": False, "runtime_activation_verified": False,
            "scope": "L01 context/gate parity and saved-path admission replay; inherited forward engine path parity remains UNVERIFIED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = verify(args.checkpoint_root)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered)


if __name__ == "__main__":
    main()
