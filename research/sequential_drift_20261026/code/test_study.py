import unittest
import numpy as np
from run_study import cusum, features, raw_path, economics

class StudyTests(unittest.TestCase):
    def test_isolated_shock_bounded(self):
        self.assertEqual(cusum(np.array([20.,0.,0.]),3.)[0].tolist(),[0,0,0])
        self.assertEqual(cusum(np.array([20.,0.,0.]),np.inf)[0].tolist(),[1,0,0])
    def test_sustained_and_reset(self):
        self.assertEqual(cusum(np.array([3.,3.,0.,3.,3.]),3.)[0].tolist(),[0,1,0,0,1])
    def test_short_symmetry(self):
        z=np.array([3.,3.,-3.,-3.,2.,-2.])
        np.testing.assert_array_equal(cusum(z,3.)[0],-cusum(-z,3.)[0])
    def test_missing_resets(self):
        self.assertEqual(cusum(np.array([3.,np.nan,3.,0.]),3.)[0].tolist(),[0,0,0,0])
    def test_causal_vol_and_prefix(self):
        rng=np.random.default_rng(12);hc=np.exp(np.cumsum(rng.normal(0,.01,2401)))
        a=features(hc,3.);b=features(hc[:1921],3.)
        for x,y in zip(a,b):np.testing.assert_allclose(x[:len(y)],y,equal_nan=True)
        altered=hc.copy();altered[80*24:]*=4
        self.assertAlmostEqual(features(altered,3.)[1][80],a[1][80])
    def test_stop_next_quote_gap(self):
        p=np.full(5000,100.);p[1450]=89;p[1451]=85
        x,why=raw_path(p,np.ones(len(p),bool),np.zeros(4),np.ones(4),1,1,90,1)
        self.assertEqual((x,why),(1451,'stop'))
    def test_opposite_signal(self):
        p=np.full(5000,100.);sig=np.array([0,1,-1,0]);x,r=raw_path(p,np.ones(len(p),bool),sig,np.ones(4),1,1,90,1)
        self.assertEqual((x,r),(2881,'opposite_signal'))
    def test_censor_does_not_forward_fill(self):
        p=np.full(5000,100.);p[1500]=np.nan
        self.assertEqual(raw_path(p,np.ones(len(p),bool),np.zeros(4),np.ones(4),1,1,90,1),(1499,'data_censor'))
    def test_desk_costs_two_legs(self):
        v=economics(1,100,100,90,.00255,.00255,'stop',0)
        self.assertAlmostEqual(v['net'],1000*(99.745/100.255-1)-.00055*1000*(1+99.745/100.255))
    def test_funding_sign(self):
        for side in [-1,1]:
            a=economics(side,100,110,100-side*10,0,0,'terminal',2)
            b=economics(side,100,110,100-side*10,0,0,'terminal',0)
            self.assertAlmostEqual(a['net']-b['net'],-side*20)

if __name__=='__main__':unittest.main()
