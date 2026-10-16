"""Causal clock, real quote interface, observed funding and SQLite regression."""
from datetime import timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import select, func

from core.execution.f111_paper import F111Runtime, _funding_for_open
from core.execution.f111_funding import observed_funding_fraction
from core.execution.paper import PaperBroker
from core.execution.paper_cash import PaperCashStore
from core.execution.broker import Instrument
from core.ledger.store import Ledger
from core.ledger.models import TradeRecord, PaperCashEvent
from core.db import session_scope
from core.strategy.f111_semantics import new_protection_state
from research.costs import CostModel
from tests.test_f111_paper import T0, _available, _pass_signal

SYMBOL = "BTCUSDT"


class Data:
    """Actual data interface, deliberately no mutable .prices dictionary."""
    def __init__(self, price=101.): self.price = price; self.quotes = 0; self.settlement_prices = {}
    def latest_price(self, symbol): self.quotes += 1; return self.price
    def fetch(self, symbol, tf, start, end):
        return pd.DataFrame({"open": [self.settlement_prices.get(start, 100.)]}, index=pd.DatetimeIndex([start]))


def setup(tmp_path, *, ledger=None, slip=0.):
    clock = [T0]; data = Data()
    broker = PaperBroker(starting_equity=10000., costs=CostModel(slippage=slip),
                         data_source=data, cash_store=PaperCashStore(tmp_path/"cash.json"), lock_cost_model=True)
    broker._now = lambda: clock[0]
    risk = SimpleNamespace(evaluate=lambda *a: SimpleNamespace(is_approved=True, quantity=1.))
    rt = F111Runtime(broker=broker, risk=risk, ledger=ledger, clock=lambda: clock[0],
                     state_path=tmp_path/"runtime.json", disable_flag=tmp_path/"disabled")
    rt.registry[SYMBOL] = _available()
    return rt, broker, data, clock


def candles(side="LONG"):
    values = [[100.8,101.2,99.9,101.], [101.,101.4,100.8,101.2]] if side == "LONG" else [[99.2,100.1,98.8,99.], [99.,99.2,98.6,98.8]]
    return pd.DataFrame(values, columns=["open","high","low","close"], index=pd.date_range(T0, periods=2, freq="min"))


@pytest.mark.parametrize("side", ["LONG", "SHORT"])
@pytest.mark.parametrize("offset", [0,15,59,61])
def test_consumer_entry_at_current_action(tmp_path, side, offset):
    rt,b,data,clock = setup(tmp_path)
    data.price = 101. if side == "LONG" else 99.
    _pass_signal(rt, side=side, close=data.price)
    clock[0] = T0 + timedelta(minutes=1, seconds=offset)
    rt._consume_minutes(SYMBOL, candles(side), clock[0])
    if offset <= 60:
        assert rt.pending[0]["status"] == "filled"
        assert b._positions[SYMBOL].entry_price == data.price
        fill = next(x for x in rt.events if x.get("simulated_fill") is not None)
        assert fill["quote_time"] == clock[0].isoformat()
        assert fill["poll_latency"] == offset
    else:
        assert rt.pending[0]["rejection_reason"] == "stale_action"
        assert not b._positions


def test_missing_current_quote_never_uses_old_candle_open(tmp_path):
    rt,b,data,clock = setup(tmp_path); _pass_signal(rt); data.price = None
    clock[0] = T0 + timedelta(minutes=1,seconds=15)
    rt._consume_minutes(SYMBOL,candles(),clock[0])
    assert not b._positions and rt.pending[0]["rejection_reason"] == "missing_candle_or_quote"


def test_slow_request_rechecks_action_clock(tmp_path):
    rt,b,data,clock = setup(tmp_path); _pass_signal(rt)
    clock[0] = T0 + timedelta(minutes=1,seconds=15); initial=clock[0]
    def slow(symbol): clock[0] += timedelta(seconds=61); return 101.
    data.latest_price = slow
    rt._consume_minutes(SYMBOL,candles(),initial)
    assert rt.pending[0]["rejection_reason"] == "stale_action" and not b._positions


def test_all_future_rows_are_excluded(tmp_path):
    rt,b,data,clock=setup(tmp_path);_pass_signal(rt)
    f=pd.concat([candles(),candles().iloc[:1].set_axis([pd.Timestamp(T0+timedelta(minutes=2))])])
    clock[0]=T0+timedelta(seconds=30);rt._consume_minutes(SYMBOL,f,clock[0])
    assert rt.pending[0]["touch_time"] is None and rt.pending[0]["reclaim_time"] is None


