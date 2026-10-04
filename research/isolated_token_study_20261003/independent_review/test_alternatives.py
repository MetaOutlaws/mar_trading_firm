import sys,unittest
from pathlib import Path
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from alternative_study import pair_trade,continuation_features,residual_features
import study
class AlternativeTests(unittest.TestCase):
 def fixture(self,n=300):
  ix=pd.date_range('2024-01-01',periods=n,freq='min',tz='UTC')
  c=pd.DataFrame({'open':100.,'high':100.,'low':100.,'close':100.,'volume':1.},index=ix)
  f=pd.DataFrame({'funding_rate':[]},index=pd.DatetimeIndex([],tz='UTC'))
  return c,f
 def test_flat_pair_pays_both_legs(self):
  c,f=self.fixture();t=study.Tape(c,f)
  r=pair_trade(t,t,c.index[0],1,1,0,0,c.index[240])
  self.assertAlmostEqual(r['net_return'],-.0011)
  self.assertEqual(r['holding_minutes'],240)
 def test_equal_moves_cancel_beta_one(self):
  c,f=self.fixture();c.iloc[1:,0:4]=110;t=study.Tape(c,f)
  r=pair_trade(t,t,c.index[0],1,1,0,0,c.index[240])
  self.assertAlmostEqual(r['gross_return'],0)
 def test_joint_stop_on_minute_open(self):
  c,f=self.fixture();b=c.copy();c.iloc[10:,0:4]=97
  r=pair_trade(study.Tape(c,f),study.Tape(b,f),c.index[0],1,1,0,0,c.index[240])
  self.assertEqual(r['reason'],'stop');self.assertEqual(r['holding_minutes'],10)
  self.assertAlmostEqual(r['gross_return'],-.015)
 def test_two_leg_funding_cancels_equal_rates(self):
  c,f=self.fixture();f=pd.DataFrame({'funding_rate':[.001]},index=c.index[120:121]);t=study.Tape(c,f)
  r=pair_trade(t,t,c.index[0],1,1,0,0,c.index[240])
  self.assertAlmostEqual(r['funding'],0)
 def test_cost_stress_reduces_flat_pair(self):
  c,f=self.fixture();t=study.Tape(c,f)
  a=pair_trade(t,t,c.index[0],2,1,.0005,.0005,c.index[240]);b=pair_trade(t,t,c.index[0],2,1,.001,.001,c.index[240])
  self.assertLess(b['net_return'],a['net_return'])
 def test_features_do_not_use_future(self):
  c,f=self.fixture(60*1800);rng=np.random.default_rng(702)
  price=100*np.exp(np.cumsum(rng.normal(0,.001,len(c))))
  c['open']=price;c['close']=price;c['high']=price*1.001;c['low']=price*.999
  b=c.copy();b[['open','close','high','low']]*=np.exp(np.cumsum(rng.normal(0,.0003,len(c))))[:,None]
  cut=c.index[60*1600];changed=c.copy();changed.loc[changed.index>=cut,['open','high','low','close']]*=1.5
  a=continuation_features(c);x=continuation_features(changed)
  pd.testing.assert_frame_equal(a.loc[:cut],x.loc[:cut])
  a=residual_features(c,b);x=residual_features(changed,b)
  pd.testing.assert_frame_equal(a.loc[:cut],x.loc[:cut])
if __name__=='__main__':unittest.main(verbosity=2)
