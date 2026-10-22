import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import collect_funding_history as f

class FundingTests(unittest.TestCase):
    def payload(self,rows):return {'retCode':0,'result':{'category':'linear','list':rows}}
    def row(self,t,rate='0.0001',symbol='BTCUSDT'):
        return {'symbol':symbol,'fundingRateTimestamp':str(t),'fundingRate':rate}
    def test_signed_rate_and_order(self):
        x=f.validate(self.payload([self.row(f.BEGIN+1000,'-0.001'),self.row(f.BEGIN)]),'BTCUSDT',f.BEGIN,f.BEGIN+2000)
        self.assertEqual(x,[(f.BEGIN,'0.0001'),(f.BEGIN+1000,'-0.001')])
    def test_wrong_symbol(self):
        with self.assertRaises(ValueError):f.validate(self.payload([self.row(f.BEGIN,symbol='ETHUSDT')]),'BTCUSDT',f.BEGIN,f.BEGIN+2000)
    def test_duplicates_future_and_nan(self):
        cases=[[self.row(f.BEGIN)]*2,[self.row(f.END)],[self.row(f.BEGIN,'nan')]]
        for rows in cases:
            with self.subTest(rows=rows),self.assertRaises(ValueError):f.validate(self.payload(rows),'BTCUSDT',f.BEGIN,f.BEGIN+2000)
    def test_month_pagination_and_resume(self):
        lo,hi=f.month_bounds('2022-01');allrows=[(t,'0.0001') for t in range(lo,hi,3600000)];calls=[]
        def page(symbol,a,b,rawdir):
            calls.append((a,b));return [x for x in allrows if a<=x[0]<b][-200:],{'mock':True}
        with tempfile.TemporaryDirectory() as d,patch.object(f,'get_page',side_effect=page),patch.object(f.time,'sleep'):
            root=Path(d);m=f.collect_month(root,'BTCUSDT','2022-01')
            self.assertEqual(m['coverage']['settlements'],744);self.assertEqual(len(calls),4)
            self.assertFalse(m['coverage']['matches_calendar_8h_grid'])
            self.assertFalse(m['coverage']['complete_verified'])
            count=len(calls);self.assertEqual(f.collect_month(root,'BTCUSDT','2022-01'),m);self.assertEqual(len(calls),count)
            (root/'funding/BTCUSDT/2022-01.csv.gz').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'checksum'):f.collect_month(root,'BTCUSDT','2022-01')
    def test_missing_grid_is_not_filled(self):
        stats=f.coverage([(f.BEGIN,'0.0001')],f.BEGIN,f.BEGIN+86400000)
        self.assertEqual(stats['settlements'],1);self.assertFalse(stats['matches_calendar_8h_grid'])
    def test_nonjson_rejected(self):
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return b'<html>Site Unavailable</html>'
        with tempfile.TemporaryDirectory() as d,patch.object(f.urllib.request,'urlopen',return_value=Response()):
            with self.assertRaisesRegex(ValueError,'non-JSON'):f.get_page('BTCUSDT',f.BEGIN,f.BEGIN+86400000,Path(d))
            self.assertEqual(list(Path(d).iterdir()),[])

if __name__=='__main__':unittest.main(verbosity=2)
