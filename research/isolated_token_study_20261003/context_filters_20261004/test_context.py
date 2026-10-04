import unittest
import numpy as np
import pandas as pd
from run_context import pivots,structure,zone_states,assess_zones,DAY_NS,base

def frame(n=40,freq='h'):
    return pd.DataFrame({'open':100.,'high':101.,'low':99.,'close':100.,'volume':1.},index=pd.date_range('2024-01-01',periods=n,freq=freq,tz='UTC'))
class ContextChecks(unittest.TestCase):
    def test_pivot_delay_and_ties(self):
        b=frame(8);b['high']=[1,2,5,2,1,2,2,1];h,l=pivots(b);self.assertFalse(h[2]);self.assertTrue(h[4]);b.iloc[3,b.columns.get_loc('high')]=5;self.assertFalse(pivots(b)[0].any())
    def test_structure(self):
        b=frame(13);b['high']=[1,2,5,2,1,2,6,2,1,3,7,2,1];b['low']=[0,-1,-2,-1,0,-1,-1.5,-1,0,-1,-1,-.5,0]
        s=structure(b);self.assertEqual(s.iloc[7],0);self.assertEqual(s.iloc[8],1)
        z=b.copy();z['high']=-b.low;z['low']=-b.high;self.assertEqual(structure(z).iloc[8],-1)
    def test_zone_creation_invalidation(self):
        b=frame();b.iloc[16,b.columns.get_loc('low')]=95;z=zone_states(b);self.assertFalse(z[17][0]);self.assertEqual(len(z[18][0]),1);self.assertLess(z[18][0][0][0],95);self.assertGreater(z[18][0][0][1],95)
        b.iloc[20,b.columns.get_loc('close')]=90;z=zone_states(b);self.assertFalse(z[20][0]);self.assertFalse(z[21][0])
    def test_zone_expiry(self):
        b=frame(800);b.iloc[16,b.columns.get_loc('low')]=95;z=zone_states(b);self.assertTrue(z[18+720][0]);self.assertFalse(z[18+721][0])
    def test_rejection_and_target_room(self):
        ts=pd.Timestamp('2024-01-02',tz='UTC').value;d=(98.,99.,ts,ts);s=(102.,103.,ts,ts)
        b=pd.Series({'open':98.5,'high':100.5,'low':98.,'close':100.})
        a,block=assess_zones(((d,),(s,)),1,b,100.,.01,ts);self.assertEqual(a,d);self.assertIsNone(block)
        self.assertEqual(assess_zones(((d,),(s,)),1,b,100.,.025,ts)[1],s)
        bad=b.copy();bad['close']=98.7;self.assertIsNone(assess_zones(((d,),()),1,bad,100.,.02,ts)[0])
        self.assertIsNone(assess_zones(((d,),()),1,b,100.,.02,ts+31*DAY_NS)[0])
    def test_short_geometry(self):
        z=(101.,102.,0,0);op=(97.,98.,0,0);b=pd.Series({'open':102.,'high':102.5,'low':99.,'close':100.})
        a,block=assess_zones(((op,),(z,)),-1,b,100.,.03,0);self.assertEqual(a,z);self.assertEqual(block,op)
    def test_future_context_independence(self):
        rng=np.random.default_rng(7);b=frame(300);b['close']=100+np.cumsum(rng.normal(size=300));b['high']=b.close+1;b['low']=b.close-1;b['open']=b.close
        s=structure(b);z=zone_states(b);alter=b.copy();alter.iloc[220:,:4]*=2
        pd.testing.assert_series_equal(s.iloc[:220],structure(alter).iloc[:220]);self.assertEqual(z[:220],zone_states(alter)[:220])
    def test_empty_execution(self):
        b=frame(3,'min');t=base.Tape(b,pd.DataFrame({'funding_rate':[]},index=pd.DatetimeIndex([],tz='UTC')))
        r=pd.DataFrame([t.raw(0,1,.02,3,3)]).iloc[:0];v=t.cost(base.chronological(r),1,.001);self.assertEqual(base.score(v)['n'],0);self.assertEqual(t.mtm(v,1,.001,0,3),0)

if __name__=='__main__':unittest.main()
