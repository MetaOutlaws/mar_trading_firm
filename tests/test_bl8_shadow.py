"""Offline unit/integration checks; real SQLite, no network or trading keys."""
import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core.execution.bl8_shadow import Ledger, depth_fill, FEE, SLIP
from core.risk.limits import PAPER_LIMITS
from core.risk.sizing import size_position
from core.strategy.bl8 import fill_gate
from core.strategy.bl8 import decision, HOUR

T=1_800_000_000_000//3_600_000*3_600_000


def signal(symbol='XUSDT', uid='s'):
    return dict(symbol=symbol,uid=uid,signal_ms=T,action_ms=T+60_000,
                eligible_signal=True,stop=90.,target=115.,regime='trend_down')


def reference_entry(ask=100.):
    """Touch ask plus the modeled 20bp entry slip the ledger sizes against."""
    return ask*(1+SLIP)


def stop_at(distance, ask=100.):
    """Stop that puts ``distance`` of the reference entry between fill and stop."""
    return reference_entry(ask)*(1-distance)


def book(now, bid=99.9, ask=100., symbol='XUSDT'):
    return dict(ts=now,s=symbol,b=[[str(bid),'100']],a=[[str(ask),'100']])


INST={'symbol':'XUSDT','status':'Trading','lotSizeFilter':{'qtyStep':'.001','minOrderQty':'.001','minNotionalValue':'5','maxMktOrderQty':'100'}}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'paper.db';self.ledger=Ledger(self.path,'fixed');self.s=signal();self.now=T+60_000
        self.ledger.signal(self.s,T+1)
    def tearDown(self): self.ledger.db.close();self.tmp.cleanup()
    def enter(self): return self.ledger.enter(self.s,book(self.now),INST,self.now)
    def test_entry_rounding_risk_and_fees(self):
        p=self.enter();equity=self.ledger.starting_equity
        self.assertGreater(p['initial_risk_usdt'],0)
        self.assertLessEqual(p['initial_risk_usdt'],equity*PAPER_LIMITS.max_risk_per_trade_pct+1e-6)
        self.assertLessEqual(p['notional_usdt'],equity*PAPER_LIMITS.max_position_pct+1e-6)
        self.assertLessEqual(p['notional_usdt'],equity*PAPER_LIMITS.max_leverage+1e-6)
        self.assertAlmostEqual(self.ledger.audit()['cash_pnl_usdt'],-p['entry_price']*p['quantity']*FEE)
    def test_ten_percent_cap_binds(self):
        # An 9% stop wants about 11.1% of equity from the 1% risk budget, so the 10% cap wins.
        s=signal(uid='cap');s['stop']=stop_at(0.09);self.ledger.signal(s,self.now)
        p=self.ledger.enter(s,book(self.now),INST,self.now)
        cap=self.ledger.starting_equity*PAPER_LIMITS.max_position_pct
        self.assertAlmostEqual(p['notional_usdt'],cap,delta=1)
        self.assertLess(p['initial_risk_usdt'],self.ledger.starting_equity*PAPER_LIMITS.max_risk_per_trade_pct)
        self.assertEqual(self.ledger.limits.max_position_pct,0.10)
    def test_risk_cap_binds_with_tight_stop(self):
        # With the 10% cap out of the way, a 2% stop is sized by equity*1%/distance.
        from dataclasses import replace
        limits=replace(PAPER_LIMITS,max_position_pct=1.0,max_total_exposure_pct=1.0)
        equity=10_000.;distance=0.02
        _qty,notional,risk,notes,_reduced=size_position(
            equity=equity,stop_distance_pct=distance,entry_price=100.,total_exposure=0.,limits=limits)
        self.assertEqual(limits.max_risk_per_trade_pct,PAPER_LIMITS.max_risk_per_trade_pct)
        self.assertAlmostEqual(notional,equity*0.01/distance)
        self.assertAlmostEqual(risk,equity*0.01)
        self.assertTrue(any('risk-per-trade' in note for note in notes))
        self.assertLess(notional,equity*limits.max_position_pct)
    def test_observer_risk_cap_binds_on_wide_stop(self):
        # Under the real caps a stop wider than 10% is the case the 1% budget binds.
        s=signal(uid='wide');s['stop']=stop_at(0.20);self.ledger.signal(s,self.now)
        p=self.ledger.enter(s,book(self.now),INST,self.now)
        self.assertAlmostEqual(p['initial_risk_usdt'],self.ledger.starting_equity*0.01,delta=0.05)
        self.assertAlmostEqual(p['notional_usdt'],self.ledger.starting_equity*0.01/0.20,delta=1)
        self.assertTrue(any('risk-per-trade' in note for note in p['sizing_notes']))
        self.assertLess(p['notional_usdt'],self.ledger.starting_equity*PAPER_LIMITS.max_position_pct)
    def test_exposure_room_binds(self):
        held={'symbol':'OTHERUSDT','entry_price':100.,'quantity':46.,'mark_price':100.,
              'entry_ms':self.now-60_000,'exit_ms':None,'initial_risk_usdt':1.,'entry_fee':0.,
              'stop':90.,'target':115.,'funding_status':'unknown'}
        self.ledger.db.execute('INSERT INTO positions VALUES(?,?,?,?)',('held','OTHERUSDT','open',json.dumps(held)))
        self.ledger.db.commit()
        s=signal(uid='next');s['stop']=stop_at(0.09);self.ledger.signal(s,self.now)
        p=self.ledger.enter(s,book(self.now),INST,self.now)
        self.assertAlmostEqual(p['notional_usdt'],400,delta=1)
        self.assertLess(p['notional_usdt'],self.ledger.starting_equity*PAPER_LIMITS.max_position_pct)
        self.assertTrue(any('exposure headroom' in note for note in p['sizing_notes']))
    def test_reject_below_five_usdt_never_upsizes(self):
        inst=copy.deepcopy(INST)
        inst['lotSizeFilter']['minNotionalValue']='1'
        inst['lotSizeFilter']['minOrderQty']='.001'
        self.ledger.starting_equity=40.  # 10% cap is 4 USDT, already under the floor
        under=signal(uid='under');under['stop']=stop_at(0.09);self.ledger.signal(under,self.now)
        self.assertIsNone(self.ledger.enter(under,book(self.now),inst,self.now))
        self.ledger.starting_equity=50.  # 10% cap is exactly 5; the lot floor drops it under 5
        rounded=signal(uid='rounded');rounded['stop']=stop_at(0.09);self.ledger.signal(rounded,self.now)
        self.assertIsNone(self.ledger.enter(rounded,book(self.now),inst,self.now))
        self.assertEqual(self.ledger.positions(),[])
        rows={r[0]:r[1] for r in self.ledger.db.execute("SELECT uid,status FROM signals WHERE uid IN ('under','rounded')")}
        self.assertEqual(rows['under'],'below_min_notional')
        self.assertEqual(rows['rounded'],'below_min_notional')
    def test_leverage_cap_binds_at_one_times_equity(self):
        from dataclasses import replace
        self.ledger.limits=replace(PAPER_LIMITS,max_risk_per_trade_pct=1.0,max_position_pct=5.0,max_total_exposure_pct=5.0)
        self.ledger.starting_equity=1_000.
        self.assertEqual(self.ledger.limits.max_leverage,1.0)
        self.assertEqual(PAPER_LIMITS.max_leverage,1.0)
        s=signal(uid='lev');s['stop']=stop_at(0.09);self.ledger.signal(s,self.now)
        p=self.ledger.enter(s,book(self.now),INST,self.now)
        self.assertAlmostEqual(p['notional_usdt'],1_000,delta=1)
        self.assertLessEqual(p['notional_usdt'],self.ledger.starting_equity*1.0+1e-6)
        self.assertTrue(any('leverage cap' in note for note in p['sizing_notes']))
    def test_restart_exactly_once(self):
        p=self.enter();self.ledger.db.close();self.ledger=Ledger(self.path,'fixed');self.enter()
        self.assertEqual(len(self.ledger.positions()),1);self.assertEqual(self.ledger.audit()['cash_events'],1)
    def test_config_drift_refuses_existing_book(self):
        with self.assertRaisesRegex(ValueError,'configuration mismatch'): Ledger(self.path,'changed')
    def test_funding_debit_credit_and_duplicate(self):
        p=self.enter();settle=self.now+8*3_600_000
        observations=[{'t':settle,'rate':.001,'price':120.}]
        self.ledger.funding('s',settle,observations,complete=True);self.ledger.funding('s',settle,observations,complete=True)
        self.assertAlmostEqual(self.ledger.audit()['positions'][0]['funding_usdt'],p['quantity']*.12)
        observations.append({'t':settle+8*3_600_000,'rate':-.002,'price':110.})
        self.ledger.funding('s',settle+8*3_600_000,observations,complete=True)
        self.assertAlmostEqual(self.ledger.audit()['positions'][0]['funding_usdt'],p['quantity']*(.12-.22))
    def test_funding_gap_never_final_zero(self):
        self.enter();t=self.now+60_000;self.ledger.exit('s',book(t,89,89.1),t)
        a=self.ledger.audit();self.assertIsNone(a['positions'][0]['net_R'])
        self.ledger.funding('s',t,[],complete=False);self.assertIsNone(self.ledger.audit()['positions'][0]['net_R'])
        self.ledger.funding('s',t,[],complete=True);self.assertIsNotNone(self.ledger.audit()['positions'][0]['net_R'])
    def test_funding_snapshot_cannot_erase_prior(self):
        self.enter();t=self.now+1000;self.ledger.funding('s',t,[dict(t=t,rate=.001,price=100)],complete=True)
        with self.assertRaisesRegex(ValueError,'omitted_prior'):self.ledger.funding('s',t+1,[],complete=True)
    def test_close_cash_and_restart(self):
        p=self.enter();t=self.now+60_000;closed=self.ledger.exit('s',book(t,115.,115.1),t)
        expected=p['quantity']*(115*(1-SLIP)-p['entry_price'])-p['entry_fee']-p['quantity']*115*(1-SLIP)*FEE
        self.assertAlmostEqual(self.ledger.audit()['cash_pnl_usdt'],expected)
        self.ledger.exit('s',book(t,115,115.1),t);self.assertEqual(self.ledger.audit()['cash_events'],2)
        self.assertTrue(self.ledger.audit()['cash_accounting_pass']);self.assertEqual(closed['exit_reason'],'target')
    def test_atomic_close_failure_and_retry(self):
        self.enter();before=self.ledger.audit()['cash_pnl_usdt']
        self.ledger.db.execute("CREATE TRIGGER fail_close BEFORE UPDATE ON positions WHEN NEW.status='closed' BEGIN SELECT RAISE(ABORT,'injected'); END")
        t=self.now+60_000
        with self.assertRaises(sqlite3.IntegrityError):self.ledger.exit('s',book(t,89,89.1),t)
        self.assertEqual(self.ledger.audit()['cash_pnl_usdt'],before);self.assertEqual(len(self.ledger.positions()),1)
        self.ledger.db.execute('DROP TRIGGER fail_close');self.ledger.exit('s',book(t,89,89.1),t)
        self.assertEqual(self.ledger.audit()['closed_positions'],1);self.assertTrue(self.ledger.audit()['cash_accounting_pass'])
    def test_stop_fills_observed_depth_not_stop_level(self):
        self.enter();t=self.now+60_000;p=self.ledger.exit('s',book(t,85,85.1),t);self.assertEqual(p['exit_price'],85)
    def test_no_exit_on_entry_minute(self):
        self.enter();self.assertIsNone(self.ledger.exit('s',book(self.now+5000,85,85.1),self.now+5000))
    def test_disabled_entries_keep_exits(self):
        self.enter();t=self.now+60_000;self.assertIsNotNone(self.ledger.exit('s',book(t,85,85.1),t))
        s=signal(uid='two');s['action_ms']=t+60_000;self.ledger.signal(s,t)
        self.assertIsNone(self.ledger.enter(s,book(t+60_000),INST,t+60_000,entries_enabled=False))
    def test_exit_minute_occupied(self):
        self.enter();t=self.now+60_000;self.ledger.exit('s',book(t,85,85.1),t)
        s=signal(uid='two');s['action_ms']=t;self.ledger.signal(s,t)
        self.assertIsNone(self.ledger.enter(s,book(t+1000),INST,t+1000))
    def test_low_size_is_rejected_not_upsized(self):
        inst=copy.deepcopy(INST);inst['lotSizeFilter']['minNotionalValue']='1000'
        self.assertIsNone(self.ledger.enter(self.s,book(self.now),inst,self.now));self.assertEqual(len(self.ledger.positions()),0)
    def test_invalid_limits_refuse_entry(self):
        inst=copy.deepcopy(INST);inst['lotSizeFilter']['minOrderQty']='NaN'
        with self.assertRaisesRegex(ValueError,'invalid_instrument'):self.ledger.enter(self.s,book(self.now),inst,self.now)
    def test_unavailable_or_wrong_symbol(self):
        inst=copy.deepcopy(INST);inst['status']='Closed';self.assertIsNone(self.ledger.enter(self.s,book(self.now),inst,self.now))
    def test_future_and_expired_signals(self):
        with self.assertRaises(ValueError):self.ledger.signal(signal(uid='future'),T-1)
        self.ledger.signal(signal(uid='late'),T+500_000);self.assertEqual(len(self.ledger.signals()),1)
    def test_action_deadline(self):
        self.assertIsNone(self.ledger.enter(self.s,book(self.now-1),INST,self.now-1))
        self.assertIsNone(self.ledger.enter(self.s,book(self.now+60_001),INST,self.now+60_001))
    def test_missing_quote_does_not_close(self):
        self.enter();t=self.now+60_000;b=book(t);b['b']=[]
        with self.assertRaises(ValueError):self.ledger.exit('s',b,t)
        self.assertEqual(len(self.ledger.positions()),1)
    def test_equity_cash_unrealized_and_stale_marks(self):
        p=self.enter();t=self.now+60_000;self.ledger.mark('s',book(t,105,105.1),t)
        e=self.ledger.equity(t);self.assertAlmostEqual(e['equity_pnl_usdt'],-p['entry_fee']+p['quantity']*(105-p['entry_price']))
        self.assertTrue(e['all_open_marks_fresh']);self.assertFalse(self.ledger.equity(t+15_001)['all_open_marks_fresh'])
    def test_out_of_order_marks_do_not_replace_recent(self):
        self.enter();t=self.now+60_000;self.ledger.mark('s',book(t),t)
        with self.assertRaisesRegex(ValueError,'out_of_order'):self.ledger.mark('s',book(t-1),t)
    def test_readonly_verifier_distinguishes_activation_and_fill_evidence(self):
        from scripts import verify_bl8_paper as verifier
        root=Path(self.tmp.name)/'release';(root/'config/sleeves').mkdir(parents=True);(root/'docs/bl8-paper-validation').mkdir(parents=True)
        raw=json.dumps({'universe':['XUSDT']}).encode();(root/'config/sleeves/mar_bl8_shadow_v1.json').write_bytes(raw)
        (root/'BL8_RELEASE_SHA').write_text('a'*40);(root/'docs/bl8-paper-validation/RELEASE_MANIFEST.json').write_text('{"runtime_sha256":{}}')
        status={'heartbeat_ms':self.now,'started_ms':T,'release':'a'*40,'config_sha':hashlib.sha256(raw).hexdigest()}
        with self.ledger.db:self.ledger.db.execute("UPDATE meta SET v=? WHERE k='config_sha'",(status['config_sha'],))
        (self.path.parent/'status.json').write_text(json.dumps(status))
        self.ledger.observe(self.now,'context',{'symbol':'XUSDT','reason':'no_signal','instrument':INST})
        argv=['verify','--db',str(self.path),'--expected-commit','a'*40];buf=io.StringIO()
        with patch.object(verifier,'ROOT',root),patch('sys.argv',argv),patch.object(verifier.time,'time_ns',return_value=self.now*1_000_000),contextlib.redirect_stdout(buf):
            with self.assertRaises(SystemExit) as ex:verifier.main()
        self.assertEqual(ex.exception.code,False);result=json.loads(buf.getvalue());self.assertTrue(result['activation_verified']);self.assertFalse(result['observed_fill_close_cash_checks_pass']);self.assertFalse(result['profitability_validated'])


