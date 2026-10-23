import copy
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

from research.cipher_forward.config import frozen_config
from research.cipher_forward.ledger import (
    PaperTrial, BOOKS, MINUTE, DAY, EXIT_TICK, canonical, make_account, observe_close, recover)
from research.cipher_forward.seed import SeedStore, aggregate, atomic_json
from research.cipher_forward.reporting import report, render, report_and_verify
from research.cipher_forward.feed import advance_retest, parse_bars
from scripts.run_cipher_forward_paper import Market, scan

T=20000*DAY+MINUTE
ROOT=Path(__file__).resolve().parents[1]


def quote(s='BTCUSDT',t=T,bid=99.9,ask=100.,size='100000'):
    return dict(s=s,ts=t,b=[[str(bid),size]],a=[[str(ask),size]])


def instrument(s='BTCUSDT'):
    return dict(symbol=s,status='Trading',fundingInterval=480,
        lotSizeFilter=dict(qtyStep='.001',minOrderQty='.001',maxMktOrderQty='100000',minNotionalValue='5'))


def signal(uid='one',symbol='BTCUSDT',t=T,source='B',side=1,**changes):
    return dict(uid=uid,symbol=symbol,source=source,side=side,sector='majors',signal_ms=t-MINUTE,
        action_ms=t,eligible_signal=True,stop=90.,target=110.,prior_atr=3.)|changes


def short(uid='c3',symbol='BTCUSDT',t=T,filtered=True):
    return signal(uid,symbol,t,'C3',-1,stop=112.,original_target=76.,target=64.,filter_pass=filtered)


@pytest.fixture
def book(tmp_path):
    b=PaperTrial(tmp_path/'trial.db',frozen_config(),create=True)
    yield b
    b.db.close()


def cycle(b,t=T,signals=(),bid=99.9,ask=100.,funding=None,manual=False):
    symbols={p['symbol'] for p in b.positions()}|{s['symbol'] for s in signals}
    return b.cycle(str(t),t,{s:quote(s,t,bid,ask) for s in symbols},
        {s:instrument(s) for s in symbols},signals,funding,manual_halt=manual)


def edit(b,**values):
    s=b.state()
    for a in s['accounts'].values(): a.update(copy.deepcopy(values))
    b.db.execute('UPDATE state SET body=?',(canonical(s),))


def test_12_independent_books_and_three_opportunities(book):
    r=cycle(book,signals=[signal()])
    assert (r['new_entries'],r['opportunity_entries'])==(12,3)
    ps=book.positions()
    for p in ps:
        if p['book'] in BOOKS:
            assert p['planned_loss_usdt']<=200+1e-9
            assert p['quantity']*p['entry']<=2000+1e-9
    for cost in ('baseline','moderate','severe'):
        pair=[p for p in ps if p['book'].startswith(cost+':') and p['book'] in BOOKS]
        assert len({(p['entry'],p['quantity']) for p in pair})==1
    assert book.reconcile()


def test_challenger_membership_half_size_and_filter(book):
    cycle(book,signals=[short(filtered=False)])
    names={p['book'] for p in book.positions()}
    assert all(not n.endswith(':I') and not n.endswith(':IF') for n in names)
    for cost in ('baseline','moderate','severe'):
        full=next(p for p in book.positions() if p['book']==cost+':IC')
        half=next(p for p in book.positions() if p['book']==cost+':IM')
        assert half['quantity']<=full['quantity']/2+.001
    assert len(book.positions())==9
    assert book.db.execute('SELECT count(*) FROM decisions').fetchone()[0]==15


def test_same_snapshot_costs_have_separate_cash_and_gates(book):
    cycle(book,signals=[short()])
    ps={p['book']:p for p in book.positions()}
    assert ps['baseline:IC']['entry']>ps['moderate:IC']['entry']>ps['severe:IC']['entry']
    assert ps['baseline:IC']['entry_quote']==ps['severe:IC']['entry_quote']
    # Costs can reject separately even though the extended 3R target is unchanged.
    s=short('other','ETHUSDT',T+MINUTE);s.update(stop=101.,original_target=98.,target=97.)
    cycle(book,T+MINUTE,[s])
    severe=json.loads(book.db.execute("SELECT body FROM decisions WHERE book='severe:IC' AND uid='other'").fetchone()[0])
    assert 'original_2R_fill_gate' in severe['reasons']


def test_restart_replay_and_signal_conflict_atomicity(book):
    cycle(book,signals=[signal()]);before=book.state()
    assert cycle(book,signals=[signal()])['duplicate']
    with pytest.raises(ValueError,match='conflicting event'): cycle(book,signals=[signal('other')])
    with pytest.raises(ValueError,match='conflicting signal'): cycle(book,T+1,[signal(t=T+1)])
    assert book.state()==before
    other=PaperTrial(book.path,frozen_config());assert other.state()==before;other.db.close()