def open_position(rt,b,data,clock, *, side=1, ledger=None):
    data.price=100.;b._instruments[SYMBOL]=Instrument(SYMBOL,.01,.001,.001)
    fill=b.place_market_order(SYMBOL,"LONG" if side==1 else "SHORT",1.,100.,quoted_price=100.)
    assert fill.success
    p=b._positions[SYMBOL];p.observed_funding_only=True
    state=new_protection_state(entry_price=p.entry_price,side=side,prior_atr=1.,quantity=p.quantity,entry_fee=p.entry_fee)
    state.update(symbol=SYMBOL,side_name=p.side,opened_at=T0.isoformat(),last_protection_minute=T0.isoformat())
    if ledger is not None:
        state['position_id']=ledger.open_position(symbol=SYMBOL,side=p.side,quantity=p.quantity,entry_price=p.entry_price,expected_entry_price=100.,take_profit=state['target'],stop_loss=state['initial_stop'],strategy="mar_f111_r12_extension_latefloor_v1",sector="majors",signal_score=1.,signal_reason="fixture",broker_order_id=fill.order_id,entry_fee=p.entry_fee)
    rt.protection[SYMBOL]=state;b.set_stops(SYMBOL,state['target'],state['initial_stop'])


@pytest.mark.parametrize("side", [1,-1])
@pytest.mark.parametrize("restart", [False,True])
def test_repeat_and_restart_cannot_replay_protection(tmp_path, monkeypatch, side, restart):
    rt,b,data,clock=setup(tmp_path);open_position(rt,b,data,clock,side=side)
    monkeypatch.setattr('core.execution.f111_paper._funding_for_open',lambda *a:(0.,'observed fixture'))
    data.price=100.+side*3.9;clock[0]=T0+timedelta(minutes=1)
    rt._consume_minutes(SYMBOL,candles(),clock[0]);assert rt.protection[SYMBOL]['armed']
    assert rt.protection[SYMBOL]['floor_effective_at'] is None
    if restart:
        replacement=F111Runtime(broker=b,risk=rt.risk,state_path=rt.state_path,clock=lambda:clock[0]);replacement.restore();rt=replacement
    clock[0]+=timedelta(seconds=15);rt._consume_minutes(SYMBOL,candles(),clock[0])
    assert SYMBOL in b._positions and rt.protection[SYMBOL]['floor_effective_at'] is None
    clock[0]=T0+timedelta(minutes=2);rt._consume_minutes(SYMBOL,candles(),clock[0])
    assert SYMBOL in b._positions and rt.protection[SYMBOL]['floor_effective_at']==clock[0].isoformat()


def test_entry_minute_cannot_arm_and_old_quote_cannot_exit(tmp_path):
    rt,b,data,clock=setup(tmp_path);open_position(rt,b,data,clock)
    assert rt._advance_protection(SYMBOL,T0,103.9,T0,T0,0.,'fixture',T0)==[]
    clock[0]=T0+timedelta(minutes=1)
    rt._advance_protection(SYMBOL,clock[0],96.,T0,clock[0],0.,'fixture',clock[0])
    assert SYMBOL in b._positions and rt.protection[SYMBOL]['last_protection_minute']==T0.isoformat()


@pytest.mark.parametrize("side",[1,-1])
def test_target_close_uses_one_quote_and_one_slippage(tmp_path,side):
    rt,b,data,clock=setup(tmp_path,slip=.002);open_position(rt,b,data,clock,side=side)
    state=rt.protection[SYMBOL];quote=state['target']+side*.1;data.price=100.
    clock[0]=T0+timedelta(minutes=1)
    out=rt._advance_protection(SYMBOL,clock[0],quote,clock[0],clock[0],0.,'fixture',clock[0])[-1]
    assert out['simulated_fill']==pytest.approx(quote*(1-side*.002))
    assert not b._positions
    assert b.cash==pytest.approx(10000.+out['realised_net_profit'])


def response(records,code=0):return SimpleNamespace(status_code=200,json=lambda:{'retCode':code,'result':{'list':records}})
def settlement(at,rate):return {'fundingRateTimestamp':str(int(at.timestamp()*1000)),'fundingRate':str(rate)}


