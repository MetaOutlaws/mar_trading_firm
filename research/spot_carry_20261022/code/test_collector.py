"""Offline tests of data boundaries, failure handling and resumability."""
import csv,gzip,hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import collect_matched_history as c

class CollectorTests(unittest.TestCase):
    def payload(self,rows):
        return {'retCode':0,'result':{'category':'spot','symbol':'BTCUSDT','list':rows}}
    def row(self,t):return [str(t),'100','102','99','101','2','201']
    def test_reverse_response_sorted(self):
        rows=c.validate_response(self.payload([self.row(c.BEGIN+c.MINUTE),self.row(c.BEGIN)]),'spot','BTCUSDT',c.BEGIN,c.BEGIN+2*c.MINUTE)
        self.assertEqual([int(x[0]) for x in rows],[c.BEGIN,c.BEGIN+c.MINUTE])
    def test_wrong_market_rejected(self):
        with self.assertRaises(ValueError):c.validate_response(self.payload([]),'linear','BTCUSDT',c.BEGIN,c.BEGIN+c.MINUTE)
    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):c.validate_response(self.payload([self.row(c.BEGIN)]*2),'spot','BTCUSDT',c.BEGIN,c.BEGIN+c.MINUTE)
    def test_future_and_out_of_window_rejected(self):
        for t in [c.END,c.BEGIN-1,c.BEGIN+2*c.MINUTE]:
            with self.subTest(t=t),self.assertRaises(ValueError):c.validate_response(self.payload([self.row(t)]),'spot','BTCUSDT',c.BEGIN,c.BEGIN+c.MINUTE)
    def test_nonfinite_invalid_ohlc_rejected(self):
        for value in ['nan','-1','103']:
            r=self.row(c.BEGIN);r[3]=value
            with self.subTest(value=value),self.assertRaises(ValueError):c.validate_response(self.payload([r]),'spot','BTCUSDT',c.BEGIN,c.BEGIN+c.MINUTE)
    def test_gap_is_counted_not_filled(self):
        x=c.validate_month([self.row(c.BEGIN)],c.BEGIN,c.BEGIN+2*c.MINUTE)
        self.assertEqual(x,{'expected_minutes':2,'observed_minutes':1,'missing_minutes':1,'complete':False})
    def test_no_2026_month(self):
        self.assertEqual(len(list(c.month_labels('2022-01','2025-12'))),48)
        self.assertEqual(c.month_bounds('2025-12')[1],c.END)
        with self.assertRaises(ValueError):list(c.month_labels('2025-12','2026-01'))
    def test_nonjson_site_unavailable_rejected(self):
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return b'<html>Site Unavailable</html>'
        with tempfile.TemporaryDirectory() as d,patch.object(c.urllib.request,'urlopen',return_value=Response()):
            with self.assertRaisesRegex(ValueError,'non-JSON'):c.get_page('spot','BTCUSDT',c.BEGIN,c.BEGIN+c.MINUTE,Path(d))
            self.assertEqual(list(Path(d).iterdir()),[])
    def test_complete_month_resume_and_corruption(self):
        lo,hi=c.month_bounds('2022-02');calls=[]
        def fake(stream,symbol,a,b,rawdir):
            calls.append((a,b));return [self.row(t) for t in range(a,b,c.MINUTE)],{'mock':True}
        with tempfile.TemporaryDirectory() as d,patch.object(c,'get_page',side_effect=fake),patch.object(c.time,'sleep'):
            root=Path(d);m=c.collect_month(root,'spot','BTCUSDT','2022-02')
            self.assertTrue(m['coverage']['complete']);self.assertEqual(m['coverage']['observed_minutes'],40320)
            self.assertEqual(calls[0][0],lo);self.assertEqual(calls[-1][1],hi)
            self.assertTrue(all(b-a<=1000*c.MINUTE for a,b in calls))
            for a,b in zip(calls,calls[1:]):self.assertEqual(a[1],b[0])
            count=len(calls);self.assertEqual(c.collect_month(root,'spot','BTCUSDT','2022-02'),m);self.assertEqual(len(calls),count)
            target=root/'spot/BTCUSDT/2022-02.csv.gz';target.write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError,'checksum'):c.collect_month(root,'spot','BTCUSDT','2022-02')

if __name__=='__main__':unittest.main(verbosity=2)
