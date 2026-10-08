"""Meaningful clock, causality, delayed-fill and admission checks."""
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from latency_rule import scheduled_index,delayed_trade
from bracket_rule import raw_trade,independent_path

class Barrier:
    def __init__(self,a,high):self.a,self.high=np.array(a),high
    def first(self,i,end,level):
        hits=np.flatnonzero(self.a[i:end]>=level if self.high else self.a[i:end]<=level)
        return i+int(hits[0]) if len(hits) else end

def tape():
    t=SimpleNamespace(index=pd.date_range('2025-01-01',periods=20,freq='min',tz='UTC'),o=np.full(20,100.),h=np.full(20,100.1),l=np.full(20,99.9),cl=np.full(20,100.))
    return rebuild(t)

def rebuild(t):t.hi=Barrier(t.h,True);t.lo=Barrier(t.l,False);return t

@pytest.mark.parametrize('d',[0,1,5,15])
def test_schedule(d):assert scheduled_index(tape().index,0,20,d)==d

@pytest.mark.parametrize('d',[-1,2,16,1.5,True])
def test_invalid_delay(d):
    with pytest.raises(ValueError):scheduled_index(tape().index,0,20,d)

def test_endpoint_and_gap():
    t=tape();assert scheduled_index(t.index,5,20,15) is None
    with pytest.raises(ValueError):scheduled_index(t.index.delete(1),0,19,5)

@pytest.mark.parametrize('side',[-1,1])
def test_zero_identity_and_waiting_path_ignored(side):
    t=tape();t.h[1]=120;t.l[1]=80;rebuild(t)
    a=delayed_trade(t,0,side,.001,20,0);b=raw_trade(t,0,side,.001,20,'fill_brackets')
    assert all(a[k]==v for k,v in b.items()) and a['reason']=='stop'
    d=delayed_trade(t,0,side,.001,20,5)
    assert d['reason']=='boundary_mtm' and d['entry_i']==5 and d['signal_i']==0
    independent_path(t,d,side,.001,20,'fill_brackets')

@pytest.mark.parametrize('side',[-1,1])
def test_delayed_fill_levels_and_first_minute_tie(side):
    t=tape();t.o[5]=105;t.h[5]=115;t.l[5]=95;rebuild(t)
    d=delayed_trade(t,0,side,.001,20,5)
    assert d['entry_fill']==105*(1+side*.001)
    assert d['stop_price']==d['entry_fill']*(1-side*.02)
    assert d['target_price']==d['entry_fill']*(1+side*.025)
    assert d['exit_i']==5 and d['reason']=='stop' and d['ambiguous']
    independent_path(t,d,side,.001,20,'fill_brackets')

def test_admission_at_execution_time_keeps_exit_minute_occupied():
    from run_latency import admit,replay
    stamp=pd.Timestamp('2025-01-01',tz='UTC')
    q=pd.DataFrame([dict(symbol='BTCUSDT',side=1,tf=60,rank=1,entry=stamp+pd.Timedelta(minutes=i),exit_bar=stamp+pd.Timedelta(minutes=j),entry_i=i,signal_i=k) for i,j,k in [(0,5,0),(5,7,1),(6,8,2)]])
    accepted,rejected=admit(q);ids,counts=replay(q)
    assert accepted.signal_i.tolist()==[0,2] and counts=={'token_busy':1}
    assert ids==list(accepted[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
