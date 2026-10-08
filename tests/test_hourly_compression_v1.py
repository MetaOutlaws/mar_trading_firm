from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest

from core.strategy.base import SignalSide
from core.strategy.hourly_compression_v1 import HourlyCompressionV1Strategy as Rule
from scripts.enable_hourly_compression import desired_records, merged_book


def tape():
    n = 850
    q = pd.DataFrame({"open": 100., "high": 102., "low": 98., "close": 100., "volume": 100.},
                     index=pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC"))
    q.iloc[-7:-1, q.columns.get_indexer(["high", "low"])] = [100.2, 99.8]
    q.iloc[-1] = [100., 108., 99., 107., 200.]
    return q


@pytest.mark.parametrize("side", [SignalSide.LONG, SignalSide.SHORT])
def test_closed_hourly_entry_and_prefix_invariance(side):
    q = tape()
    if side == SignalSide.SHORT:
        q[["open", "high", "low", "close"]] = 200-q[["open", "low", "high", "close"]].to_numpy()
    rule = Rule(replace(Rule().params, side=side))
    prefix = rule.generate_signals(q)
    assert prefix.signal.iloc[-1] == side.sign
    later = q.iloc[[-1]].copy(); later.index += pd.Timedelta(hours=1)
    later.loc[:, ["open", "high", "low", "close"]] *= 1.8
    full = rule.generate_signals(pd.concat([q, later]))
    pd.testing.assert_frame_equal(prefix, full.iloc[:-1])
    q.iloc[-1, q.columns.get_loc("volume")] = 100.
    assert rule.generate_signals(q).signal.iloc[-1] == 0


def test_rejects_wrong_clock_gaps_and_changed_exit():
    q = tape()
    with pytest.raises(ValueError, match="contiguous"):
        Rule().generate_signals(q.drop(q.index[400]))
    with pytest.raises(ValueError, match="fixed"):
        Rule(replace(Rule().params, stop_loss_pct=.03))


def test_live_and_unapproved_symbol_blocked(monkeypatch):
    from config.settings import TradingMode
    monkeypatch.setattr("config.settings.get_settings", lambda: SimpleNamespace(trading_mode=TradingMode.LIVE))
    with pytest.raises(RuntimeError, match="paper-only"):
        Rule().latest_signal("BTCUSDT", tape())
    monkeypatch.setattr("config.settings.get_settings", lambda: SimpleNamespace(trading_mode=TradingMode.PAPER))
    with pytest.raises(ValueError, match="only"):
        Rule().latest_signal("DOGEUSDT", tape())


def test_six_paper_rows_preserve_book_and_exclude_live(monkeypatch):
    from config.universe import Universe
    import core.execution.engine as engine
    original = {"_metadata": {"owner": "unchanged"}, "old:BTCUSDT:LONG:1h": {"approved": False}}
    book = merged_book(original)
    assert all(book[k] == v for k, v in original.items())
    assert merged_book(book) == book
    assert len(desired_records()) == 6 and not any(r["approved"] for r in desired_records().values())
    universe = Universe(approvals=book)
    monkeypatch.setattr(engine, "get_universe", lambda: universe)
    monkeypatch.setattr("core.data.soko_trend.read_live_soko_trend", lambda: None)
    plan = engine.build_plan(require_approval=False)
    assert len([e for e in plan.entries if e.strategy.name == Rule.name]) == 6
    assert all(e.strategy.name != Rule.name for e in engine.build_plan(require_approval=True).entries)
    bad = dict(book); bad[next(iter(desired_records()))] = {"approved": True}
    with pytest.raises(ValueError, match="overwrite"):
        merged_book(bad)


def test_atomic_activation_backup_and_cycle_verification(tmp_path, monkeypatch, capsys):
    import json
    from datetime import datetime, timedelta, timezone
    import config.universe as universe
    from scripts import enable_hourly_compression as command
    real = tmp_path/'persistent_approvals.json'
    original = {"_owner_metadata": {"preserve": True}}
    real.write_text(json.dumps(original))
    link = tmp_path/'approved_strategies.json'; link.symlink_to(real)
    monkeypatch.setattr(universe, "APPROVALS_PATH", link)
    monkeypatch.setenv("TRADING_MODE", "paper")
    from config.settings import get_settings
    get_settings.cache_clear(); universe.get_universe.cache_clear()
    monkeypatch.setattr("sys.argv", ["enable", "--apply"])
    command.main()
    assert link.is_symlink()
    installed = json.loads(real.read_text())
    assert installed['_owner_metadata'] == original['_owner_metadata']
    assert len(installed) == 7
    backups = list(tmp_path.glob('persistent_approvals.json.before-hourly-*'))
    assert len(backups) == 1 and json.loads(backups[0].read_text()) == original
    activation = json.loads((tmp_path/'hourly_compression_v1_activation.json').read_text())
    assert activation['status'] == 'installed_awaiting_cycle'
    cycle = {'started_at': (datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat(),
             'symbols_scanned': 6, 'errors': [], 'entries_blocked': False, 'halted': False,
             'plan': [dict(strategy='hourly_compression_v1',symbol=s,side=d,timeframe='1h')
                      for s in ['BTCUSDT','ETHUSDT','SOLUSDT'] for d in ['LONG','SHORT']]}
    monkeypatch.setattr("core.execution.engine.load_last_cycle", lambda: cycle)
    monkeypatch.setattr("sys.argv", ["enable", "--verify"])
    command.main()
    assert 'scanning_verified' in capsys.readouterr().out
    cycle['plan'].pop()
    with pytest.raises(RuntimeError, match="Cycle plan/health"):
        command.main()
    universe.get_universe.cache_clear(); get_settings.cache_clear()