class MarketChecks(unittest.TestCase):
    def test_quote_age_and_future(self):
        for ts in [T-5001,T+1]:
            with self.assertRaises(ValueError):depth_fill(book(ts),.1,True,T)
    def test_depth_vwap(self):
        b=book(T);b['a']=[['100','.1'],['101','.2']];self.assertAlmostEqual(depth_fill(b,.2,True,T),100.5)
    def test_insufficient_crossed_and_unsorted(self):
        for b in [book(T,101,100),dict(book(T),a=[['101','1'],['100','1']]),dict(book(T),a=[['100','.001']])]:
            with self.assertRaises(ValueError):depth_fill(b,.1,True,T)
    def test_fill_gate_boundaries(self):
        s=signal();self.assertFalse(fill_gate(s,115));self.assertFalse(fill_gate(s,90));self.assertFalse(fill_gate(s,97));self.assertTrue(fill_gate(s,100))
    def test_public_only_endpoint(self):
        from scripts.run_bl8_paper import public_get
        with self.assertRaises(ValueError):public_get('order/create')
    def test_frozen_config(self):
        root=Path(__file__).resolve().parents[1];c=json.loads((root/'config/sleeves/mar_bl8_shadow_v1.json').read_text())
        old=json.loads((root/'config/sleeves/mar_l01_long_f111_short_v1.json').read_text())
        self.assertEqual(c['universe'],old['universe']);self.assertEqual(len(set(c['universe'])),96);self.assertFalse(c['live_authorized'])
        self.assertEqual(c['sizing_policy'],'hourly_paper_limits')
        self.assertNotIn('initial_price_stop_risk_usdt',c)
        self.assertEqual(c['starting_equity_usdt'],10000)
        self.assertEqual(c['max_risk_per_trade_pct'],PAPER_LIMITS.max_risk_per_trade_pct)
        self.assertEqual(c['max_position_pct'],PAPER_LIMITS.max_position_pct)
        self.assertEqual(c['max_total_exposure_pct'],PAPER_LIMITS.max_total_exposure_pct)
        self.assertEqual(c['max_leverage'],PAPER_LIMITS.max_leverage)
        self.assertEqual(c['min_notional_usdt'],PAPER_LIMITS.min_notional_usdt)
    def test_warmup_boundary_and_bad_bars(self):
        asof=T//(4*HOUR)*(4*HOUR)
        h=[dict(t=asof-(24-i)*HOUR,o=100.,h=101.,l=99.,c=100.) for i in range(25)]
        b=[dict(t=asof-(17-i)*4*HOUR,o=100.,h=101.,l=99.,c=100.) for i in range(18)]
        self.assertEqual(decision('X',h,b,asof)['reason'],'no_signal')
        self.assertEqual(decision('X',h,b[1:],asof)['reason'],'missing_context')
        bad=copy.deepcopy(h);bad[-1]['t']+=HOUR
        with self.assertRaisesRegex(ValueError,'future'):decision('X',bad,b,asof)
        bad=copy.deepcopy(h);bad[-2]['t']=bad[-3]['t']
        with self.assertRaisesRegex(ValueError,'duplicate'):decision('X',bad,b,asof)
    def test_fixed_band_strict_boundary_arithmetic(self):
        from core.strategy.bl8 import _sum20
        import math
        prices=[.227,.226,.226,.226,.226,.224,.223,.229,.229,.229,.226,.226,.224,.224,.226,.227,.223,.224,.219,.22]
        mean=_sum20(prices)/20;dev=[v-mean for v in prices];sd=math.sqrt(_sum20([v*v for v in dev])/20)
        self.assertEqual(mean,.22519999999999998);self.assertLess(mean-2*sd,.22)
    def test_funding_public_response_gap_is_unknown(self):
        from scripts.run_bl8_paper import funding_snapshot
        interval=8*HOUR;start=T//interval*interval+60_000;end=start//interval*interval+interval
        p={'symbol':'XUSDT','entry_ms':start,'exit_ms':end}
        with patch('scripts.run_bl8_paper.public_get',return_value={'result':{'list':[]}}):
            through,values,complete=funding_snapshot(p,480)
            self.assertFalse(complete);self.assertEqual(values,[])
    def test_funding_public_response_values_settlement_open(self):
        from scripts.run_bl8_paper import funding_snapshot
        interval=8*HOUR;start=T//interval*interval+60_000;end=start//interval*interval+interval
        p={'symbol':'XUSDT','entry_ms':start,'exit_ms':end}
        def fake(path,**kw):
            if path=='funding/history':return {'result':{'list':[{'symbol':'XUSDT','fundingRateTimestamp':str(end),'fundingRate':'-.001'}]}}
            self.assertEqual(kw['start'],end);return {'result':{'list':[[str(end),'120','121','119','120','1']]}}
        with patch('scripts.run_bl8_paper.public_get',side_effect=fake):
            through,values,complete=funding_snapshot(p,480)
            self.assertTrue(complete);self.assertEqual(values[0]['price'],120.);self.assertEqual(values[0]['rate'],-.001)


if __name__=='__main__':unittest.main()