def test_midtransaction_failure_rolls_back_every_book(book):
    edit(book,streak=6,raw_streak=6,last_loss_ms=T-DAY)
    before=book.state()
    with patch.object(book,'save_position',side_effect=RuntimeError('crash')):
        with pytest.raises(RuntimeError): cycle(book,signals=[signal()])
    assert book.state()==before and not book.positions()
    assert book.db.execute('SELECT count(*) FROM events').fetchone()[0]==0
    assert book.db.execute('SELECT count(*) FROM decisions').fetchone()[0]==0


def test_abrupt_process_death_cannot_commit_partial_cash(book):
    code='''import os,sys
from pathlib import Path
from research.cipher_forward.ledger import PaperTrial
from research.cipher_forward.config import frozen_config
b=PaperTrial(Path(sys.argv[1]),frozen_config())
b.db.execute('BEGIN IMMEDIATE')
b.db.execute("UPDATE state SET body='broken'")
os._exit(23)
'''
    r=subprocess.run([sys.executable,'-c',code,str(book.path)],cwd=ROOT)
    assert r.returncode==23 and book.reconcile()


def test_corrupt_missing_or_changed_book_is_not_reinitialized(book,tmp_path):
    with pytest.raises(ValueError): PaperTrial(tmp_path/'missing.db',frozen_config())
    with pytest.raises(FileExistsError): PaperTrial(book.path,frozen_config(),create=True)
    with pytest.raises(ValueError): PaperTrial(book.path,frozen_config()|dict(max_open_positions=16))
    edit(book,cash=25000.)
    with pytest.raises(ValueError,match='reconcile'): PaperTrial(book.path,frozen_config())


