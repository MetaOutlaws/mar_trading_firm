"""Closed-hour causal contexts; no outcome variables enter these calculations."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent.parent
for name in ['hourly_adx_filter_20261007','hourly_rsi_filter_20261008','hourly_connors_filter_20261008','hourly_extension_regime_20261008']:
    sys.path.insert(0,str(ROOT/name))
import adx_rule as adx
import rsi_rule as rsi
import connors_rule as crsi
import regime_rule as er

def context(c):
    adx.validate_minutes(c)
    b=c.resample('h',closed='left',label='right').agg(open=('open','first'),high=('high','max'),
        low=('low','min'),close=('close','last'),volume=('volume','sum'))
    a=adx.adx_frame(b);r=rsi.rsi_frame(b.close);cr=crsi.connors_frame(b.close)
    prev=b.close.shift(1)
    tr=pd.concat([b.high-b.low,(b.high-prev).abs(),(b.low-prev).abs()],axis=1).max(axis=1)
    b['prior_atr']=a.smoothed_tr.shift(1)
    b['prior_atr_pct']=b.prior_atr/b.close
    b['volume_ratio']=b.volume/b.volume.shift(1).rolling(20,min_periods=20).median().replace(0,np.nan)
    b['compression']=tr.shift(1).rolling(6,min_periods=6).mean()/tr.shift(1).rolling(60,min_periods=60).median().replace(0,np.nan)
    b['signal_tr_atr']=tr/b.prior_atr
    b['rsi14']=r.filter_rsi14;b['filter_crsi']=cr.filter_crsi;b['adx14']=a.adx14
    b['r24']=b.close.pct_change(24,fill_method=None)
    b['high20']=b.high.shift(1).rolling(20,min_periods=20).max()
    b['low20']=b.low.shift(1).rolling(20,min_periods=20).min()
    b=b.join(er.context(b.close));b['last_input_minute']=b.index-pd.Timedelta(minutes=1)
    return b

def at_entries(q,records,btc):
    x=q.reindex(pd.DatetimeIndex(records.entry)).copy()
    if x.index.has_duplicates:raise ValueError('duplicate signal hour per token')
    x['side']=records.side.to_numpy()
    x['btc24']=btc.reindex(x.index).to_numpy()
    x['extension_atr']=x.side*(x.close-np.where(x.side==1,x.high20,x.low20))/x.prior_atr
    x['aligned_rsi14']=x.side*(x.rsi14-50)
    x['aligned_crsi']=x.side*(x.filter_crsi-50)
    x['aligned_btc24']=x.side*x.btc24;x['aligned_own24']=x.side*x.r24
    x['aligned_body_atr']=x.side*(x.close-x.open)/x.prior_atr
    return x

def verify_indicators(c,q,records):
    ix=pd.DatetimeIndex(records.entry)
    aa=adx.independent_context(c).reindex(ix)
    rr=rsi.independent_context(c).reindex(ix)
    cc=crsi.independent_context(c).reindex(ix)
    for actual,expected in [(q.loc[ix,'adx14'],aa.adx14),(q.loc[ix,'rsi14'],rr.filter_rsi14),(q.loc[ix,'filter_crsi'],cc.filter_crsi)]:
        assert np.allclose(actual,expected,atol=1e-9,rtol=0)
    for t in ix:
        assert np.isclose(q.loc[t,'efficiency24_before_signal'],er.independent_at(c,t),atol=1e-11,rtol=0)
    return len(ix)*4
