from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
import pandas as pd
import pytest
from polling_rule import sample_indices,poll_trade,verify_path,independent_cost
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'hourly_entry_latency_20261008'))
from test_latency import tape,rebuild
from bracket_rule import raw_trade

@pytest.mark.parametrize('side',[-1,1])
def test_exact_intrabar_comparator(side):
    t=tape();t.h[1]=110;t.l[1]=90;rebuild(t)
    a=raw_trade(t,0,side,.001,20,'fill_brackets');b=poll_trade(t,0,side,.001,20,0)
    assert all(a[k]==b[k] for k in a)

@pytest.mark.parametrize('poll',[1,5,15])
def test_global_phase_and_no_entry_poll(poll):
    t=tape();t.index=t.index+pd.Timedelta(minutes=2)
    ix=sample_indices(t.index,0,20,poll)
    assert (ix>0).all() and all((t.index[j].minute%poll)==0 for j in ix)

@pytest.mark.parametrize('poll',[-1,2,0,16,1.5,True])
def test_invalid_schedule(poll):
    with pytest.raises(ValueError):sample_indices(tape().index,0,20,poll)

@pytest.mark.parametrize('side',[-1,1])
@pytest.mark.parametrize('touch',['target','stop'])
def test_transient_touch_is_not_remembered(side,touch):
    t=tape();favourable=side if touch=='target' else -side
    if favourable==1:t.h[0]=105
    else:t.l[0]=95
    rebuild(t)
    assert poll_trade(t,0,side,0,20,0)['reason']==touch
    r=poll_trade(t,0,side,0,20,1)
    assert r['reason']=='boundary_mtm';verify_path(t,r,side,0,20,1)

@pytest.mark.parametrize('side',[-1,1])
@pytest.mark.parametrize('reason',['stop','target'])
def test_observed_quote_overshoot_and_clock(side,reason):
    t=tape();t.o[5]=100*(1+side*(.04 if reason=='target' else -.03));t.h[5]=max(100.1,t.o[5]);t.l[5]=min(99.9,t.o[5]);rebuild(t)
    r=poll_trade(t,0,side,.001,20,5)
    assert r['exit_i']==5 and r['quote']==t.o[5] and r['reason']==reason and r['fund_mode']=='open'
    verify_path(t,r,side,.001,20,5)

def test_no_endpoint_poll_and_last_close_mark():
    t=tape();t.o[15]=110;t.cl[14]=99.7;rebuild(t)
    r=poll_trade(t,0,1,0,15,15)
    assert r['reason']=='boundary_mtm' and r['exit_i']==14 and r['quote']==99.7

@pytest.mark.parametrize('side',[-1,1])
def test_funding_only_through_actual_sample_timestamp(side):
    t=tape();c=pd.DataFrame({'open':t.o},index=t.index)
    f=pd.DataFrame({'funding_rate':[.01,.02,.03]},index=t.index[[0,5,6]])
    ep=100.;xp=97. if side==1 else 103.;fees=.00055*(1+xp/ep)
    r=SimpleNamespace(entry_i=0,exit_i=5,quote=xp,fund_mode='open',entry_price=ep,exit_price=xp,fees=fees,funding=side*.02,net_return=side*(xp/ep-1)-fees-side*.02,holding_minutes=5)
    independent_cost(c,f,r,side,0)
