from dataclasses import replace
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from core.strategy.base import SignalSide
from core.strategy.hourly_compression_connors_v1 import HourlyCompressionConnorsV1Strategy as Rule,connors_components,connors_gate
from scripts.enable_hourly_connors import desired_records,merged_book
from scripts.enable_hourly_compression import desired_records as original
from tests.test_hourly_compression_v1 import tape


def test_components_flat_rank_ties_and_streak_reset():
    q=pd.Series(np.full(110,100.))
    c=connors_components(q)
    assert c.filter_crsi.iloc[:101].isna().all()
    assert np.allclose(c.filter_crsi.iloc[101:],100/3)
    assert (c.rank100.iloc[101:]==0).all()
    x=pd.Series([100.,101,102,101,100,100,101])
    assert connors_components(x).streak.tolist()==[0,1,2,-1,-2,0,1]


def test_thresholds_and_missing_fail_closed():
    assert connors_gate([90,90.01,10,np.nan,101,-1],1).tolist()==[True,False,True,False,False,False]
    assert connors_gate([10,9.99,90,np.nan,101,-1],-1).tolist()==[True,False,True,False,False,False]


@pytest.mark.parametrize('side',[SignalSide.LONG,SignalSide.SHORT])
def test_gate_clears_extreme_breakout_and_is_causal(side):
    q=tape()
    if side==SignalSide.SHORT:q[['open','high','low','close']]=200-q[['open','low','high','close']].to_numpy()
    rule=Rule(replace(Rule().params,side=side))
    out=rule.generate_signals(q)
    assert out.signal.iloc[-1]==0
    assert out.reason.iloc[-1]==''
    extra=q.iloc[[-1]].copy();extra.index+=pd.Timedelta(hours=1)
    extra[['open','high','low','close']]*=2
    pd.testing.assert_frame_equal(out,rule.generate_signals(pd.concat([q,extra])).iloc[:-1])


def test_merge_retires_only_known_six_preserves_others_and_is_idempotent():
    others={'_metadata':{'keep':True},'other:BTCUSDT:LONG:1h':{'approved':True,'strategy':'other'}}
    merged=merged_book({**others,**original()})
    assert merged=={**others,**desired_records()}
    assert merged_book(merged)==merged
    assert all(not v['approved'] and v['paper_override'] for v in desired_records().values())
    bad=original();bad[next(iter(bad))]={**bad[next(iter(bad))],'params':{}}
    with pytest.raises(ValueError,match='Different baseline'):merged_book(bad)
    with pytest.raises(ValueError,match='Another active'):merged_book({'hourly_compression_btc_v1:ETHUSDT:LONG:1h':{'paper_override':True}})


def test_plan_only_six_paper_entries(monkeypatch):
    from config.universe import Universe
    import core.execution.engine as engine
    universe=Universe(approvals=merged_book(original()))
    monkeypatch.setattr(engine,'get_universe',lambda:universe)
    monkeypatch.setattr('core.data.soko_trend.read_live_soko_trend',lambda:None)
    plan=engine.build_plan(require_approval=False)
    assert len(plan.entries)==6 and all(e.strategy.name==Rule.name for e in plan.entries)
    assert not engine.build_plan(require_approval=True).entries


def test_live_wrong_symbol_wrong_brackets_blocked(monkeypatch):
    from config.settings import TradingMode
    monkeypatch.setattr('config.settings.get_settings',lambda:SimpleNamespace(trading_mode=TradingMode.LIVE))
    with pytest.raises(RuntimeError,match='paper-only'):Rule().latest_signal('BTCUSDT',tape())
    monkeypatch.setattr('config.settings.get_settings',lambda:SimpleNamespace(trading_mode=TradingMode.PAPER))
    with pytest.raises(ValueError,match='only'):Rule().latest_signal('DOGEUSDT',tape())
    with pytest.raises(ValueError,match='fixed'):Rule(replace(Rule().params,stop_loss_pct=.03))


def test_atomic_activation_backup_and_cycle_verification(tmp_path, monkeypatch, capsys):
    import json
    from datetime import datetime, timedelta, timezone
    import config.universe as universe
    from scripts import enable_hourly_connors as command
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
    activation = json.loads((tmp_path/'hourly_compression_connors_v1_activation.json').read_text())
    assert activation['status'] == 'installed_awaiting_cycle'
    cycle = {'started_at': (datetime.now(timezone.utc)+timedelta(seconds=1)).isoformat(),
             'symbols_scanned': 6, 'errors': [], 'entries_blocked': False, 'halted': False,
             'exit_supervision_ran': True, 'plan': [dict(strategy='hourly_compression_connors_v1',symbol=s,side=d,timeframe='1h')
                      for s in ['BTCUSDT','ETHUSDT','SOLUSDT'] for d in ['LONG','SHORT']]}
    monkeypatch.setattr("core.execution.engine.load_last_cycle", lambda: cycle)
    monkeypatch.setattr("sys.argv", ["enable", "--verify"])
    command.main()
    assert 'scanning_verified' in capsys.readouterr().out
    cycle['plan'].pop()
    with pytest.raises(RuntimeError, match="Cycle plan/health"):
        command.main()
    universe.get_universe.cache_clear(); get_settings.cache_clear()
