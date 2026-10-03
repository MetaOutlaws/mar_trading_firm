"""Offline-only candle study. No network, production imports or order interface."""
from __future__ import annotations
import argparse, hashlib, itertools, json
from pathlib import Path
import numpy as np
import pandas as pd

SYMBOLS=('BTCUSDT','ETHUSDT','SOLUSDT')
START=pd.Timestamp('2022-01-01',tz='UTC')
END=pd.Timestamp('2026-10-03',tz='UTC')
PARTS={'discovery':(START,pd.Timestamp('2025-01-01',tz='UTC')),
       'validation':(pd.Timestamp('2025-01-01',tz='UTC'),pd.Timestamp('2026-01-01',tz='UTC')),
       'reserved':(pd.Timestamp('2026-01-01',tz='UTC'),END)}
CONFIGS=list(itertools.product(('opening_range','sweep_reclaim'),(1,-1),(.03,.05),(.01,.015)))
FEE=.00055
MINUTE=pd.Timedelta(minutes=1)

def load(path:Path, funding=False):
    df=pd.read_parquet(path) if path.suffix=='.parquet' else pd.read_csv(path)
    if 'timestamp' in df: df=df.set_index('timestamp')
    idx=pd.DatetimeIndex(df.index)
    if idx.tz is None: raise ValueError(f'{path.name}: timezone must be explicit')
    df.index=idx.tz_convert('UTC')
    if not df.index.is_unique: raise ValueError(f'{path.name}: duplicate timestamps')
    df=df.sort_index()
    if funding:
        if 'funding_rate' not in df: raise ValueError('funding_rate column required')
        if not np.isfinite(df.funding_rate).all(): raise ValueError('Invalid funding')
    else:
        cols=['open','high','low','close','volume']
        if not np.isfinite(df[cols]).all().all(): raise ValueError('Nonfinite candles')
        if (df[['open','high','low','close']]<=0).any().any(): raise ValueError('Nonpositive price')
        if (df.volume<0).any(): raise ValueError('Negative volume')
        if ((df.high<df[['open','close','low']].max(axis=1))|
            (df.low>df[['open','close','high']].min(axis=1))).any(): raise ValueError('Invalid OHLC')
        if not (df.index==df.index.floor('min')).all(): raise ValueError('Unaligned minute')
    return df

def audit(c, f):
    expected=pd.date_range(START,END,freq='1min',inclusive='left')
    missing=expected.difference(c.index)
    if len(missing): raise ValueError(f'Missing {len(missing)} required 1m bars; first {missing[0]}')
    fw=f.loc[(f.index>=START-pd.Timedelta(hours=8))&(f.index<=END)]
    if len(fw)<2 or fw.index.min()>START or fw.index.max()<END-pd.Timedelta(hours=8):
        raise ValueError('Funding coverage does not span study')
    if np.diff(fw.index.asi8).max()>pd.Timedelta(hours=8).value:
        raise ValueError('Funding gap >8h; resolve using instrument settlement history')
    return {'candles':len(c),'start':str(c.index.min()),'end':str(c.index.max()),
            'missing_required_bars':len(missing),'funding_events':len(fw)}

