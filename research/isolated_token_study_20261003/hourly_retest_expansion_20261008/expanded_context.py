"""Offline additional-token contexts. No runtime approval or execution changes.

The old research confirmation helper and paper market-context binder accept
only reference symbols. Use the protocol's exact sign rule here, and validate
compression through the runtime's symbol-free numerical calculator. Never call
latest_signal or widen an approval allowlist.
"""
from dataclasses import replace
import sys
import numpy as np
import pandas as pd

def btc_confirmation(symbol, side, returns):
    if side not in (-1,1):raise ValueError('side must be +/-1')
    x=np.asarray(returns,float)
    return np.isfinite(x) & (np.ones(x.shape,dtype=bool) if symbol=='BTCUSDT' else side*x>0)

def contexts(rep,c,f,btc,btc_ohlcv,symbol,member,begin,end,runtime):
    b=rep.feature_frame(c,f,btc.btc24,60)
    # Exact join supersedes the predecessor feature builder's forward fill.
    b['btc24']=btc.btc24.reindex(b.index)
    q=rep.cr.hourly_context(c);ind=rep.cr.independent_context(c)
    state=rep.er.context(c.close.resample('h',closed='left',label='right').last())
    geo=rep.minute_context(c)
    start,stop=[c.index.searchsorted(pd.Timestamp(v,tz='UTC')) for v in [begin,end]]
    ranks=member[(member.symbol==symbol)&member.eligible].set_index('month')['rank']
    candidates=[];checks=0
    for side in [1,-1]:
        g=rep.compression_entries(b,side,start,stop).copy()
        g['rank']=pd.Series(g.index.strftime('%Y-%m'),index=g.index).map(ranks)
        g=g[g['rank'].notna()].copy();g['symbol']=symbol;g['side']=side;g['entry']=g.index
        g=g.join(rep.cr.context_at(q,g.index)).join(btc.reindex(g.index).drop(columns=['btc24'])).join(state)
        g['entry_boundary']=g.high20 if side==1 else g.low20
        g['extension_atr'],g['passes_extension']=rep.extension(g.close,g.entry_boundary,g.prior_atr,side)
        g['passes_crsi']=rep.cr.gate(g.filter_crsi,side)
        g['passes_btc']=btc_confirmation(symbol,side,g.btc24)
        g['passes_approved']=g.passes_crsi & g.passes_btc & (g.directional|g.passes_extension)
        for row in g.itertuples():
            T=row.entry
            for col in ['filter_crsi','price_rsi3','streak_rsi2','rank100','streak','return1']:
                assert np.isclose(getattr(row,col),ind.loc[T,col],rtol=1e-11,atol=1e-9),(symbol,T,col)
            assert np.isclose(row.efficiency24_before_signal,rep.er.independent_at(c,T),atol=1e-12)
            x=geo.loc[T];boundary=x.high20 if side==1 else x.low20
            for a,z in [(row.prior_atr,x.prior_atr),(row.entry_boundary,boundary),(row.close,x.signal_close)]:
                assert np.isclose(a,z,atol=1e-9,rtol=1e-11)
            assert row.crsi_asof==row.feature_asof==T
            assert row.regime_asof==T-pd.Timedelta(hours=1) and row.crsi_last_minute<T
            if np.isfinite(row.btc24):assert row.btc_asof==T and row.btc_last_minute<T
            else:assert not row.passes_btc and not row.passes_approved
            checks+=1
        candidates.append(g)
    raw=pd.concat(candidates)
    # Independent full-hour calculator: production compression math without
    # symbol binding or execution, scalar Connors components, array-based ER.
    sys.path.insert(0,str(runtime))
    from core.strategy.base import SignalSide
    from core.strategy.hourly_compression_v1 import HourlyCompressionV1Strategy as Compression
    h=c.resample('h').agg(dict(open='first',high='max',low='min',close='last',volume='sum'))
    closes=c.close.to_numpy().reshape(-1,60)[:,-1]
    cumulative=np.r_[0,np.cumsum(np.abs(np.diff(closes)))]
    er=np.full(len(closes),np.nan)
    net=np.abs(closes[24:-1]-closes[:-25]);path=cumulative[24:-1]-cumulative[:-25]
    er[25:]=np.divide(net,path,out=np.zeros_like(net),where=path!=0)
    independent_er=pd.Series(er,index=ind.index)
    ix=b.index[(b.index>=pd.Timestamp(begin,tz='UTC'))&(b.index<pd.Timestamp(end,tz='UTC'))]
    valid=b.loc[ix,'eligible'].to_numpy() & ix.strftime('%Y-%m').isin(ranks.index)
    hourly_checks=0
    for side in [SignalSide.LONG,SignalSide.SHORT]:
        rule=Compression(replace(Compression().params,side=side));full=rule.generate_signals(h)
        compression=full.loc[ix-pd.Timedelta(hours=1),'signal'].to_numpy()==side.sign
        crsi=ind.filter_crsi.reindex(ix).to_numpy()
        crsi_ok=np.isfinite(crsi)&((crsi<=90) if side.sign==1 else (crsi>=10))
        boundary=geo.high20.reindex(ix).to_numpy() if side.sign==1 else geo.low20.reindex(ix).to_numpy()
        atr=geo.prior_atr.reindex(ix).to_numpy();price=geo.signal_close.reindex(ix).to_numpy()
        extension=side.sign*(price-boundary)/atr
        efficiency=independent_er.reindex(ix).to_numpy()
        cap=np.isfinite(efficiency)&np.isfinite(extension)&((efficiency>=.30)|(extension<=1.))
        expected=compression & crsi_ok & btc_confirmation(symbol,side.sign,btc.btc24.reindex(ix)) & cap
        observed=ix.isin(raw[(raw.side==side.sign)&raw.passes_approved].index)
        assert np.array_equal(expected[valid],observed[valid]),(symbol,side,'offline independent signal parity')
        hourly_checks+=int(valid.sum())
    return raw,dict(independent_contexts=checks,independent_hour_side_checks=hourly_checks,
                    production_compression_numeric_frames=2,production_approval_unchanged=True)
