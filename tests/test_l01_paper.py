"""Directional admission, causal context, migration and activation guarantees."""
import copy
import json
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from core.execution.f111_paper import F111Runtime
from core.strategy.f111_config import L01_CONFIG_PATH, load_f111_config
from core.strategy.l01_context import ALPHA, ContextStore, ContextUnavailable, SEED_SHA256, advance, decision
from scripts.enable_l01_paper import preflight, write_marker
from tests.test_f111_paper import T0, _available, _pass_signal, _runtime


def state(at=T0, *, close=110.0, tail=None, count=100):
    return {"processed_through": pd.Timestamp(at).isoformat(), "available_at": pd.Timestamp(at).isoformat(),
            "complete_bars": count, "close4": close, "ema_tail": tail or [99., 100., 101., 102.]}


def runtime(tmp_path):
    config, digest = load_f111_config(L01_CONFIG_PATH)
    r = F111Runtime(config=config, config_sha=digest, state_path=tmp_path/'state.json',
                    telemetry_path=tmp_path/'telemetry.jsonl', clock=lambda:T0)
    r.registry['BTCUSDT'] = _available()
    return r


@pytest.mark.parametrize('context', [None, {}, state(close=90), state(at=T0+timedelta(hours=4))])
def test_short_does_not_depend_on_long_context(context, tmp_path):
    r = runtime(tmp_path)
    event = _pass_signal(r, side='SHORT', long_context=context)
    assert event['gate_decision'] is True and event['rejection_reason'] is None
    assert len(r.pending) == 1 and r.pending[0]['side'] == 'SHORT'


@pytest.mark.parametrize(('context','reason'), [
    (None,'l01_context_missing'), (state(close=102),'l01_long_trend_gate'),
    (state(tail=[102.,102.,102.,102.]),'l01_long_trend_gate'),
    (state(at=T0+timedelta(hours=4)),'l01_context_after_signal'),
    (state(at=T0-timedelta(hours=4)),'l01_context_stale'),
    (state(count=52),'l01_context_warmup'),
    (state(tail=[99.,100.,101.,float('nan')]),'l01_context_invalid'),
])
def test_long_rejected_before_pending_creation(context, reason, tmp_path):
    r = runtime(tmp_path);event = _pass_signal(r, long_context=context)
    assert event['rejection_reason'] == reason and event['gate_decision'] is False
    assert r.pending == []


def test_long_pass_is_frozen_at_original_signal(tmp_path):
    r = runtime(tmp_path);event = _pass_signal(r, long_context=state())
    assert event['rejection_reason'] is None
    assert event['feature_asof_times']['l01_4h_close'] == pd.Timestamp(T0).isoformat()
    assert r.pending[0]['entry_case'] == 'L01'
    assert r.pending[0]['features']['l01_ema50'] == 102
    assert event['strategy_version'] == 'l01-long-f111-short-v1'


def test_parent_rejection_is_not_masked_by_context(tmp_path):
    event = _pass_signal(runtime(tmp_path), compression=.5, long_context=None)
    assert event['rejection_reason'] == 'compression_gate'


def test_incremental_minute_ema_matches_pandas_and_ignores_future():
    initial = state(tail=[99.,100.,101.,102.]);end = T0+timedelta(hours=12)
    minutes = pd.DataFrame({'close':np.linspace(100,140,720)},index=pd.date_range(T0,periods=720,freq='min'))
    closes = minutes.close.resample('4h',closed='left',label='right').last()
    expected = pd.Series([102.,*closes]).ewm(span=50,adjust=False).mean()
    actual = advance(initial,minutes,end)
    np.testing.assert_allclose(actual['ema_tail'],expected,rtol=0,atol=1e-12)
    future = pd.DataFrame({'close':1e8},index=pd.date_range(end,periods=240,freq='min'))
    assert advance(initial,pd.concat([minutes,future]),end) == actual
    assert initial['complete_bars'] == 100


def test_missing_internal_minute_excludes_entire_bar_and_never_interpolates():
    minutes=pd.DataFrame({'close':110.},index=pd.date_range(T0,periods=720,freq='min')).drop(pd.Timestamp(T0)+pd.Timedelta(minutes=250))
    out=advance(state(),minutes,T0+timedelta(hours=12))
    assert out['complete_bars']==102 and out['skipped_incomplete_bars']==1
    expected=(1-ALPHA)*((1-ALPHA)*102+ALPHA*110)+ALPHA*110
    assert out['ema_tail'][-1] == pytest.approx(expected)


@pytest.mark.parametrize('kind',['missing_edge','duplicate','unaligned'])
def test_bad_download_cannot_advance_context(kind):
    minutes=pd.DataFrame({'close':110.},index=pd.date_range(T0,periods=240,freq='min'))
    if kind=='missing_edge':minutes=minutes.iloc[:-1]
    if kind=='duplicate':minutes=pd.concat([minutes,minutes.iloc[:1]])
    if kind=='unaligned':minutes.index=minutes.index+pd.Timedelta(seconds=1)
    with pytest.raises(ContextUnavailable):advance(state(),minutes,T0+timedelta(hours=4))