@pytest.mark.parametrize('halt',[dict(killed={'reason':'drawdown'}),dict(supervision_gap={'reason':'gap'}),
    dict(closed_daily={str(T//DAY):-700}),dict(streak=6,raw_streak=6,last_loss_ms=T-MINUTE),
    dict(entries_daily={str(T//DAY):20})])
def test_account_rejections_preserve_opportunity(book,halt):
    edit(book,**halt);r=cycle(book,signals=[signal()])
    assert (r['new_entries'],r['opportunity_entries'])==(0,3)


def test_c24_boundary_keeps_raw_streak_and_other_halts():
    a=make_account();a.update(streak=6,raw_streak=8,last_loss_ms=T+123,killed={'reason':'dd'})
    recover(a,'C24',T+DAY);assert a['streak']==6
    recover(a,'C24',T+DAY+MINUTE);assert a['streak']==0 and a['raw_streak']==8 and a['killed']
    observe_close(a,dict(net_pnl=0,exit_ms=T+2*DAY,uid='zero'))
    assert a['streak']==1 and a['raw_streak']==9


def test_manual_halt_blocks_entries_exits_continue(book):
    cycle(book,signals=[signal()]);r=cycle(book,T+MINUTE,[signal('next','ETHUSDT',T+MINUTE,stop=98.,target=125.)],bid=111,ask=111.1,manual=True)
    assert r['exits']==15 and r['new_entries']==0 and r['opportunity_entries']==3


def test_sector_cap_and_shared_source_priority(book):
    symbols=['BTCUSDT','ETHUSDT','SOLUSDT']
    r=cycle(book,signals=[signal(str(i),s) for i,s in enumerate(symbols)])
    assert (r['new_entries'],r['opportunity_entries'])==(24,9)
    assert all(sum(p['book']==b for p in book.positions())==2 for b in BOOKS)


def test_source_priority_and_generator_candidates(book):
    rows=[signal('B'),short(),signal('H',source='H')]
    book.cycle('x',T,{'BTCUSDT':quote()},{'BTCUSDT':instrument()},iter(rows))
    assert all(p['source']=='H' for p in book.positions() if p['book'] in BOOKS)
    assert len([p for p in book.positions() if p['book']=='baseline:OPPORTUNITY'])==3


def test_gross_cap_remains_admission_ceiling(book):
    rows=[signal(str(i),s,sector='sector'+str(i)) for i,s in enumerate(frozen_config()['universe'][:10])]
    cycle(book,signals=rows)
    for name,a in book.state()['accounts'].items():
        gross=sum(p['quantity']*p['mark'] for p in book.positions() if p['book']==name)
        assert gross<=a['equity']*.5+2. # bounded entry fee/mark adjustment after last admission


@pytest.mark.parametrize('offset',[-5001,1])
def test_stale_or_future_quote_has_no_fill(book,offset):
    r=book.cycle('x',T,{'BTCUSDT':quote(t=T+offset)},{'BTCUSDT':instrument()},[signal()])
    assert r['new_entries']==r['opportunity_entries']==0


def test_missed_window_records_all_15_decisions(book):
    cycle(book,T+MINUTE,[signal()]);assert not book.positions()
    assert book.db.execute('SELECT count(*) FROM decisions').fetchone()[0]==15


def test_short_target_and_roundtrip_accounting(book):
    cycle(book,signals=[short()]);cycle(book,T+EXIT_TICK,bid=63.4,ask=63.5)
    for p in book.positions(None):
        assert p['status']=='closed' and p['exit_reason']==2 and p['net_pnl']>0
        if p['book'] in BOOKS:
            a=book.state()['accounts'][p['book']]
            assert a['cash']-20000==pytest.approx(p['net_pnl'])
    assert book.reconcile()


def test_short_stop_and_insufficient_depth_exit_remains_latched(book):
    cycle(book,signals=[short()])
    book.cycle('thin',T+EXIT_TICK,{'BTCUSDT':quote(t=T+EXIT_TICK,bid=113,ask=113.1,size='.0001')},{})
    assert all(p['pending_exit_reason']==1 and p['status']=='open' for p in book.positions())
    cycle(book,T+2*EXIT_TICK,bid=99.9,ask=100.)
    assert all(p['exit_reason']==1 and p['status']=='closed' for p in book.positions(None))


def test_exit_minute_occupancy_survives_restart(book):
    cycle(book,signals=[signal()]);cycle(book,T+MINUTE,bid=111,ask=111.1)
    r=cycle(book,T+MINUTE+1000,[signal('new',t=T+MINUTE)])
    assert r['new_entries']==0 and r['opportunity_entries']==3


def test_funding_short_credit_exact_once_unknown_blocks_but_exits_continue(book):
    t=20000*DAY+480*MINUTE-MINUTE
    cycle(book,t,[short(t=t)]);cycle(book,t+MINUTE,bid=63.4,ask=63.5)
    assert all(p['status']=='pending_funding' for p in book.positions())
    r=cycle(book,t+MINUTE+1000,[signal('new','ETHUSDT',t+MINUTE)])
    # Only I has no open C3/funding obligation; the other three arms are held.
    assert r['new_entries']==3 and r['opportunity_entries']==3
    funding={'BTCUSDT':dict(through_ms=t+2*MINUTE,rows=[dict(t=t+MINUTE,rate=.001,price=100.)])}
    cycle(book,t+2*MINUTE,funding=funding)
    old={p['book']:p['funding'] for p in book.positions(None) if p['symbol']=='BTCUSDT'}
    assert all(v<0 for v in old.values())
    cycle(book,t+3*MINUTE,funding=funding)
    assert old=={p['book']:p['funding'] for p in book.positions(None) if p['symbol']=='BTCUSDT'}
    assert book.reconcile()


def test_quote_gap_latches_only_funded_accounts_with_positions(book):
    cycle(book,signals=[short()]);cycle(book,T+2*MINUTE,bid=63.4,ask=63.5)
    for name,a in book.state()['accounts'].items():
        assert bool(a['supervision_gap'])==(not name.endswith(':I'))


def test_hourly_floor_waits_for_next_minute(book):
    cycle(book,signals=[signal(source='H')])
    cycle(book,T+MINUTE,bid=112.,ask=112.1) # floor arm below 4ATR target
    p=next(p for p in book.positions() if p['book']=='baseline:I')
    assert p['protection']['armed'] and p['protection']['effective_level']<0
    cycle(book,T+MINUTE+EXIT_TICK,bid=102.,ask=102.1)
    assert any(p['book']=='baseline:I' for p in book.positions())
    cycle(book,T+2*MINUTE,bid=102.,ask=102.1)
    p=next(p for p in book.positions(None) if p['book']=='baseline:I')
    assert p['status']=='closed' and p['exit_reason']==4


def minutes(start,n=60):
    return [[start+i*MINUTE,'100','101','99','100','2','201'] for i in range(n)]


def test_minute_aggregation_exact_turnover_missing_and_duplicate():
    a=aggregate(minutes(0),0,60*MINUTE)
    assert a.tolist()==[[100,101,99,100,120,12060]]
    assert np.isnan(aggregate(minutes(0,59),0,60*MINUTE)).all()
    with pytest.raises(ValueError): aggregate(minutes(0)+minutes(0,1),0,60*MINUTE)
    with pytest.raises(ValueError): aggregate(minutes(MINUTE),0,60*MINUTE)


def test_seed_restart_continuation_and_backwards_clock(tmp_path):
    hour=60*MINUTE;root=tmp_path/'seed'
    store=SeedStore(root,['BTCUSDT'],initialize_asof=804*hour)
    def get(path,**kw):
        return dict(result=dict(symbol=kw['symbol'],category='linear',list=minutes(kw['start'],(kw['end']+1-kw['start'])//MINUTE)))
    a=store.advance('BTCUSDT',804*hour,get)
    receipt=store.receipt();assert a.shape==(805,6) and np.isnan(a[0]).all()
    restarted=SeedStore(root,['BTCUSDT']);b=restarted.advance('BTCUSDT',805*hour,get)
    np.testing.assert_array_equal(a,b[:-1])
    assert restarted.receipt()['manifest_sha256']==receipt['manifest_sha256']
    with pytest.raises(ValueError): restarted.advance('BTCUSDT',804*hour,get)
    with pytest.raises(ValueError): SeedStore(root,['ETHUSDT'])


def test_public_allowlist_cannot_submit_orders():
    m=Market()
    with pytest.raises(ValueError,match='allowlisted'): m.get('../order/create',symbol='BTCUSDT')
    with pytest.raises(ValueError,match='allowlisted'): m.get('order/create')


def test_zero_signal_scan_retains_unavailable_instruments():
    class Feed:
        universe=['BTCUSDT','OLDUSDT']
        def histories(self,s,asof): return dict(symbol=s,unavailable=s=='OLDUSDT',hours=[],instrument={} if s=='BTCUSDT' else None)
        def evaluate(self,h,btc,asof): return [],[],[dict(symbol=h['symbol'],unavailable=h['unavailable'])]
    s=scan(Feed(),T)
    assert s['coverage']==2 and s['unavailable']==1 and not s['ready']


def test_report_r_costs_attribution_and_no_opportunity_roi(book):
    cycle(book,signals=[short()]);cycle(book,T+MINUTE,bid=63.4,ask=63.5)
    r=report(book,T+MINUTE)
    a=r['accounts']['baseline:IC']
    assert a['closed_net_R']>0 and a['calendar_years'] and a['attribution']['symbol']['BTCUSDT']['closed']==1
    assert 'return_pct' not in r['opportunities']['baseline:OPPORTUNITY']
    assert a['assumed_slippage_cost']>0 and a['fees']>0
    r['verification']={'activation_verified':False}
    assert '<table>' in render(r) and 'not the 2022' in render(r)


def test_retest_missing_candle_never_uses_old_open():
    p=signal(source='H')|dict(next_minute=T,touched=False,boundary=100)
    assert advance_retest(p,[],T+MINUTE)[2]=='retest_missing_minute'
    with pytest.raises(ValueError): parse_bars(minutes(T,1)*2,MINUTE,T+MINUTE)


def test_zero_fills_only_verify_after_fresh_future_scan_and_receipts(book,tmp_path):
    hour=60*MINUTE;cutoff=T//hour*hour+hour;now=cutoff+65000
    seed=SeedStore(tmp_path/'seed',frozen_config()['universe'],initialize_asof=cutoff)
    atomic_json(tmp_path/'warmup.json',dict(ready=True,seed=seed.receipt()))
    atomic_json(tmp_path/'deployment.json',dict(image_id='test-only-image',release='a'*40))
    atomic_json(tmp_path/'status.json',dict(heartbeat_ms=now,release='a'*40))
    book.save_feed('first_forward_hour',cutoff)
    cycle(book,now)
    v=report_and_verify(book,now,tmp_path,tmp_path/'seed')['verification']
    assert not v['activation_verified'] and 'first future scan pending' in v['failures']
    book.save_feed('last_scan',dict(hour=cutoff,coverage=96,errors=0,available=79,unavailable=17,completed_ms=now))
    v=report_and_verify(book,now,tmp_path,tmp_path/'seed')['verification']
    assert v['activation_verified'] and v['zero_fills_valid'] and not book.positions()
    v=report_and_verify(book,now+45001,tmp_path,tmp_path/'seed')['verification']
    assert not v['activation_verified'] and 'worker heartbeat not fresh' in v['failures']


def test_history_snapshot_revisions_are_visible_not_overwritten(book):
    book.history_snapshot(T,dict(BTCUSDT=dict(hours=[])))
    first=book.db.execute('SELECT sha256,payload FROM history_snapshots').fetchone()
    book.history_snapshot(T,dict(BTCUSDT=dict(hours=[{'changed':True}])))
    second=book.db.execute('SELECT sha256,payload FROM history_snapshots').fetchone()
    assert tuple(first)==tuple(second)
    assert book.db.execute("SELECT count(*) FROM observations WHERE kind='history_revision'").fetchone()[0]==1
