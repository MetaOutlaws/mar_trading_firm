import numpy as np
import pandas as pd
from regime_rule import context,independent_at,policy_pass

def test_prior_hour_exclusion_and_independent_endpoint():
    index=pd.date_range('2025-01-01',periods=40,freq='h',tz='UTC')
    closes=pd.Series(np.arange(100.,140.),index=index)
    q=context(closes);assert q.efficiency24_before_signal.iloc[-1]==1
    changed=closes.copy();changed.iloc[-1]=10000
    assert context(changed).iloc[-1].equals(q.iloc[-1])
    minutes=pd.DataFrame({'close':np.repeat(closes.to_numpy(),60)},index=pd.date_range(index[0]-pd.Timedelta(hours=1),periods=2400,freq='min'))
    assert independent_at(minutes,index[-1])==q.efficiency24_before_signal.iloc[-1]

def test_flat_loweff_and_boundary_partition():
    index=pd.date_range('2025-01-01',periods=40,freq='h',tz='UTC')
    q=context(pd.Series(100.,index=index));assert q.efficiency24_before_signal.iloc[-1]==0 and not q.directional.iloc[-1]
    assert q.efficiency24_before_signal.iloc[:25].isna().all()
    assert policy_pass([False,True,False,True],[True,True,False,False],'directional').tolist()==[False,True,True,True]
    assert policy_pass([False,True,False,True],[True,True,False,False],'loweff').tolist()==[True,True,False,True]