def test_seed_provenance_and_large_catchup_rejected_in_trading_loop(tmp_path):
    store=ContextStore(root=tmp_path)
    seed=store.read('BTCUSDT');target=pd.Timestamp(seed['processed_through'])+pd.Timedelta(days=2)
    class NoNetwork:
        def fetch(self,*args,**kwargs):pytest.fail('inline historical backfill')
    with pytest.raises(ContextUnavailable,match='prepare_required'):store.refresh('BTCUSDT',target,NoNetwork())
    with pytest.raises(ContextUnavailable):store.read('../outside')


def test_store_persists_recurrence_and_recovers_without_replaying(tmp_path):
    store=ContextStore(root=tmp_path);seed=store.read('BTCUSDT');start=pd.Timestamp(seed['processed_through']);end=start+pd.Timedelta(hours=4)
    class Data:
        def fetch(self,*args,**kwargs):return pd.DataFrame({'close':seed['close4']*1.01},index=pd.date_range(start,periods=240,freq='min'))
    result=store.refresh('BTCUSDT',end,Data())
    assert ContextStore(root=tmp_path).read('BTCUSDT')==result
    raw=json.loads((tmp_path/'BTCUSDT.json').read_text());raw['seed_sha256']='wrong';(tmp_path/'BTCUSDT.json').write_text(json.dumps(raw))
    with pytest.raises(ContextUnavailable,match='provenance'):store.read('BTCUSDT')


def test_upgrade_cancels_only_unfiltered_pending_longs_preserving_positions(tmp_path):
    old=_runtime(tmp_path);_pass_signal(old);_pass_signal(old,side='SHORT');old.protection={'ETHUSDT':{'position_id':'existing','configured_stop':100.}}
    old.persist();saved=copy.deepcopy(old.protection)
    new=runtime(tmp_path);new.state_path=old.state_path;new.restore()
    assert new.pending[0]['status']=='rejected'
    assert new.pending[1]['status']=='watching'
    assert new.protection==saved
    assert new.pending[0]['source_signal_id'] in new.seen_signals


def test_existing_l01_pending_survives_restart(tmp_path):
    first=runtime(tmp_path);_pass_signal(first,long_context=state());first.persist()
    second=runtime(tmp_path);second.restore()
    assert second.pending[0]['status']=='watching'


def test_preflight_checks_context_without_requiring_a_bullish_signal():
    config={'universe':['BTCUSDT']}
    class Store:
        def read(self,symbol):return state(close=90)
    report=preflight(config,Store(),[_available()],T0)
    assert report['ready'] is True
    assert preflight(config,Store(),[],T0)['ready'] is False


def test_activation_marker_hash_is_checked_and_never_silently_overwritten(tmp_path,monkeypatch):
    import core.strategy.f111_config as cfg
    path=tmp_path/'enabled.json';monkeypatch.setattr(cfg,'L01_ENABLE_PATH',path)
    _config,digest=load_f111_config(L01_CONFIG_PATH)
    write_marker(path,digest,T0)
    assert load_f111_config()[0]['research_case']=='L01'
    with pytest.raises(RuntimeError):write_marker(path,'different',T0)
    marker=json.loads(path.read_text());marker['configuration_sha256']='wrong';path.write_text(json.dumps(marker))
    with pytest.raises(RuntimeError,match='marker'):load_f111_config()


def test_l01_config_does_not_change_short_or_exit_rules():
    baseline,_=load_f111_config();approved,_=load_f111_config(L01_CONFIG_PATH)
    for key in ['universe','sides','signal','entry','exits','paper_cost_reference','stale_action','execution_model_version']:
        assert baseline[key]==approved[key]
    assert approved['live_authorized'] is False


def test_wrong_threshold_cannot_be_enabled(tmp_path):
    config,_=load_f111_config(L01_CONFIG_PATH);config['directional_long_filter']['ema_span']=20
    path=tmp_path/'bad.json';path.write_text(json.dumps(config))
    with pytest.raises(RuntimeError,match='owner-approved'):load_f111_config(path)


@pytest.mark.parametrize('fault', ['none', 'no_restart', 'fresh_scan_only', 'wrong_hash', 'dead_process', 'stale', 'no_gate'])
def test_activation_requires_actual_current_worker_evidence(tmp_path, fault):
    from scripts.verify_l01_paper import worker_evidence
    r = runtime(tmp_path)
    start = r.note_restart()
    r.sleeve_rows([_available()])
    _pass_signal(r, long_context=state())
    rows = copy.deepcopy(r.events)
    if fault == 'no_restart':
        rows = rows[1:]
    elif fault == 'fresh_scan_only':
        for row in rows[1:]:
            row['run_id'] = 'separate-registry-command'
    elif fault == 'wrong_hash':
        rows[0]['configuration_sha256'] = 'old-config'
    elif fault == 'no_gate':
        rows = [row for row in rows if not row.get('source_signal_id')]
    now = T0 + timedelta(hours=2) if fault == 'stale' else T0
    report = worker_evidence(rows, r.config, r.config_sha, start['runtime_code_sha256'],
                             now, lambda _: fault != 'dead_process')
    assert report['verified'] is (fault == 'none')


def test_nonpaper_and_live_confirmation_refuse_activation():
    from types import SimpleNamespace
    from config.settings import TradingMode
    from core.strategy.f111_config import assert_f111_paper_only
    for settings in [SimpleNamespace(trading_mode=TradingMode.LIVE, go_live_confirmed=''),
                     SimpleNamespace(trading_mode=TradingMode.PAPER, go_live_confirmed='armed')]:
        with pytest.raises(RuntimeError):
            assert_f111_paper_only(settings)
