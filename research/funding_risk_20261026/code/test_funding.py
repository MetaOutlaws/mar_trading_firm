import unittest
import numpy as np
from run_funding import required_stop,levels,funding_path,FEE

class FundingTests(unittest.TestCase):
    def budget(self,E,q,stop,side,slip):
        exit=stop*(1-side*slip)
        return q*(side*(E-exit)+FEE*(E+exit))
    def test_initial_identity_all_costs(self):
        for side in [-1,1]:
            for a in [0,.002,.00255,.01]:
                E=100.;q=10.;stop=E-side*10;L=self.budget(E,q,stop,side,a)
                self.assertAlmostEqual(required_stop(E,q,L,side,a,0),stop)
    def test_net_budget_identity(self):
        for side in [-1,1]:
            for a in [0,.002,.00255,.01]:
                E=100.;q=10.;stop=E-side*10;L=self.budget(E,q,stop,side,a)
                for F in [0,20,-10,100]:
                    s=required_stop(E,q,L,side,a,F);xp=s*(1-side*a);net=side*q*(xp-E)-q*FEE*(E+xp)-F
                    self.assertAlmostEqual(net,-L)
    def test_credits_never_loosen(self):
        for side in [-1,1]:
            stop=100-side*10;L=self.budget(100,10,stop,side,.00255)
            a=levels(100,10,L,side,.00255,stop,np.array([0,10,5,-50,20.]))
            self.assertTrue((side*np.diff(a)>=-1e-12).all());self.assertAlmostEqual(a[1],a[2]);self.assertAlmostEqual(a[1],a[3])
    def setup_path(self):
        op=np.full(5000,100.);ok=np.ones(5000,bool);fc=np.zeros(5000);sig=np.zeros(4);sd=np.ones(4)*.05
        return op,ok,fc,sig,sd
    def test_one_minute_funding_availability_and_gap(self):
        op,ok,fc,sig,sd=self.setup_path();op[1450:1452]=91.;op[1452]=85.;fc[1450:]=91*.02
        x,r,d=funding_path(op,ok,fc,sig,sd,1,1,90,1,0,0)
        self.assertEqual((x,r,d['trigger']),(1452,'stop',1451));self.assertTrue(d['tightened_at_exit'])
    def test_existing_stop_can_exit_before_new_funding_stop(self):
        op,ok,fc,sig,sd=self.setup_path();op[1450]=89.;fc[1450:]=89*.02
        x,r,d=funding_path(op,ok,fc,sig,sd,1,1,90,1,0,0)
        self.assertEqual((x,r,d['trigger']),(1451,'stop',1450));self.assertFalse(d['tightened_at_exit'])
    def test_entry_funding_excluded(self):
        op,ok,fc,sig,sd=self.setup_path();fc[:]=50.
        x,r,d=funding_path(op,ok,fc,sig,sd,1,1,90,1,0,0)
        self.assertEqual(d['stop_updates'],0);self.assertAlmostEqual(d['stop_at_trigger'],90.)
    def test_closed_before_later_funding(self):
        op,ok,fc,sig,sd=self.setup_path();sig[2]=-1;fc[3000:]=200.
        x,r,d=funding_path(op,ok,fc,sig,sd,1,1,90,1,0,0)
        self.assertEqual((x,r),(2881,'opposite_signal'));self.assertEqual(d['stop_updates'],0)
    def test_stop_before_same_clock_opposite(self):
        op,ok,fc,sig,sd=self.setup_path();sig[2]=-1;op[2881]=89.
        x,r,d=funding_path(op,ok,fc,sig,sd,1,1,90,1,0,0)
        self.assertEqual((x,r),(2882,'stop'))
    def test_short_payment_tightens(self):
        op,ok,fc,sig,sd=self.setup_path();op[1450:1452]=109.;fc[1450:]=-109*.02
        x,r,d=funding_path(op,ok,fc,sig,sd,1,-1,110,1,0,0)
        self.assertEqual((x,r,d['trigger']),(1452,'stop',1451));self.assertLess(d['stop_at_trigger'],110)
    def test_prefix_invariance_of_stops(self):
        f=np.array([0,2,-1,3,8,4,9.]);L=self.budget(100,10,90,1,.00255)
        for n in range(1,len(f)):
            np.testing.assert_array_equal(levels(100,10,L,1,.00255,90,f)[:n],levels(100,10,L,1,.00255,90,f[:n]))
    def test_zero_funding_exactly_preserves_stop(self):
        for side in [-1,1]:
            for a in [0,.002,.00255,.01]:
                stop=100-side*10;L=self.budget(100,10,stop,side,a)
                np.testing.assert_array_equal(levels(100,10,L,side,a,stop,np.zeros(20)),np.full(20,stop))
    def test_missing_quote_is_censor(self):
        op,ok,fc,sig,sd=self.setup_path();op[1500]=np.nan
        x,r,_=funding_path(op,ok,fc,sig,sd,1,1,90,1,0,0);self.assertEqual((x,r),(1499,'data_censor'))
    def test_after_funding_gap_may_exceed_budget(self):
        E=100;q=10;L=self.budget(E,q,90,1,0);stop=required_stop(E,q,L,1,0,20)
        self.assertGreater(stop,90);actual=85;net=q*(actual-E)-q*FEE*(E+actual)-20
        self.assertLess(net,-L)

if __name__=='__main__':unittest.main()
