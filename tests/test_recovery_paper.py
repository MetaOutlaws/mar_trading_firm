import copy
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from core.execution.recovery_paper import (PaperTrial, MINUTE, DAY, canonical,
    observe_close, recover, make_account, funding_known)
from core.execution.recovery_feed import advance_retest, parse_bars
from core.execution.paper_cash import replay_events
from scripts.resize_paper_account import (resize, inspect_account,
    legacy_backfill_close_desktop)
from scripts.report_recovery_paper import report, render

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'config/sleeves/mar_recovery_paper_v1.json').read_text())
T=20_000*DAY+MINUTE


def quote(symbol='BTCUSDT', t=T, bid=99.9, ask=100.):
    return dict(s=symbol,ts=t,b=[[str(bid),'100000']],a=[[str(ask),'100000']])


def instrument(symbol='BTCUSDT'):
    return dict(symbol=symbol,status='Trading',fundingInterval=480,
                lotSizeFilter=dict(qtyStep='.001',minOrderQty='.001',
                                  maxMktOrderQty='100000',minNotionalValue='5'))


def signal(uid='first',symbol='BTCUSDT',t=T,source='B',side=1):
    return dict(uid=uid,symbol=symbol,source=source,side=side,sector='majors',
                signal_ms=t-MINUTE,action_ms=t,eligible_signal=True,
                stop=90.,target=110.,prior_atr=3.)


class TrialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'book.db'
        self.book=PaperTrial(self.path,CONFIG,create=True)

    def tearDown(self):
        self.book.db.close();self.tmp.cleanup()

    def cycle(self,t=T,signals=(),bid=99.9,ask=100.,funding=None,manual=False):
        symbols={p['symbol'] for p in self.book.positions()}|{s['symbol'] for s in signals}
        return self.book.cycle(str(t),t,{s:quote(s,t,bid,ask) for s in symbols},
                              {s:instrument(s) for s in symbols},signals,funding,manual_halt=manual)

    def seed_account(self,**values):
        state=self.book.state()
        for a in state['accounts'].values(): a.update(copy.deepcopy(values))
        self.book.db.execute('UPDATE state SET body=?',(canonical(state),))

    def test_matched_entries_sizes_include_fees_and_persist(self):
        result=self.cycle(signals=[signal()])
        self.assertEqual((result['new_entries'],result['opportunity_entries']),(2,1))
        positions=self.book.positions()
        for p in positions:
            if p['book']!='OPPORTUNITY':
                self.assertLessEqual(p['planned_loss_usdt'],200+1e-9)
                self.assertLessEqual(p['quantity']*p['entry'],2000+1e-9)
        a,b=positions[:2]
        self.assertEqual((a['entry'],a['quantity']),(b['entry'],b['quantity']))
        self.book.db.close();self.book=PaperTrial(self.path,CONFIG)
        self.assertEqual(len(self.book.positions()),3)

    def test_exact_replay_does_not_admit_again(self):
        s=signal();self.cycle(signals=[s]);cash=self.book.state()
        result=self.cycle(signals=[s])
        self.assertTrue(result['duplicate']);self.assertEqual(cash,self.book.state())

    def test_conflicting_event_replay_is_refused(self):
        self.cycle(signals=[signal()])
        with self.assertRaisesRegex(ValueError,'conflicting event'):
            self.cycle(signals=[signal('different')])
        self.assertEqual(len(self.book.positions()),3)

    def test_conflicting_signal_is_atomic(self):
        self.cycle(signals=[signal()]);before=self.book.state()
        with self.assertRaisesRegex(ValueError,'conflicting signal'):
            self.cycle(T+1,[signal(t=T+1)])
        self.assertEqual(before,self.book.state())

    def test_rollback_covers_cash_decisions_fills_and_recovery(self):
        self.seed_account(streak=6,raw_streak=6,last_loss_ms=T-DAY)
        before=self.book.state()
        with patch.object(self.book,'save_position',side_effect=RuntimeError('simulated interruption')):
            with self.assertRaises(RuntimeError): self.cycle(signals=[signal()])
        self.assertEqual(self.book.state(),before)
        self.assertEqual(self.book.db.execute('SELECT count(*) FROM decisions').fetchone()[0],0)
        self.assertEqual(self.book.positions(),[])

    def test_unknown_config_or_missing_book_never_resets(self):
        changed=CONFIG|dict(starting_equity_usdt=10000)
        with self.assertRaises(ValueError): PaperTrial(self.path,changed)
        with self.assertRaises(ValueError): PaperTrial(self.path.parent/'absent.db',CONFIG)
        with self.assertRaises(FileExistsError): PaperTrial(self.path,CONFIG,create=True)

    def test_restart_refuses_unreconciled_cash(self):
        self.seed_account(cash=25000.)
        with self.assertRaisesRegex(ValueError,'does not reconcile'):
            PaperTrial(self.path,CONFIG)

    def test_c24_opens_when_control_remains_blocked(self):
        self.seed_account(streak=6,raw_streak=6,last_loss_ms=T-DAY)
        r=self.cycle(signals=[signal()])
        self.assertEqual((r['new_entries'],r['opportunity_entries']),(1,1))
        self.assertEqual({p['book'] for p in self.book.positions()},{'C24','OPPORTUNITY'})
        accounts=self.book.state()['accounts']
        self.assertEqual(accounts['C24']['raw_streak'],6)
        self.assertEqual(accounts['C24']['streak'],0)

    def test_recovery_does_not_clear_drawdown_or_manual_halt(self):
        self.seed_account(streak=6,raw_streak=6,last_loss_ms=T-DAY,
                          killed=dict(reason='drawdown'))
        r=self.cycle(signals=[signal()],manual=True)
        self.assertEqual((r['new_entries'],r['opportunity_entries']),(0,1))
        self.assertIsNotNone(self.book.state()['accounts']['C24']['killed'])

    def test_daily_loss_blocks_accounts_not_opportunities(self):
        self.seed_account(closed_daily={str(T//DAY):-700.})
        r=self.cycle(signals=[signal()])
        self.assertEqual((r['new_entries'],r['opportunity_entries']),(0,1))

    def test_account_stop_limit_does_not_hide_strategy_opportunity(self):
        s=signal()|dict(stop=75.)
        r=self.cycle(signals=[s])
        self.assertEqual((r['new_entries'],r['opportunity_entries']),(0,1))

    def test_sector_limit_still_records_rejected_opportunity(self):
        signals=[signal(str(i),s) for i,s in enumerate(('BTCUSDT','ETHUSDT','SOLUSDT'))]
        r=self.cycle(signals=signals)
        self.assertEqual((r['new_entries'],r['opportunity_entries']),(4,3))

    def test_position_ceiling_is_fifteen(self):
        self.book.limits=replace(self.book.limits,max_position_pct=.01,max_positions_per_sector=20)
        signals=[signal(str(i),s) for i,s in enumerate(CONFIG['universe'][:16])]
        r=self.cycle(signals=signals)
        self.assertEqual((r['new_entries'],r['opportunity_entries']),(30,16))

    def test_gross_exposure_limit_applies(self):
        self.book.limits=replace(self.book.limits,max_positions_per_sector=20)
        self.cycle(signals=[signal(str(i),s) for i,s in enumerate(CONFIG['universe'][:12])])
        for book,a in self.book.state()['accounts'].items():
            exposure=sum(p['quantity']*p['mark'] for p in self.book.positions() if p['book']==book)
            self.assertLessEqual(exposure,a['equity']*.5+1e-6)

    def test_hourly_first_independent_of_input_order(self):
        self.cycle(signals=[signal('B'),signal('H',source='H')])
        for p in self.book.positions():
            if p['book']!='OPPORTUNITY': self.assertEqual(p['source'],'H')
        self.assertEqual(len([p for p in self.book.positions() if p['book']=='OPPORTUNITY']),2)

    def test_bad_quote_does_not_fabricate_opportunity_fill(self):
        result=self.book.cycle('x',T,{'BTCUSDT':quote(t=T-5001)},
            {'BTCUSDT':instrument()},[signal()])
        self.assertEqual(result['new_entries']+result['opportunity_entries'],0)

    def test_expired_signal_is_recorded_without_hindsight_fill(self):
        self.cycle(T+MINUTE,[signal()])
        self.assertEqual(self.book.positions(),[])
        self.assertEqual(self.book.db.execute('SELECT count(*) FROM decisions').fetchone()[0],3)

    def test_exit_minute_occupancy_survives_restart(self):
        self.cycle(signals=[signal()]);self.cycle(T+MINUTE,bid=110.5,ask=110.6)
        self.book.db.close();self.book=PaperTrial(self.path,CONFIG)
        r=self.cycle(T+MINUTE+1000,[signal('second',t=T+MINUTE)])
        self.assertEqual(r['new_entries'],0)
        self.assertEqual(r['opportunity_entries'],1)

    def test_roundtrip_reconciles_cash_fees_and_net(self):
        self.cycle(signals=[signal()]);self.cycle(T+MINUTE,bid=110.5,ask=110.6)
        for book,a in self.book.state()['accounts'].items():
            p=next(p for p in self.book.positions(None) if p['book']==book)
            self.assertEqual(p['status'],'closed')
            self.assertAlmostEqual(a['cash']-20000,p['net_pnl'])
            self.assertAlmostEqual(a['realised_pnl'],p['net_pnl'])

    def test_short_funding_credit_and_short_exit(self):
        t=20_000*DAY+480*MINUTE-MINUTE
        self.cycle(t,[signal('short',t=t,source='H',side=-1)])
        f={'BTCUSDT':dict(through_ms=t+MINUTE,rows=[dict(t=t+MINUTE,rate=.001,price=100.)])}
        self.cycle(t+MINUTE,bid=87.4,ask=87.5,funding=f)
        for p in self.book.positions(None):
            self.assertEqual(p['status'],'closed');self.assertLess(p['funding'],0)
            if p['book'] in ('NONE','C24'):
                self.assertAlmostEqual(self.book.state()['accounts'][p['book']]['cash']-20000,p['net_pnl'])

    def test_unknown_funding_queues_close_and_blocks_only_accounts(self):
        t=20_000*DAY+480*MINUTE-MINUTE
        self.cycle(t,[signal(t=t)])
        self.cycle(t+MINUTE,bid=110.5,ask=110.6)
        self.assertTrue(all(p['status']=='pending_funding' for p in self.book.positions()))
        r=self.cycle(t+MINUTE+1000,[signal('new','ETHUSDT',t+MINUTE)])
        self.assertEqual((r['new_entries'],r['opportunity_entries']),(0,1))
        f={'BTCUSDT':dict(through_ms=t+2*MINUTE,rows=[dict(t=t+MINUTE,rate=.001,price=105.)])}
        self.cycle(t+2*MINUTE,funding=f)
        for book,a in self.book.state()['accounts'].items():
            self.assertEqual(a['closed_trades'],1)
        self.assertFalse(any(p['status']=='pending_funding' for p in self.book.positions()))

    def test_missing_minute_latches_before_last_position_exit(self):
        self.cycle(signals=[signal()]);self.cycle(T+2*MINUTE,bid=110.5,ask=110.6)
        for a in self.book.state()['accounts'].values(): self.assertIsNotNone(a['supervision_gap'])
        r=self.cycle(T+3*MINUTE,[signal('next','ETHUSDT',T+3*MINUTE)])
        self.assertEqual((r['new_entries'],r['opportunity_entries']),(0,1))

    def test_drawdown_latches_even_without_candidate(self):
        self.cycle(signals=[signal()])
        self.seed_account(peak=30000.)
        self.cycle(T+MINUTE)
        for a in self.book.state()['accounts'].values(): self.assertIsNotNone(a['killed'])

    def test_report_never_calls_opportunity_sum_portfolio_roi(self):
        self.cycle(signals=[signal()])
        report=self.book.report(T)
        self.assertIn('NOT portfolio ROI',report['opportunity_basis'])
        self.assertFalse(report['activation_verified'])

    def test_partial_quote_closes_execute_but_ordering_waits(self):
        self.cycle(signals=[signal('z','BTCUSDT'),signal('a','ETHUSDT')])
        t=T+MINUTE
        self.book.cycle('partial',t,{'BTCUSDT':quote(t=t,bid=110.5,ask=110.6)},
                        {'BTCUSDT':instrument()},[])
        self.assertEqual(self.book.state()['accounts']['NONE']['closed_trades'],0)
        self.assertTrue(any(p['uid']=='z' and p['status']=='pending_funding' for p in self.book.positions()))
        self.cycle(t+1000,bid=110.5,ask=110.6)
        a=self.book.state()['accounts']['NONE']
        self.assertEqual(a['closed_trades'],2)
        self.assertEqual(a['last_close_key'],[t//MINUTE,'z'])
        self.assertIsNone(a['supervision_gap'])

    def test_abrupt_process_death_rolls_back_whole_transaction(self):
        script='''
import json,os,sys
from pathlib import Path
from core.execution.recovery_paper import PaperTrial
from tests.test_recovery_paper import CONFIG,T,quote,instrument,signal
b=PaperTrial(Path(sys.argv[1]),CONFIG)
original=b.save_position
def interrupt(p):
    original(p)
    os._exit(91)
b.save_position=interrupt
b.cycle('crash',T,{'BTCUSDT':quote()},{'BTCUSDT':instrument()},[signal()])
'''
        proc=subprocess.run([sys.executable,'-c',script,str(self.path)],cwd=ROOT,capture_output=True)
        self.assertEqual(proc.returncode,91,proc.stderr.decode())
        self.assertEqual(self.book.positions(),[])
        self.assertEqual(self.book.state()['accounts']['NONE']['cash'],20000.)
        self.assertEqual(self.book.db.execute('SELECT count(*) FROM decisions').fetchone()[0],0)

    def test_report_reconciles_but_never_invents_runtime_activation(self):
        self.cycle(signals=[signal()]);self.cycle(T+MINUTE,bid=110.5,ask=110.6)
        r=report(self.path,self.path.parent/'missing-status.json',now=T+MINUTE)
        self.assertFalse(r['activation_verified'])
        self.assertTrue(all(a['cash_reconciled'] for a in r['accounts'].values()))
        self.assertTrue(any(b['dimension']=='year' for b in r['breakdowns']))
        page=render(r)
        self.assertIn('<!doctype html>',page);self.assertIn('not account returns',page)


class RuleTests(unittest.TestCase):
    def test_boundary_loss_extension_and_positive_clear(self):
        a=make_account()
        for i in range(6): observe_close(a,dict(net_pnl=0.,exit_ms=T+i*MINUTE,uid=str(i)))
        loss=T+5*MINUTE
        recover(a,'C24',loss+DAY-MINUTE);self.assertEqual(a['streak'],6)
        observe_close(a,dict(net_pnl=-1.,exit_ms=loss+MINUTE,uid='later'))
        recover(a,'C24',loss+DAY);self.assertEqual(a['streak'],7)
        recover(a,'C24',loss+MINUTE+DAY);self.assertEqual(a['streak'],0)
        self.assertEqual(a['raw_streak'],7)
        observe_close(a,dict(net_pnl=1.,exit_ms=loss+DAY+2*MINUTE,uid='winner'))
        self.assertEqual(a['raw_streak'],0)

    def test_retest_uses_completed_close_and_next_minute(self):
        p=signal(source='H')|dict(next_minute=T,touched=False,boundary=100.,signal_ms=T)
        bar=dict(t=T+MINUTE,o=100.,h=101.,l=99.,c=100.5,v=1.)
        pending,s,_=advance_retest(p,[bar],T+MINUTE-1)
        self.assertIsNone(s);self.assertIsNotNone(pending)
        pending,s,_=advance_retest(p,[bar],T+MINUTE)
        self.assertIsNone(pending);self.assertEqual(s['action_ms'],T+MINUTE)

    def test_equal_boundary_does_not_reclaim_and_gap_is_explicit(self):
        p=signal(source='H')|dict(next_minute=T,touched=False,boundary=100.,signal_ms=T)
        bar=dict(t=T+MINUTE,o=100.,h=101.,l=99.,c=100.,v=1.)
        pending,s,_=advance_retest(p,[bar],T+MINUTE)
        self.assertIsNone(s);self.assertTrue(pending['touched'])
        _,_,reason=advance_retest(p,[],T+MINUTE)
        self.assertEqual(reason,'retest_missing_minute')

    def test_bar_validation_rejects_future_duplicate_and_gap(self):
        row=[T,'100','101','99','100','1']
        with self.assertRaises(ValueError): parse_bars([row,row],MINUTE,T+MINUTE)
        with self.assertRaises(ValueError): parse_bars([row],MINUTE,T)
        later=[T+2*MINUTE,*row[1:]]
        with self.assertRaises(ValueError): parse_bars([row,later],MINUTE,T+3*MINUTE)


class ResizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.data=self.root/'data';self.data.mkdir();self.app=self.root/'app'
        (self.app/'core/risk').mkdir(parents=True)
        limits=(ROOT/'core/risk/limits.py').read_text().replace(
            'PAPER_LIMITS = RiskLimits(max_concurrent_positions=15)','PAPER_LIMITS = RiskLimits()')
        (self.app/'core/risk/limits.py').write_text(limits)
        self.events=[dict(event_id='capital',kind='capital',amount=10000),
                     dict(event_id='entry',kind='open',symbol='BTCUSDT',fee=2.)]
        self.write_cash(self.events)
        (self.data/'killswitch.json').write_text('{"tripped":true}')
        db=sqlite3.connect(self.data/'firm.db')
        db.execute('CREATE TABLE positions(id INTEGER,mode TEXT,status TEXT,stop_loss_price REAL)')
        db.execute("INSERT INTO positions VALUES(1,'paper','open',90)")
        db.commit();db.close()

    def write_cash(self,events):
        state=replay_events(events)
        raw={k:getattr(state,k) for k in ('cash','realised_pnl','contributed_capital','total_fees','total_funding')}
        raw['events']=events;raw['version']=1
        (self.data/'paper_cash.json').write_text(json.dumps(raw))

    def tearDown(self): self.tmp.cleanup()

    def test_topup_is_capital_preserves_positions_kill_and_history(self):
        before=inspect_account(self.data,self.app)
        receipt=resize(self.data,self.app,self.root/'backups',apply=True)
        after=inspect_account(self.data,self.app)
        self.assertEqual(after['current'].cash,20000.)
        self.assertEqual(after['current'].realised_pnl,before['current'].realised_pnl)
        self.assertEqual(after['positions'],before['positions'])
        self.assertEqual(after['protective'],before['protective'])
        self.assertEqual(after['events'][:-1],before['events'])
        self.assertEqual(after['limits']['max_concurrent_positions'],15)
        self.assertTrue((Path(receipt['backup'])/'firm.db').exists())

    def test_rerun_does_not_replenish_later_losses(self):
        resize(self.data,self.app,self.root/'backups',apply=True)
        events=json.loads((self.data/'paper_cash.json').read_text())['events']
        events.append(dict(event_id='later',kind='open',symbol='ETHUSDT',fee=5.))
        self.write_cash(events)
        receipt=resize(self.data,self.app,self.root/'backups',apply=True)
        self.assertTrue(receipt['already_applied']);self.assertEqual(receipt['cash_after'],19995.)

    def test_dry_run_has_no_side_effects(self):
        cash=(self.data/'paper_cash.json').read_bytes()
        resize(self.data,self.app,self.root/'backups')
        self.assertEqual((self.data/'paper_cash.json').read_bytes(),cash)
        self.assertFalse((self.root/'backups').exists())

    def test_live_position_is_refused(self):
        db=sqlite3.connect(self.data/'firm.db');db.execute("UPDATE positions SET mode='live'");db.commit();db.close()
        with self.assertRaises(ValueError): resize(self.data,self.app,self.root/'backups',apply=True)

    def test_unreconciled_journal_is_refused(self):
        path=self.data/'paper_cash.json';raw=json.loads(path.read_text());raw['cash']+=1;path.write_text(json.dumps(raw))
        with self.assertRaises(ValueError): resize(self.data,self.app,self.root/'backups',apply=True)


# Preview of a journal that contains only the seven Oct 9 desktop closes.
# replay_events starts from zero, so this is not the live account.
# Live server preflight (resize-preview.json) must still show:
#   realised P&L -174.39, top-up +10175.01, resulting cash 20000.
# Those three figures need the rest of paper_cash.json, which is not in this repo.
PARTIAL_REALISED_PNL=-114.50250483113291
PARTIAL_TOP_UP=20114.502504831133
PARTIAL_RESULT_CASH=20000.0
SERVER_PREFLIGHT_REALISED_PNL=-174.39
SERVER_PREFLIGHT_TOP_UP=10175.01
SERVER_PREFLIGHT_RESULT_CASH=20000.0


class LegacyBackfillCloseTests(unittest.TestCase):
    """paper_cash_events 11-17 are backfill-close:desktop:1..7 with no payload event_id."""

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.data=self.root/'data';self.data.mkdir();self.app=self.root/'app'
        (self.app/'core/risk').mkdir(parents=True)
        limits=(ROOT/'core/risk/limits.py').read_text().replace(
            'PAPER_LIMITS = RiskLimits(max_concurrent_positions=15)','PAPER_LIMITS = RiskLimits()')
        (self.app/'core/risk/limits.py').write_text(limits)
        fix=ROOT/'tests/fixtures'
        self.rows=json.loads((fix/'legacy_backfill_close_rows_11_17.json').read_text())
        self.journal=json.loads((fix/'legacy_backfill_close_journal_1_7.json').read_text())
        self.assertEqual([r['id'] for r in self.rows], list(range(11,18)))
        self.assertEqual([r['event_id'] for r in self.rows],
                         [f'backfill-close:desktop:{i}' for i in range(1,8)])

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rows, events):
        db_path=self.data/'firm.db'
        if db_path.exists(): db_path.unlink()
        state=replay_events(events)
        raw={k:getattr(state,k) for k in ('cash','realised_pnl','contributed_capital','total_fees','total_funding')}
        raw['events']=events;raw['version']=1
        (self.data/'paper_cash.json').write_text(json.dumps(raw))
        db=sqlite3.connect(db_path)
        db.execute('CREATE TABLE positions(id INTEGER, mode TEXT, status TEXT)')
        db.execute('CREATE TABLE paper_cash_events('
                   'id INTEGER PRIMARY KEY, event_id TEXT, kind TEXT, mode TEXT, symbol TEXT, '
                   'position_id INTEGER, payload TEXT, recorded_at TEXT)')
        db.executemany('INSERT INTO paper_cash_events VALUES (?,?,?,?,?,?,?,?)',
                       [(r['id'],r['event_id'],r['kind'],r['mode'],r['symbol'],r['position_id'],
                         r['payload'],r['recorded_at']) for r in rows])
        db.commit();db.close()

    def test_seven_legacy_rows_pass_the_check(self):
        for row, event in zip(self.rows, self.journal):
            payload=json.loads(row['payload'])
            self.assertIs(payload['backfill'], True)
            self.assertNotIn('event_id', payload)
            self.assertTrue(legacy_backfill_close_desktop(row, payload))
            expected=event['gross_pnl']-event['fee']-event['entry_fee']+event['funding']
            self.assertAlmostEqual(payload['net'], expected, delta=1e-6)
            self.assertEqual(payload['cash_after'], event['cash_after'])
            self.assertEqual(payload['source_trade_id'], event['source_trade_id'])
            self.assertEqual(row['symbol'], event['symbol'])
            self.assertEqual(event['funding'], 0.0)
            self.assertEqual(event['entry_fee'], 0.0)
        self.assertFalse(legacy_backfill_close_desktop(
            {'event_id':'paper-close:1:ETHUSDT:stop:1.00000000:100.00000000','kind':'close'},
            {'event_id':'other','kind':'close','symbol':'ETHUSDT'}))
        self.write(self.rows, self.journal)
        inspected=inspect_account(self.data, self.app)
        self.assertEqual(
            [e['event_id'] for e in inspected['events']],
            [e['event_id'] for e in self.journal])

    def test_unknown_or_mismatched_event_still_fails(self):
        unknown=copy.deepcopy(self.rows)
        unknown.append(dict(id=99,event_id='not-a-real-event',kind='close',mode='paper',
                            symbol='ETHUSDT',position_id=None,
                            payload=json.dumps(dict(event_id='someone-else',kind='close')),
                            recorded_at='2026-10-09 08:39:15.501024'))
        self.write(unknown, self.journal)
        with self.assertRaisesRegex(ValueError, 'durable cash event identity mismatch'):
            inspect_account(self.data, self.app)

        shaped=copy.deepcopy(self.rows)
        shaped.append(dict(id=100,event_id='backfill-close:desktop:99',kind='close',mode='paper',
                           symbol='ETHUSDT',position_id=None,
                           payload=json.dumps(dict(backfill=True,source_trade_id=99,net=0.0,cash_after=0.0)),
                           recorded_at='2026-10-09 08:39:15.501024'))
        self.write(shaped, self.journal)
        with self.assertRaisesRegex(ValueError, 'durable cash event identity mismatch'):
            inspect_account(self.data, self.app)

        # Same economic fields, but a payload event_id means this is not the legacy shape.
        strict=copy.deepcopy(self.rows)
        payload=json.loads(strict[0]['payload'])
        payload['event_id']=strict[0]['event_id']
        strict[0]['payload']=json.dumps(payload)
        self.assertFalse(legacy_backfill_close_desktop(strict[0], payload))
        self.write(strict, self.journal)
        with self.assertRaisesRegex(ValueError, 'durable cash event economic conflict'):
            inspect_account(self.data, self.app)

    def test_tampered_legacy_row_fails(self):
        cash=copy.deepcopy(self.rows)
        payload=json.loads(cash[0]['payload'])
        payload['cash_after']=payload['cash_after']+1.0
        cash[0]['payload']=json.dumps(payload)
        self.write(cash, self.journal)
        with self.assertRaisesRegex(ValueError, 'durable cash event identity mismatch'):
            inspect_account(self.data, self.app)

        net=copy.deepcopy(self.rows)
        payload=json.loads(net[3]['payload'])
        payload['net']=payload['net']+0.01
        net[3]['payload']=json.dumps(payload)
        self.write(net, self.journal)
        with self.assertRaisesRegex(ValueError, 'durable cash event identity mismatch'):
            inspect_account(self.data, self.app)

        source=copy.deepcopy(self.rows)
        payload=json.loads(source[1]['payload'])
        payload['source_trade_id']=99
        source[1]['payload']=json.dumps(payload)
        self.write(source, self.journal)
        with self.assertRaisesRegex(ValueError, 'durable cash event identity mismatch'):
            inspect_account(self.data, self.app)

        symbol=copy.deepcopy(self.rows)
        symbol[2]['symbol']='BTCUSDT'
        self.write(symbol, self.journal)
        with self.assertRaisesRegex(ValueError, 'durable cash event identity mismatch'):
            inspect_account(self.data, self.app)

    def test_preview_numbers_from_these_rows_and_journal(self):
        """Dry-run top-up of a book whose journal is only these seven closes.

        Partial preview (this fixture): realised P&L -114.50250483,
        top-up +20114.50250483, resulting cash 20000.

        Left for the server preflight against the live paper journal:
        realised P&L -174.39, top-up +10175.01, resulting cash 20000.
        """
        self.write(self.rows, self.journal)
        before=(self.data/'paper_cash.json').read_bytes()
        receipt=resize(self.data, self.app, self.root/'backups')
        self.assertEqual((self.data/'paper_cash.json').read_bytes(), before)
        self.assertFalse((self.root/'backups').exists())
        state=replay_events(self.journal)
        nets=sum(json.loads(r['payload'])['net'] for r in self.rows)
        self.assertAlmostEqual(receipt['realised_pnl_before'], state.realised_pnl, delta=1e-12)
        self.assertAlmostEqual(receipt['realised_pnl_before'], nets, delta=1e-9)
        self.assertAlmostEqual(receipt['realised_pnl_before'], PARTIAL_REALISED_PNL, delta=1e-9)
        self.assertAlmostEqual(receipt['capital_addition'], max(0., 20000.-state.cash), delta=1e-9)
        self.assertAlmostEqual(receipt['capital_addition'], PARTIAL_TOP_UP, delta=1e-9)
        self.assertAlmostEqual(receipt['cash_before']+receipt['capital_addition'], receipt['cash_after'], delta=1e-9)
        self.assertAlmostEqual(receipt['cash_after'], PARTIAL_RESULT_CASH, delta=1e-9)
        self.assertNotAlmostEqual(receipt['realised_pnl_before'], SERVER_PREFLIGHT_REALISED_PNL, places=2)
        self.assertNotAlmostEqual(receipt['capital_addition'], SERVER_PREFLIGHT_TOP_UP, places=2)
        self.assertAlmostEqual(SERVER_PREFLIGHT_RESULT_CASH, 20000.0)


if __name__=='__main__': unittest.main()
