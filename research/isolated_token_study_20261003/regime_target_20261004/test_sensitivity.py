import unittest
import numpy as np
import pandas as pd
from run_study import Tape, BarrierTree, chronological, decisions

def candles(o,h=None,l=None,c=None):
    o=np.asarray(o,float);return pd.DataFrame({'open':o,'high':o if h is None else h,'low':o if l is None else l,'close':o if c is None else c,'volume':1.},index=pd.date_range('2024-01-01',periods=len(o),freq='min',tz='UTC'))
def funding():return pd.DataFrame({'funding_rate':[]},index=pd.DatetimeIndex([],tz='UTC'))
def scalar(t,i,side,target,end,regime):
    ep=t.o[i];stop=ep*(1-side*.01);tp=ep*(1+side*target)
    for j in range(i,end):
        if j==regime:
            if side*(t.o[j]-stop)<=0:return j,t.o[j],'stop'
            if side*(t.o[j]-tp)>=0:return j,tp,'target'
            return j,t.o[j],'regime'
        stophit=t.l[j]<=stop if side==1 else t.h[j]>=stop
        targethit=t.h[j]>=tp if side==1 else t.l[j]<=tp
        if stophit:return j,min(stop,t.o[j]) if side==1 else max(stop,t.o[j]),'stop'
        if targethit:return j,tp,'target'
    return end-1,t.cl[end-1],'boundary_mtm'

class Checks(unittest.TestCase):
    def test_tree_random(self):
        rng=np.random.default_rng(8);a=rng.normal(size=333)
        for minimum in (False,True):
            tree=BarrierTree(a,minimum)
            for _ in range(300):
                i=int(rng.integers(0,330));end=int(rng.integers(i+1,334));level=float(rng.normal());hits=np.flatnonzero(a[i:end]<=level if minimum else a[i:end]>=level)
                want=i+hits[0] if len(hits) else end;self.assertEqual(tree.first(i,end,level),want)
    def test_scalar_random_execution(self):
        rng=np.random.default_rng(97)
        for _ in range(100):
            o=100*np.exp(np.cumsum(rng.normal(0,.002,400)));c=candles(o,o*(1+rng.uniform(0,.005,400)),o*(1-rng.uniform(0,.005,400)))
            t=Tape(c,funding())
            for side in (-1,1):
                for target in (.01,.025):
                    for regime in (400,80):
                        r=t.raw(10,side,target,350,min(regime,350));s=scalar(t,10,side,target,350,min(regime,350))
                        self.assertEqual((r['exit_i'],r['reason']),(s[0],s[2]));self.assertAlmostEqual(r['quote'],s[1],12)
    def test_open_regime_precedes_later_stop(self):
        t=Tape(candles([100,100],[100,105],[100,95]),funding());r=t.raw(0,1,.02,2,1)
        self.assertEqual(r['reason'],'regime');self.assertEqual(r['quote'],100)
    def test_same_bar_stop_first_gap(self):
        t=Tape(candles([100,97],[100,105],[100,96]),funding());r=t.raw(0,1,.02,2,2)
        self.assertEqual(r['reason'],'stop');self.assertTrue(r['ambiguous']);self.assertEqual(r['quote'],97)
    def test_no_holding_cap_and_boundary(self):
        o=np.full(3001,100.);o[-1]=103;t=Tape(candles(o),funding());r=t.raw(0,1,.02,len(o),len(o));self.assertEqual(r['exit_i'],3000);self.assertEqual(r['reason'],'target')
        r=t.raw(0,1,.05,len(o),len(o));self.assertEqual(r['reason'],'boundary_mtm')
    def test_funding_open_close_and_fees(self):
        c=candles([100]*4);f=pd.DataFrame({'funding_rate':[.001,.002]},index=c.index[[1,2]]);t=Tape(c,f)
        for side in (-1,1):
            for mode in ('open','close','bar'):
                raw=pd.DataFrame([{'entry_i':0,'exit_i':1,'quote':100.,'reason':'regime','ambiguous':False,'fund_mode':mode}]);a=t.cost(raw,side,.001).iloc[0];ep=100*(1+side*.001);xp=100*(1-side*.001)
                fund=(.1 if mode=='open' else .3)*side/ep
                if mode=='bar':fund=max(.1*side/ep,.3*side/ep)
                self.assertAlmostEqual(a.funding,fund);self.assertAlmostEqual(a.net_return,side*(xp/ep-1)-.00055*(1+xp/ep)-fund)
    def test_chronological_skip(self):
        raw=pd.DataFrame({'entry_i':[0,2,5,6],'exit_i':[5,3,8,9]});self.assertEqual(chronological(raw).entry_i.tolist(),[0,6])
    def test_mtm_sees_unrealized_drawdown(self):
        t=Tape(candles([100,99.5,100]),funding());r=pd.DataFrame([t.raw(0,1,.02,3,3)]);a=t.cost(r,1,0)
        self.assertGreater(t.mtm(a,1,0,0,3),.005)
    def test_future_features_and_clock(self):
        rng=np.random.default_rng(2);o=100*np.exp(np.cumsum(rng.normal(.00001,.0003,60000)));c=candles(o,o*1.0001,o*.9999);cut=57000
        for tf in (5,15,60):
            a,r=decisions(c,tf);alter=c.copy();alter.iloc[cut:,:4]*=2;b,q=decisions(alter,tf)
            for side in (-1,1):
                np.testing.assert_array_equal(a[side][a[side]<=cut],b[side][b[side]<=cut]);np.testing.assert_array_equal(r[side][r[side]<=cut],q[side][q[side]<=cut]);self.assertTrue(np.all(a[side]%tf==0))

if __name__=='__main__':unittest.main()
