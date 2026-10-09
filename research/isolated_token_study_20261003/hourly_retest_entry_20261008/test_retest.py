import numpy as np
import pandas as pd
import pytest
from entry_rule import select_entry,sequential_entry

def path():
    return np.full(65,102.),np.full(65,101.),np.full(65,101.5)

@pytest.mark.parametrize('side',[1,-1])
def test_touch_equality_same_bar_and_long_short_symmetry(side):
    h,l,c=path();l[0]=100
    if side==-1:h,l,c=200-l,200-h,200-c
    p=select_entry(h,l,c,0,65,side,100)
    assert p==sequential_entry(h,l,c,0,65,side,100)
    assert p['planned_entry_i']==1 and p['touch_i']==0 and p['confirm_i']==0

def test_strict_reclaim_and_armed_state():
    h,l,c=path();l[0]=99;c[:3]=100
    p=select_entry(h,l,c,0,65,1,100)
    assert p['touch_i']==0 and p['confirm_i']==3 and p['planned_entry_i']==4

def test_last_eligible_fill_and_too_late():
    h,l,c=path();l[59]=100
    assert select_entry(h,l,c,0,65,1,100)['planned_entry_i']==60
    l[59]=101;l[60]=100
    assert select_entry(h,l,c,0,65,1,100)['entry_status']=='no_retest'

def test_no_retest_and_no_reclaim():
    h,l,c=path()
    assert select_entry(h,l,c,0,65,1,100)['entry_status']=='no_retest'
    l[:]=99;c[:]=100
    assert select_entry(h,l,c,0,65,1,100)['entry_status']=='retest_no_reclaim'

def test_endpoint_fill_excluded_but_earlier_fill_valid():
    h,l,c=path();l[4]=100
    p=select_entry(h,l,c,0,5,1,100)
    assert p['entry_status']=='endpoint_censored' and p['confirm_i']==4 and p['planned_entry_i']==-1
    l[3]=100
    assert select_entry(h,l,c,0,5,1,100)['planned_entry_i']==4

def test_partial_window_censored_without_touch():
    h,l,c=path()
    assert select_entry(h,l,c,0,60,1,100)['entry_status']=='endpoint_censored'

def test_future_and_fill_bar_ohlc_cannot_change_selection():
    h,l,c=path();l[5]=100
    p=select_entry(h,l,c,0,65,1,100)
    h[6:]=1e6;l[6:]=.01;c[6:]=.02
    assert p==select_entry(h,l,c,0,65,1,100)
    assert p==select_entry(h[:7],l[:7],c[:7],0,7,1,100)

def test_gap_through_then_later_reclaim_and_no_price_barrier_cancellation():
    h,l,c=path();h[0]=99;l[0]=90;c[0]=91;c[1]=101.5
    p=select_entry(h,l,c,0,65,1,100)
    assert p['planned_entry_i']==2

def test_causality_random_paths():
    rng=np.random.default_rng(721)
    for side in [-1,1]:
        for _ in range(50):
            c=100+rng.normal(size=90);h=c+rng.uniform(0,1,90);l=c-rng.uniform(0,1,90)
            p=select_entry(h,l,c,5,90,side,100)
            assert p==sequential_entry(h,l,c,5,90,side,100)

def test_admission_at_fill_and_exit_minute_occupied():
    from run_retest import admission
    utc=lambda m:pd.Timestamp('2025-01-01',tz='UTC')+pd.Timedelta(minutes=m)
    rows=[dict(symbol='BTCUSDT',tf=60,side=1,rank=1,signal_i=0,signal_time=utc(0),entry_i=1,entry=utc(1),exit_bar=utc(3)),
          dict(symbol='BTCUSDT',tf=60,side=1,rank=1,signal_i=1,signal_time=utc(1),entry_i=3,entry=utc(3),exit_bar=utc(5)),
          dict(symbol='BTCUSDT',tf=60,side=1,rank=1,signal_i=2,signal_time=utc(2),entry_i=4,entry=utc(4),exit_bar=utc(6))]
    t,r=admission(pd.DataFrame(rows))
    assert t.entry_i.tolist()==[1,4] and r.signal_i.tolist()==[1]

@pytest.mark.parametrize('side,boundary',[(0,100),(1,0),(1,float('nan'))])
def test_bad_geometry(side,boundary):
    h,l,c=path()
    with pytest.raises(ValueError):select_entry(h,l,c,0,65,side,boundary)
