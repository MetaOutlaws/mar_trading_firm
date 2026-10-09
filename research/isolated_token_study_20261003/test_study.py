"""Synthetic checks, not historical market results."""
import unittest
import numpy as np
import pandas as pd
from study import Tape,signals,audit,opportunity
class StudyTests(unittest.TestCase):
    def tape(self,n=8):
        ix=pd.date_range('2025-01-01',periods=n,freq='min',tz='UTC')
        return pd.DataFrame({'open':100.,'high':100.,'low':100.,'close':100.,'volume':1.},index=ix),pd.DataFrame({'funding_rate':[]},index=pd.DatetimeIndex([],tz='UTC'))
    def trade(self,c,f,side=1,slip=0,times=None):
        return Tape(c,f).run(c.index[:1] if times is None else times,side,.03,.01,slip,c.index[0],c.index[-1]+pd.Timedelta(minutes=1),holding=4)
    def test_ambiguous_bar_stop_first(self):
        c,f=self.tape(); c.iloc[0,:4]=[100,104,98,100]; r=self.trade(c,f).iloc[0]
        self.assertEqual(r.reason,'stop'); self.assertTrue(r.ambiguous); self.assertAlmostEqual(r.exit_price,99)
    def test_long_gap_stop(self):
        c,f=self.tape(); c.iloc[1,:4]=[95,96,94,95]; r=self.trade(c,f).iloc[0]
        self.assertEqual(r.exit_price,95); self.assertEqual(r.reason,'stop')
    def test_short_gap_stop(self):
        c,f=self.tape(); c.iloc[1,:4]=[105,106,104,105]; r=self.trade(c,f,side=-1).iloc[0]
        self.assertEqual(r.exit_price,105); self.assertLess(r.net_return,0)
    def test_costs(self):
        c,f=self.tape(); a=self.trade(c,f).iloc[0]; b=self.trade(c,f,slip=.001).iloc[0]
        self.assertAlmostEqual(a.net_return,-.0011); self.assertLess(b.net_return,a.net_return)
    def test_funding_direction(self):
        # ns is the pandas 2 default; us is the pandas 3 date_range default.
        # Both must accrue. Comparing asi8 to Timestamp.value misses us events.
        c,_=self.tape()
        for unit in ('ns','us'):
            ix=c.index.as_unit(unit); cc=c.copy(); cc.index=ix
            f=pd.DataFrame({'funding_rate':[.001]},index=ix[1:2])
            self.assertAlmostEqual(self.trade(cc,f).iloc[0].funding,.001)
            self.assertAlmostEqual(self.trade(cc,f,side=-1).iloc[0].funding,-.001)
    def test_entry_funding_excluded(self):
        c,f=self.tape(); f=pd.DataFrame({'funding_rate':[.001]},index=c.index[:1])
        self.assertEqual(self.trade(c,f).iloc[0].funding,0)
    def test_nonoverlap(self):
        c,f=self.tape(); r=self.trade(c,f,times=c.index)
        self.assertEqual(len(r),2); self.assertGreater(r.entry.iloc[1],r.exit_bar.iloc[0])
    def test_boundary_purge(self):
        c,f=self.tape(); self.assertTrue(self.trade(c,f,times=c.index[-2:]).empty)
    def test_no_future_signal_leak(self):
        c,f=self.tape(60*48); rng=np.random.default_rng(43)
        prices=100*np.exp(np.cumsum(rng.normal(0,.001,len(c))))
        c['open']=prices; c['close']=prices; c['high']=prices*1.002; c['low']=prices*.998
        cutoff=c.index[60*30]; changed=c.copy(); changed.loc[changed.index>=cutoff,['open','high','low','close']]*=2
        a=signals(c); b=signals(changed)
        for k in a: self.assertTrue(a[k][a[k]<=cutoff].equals(b[k][b[k]<=cutoff]))
    def test_incomplete_signal_bar(self):
        c,f=self.tape(14); self.assertTrue(all(len(v)==0 for v in signals(c).values()))
    def test_missing_data_blocks(self):
        c,f=self.tape()
        with self.assertRaisesRegex(ValueError,'Missing'): audit(c,f)
    def test_time_exit(self):
        c,f=self.tape(); c.iloc[3,:4]=[100.5,100.5,100.5,100.5]; r=self.trade(c,f).iloc[0]
        self.assertEqual(r.reason,'time'); self.assertEqual(r.exit_price,100.5)
    def test_opportunity_tie_is_not_a_win(self):
        c,f=self.tape(60); c.iloc[1,:4]=[100,104,98,100]
        windows,summary=opportunity(c)
        r=windows.loc[(windows.horizon_h==1)&(windows.side==1)].iloc[0]
        self.assertTrue(r.reach_3pct)
        self.assertFalse(r['target_3_before_stop_1'])
    def test_ambiguous_exit_funding_uses_worse_case(self):
        c,_=self.tape()
        for unit in ('ns','us'):
            ix=c.index.as_unit(unit); cc=c.copy(); cc.index=ix
            cc.iloc[0,:4]=[100,104,100,103]
            f=pd.DataFrame({'funding_rate':[.001]},index=ix[1:2])
            r=self.trade(cc,f).iloc[0]
            self.assertEqual(r.reason,'target'); self.assertAlmostEqual(r.funding,.001)
if __name__=='__main__': unittest.main(verbosity=2)