def signals(c):
    # Signal timestamp is the CLOSE time, i.e. the next minute's open.
    b=c.resample('15min',label='right',closed='left').agg(
        {'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
    counts=c.close.resample('15min',label='right',closed='left').count()
    b=b.loc[counts==15].copy()
    hi=b.high.shift().rolling(16,min_periods=16).max()
    lo=b.low.shift().rolling(16,min_periods=16).min()
    result={('sweep_reclaim',1):b.index[(b.low<lo)&(b.close>lo)],
            ('sweep_reclaim',-1):b.index[(b.high>hi)&(b.close<hi)]}
    # Day keys reflect candle start so midnight closes belong to preceding day.
    day=(b.index-pd.Timedelta(minutes=15)).floor('D')
    first=(b.index-pd.Timedelta(minutes=15)).hour==0
    rh=b.high.where(first).groupby(day).transform('max')
    rl=b.low.where(first).groupby(day).transform('min')
    valid=(b.index.hour>=1)&(b.index.hour<8)
    prev=b.close.shift()
    for side,mask in [(1,(b.close>rh)&(prev<=rh)),(-1,(b.close<rl)&(prev>=rl))]:
        times=b.index[valid&mask]
        result[('opening_range',side)]=times[~times.floor('D').duplicated()]
    return result

class Tape:
    def __init__(self,c,f):
        self.c=c; self.idx=c.index
        self.o=c.open.to_numpy(); self.h=c.high.to_numpy()
        self.l=c.low.to_numpy(); self.cl=c.close.to_numpy()
        self.ft=f.index.asi8
        # Funding mark proxy explicitly disclosed: contemporaneous minute open.
        loc=c.index.get_indexer(f.index.floor('min'),method='pad')
        vals=f.funding_rate.to_numpy()*self.o[np.clip(loc,0,len(c)-1)]
        self.fp=np.r_[0.,np.cumsum(vals)]
    def funding(self,side,entry,exit_bar,price,exact_close=False):
        a=np.searchsorted(self.ft,entry.value,side='right')
        x=np.searchsorted(self.ft,exit_bar.value,side='right')
        y=np.searchsorted(self.ft,(exit_bar+MINUTE).value,side='right')
        early=side*(self.fp[x]-self.fp[a])/price
        late=side*(self.fp[y]-self.fp[a])/price
        return late if exact_close else max(early,late)
    def run(self,times,side,target,stop,slip,begin,end,holding=1440):
        last=-1; rows=[]
        for ts in times:
            if ts<begin or ts+holding*MINUTE>end: continue
            i=self.idx.get_indexer([ts])[0]
            if i<0 or i<=last or i+holding>len(self.idx): continue
            ep=self.o[i]*(1+side*slip)
            tp=ep*(1+side*target); sl=ep*(1-side*stop)
            hi=self.h[i:i+holding]; lo=self.l[i:i+holding]
            st=(lo<=sl) if side==1 else (hi>=sl)
            tk=(hi>=tp) if side==1 else (lo<=tp)
            hits=np.flatnonzero(st|tk)
            ambiguous=False
            if len(hits):
                off=int(hits[0]); j=i+off
                ambiguous=bool(st[off] and tk[off])
                if st[off]:
                    reason='stop'; quote=min(sl,self.o[j]) if side==1 else max(sl,self.o[j])
                else: reason='target'; quote=tp
            else: j=i+holding-1; quote=self.cl[j]; reason='time'
            xp=quote*(1-side*slip)
            gross=side*(xp-ep)/ep
            fees=FEE*(1+xp/ep)
            funding=self.funding(side,ts,self.idx[j],ep,reason=='time')
            rows.append({'entry':ts,'exit_bar':self.idx[j],'side':side,'entry_price':ep,
                'exit_price':xp,'gross_return':gross,'fees':fees,'funding':funding,
                'net_return':gross-fees-funding,'reason':reason,'ambiguous':ambiguous,
                'holding_minutes':j-i+1})
            last=j
        return pd.DataFrame(rows)

def score(t):
    if t.empty: return {'trades':0,'mean':None,'pf':None,'win_rate':None}
    r=t.net_return.to_numpy(); loss=-r[r<0].sum()
    curve=np.r_[0.,np.cumsum(r)]
    return {'trades':len(r),'mean':float(r.mean()),'pf':float(r[r>0].sum()/loss) if loss else None,
            'win_rate':float((r>0).mean()),'sum_return_units':float(r.sum()),
            'max_drawdown_return_units':float((np.maximum.accumulate(curve)-curve).max()),
            'ambiguous_exits':int(t.ambiguous.sum()),'mean_holding_minutes':float(t.holding_minutes.mean())}

def bootstrap(t,begin,end):
    if t.empty: return [None,None]
    # Include zero-trade weeks; jointly resample sums and counts to retain clustering.
    r=t.set_index('entry').net_return
    days=pd.date_range(begin.floor('D'),end.floor('D'),freq='D',inclusive='left')
    daily=r.resample('D').agg(['sum','count']).reindex(days,fill_value=0)
    w=daily.resample('W').sum().to_numpy()
    rng=np.random.default_rng(9103); means=[]
    for _ in range(2000):
        s=w[rng.integers(0,len(w),len(w))].sum(axis=0)
        if s[1]: means.append(s[0]/s[1])
    return [float(v) for v in np.quantile(means,[.005,.995])]

def opportunity(c):
    rows=[]; o=c.open.to_numpy(); h=c.high.to_numpy(); l=c.low.to_numpy()
    for hours in (1,4,8,24):
        n=hours*60
        for i in range(0,len(c)-n+1,n):
            ep=o[i]; hi=h[i:i+n]; lo=l[i:i+n]
            prior=ep/o[i-1440]-1 if i>=1440 else np.nan
            regime='unknown' if np.isnan(prior) else 'bull' if prior>.01 else 'bear' if prior<-.01 else 'chop'
            for side in (1,-1):
                fav=hi/ep-1 if side==1 else 1-lo/ep
                adv=1-lo/ep if side==1 else hi/ep-1
                row={'start':c.index[i],'utc_hour':c.index[i].hour,'prior_24h_regime':regime,
                     'horizon_h':hours,'side':side,'mfe':float(fav.max()),
                     'mae_full_window':float(adv.max())}
                row.update({f'reach_{p}pct':bool(fav.max()>=p/100) for p in (1,2,3,5)})
                for tp in (3,5):
                    hit=np.flatnonzero(fav>=tp/100); first=int(hit[0]) if len(hit) else n
                    row[f'mae_before_{tp}pct']=float(adv[:first+1].max()) if first<n else np.nan
                    for st in (1,1.5):
                        loss=np.flatnonzero(adv>=st/100); bad=int(loss[0]) if len(loss) else n
                        row[f'target_{tp}_before_stop_{st}']=bool(first<n and first<bad)
                rows.append(row)
    df=pd.DataFrame(rows)
    summary=df.groupby(['horizon_h','side']).agg(
        windows=('mfe','size'),median_mfe=('mfe','median'),p90_mfe=('mfe',lambda s:s.quantile(.9)),
        reach_1pct=('reach_1pct','mean'),reach_2pct=('reach_2pct','mean'),
        reach_3pct=('reach_3pct','mean'),reach_5pct=('reach_5pct','mean')).reset_index()
    return df,summary

def matched_random(tape,times,conf,slip,begin,end,observed):
    _,side,tp,sl=conf
    eligible=tape.idx[(tape.idx>=begin)&(tape.idx+pd.Timedelta(hours=24)<=end)]
    eligible=eligible[eligible.minute%15==0]
    sig=times[(times>=begin)&(times+pd.Timedelta(hours=24)<=end)]
    def keys(ix): return ix.strftime('%Y-%m')+'-'+ix.strftime('%H')
    ek=keys(eligible); sk=keys(sig)
    groups={k:eligible[ek==k] for k in np.unique(sk)}
    counts=pd.Series(sk).value_counts()
    null=[]
    for seed in range(200):
        rng=np.random.default_rng(seed+4100); draw=[]
        for k,n in counts.items():
            pool=groups[k]
            if len(pool)<n: raise ValueError('Insufficient matched baseline entries')
            draw.extend(pool[rng.choice(len(pool),int(n),replace=False)])
        t=tape.run(pd.DatetimeIndex(sorted(draw)),side,tp,sl,slip,begin,end)
        if not t.empty: null.append(float(t.net_return.mean()))
    return {'null_means':null,'p_raw':(1+sum(v>=observed for v in null))/(1+len(null)) if null else None}

def run(cache,out):
    out.mkdir(parents=True,exist_ok=False)
    manifest={'status':'auditing','protocol_sha256':hashlib.sha256(Path(__file__).with_name('PROTOCOL.md').read_bytes()).hexdigest(),'data':{}}
    tapes={}
    try:
        for sym in SYMBOLS:
            cp=cache/f'{sym}_1m.parquet'; fp=cache/'funding'/f'{sym}_funding.parquet'
            c=load(cp); f=load(fp,True)
            manifest['data'][sym]=audit(c,f)
            manifest['data'][sym]['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (cp,fp)}
            tapes[sym]=Tape(c.loc[(c.index>=START)&(c.index<END)],f)
    except Exception as e:
        manifest.update(status='blocked',error=str(e))
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
        raise
    selection={}; allrows=[]; sigs={}
    for sym,tape in tapes.items():
        sigs[sym]=signals(tape.c)
        eligible=[]
        for config_id,conf in enumerate(CONFIGS):
            family,side,tp,sl=conf; slip=.001 if sym=='SOLUSDT' else .0005
            stats={}
            for part in ('discovery','validation'):
                t=tape.run(sigs[sym][family,side],side,tp,sl,slip,*PARTS[part])
                stats[part]=score(t)
                allrows.append({'symbol':sym,'config_id':config_id,'family':family,'side':side,
                    'target':tp,'stop':sl,'partition':part,**stats[part]})
            if all(s['trades']>=50 and s['mean']>0 and s['pf'] is not None and s['pf']>=1.15 for s in stats.values()):
                eligible.append((stats['validation']['mean'],config_id))
        selection[sym]=max(eligible)[1] if eligible else None
    # Choices persisted before any reserved evaluation, no fallback to another config.
    (out/'frozen_selection.json').write_text(json.dumps(selection,indent=2))
    pd.DataFrame(allrows).to_csv(out/'all_discovery_validation.csv',index=False)
    finalists=[]
    for sym,tape in tapes.items():
        windows,summary=opportunity(tape.c)
        windows.to_csv(out/f'{sym}_opportunities.csv.gz',index=False)
        summary.to_csv(out/f'{sym}_opportunity_summary.csv',index=False)
        k=selection[sym]
        if k is None: continue
        conf=CONFIGS[k]; family,side,tp,sl=conf
        slip=.001 if sym=='SOLUSDT' else .0005; begin,end=PARTS['reserved']
        t=tape.run(sigs[sym][family,side],side,tp,sl,slip,begin,end)
        t.to_csv(out/f'{sym}_reserved_trades.csv',index=False)
        stress=tape.run(sigs[sym][family,side],side,tp,sl,2*slip,begin,end)
        stat=score(t); b=matched_random(tape,sigs[sym][family,side],conf,slip,begin,end,stat['mean']) if not t.empty else {}
        finalists.append({'symbol':sym,'config_id':k,'base':stat,'stress':score(stress),
            'weekly_bootstrap_99pct':bootstrap(t,begin,end),'random_baseline':b})
    # Holm adjustment across available finalist tests.
    pairs=sorted([(i,r['random_baseline']['p_raw']) for i,r in enumerate(finalists) if r['random_baseline'].get('p_raw') is not None],key=lambda x:x[1])
    prev=0.
    for rank,(i,p) in enumerate(pairs):
        prev=max(prev,min(1.,p*(len(pairs)-rank)))
        finalists[i]['random_baseline']['p_holm']=prev
    (out/'finalists.json').write_text(json.dumps(finalists,indent=2))
    manifest.update(status='exploratory_complete',approval='NONE: requires independent review and existing F-kit gates')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'selection':selection,'status':manifest['status']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--cache',type=Path,required=True); p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); run(a.cache,a.out)
