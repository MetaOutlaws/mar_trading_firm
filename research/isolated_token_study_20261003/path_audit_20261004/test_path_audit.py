import unittest
import numpy as np
import pandas as pd
from run_audit import Tape, eligible_controls, H, interval
from entry_trailing_20261004.execution import fixed_horizon_trade, ExitSpec
from entry_trailing_20261004.features import bars_15m, compute_features

def frame(n=H):
    ix=pd.date_range('2024-01-01',periods=n,freq='min',tz='UTC')
    return pd.DataFrame({'open':100.,'high':100.,'low':100.,'close':100.,'volume':1.},index=ix)
def funds():return pd.DataFrame({'funding_rate':[]},index=pd.DatetimeIndex([],tz='UTC'))

class TestPaths(unittest.TestCase):
    def test_same_bar_adverse_first(self):
        c=frame();c.iloc[0,c.columns.get_loc('high')]=105.;c.iloc[0,c.columns.get_loc('low')]=98.
        d=Tape(c,funds()).diagnostic(0,1,0)
        self.assertGreater(d['peak_hypothetical_net'],.04);self.assertFalse(d['reach_1'])
    def test_peak_precedes_stop(self):
        c=frame();c.iloc[0,c.columns.get_loc('high')]=102.;c.iloc[1,c.columns.get_loc('low')]=98.
        d=Tape(c,funds()).diagnostic(0,1,0)
        self.assertTrue(d['reach_1']);self.assertTrue(d['positive_peak_ended_loss'])
    def test_control_exclusion(self):
        p=np.array([0,1,239,240,241,479,480,481,719,720,960]);real=np.array([240,720])
        np.testing.assert_array_equal(eligible_controls(p,real),[0,480,960])
    def test_archive_endpoint_and_scalar_peak(self):
        rng=np.random.default_rng(44)
        for side in (-1,1):
            for slip in (0,.001):
                c=frame();prices=100*np.exp(np.cumsum(rng.normal(0,.001,H)))
                c['open']=prices;c['close']=prices*1.0001;c['high']=prices*1.002;c['low']=prices*.998
                f=pd.DataFrame({'funding_rate':[.0001,-.0002]},index=c.index[[60,180]])
                tape=Tape(c,f);d=tape.diagnostic(0,side,slip)
                end=fixed_horizon_trade(c.index,tape.o,tape.h,tape.l,tape.cl,0,side,slip,tape.book,H)
                self.assertAlmostEqual(d['net_return'],end['net_return'],12)
                ep=c.open.iloc[0]*(1+side*slip);vals=[]
                for j in range(H):
                    quote=c.high.iloc[j] if side==1 else c.low.iloc[j];xp=quote*(1-side*slip)
                    funding=tape.book.charge(side,c.index[0],c.index[j],ep,1,False)
                    vals.append(side*(xp-ep)/ep-.00055*(1+xp/ep)-funding)
                self.assertAlmostEqual(d['peak_hypothetical_net'],max(vals),12)
    def test_boundaries_and_flat_cost(self):
        tape=Tape(frame(),funds());self.assertLess(tape.diagnostic(0,-1,.001)['peak_hypothetical_net'],0)
        with self.assertRaises(AssertionError):tape.diagnostic(1,1,0)
    def test_feature_future_perturbation(self):
        c=frame(4000);c['close']=100+np.sin(np.arange(len(c))/100);c['high']=c.close+1;c['low']=c.close-1
        cut=c.index[2500];a=compute_features(bars_15m(c))
        c.loc[c.index>=cut,['open','high','low','close']]*=2
        b=compute_features(bars_15m(c))
        pd.testing.assert_frame_equal(a.loc[a.index<=cut],b.loc[b.index<=cut])
    def test_gap_after_trail_activation(self):
        c=frame(3);c.iloc[0,c.columns.get_loc('high')]=102.;c.iloc[1]=[98,98,98,98,1]
        t=Tape(c,funds());r=t.execute(0,1,0,ExitSpec('trail',activation_pct=.01,trail_pct=.008,holding=3),None)
        self.assertEqual(r['exit_i'],1);self.assertEqual(r['exit_price'],98)
    def test_interval_constant(self):
        lo,hi=interval(np.ones(H)*.1,frame().index);self.assertAlmostEqual(lo,.1);self.assertAlmostEqual(hi,.1)

if __name__=='__main__':unittest.main()
