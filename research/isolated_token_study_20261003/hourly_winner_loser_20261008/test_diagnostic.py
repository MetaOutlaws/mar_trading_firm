from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from diagnostic_rule import FEATURES,auc,mask,nominate,path_anatomy
from entry_context import context,verify_indicators

def sample():
    n=60
    q=pd.DataFrame({f:np.zeros(n) for f in FEATURES})
    q['volume_ratio']=np.arange(1,n+1,dtype=float)
    q['net_return']=np.where(np.arange(n)<30,.025,-.02)
    q['partition']='historical';q['symbol']=np.resize(['BTCUSDT','ETHUSDT','SOLUSDT'],n)
    q['side']=np.resize([1,-1],n);q['reason']=np.where(q.net_return>0,'target','stop')
    return q

def minutes(n=200):
    ix=pd.date_range('2022-01-01',periods=n*60,freq='min',tz='UTC')
    x=100+np.arange(len(ix))*.0005+np.sin(np.arange(len(ix))*.011)
    return pd.DataFrame(dict(open=x,high=x+.1,low=x-.1,close=x+.01,volume=10+np.cos(np.arange(len(ix))*.009)),index=ix)

def test_auc_ties():
    assert auc([1,2,2,3],[False,True,False,True])==.875
    assert auc([1,1],[False,True])==.5
    assert np.isnan(auc([1,2],[True,True]))

def test_median_equality_and_complement():
    q=pd.DataFrame({'x':[1,2,2,3]})
    assert mask(q,'x',2,'lower').tolist()==[True,True,True,False]
    assert (mask(q,'x',2,'upper')==~mask(q,'x',2,'lower')).all()

def test_historical_nomination_does_not_read_later_outcomes():
    q=sample();_,s=nominate(q)
    later=q.assign(partition='evaluation',net_return=-q.net_return,volume_ratio=1e6)
    _,both=nominate(pd.concat([q,later],ignore_index=True))
    assert s==both and s['feature']=='volume_ratio' and s['direction']=='lower'
    assert s['threshold']==30.5 and s['retained']==30 and s['historical_n']==60

def test_no_eligible_lead_is_not_relaxed():
    q=sample();q['net_return']=-.01
    _,s=nominate(q);assert s['status']=='none'

@pytest.mark.parametrize('side',[1,-1])
def test_path_omits_exit_bar_extremes(side):
    c=pd.DataFrame({'high':[101,102.5,200],'low':[99,97.5,1]})
    r=SimpleNamespace(entry_i=0,exit_i=2,fund_mode='open',quote=98 if side==1 else 102,entry_price=100,side=side)
    a=path_anatomy(c,r)
    assert np.isclose(a['mfe'],.025) and np.isclose(a['mae'],.025) and a['holding_minutes']==2
    c.loc[2]=[500,.1];assert path_anatomy(c,r)==a

@pytest.mark.parametrize('side',[1,-1])
def test_path_includes_observed_exit_quote(side):
    c=pd.DataFrame({'high':[101,101],'low':[99,99]})
    r=SimpleNamespace(entry_i=0,exit_i=1,fund_mode='open',quote=95 if side==1 else 105,entry_price=100,side=side)
    assert np.isclose(path_anatomy(c,r)['mae'],.05)

@pytest.mark.parametrize('mode',['bar','close'])
def test_reject_ambiguous_clock_for_primary_anatomy(mode):
    with pytest.raises(ValueError):
        path_anatomy(pd.DataFrame(),SimpleNamespace(entry_i=0,exit_i=1,fund_mode=mode))

def test_hourly_prefix_and_future_perturbation():
    c=minutes();cut=c.index[120*60];a=context(c);b=context(c[c.index<cut])
    pd.testing.assert_frame_equal(b,a.loc[b.index])
    changed=c.copy();changed.loc[changed.index>=cut,['open','high','low','close']]*=2
    future=context(changed);pd.testing.assert_frame_equal(b,future.loc[b.index])
    assert a.loc[cut,'last_input_minute']==cut-pd.Timedelta(minutes=1)
    assert a.loc[cut,'close']==c.loc[cut-pd.Timedelta(minutes=1),'close']

def test_independent_indicator_recursions():
    c=minutes();q=context(c);records=pd.DataFrame({'entry':[q.index[120],q.index[160],q.index[190]]})
    assert verify_indicators(c,q,records)==12

def test_missing_feature_rejected():
    with pytest.raises(ValueError):auc([1,np.nan],[True,False])
