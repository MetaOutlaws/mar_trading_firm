from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from core.strategy.base import SignalSide
from core.strategy.hourly_compression_btc_connors_loweff_v1 import HourlyCompressionBtcConnorsLoweffV1Strategy as Rule
from core.strategy.hourly_compression_connors_v1 import HourlyCompressionConnorsV1Strategy as Connors
from scripts.enable_hourly_btc_connors_loweff import desired_records,merged_book,retired_records
from tests.test_hourly_compression_v1 import tape


def test_cap_boundary_and_missing_context():
    from core.strategy.hourly_compression_btc_connors_loweff_v1 import conditional_cap_pass
    er = np.array([.299999, .299999, .30, .31, np.nan, .1])
    ext = np.array([1., 1.000001, 1.000001, 10., .5, np.nan])
    assert conditional_cap_pass(er, ext).tolist() == [True, False, True, True, False, False]


def test_efficiency_excludes_signal_hour_and_flat_path():
    from core.strategy.hourly_compression_btc_connors_loweff_v1 import prior_efficiency24
    # Last value is the signal close and must have no influence on prior ER24.
    x = pd.Series([100., 101., 99., 102., 100.] * 6)
    expected = abs(x.iloc[-2]-x.iloc[-26]) / np.abs(np.diff(x.iloc[-26:-1])).sum()
    assert np.isclose(prior_efficiency24(x).iloc[-1], expected)
    before = prior_efficiency24(x).iloc[-1]
    x.iloc[-1] = 100000.
    assert prior_efficiency24(x).iloc[-1] == before
    assert prior_efficiency24(pd.Series([100.]*30)).iloc[-1] == 0.


def test_exact_context_no_fill_no_future_and_zero_gate():
    q=tape();rule=Rule();btc=q.copy();btc.close=np.arange(len(q))+100.
    x=rule.prepare_market_context('ETHUSDT',q,btc)
    assert x.btc24.iloc[-1]==btc.close.iloc[-1]/btc.close.iloc[-25]-1
    assert rule.generate_signals(x).passes_btc.iloc[-1]
    missing=btc.iloc[:-1].copy()
    with pytest.raises(ValueError,match='Missing exact'):rule.prepare_market_context('ETHUSDT',q,missing)
    with pytest.raises(ValueError,match='contiguous'):rule.prepare_market_context('ETHUSDT',q,btc.drop(btc.index[-25]))
    # A future hour cannot fill the missing current one.
    future=btc.iloc[[-1]].copy();future.index+=pd.Timedelta(hours=1)
    with pytest.raises(ValueError):rule.prepare_market_context('ETHUSDT',q,pd.concat([missing,future]))
    flat=btc.copy();flat.close=100.
    x=rule.prepare_market_context('ETHUSDT',q,flat)
    assert not rule.generate_signals(x).passes_btc.iloc[-1]
    x=rule.prepare_market_context('BTCUSDT',flat,None)
    assert rule.generate_signals(x).passes_btc.iloc[-1]


@pytest.mark.parametrize('side',[SignalSide.LONG,SignalSide.SHORT])
def test_side_gate_and_unbound_context_refused(side):
    rule=Rule(replace(Rule().params,side=side));q=tape();btc=q.copy()
    btc.close=np.arange(len(q))+100.
    out=rule.generate_signals(rule.prepare_market_context('SOLUSDT',q,btc))
    assert out.passes_btc.iloc[-1]==(side==SignalSide.LONG)
    with pytest.raises(ValueError,match='Explicit'):rule.generate_signals(q)
    with pytest.raises(ValueError,match='match'):rule.latest_signal('ETHUSDT',rule.prepare_market_context('SOLUSDT',q,btc))


def test_exact_known_retirement_and_conflicts():
    other={'_meta':'keep','other:BTCUSDT:LONG:1h':{'approved':True}}
    assert merged_book({**other,**retired_records()})=={**other,**desired_records()}
    assert merged_book(merged_book(other))==merged_book(other)
    bad=retired_records();bad[next(iter(bad))]={'approved':True}
    with pytest.raises(ValueError,match='Different baseline'):merged_book(bad)
    assert all(not x['approved'] and x['paper_override'] for x in desired_records().values())