def test_weighted_observed_funding_drives_cash_and_floor(tmp_path,monkeypatch):
    rt,b,data,clock=setup(tmp_path);open_position(rt,b,data,clock)
    first=T0+timedelta(hours=8);end=T0+timedelta(hours=16)
    data.settlement_prices={first:120.,end:80.}
    monkeypatch.setattr('httpx.get',lambda *a,**k:response([settlement(T0,.5),settlement(first,.001),settlement(end,-.0002),settlement(end+timedelta(seconds=1),.4)]))
    clock[0]=end
    value,source=_funding_for_open(rt,SYMBOL,end);assert value==pytest.approx(.00104)
    rt._consume_minutes(SYMBOL,candles(),end)
    assert b._positions[SYMBOL].funding_accrued==pytest.approx(.104)
    assert b.cash==pytest.approx(10000.-.055-.104)
    assert rt.protection[SYMBOL]['funding_fraction']==pytest.approx(.00104)
    b.accrue_funding(end+timedelta(hours=4));assert b.cash==pytest.approx(10000.-.055-.104)
    b.record_observed_funding(SYMBOL,.104,asof=end,source=source)
    assert sum(x['kind']=='funding' for x in b._cash_store.events())==1


@pytest.mark.parametrize('records', [[{'fundingRateTimestamp':'bad','fundingRate':'bad'}],[settlement(T0+timedelta(hours=1),'nan')],[settlement(T0+timedelta(hours=1),'inf')]])
def test_malformed_observation_stays_unknown(tmp_path,monkeypatch,records):
    rt,b,data,clock=setup(tmp_path);open_position(rt,b,data,clock)
    monkeypatch.setattr('httpx.get',lambda *a,**k:response(records))
    fraction,source=_funding_for_open(rt,SYMBOL,T0+timedelta(hours=2))
    assert fraction is None and 'unknown' in source
    b.accrue_funding(T0+timedelta(hours=2));assert b.cash==pytest.approx(9999.945)


def test_full_funding_page_requires_complete_coverage(tmp_path,monkeypatch):
    rt,b,data,clock=setup(tmp_path);open_position(rt,b,data,clock)
    records=[settlement(T0+timedelta(minutes=i),.001) for i in range(1,202)]
    calls=[]
    def get(*a,**kw):
        calls.append(kw['params']['endTime']);return response(records[1:] if len(calls)==1 else records[:1])
    monkeypatch.setattr('httpx.get',get)
    value,_=_funding_for_open(rt,SYMBOL,T0+timedelta(hours=4))
    assert len(calls)==2 and calls[1]<calls[0] and value==pytest.approx(.201)
    monkeypatch.setattr('httpx.get',lambda *a,**kw:response(records[1:]))
    value,_=_funding_for_open(rt,SYMBOL,T0+timedelta(hours=4));assert value is None


def test_empty_success_zero_but_http_failure_unknown(tmp_path,monkeypatch):
    rt,b,data,clock=setup(tmp_path);open_position(rt,b,data,clock)
    monkeypatch.setattr('httpx.get',lambda *a,**kw:response([]))
    assert _funding_for_open(rt,SYMBOL,T0+timedelta(hours=1))[0]==0.
    monkeypatch.setattr('httpx.get',lambda *a,**kw:SimpleNamespace(status_code=500))
    assert _funding_for_open(rt,SYMBOL,T0+timedelta(hours=1))[0] is None


def counts():
    with session_scope() as s:return (s.scalar(select(func.count()).select_from(TradeRecord)),s.scalar(select(func.count()).select_from(PaperCashEvent)))


@pytest.mark.parametrize('crash_after_commit',[False,True,'retry_without_restart'])
def test_real_sqlite_close_crash_recovery(tmp_path,firm_db,monkeypatch,crash_after_commit):
    from core.execution import paper_settle
    ledger=Ledger(mode='paper',starting_equity=10000.)
    rt,b,data,clock=setup(tmp_path,ledger=ledger);open_position(rt,b,data,clock,ledger=ledger)
    rt.persist();before=b.cash;clock[0]=T0+timedelta(minutes=1);data.price=96.
    real=paper_settle.settle_paper_close
    def boom():raise RuntimeError('injected crash')
    def injected(**kw):
        if not crash_after_commit:kw['before_commit']=boom
        result=real(**kw)
        if crash_after_commit:boom()
        return result
    monkeypatch.setattr(paper_settle,'settle_paper_close',injected)
    with pytest.raises(RuntimeError,match='injected crash'):
        rt._advance_protection(SYMBOL,clock[0],96.,clock[0],clock[0],0.,'fixture',clock[0])
    assert b.cash==before and SYMBOL in b._positions
    assert counts()==((1,1) if crash_after_commit else (0,0))
    monkeypatch.setattr(paper_settle,'settle_paper_close',real)
    if not crash_after_commit:
        rt._advance_protection(SYMBOL,clock[0],96.,clock[0],clock[0],0.,'fixture',clock[0])
    elif crash_after_commit == 'retry_without_restart':
        out=rt._advance_protection(SYMBOL,clock[0],95.,clock[0],clock[0],0.,'fixture',clock[0])[-1]
        assert out['simulated_fill']==96. and not b._positions
    restored=PaperBroker(starting_equity=10000.,costs=b.costs,data_source=data,cash_store=PaperCashStore(tmp_path/'cash.json'),lock_cost_model=True)
    restored.hydrate(ledger.open_positions())
    assert counts()==(1,1) and not restored._positions
    assert restored.cash==pytest.approx(10000.-4.-.055-.0528)
    restored.hydrate(ledger.open_positions());assert counts()==(1,1)
    assert restored.cash==pytest.approx(10000.-4.-.055-.0528)


