"""Independent scalar oracle and adversarial fixtures, not market performance tests."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import study

def scalar(c,f,side,target,stop,slip,holding):
    entry=c.index[0]; ep=float(c.open.iloc[0])*(1+side*slip)
    target_price=ep*(1+side*target); stop_price=ep*(1-side*stop)
    reason='time'; k=holding-1
    for j in range(holding):
        row=c.iloc[j]
        stopped=row.low<=stop_price if side==1 else row.high>=stop_price
        won=row.high>=target_price if side==1 else row.low<=target_price
        if stopped:
            k=j; reason='stop'; q=min(stop_price,row.open) if side==1 else max(stop_price,row.open); break
        if won: k=j; reason='target'; q=target_price; break
    else: q=float(c.close.iloc[k])
    xp=q*(1-side*slip)
    def funding(until):
        total=0.
        for ts,row in f.iterrows():
            if entry<ts<=until:
                proxy=float(c.loc[:ts.floor('min')].open.iloc[-1])
                total+=side*float(row.funding_rate)*proxy/ep
        return total
    early=funding(c.index[k]); late=funding(c.index[k]+pd.Timedelta(minutes=1))
    fc=late if reason=='time' else max(early,late)
    fees=study.FEE*(1+xp/ep)
    return k,reason,side*(xp-ep)/ep-fees-fc,fc

class IndependentTests(unittest.TestCase):
    def candles(self,n=20):
        ix=pd.date_range('2025-01-01',periods=n,freq='min',tz='UTC')
        return pd.DataFrame(dict(open=np.full(n,100.),high=np.full(n,100.),low=np.full(n,100.),close=np.full(n,100.),volume=np.ones(n)),index=ix)
    def test_800_randomized_oracle_cases(self):
        count=0
        for seed in range(100):
            rng=np.random.default_rng(seed); c=self.candles()
            opens=100*np.exp(np.cumsum(rng.normal(0,.006,len(c))))
            closes=opens*np.exp(rng.normal(0,.002,len(c)))
            c['open']=opens;c['close']=closes
            c['high']=np.maximum(opens,closes)*(1+rng.uniform(0,.008,len(c)))
            c['low']=np.minimum(opens,closes)*(1-rng.uniform(0,.008,len(c)))
            f=pd.DataFrame({'funding_rate':rng.uniform(-.003,.003,4)},index=c.index[[0,5,10,15]])
            for side in (1,-1):
                for target in (.01,.03):
                    for slip in (0,.001):
                        expected=scalar(c,f,side,target,.01,slip,16)
                        got=study.Tape(c,f).run(c.index[:1],side,target,.01,slip,c.index[0],c.index[-1],holding=16).iloc[0]
                        self.assertEqual(got.reason,expected[1]);self.assertEqual(got.holding_minutes,expected[0]+1)
                        self.assertAlmostEqual(got.net_return,expected[2],places=12)
                        self.assertAlmostEqual(got.funding,expected[3],places=12)
                        count+=1
        self.assertEqual(count,800)
    def test_microsecond_and_nanosecond_indexes_agree(self):
        c=self.candles(); f=pd.DataFrame({'funding_rate':[.001]},index=c.index[5:6])
        ns=study.Tape(c,f).run(c.index[:1],1,.03,.01,0,c.index[0],c.index[-1],holding=10)
        c.index=c.index.as_unit('us');f.index=f.index.as_unit('us')
        us=study.Tape(c,f).run(c.index[:1],1,.03,.01,0,c.index[0],c.index[-1],holding=10)
        self.assertAlmostEqual(ns.net_return.iloc[0],us.net_return.iloc[0],places=12)
    def test_funding_audit_counts_prestart_event(self):
        start=pd.Timestamp('2025-01-01',tz='UTC');end=start+pd.Timedelta(days=1)
        c=self.candles(1440)
        f=pd.DataFrame({'funding_rate':.0001},index=pd.date_range(start-pd.Timedelta(hours=8),end-pd.Timedelta(hours=8),freq='8h'))
        with patch.object(study,'START',start),patch.object(study,'END',end):
            self.assertEqual(study.audit(c,f)['funding_events'],4)
        self.assertEqual(len(f.loc[f.index>=start]),3)
    def test_document_short_cadence_audit_blind_spot(self):
        # A 2h funding tape missing its 04:00 event still passes the <=8h check.
        # This demonstrates a coverage-check weakness, NOT a confirmed data gap.
        start=pd.Timestamp('2025-01-01',tz='UTC');end=start+pd.Timedelta(days=1)
        c=self.candles(1440)
        stamps=pd.date_range(start,end-pd.Timedelta(hours=2),freq='2h').delete(2)
        f=pd.DataFrame({'funding_rate':.0001},index=stamps)
        with patch.object(study,'START',start),patch.object(study,'END',end):
            self.assertEqual(study.audit(c,f)['funding_events'],11)
        self.assertNotIn(start+pd.Timedelta(hours=4),f.index)
    def test_flat_market_loses_friction_both_directions(self):
        c=self.candles();f=pd.DataFrame({'funding_rate':[]},index=pd.DatetimeIndex([],tz='UTC'))
        for side in (1,-1):
            got=study.Tape(c,f).run(c.index[:1],side,.03,.01,.0005,c.index[0],c.index[-1],holding=10)
            self.assertLess(got.net_return.iloc[0],-.00209)
if __name__=='__main__':unittest.main(verbosity=2)