def test_paper_plan_and_live_restriction(monkeypatch):
    from config.universe import Universe
    from config.settings import TradingMode
    import core.execution.engine as engine
    monkeypatch.setattr(engine,'get_universe',lambda:Universe(approvals=merged_book(retired_records())))
    monkeypatch.setattr('core.data.soko_trend.read_live_soko_trend',lambda:None)
    plan=engine.build_plan(require_approval=False)
    assert len(plan.entries)==6 and all(e.strategy.name==Rule.name for e in plan.entries)
    assert not engine.build_plan(require_approval=True).entries
    monkeypatch.setattr('config.settings.get_settings',lambda:SimpleNamespace(trading_mode=TradingMode.LIVE))
    rule=Rule();q=rule.prepare_market_context('BTCUSDT',tape(),None)
    with pytest.raises(RuntimeError,match='paper-only'):rule.latest_signal('BTCUSDT',q)
    with pytest.raises(ValueError,match='only'):rule.prepare_market_context('DOGEUSDT',tape(),None)


def test_engine_supplies_matching_closed_btc_and_propagates_missing_context(monkeypatch):
    import core.execution.engine as engine
    q=tape();now=q.index[-1]+pd.Timedelta(hours=1,seconds=1)
    future=q.iloc[[-1]].copy();future.index+=pd.Timedelta(hours=1);future.close=9999.
    btc=q.copy();btc.close=np.arange(len(q))+100.
    btcfeed=pd.concat([btc,future]);calls=[]
    class Data:
        def fetch_latest(self,symbol,timeframe,bars):
            calls.append((symbol,timeframe,bars));return q if symbol=='ETHUSDT' else btcfeed
    rule=Rule();seen=[]
    def latest(symbol,candles):
        seen.append(candles);return None
    monkeypatch.setattr(rule,'latest_signal',latest)
    desk=object.__new__(engine.TradingEngine);desk._data=Data()
    entry=SimpleNamespace(symbol='ETHUSDT',timeframe='1h',strategy=rule)
    monkeypatch.setattr(engine,'_now',lambda:now.to_pydatetime())
    desk._evaluate(entry)
    assert calls==[('ETHUSDT','1h',850),('BTCUSDT','1h',850)]
    assert seen[0].btc_close.iloc[-1]==btc.close.iloc[-1]
    btcfeed=btc.iloc[:-1]
    with pytest.raises(ValueError,match='Missing exact'):desk._evaluate(entry)


def test_atomic_activation_backup_and_cycle_verification(tmp_path, monkeypatch, capsys):
    import json
    from datetime import datetime, timedelta, timezone
    import config.universe as universe
    from scripts import enable_hourly_btc_connors_loweff as command
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
    activation = json.loads((tmp_path/'hourly_compression_btc_connors_loweff_v1_activation.json').read_text())
    assert activation['status'] == 'installed_awaiting_cycle'
    cycle = {'started_at': (datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat(),
             'symbols_scanned': 6, 'errors': [], 'entries_blocked': False, 'halted': False,
             'exit_supervision_ran': True, 'plan': [dict(strategy='hourly_compression_btc_connors_loweff_v1',symbol=s,side=d,timeframe='1h')
                      for s in ['BTCUSDT','ETHUSDT','SOLUSDT'] for d in ['LONG','SHORT']]}
    monkeypatch.setattr("core.execution.engine.load_last_cycle", lambda: cycle)
    monkeypatch.setattr("sys.argv", ["enable", "--verify"])
    command.main()
    assert 'scanning_verified' in capsys.readouterr().out
    cycle['plan'].pop()
    with pytest.raises(RuntimeError, match="Cycle plan/health"):
        command.main()
    universe.get_universe.cache_clear(); get_settings.cache_clear()