def test_funding_survives_open_position_hydration(tmp_path,firm_db,monkeypatch):
    ledger=Ledger(mode='paper',starting_equity=10000.)
    rt,b,data,clock=setup(tmp_path,ledger=ledger);open_position(rt,b,data,clock,ledger=ledger)
    at=T0+timedelta(hours=8);b.record_observed_funding(SYMBOL,.12,asof=at,source='fixture')
    restored=PaperBroker(starting_equity=10000.,costs=b.costs,data_source=data,cash_store=PaperCashStore(tmp_path/'cash.json'),lock_cost_model=True)
    restored.hydrate(ledger.open_positions());before=restored.cash
    assert restored._positions[SYMBOL].observed_funding_only
    restored.accrue_funding(at+timedelta(hours=8));assert restored.cash==before
    restored.record_observed_funding(SYMBOL,.12,asof=at,source='fixture');assert restored.cash==before
    assert sum(x['kind']=='funding' for x in restored._cash_store.events())==1


def test_worker_step_enters_protects_persists_and_closes(tmp_path,firm_db,monkeypatch):
    from core.execution import f111_paper
    ledger=Ledger(mode='paper',starting_equity=10000.)
    rt,b,data,clock=setup(tmp_path,ledger=ledger);_pass_signal(rt)
    rt.last_registry_at=T0;rt.last_signal_hour=T0
    data.fetch_latest=lambda *a,**kw:candles()
    monkeypatch.setattr(f111_paper,'_ATTACHED',rt)
    monkeypatch.setattr('httpx.get',lambda *a,**kw:response([]))
    engine=SimpleNamespace(broker=b,risk=rt.risk,ledger=ledger)
    clock[0]=T0+timedelta(minutes=1,seconds=15)
    f111_paper.run_attached_minute_step(engine,data=data,now=clock[0])
    row=ledger.find_open_position(SYMBOL)
    assert row is not None and row.opened_at==clock[0]
    assert b._positions[SYMBOL].opened_at==clock[0]
    data.price=104.9;clock[0]=T0+timedelta(minutes=2,seconds=15)
    f111_paper.run_attached_minute_step(engine,data=data,now=clock[0]);assert rt.protection[SYMBOL]['armed']
    clock[0]+=timedelta(seconds=15)
    f111_paper.run_attached_minute_step(engine,data=data,now=clock[0]);assert rt.protection[SYMBOL]['floor_effective_at'] is None
    data.price=104.8;clock[0]=T0+timedelta(minutes=3,seconds=15)
    f111_paper.run_attached_minute_step(engine,data=data,now=clock[0])
    assert ledger.find_open_position(SYMBOL).stop_loss_price==pytest.approx(b._positions[SYMBOL].stop_loss)
    data.price=101.5;clock[0]=T0+timedelta(minutes=4,seconds=15)
    f111_paper.run_attached_minute_step(engine,data=data,now=clock[0])
    assert not b._positions and ledger.find_open_position(SYMBOL) is None
    # The entry is mirrored. The close is still the only trade, and cash is
    # the round trip, not the entry fee a second time.
    assert counts()==(1,2)
    with session_scope() as s:
        trade=s.scalar(select(TradeRecord))
        events=list(s.scalars(select(PaperCashEvent).order_by(PaperCashEvent.id)))
        assert trade.net_pnl==pytest.approx(b.cash-10000.)
        assert [event.kind for event in events]==["open","close"]
        assert trade.cash_event_id==events[1].event_id
    assert not __import__('json').loads(rt.state_path.read_text())['protection']


def test_generic_stop_supervisor_uses_same_observed_funding(tmp_path,firm_db,monkeypatch):
    from core.execution.engine import TradingEngine, TradingPlan
    from core.risk.engine import RiskEngine
    ledger=Ledger(mode='paper',starting_equity=10000.)
    rt,b,data,clock=setup(tmp_path,ledger=ledger);open_position(rt,b,data,clock,ledger=ledger)
    at=T0+timedelta(hours=8);clock[0]=at;data.price=96.;data.settlement_prices[at]=120.
    # Setup helper's manual ledger open also uses the same historical clock.
    monkeypatch.setattr('httpx.get',lambda *a,**kw:response([settlement(at,.001)]))
    engine=TradingEngine(broker=b,risk_engine=RiskEngine(),ledger=ledger,plan=TradingPlan(entries=[]))
    assert engine._settle_paper_exit(SYMBOL,'stop_loss',at_mark=True,mark_price=96.)==1
    with session_scope() as s:
        trade=s.scalar(select(TradeRecord));event=s.scalar(select(PaperCashEvent))
        assert trade.funding==pytest.approx(.12)
        assert trade.net_pnl==pytest.approx(b.cash-10000.)
        assert event.payload['funding_status']=='observed_through_timestamp'


def test_missing_funding_keeps_exit_supervision_and_labels_incomplete(tmp_path,firm_db,monkeypatch):
    ledger=Ledger(mode='paper',starting_equity=10000.)
    rt,b,data,clock=setup(tmp_path,ledger=ledger);open_position(rt,b,data,clock,ledger=ledger)
    monkeypatch.setattr('httpx.get',lambda *a,**kw:SimpleNamespace(status_code=500))
    clock[0]=T0+timedelta(minutes=1);data.price=96.
    rt._consume_minutes(SYMBOL,candles(),clock[0])
    assert not b._positions and counts()==(1,1)
    with session_scope() as s:
        event=s.scalar(select(PaperCashEvent));assert event.payload['funding_status']=='incomplete_at_exit'


def test_successful_response_cannot_erase_observed_settlement(tmp_path,monkeypatch):
    rt,b,data,clock=setup(tmp_path);open_position(rt,b,data,clock)
    at=T0+timedelta(hours=8)
    monkeypatch.setattr('httpx.get',lambda *a,**kw:response([settlement(at,.001)]))
    assert _funding_for_open(rt,SYMBOL,at)[0]==pytest.approx(.001)
    monkeypatch.setattr('httpx.get',lambda *a,**kw:response([]))
    assert _funding_for_open(rt,SYMBOL,at+timedelta(minutes=1))[0] is None


def test_marker_migration_is_exact_guarded_and_preserves_other_fields(tmp_path):
    import json
    from scripts.upgrade_f111_execution import migrate,REVIEWED_OLD_SHA
    from core.strategy.f111_config import load_f111_config,L01_CONFIG_PATH
    path=tmp_path/'marker.json';old={'paper_only':True,'approved_case':'L01','configuration_sha256':REVIEWED_OLD_SHA,'owner_note':'retain'}
    path.write_text(json.dumps(old));original=path.read_bytes();_,digest=load_f111_config(L01_CONFIG_PATH)
    assert migrate(path,digest)['status']=='dry_run' and path.read_bytes()==original
    assert migrate(path,digest,apply=True)['status']=='marker_migrated_restart_required'
    assert json.loads(path.read_text())['owner_note']=='retain'
    assert path.with_name(path.name+'.execution-v1-backup').read_bytes()==original
    assert migrate(path,digest,apply=True)['status']=='already_current'
    path.write_text(json.dumps(dict(old,configuration_sha256='unreviewed')))
    with pytest.raises(RuntimeError,match='differs'):migrate(path,digest,apply=True)


def test_disabling_entries_keeps_existing_runtime_exit_supervision(tmp_path,monkeypatch):
    from core.execution import f111_paper
    rt,b,data,clock=setup(tmp_path);open_position(rt,b,data,clock)
    rt.last_registry_at=T0;rt.last_signal_hour=T0;data.fetch_latest=lambda *a,**kw:candles()
    rt.disable_flag.touch();monkeypatch.setattr(f111_paper,'_ATTACHED',rt)
    monkeypatch.setattr('httpx.get',lambda *a,**kw:response([]))
    clock[0]=T0+timedelta(minutes=1);data.price=96.
    engine=SimpleNamespace(broker=b,risk=rt.risk,ledger=None)
    f111_paper.run_attached_minute_step(engine,data=data,now=clock[0])
    assert not b._positions


def test_disabling_entries_rejects_already_scheduled_entry(tmp_path):
    rt,b,data,clock=setup(tmp_path);_pass_signal(rt)
    rt._advance_pending(rt.pending[0],T0,101.2,99.9,101.,None,None,T0+timedelta(minutes=1),None,None)
    rt.disable_flag.touch();clock[0]=T0+timedelta(minutes=1,seconds=15)
    rt._consume_minutes(SYMBOL,candles(),clock[0])
    assert not b._positions and rt.pending[0]['rejection_reason']=='f111_scan_disabled'
