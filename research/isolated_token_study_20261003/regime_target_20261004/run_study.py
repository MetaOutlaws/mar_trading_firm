"""Frozen no-time-limit regime/target sensitivity. No live dependencies."""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import study
from entry_trailing_20261004.execution import FundingBook

TARGETS=(.01,.015,.02,.025,.03)
PARTS={'discovery':('2022-01-01','2025-01-01'),'validation':('2025-01-01','2026-01-01')}
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def bars(c,minutes):
    g=c.resample(f'{minutes}min',closed='left',label='right')
    b=g.agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
    return b.loc[g.close.count()==minutes]

def decisions(c,tf):
    b4=bars(c,240);slow=b4.close.ewm(span=200,adjust=False,min_periods=200).mean();fast=b4.close.ewm(span=50,adjust=False,min_periods=50).mean()
    regime=pd.Series(np.where((b4.close>slow)&(fast>slow)&(fast>fast.shift(3)),1,
      np.where((b4.close<slow)&(fast<slow)&(fast<fast.shift(3)),-1,0)),index=b4.index)
    b=bars(c,tf);ema=b.close.ewm(span=20,adjust=False,min_periods=20).mean()
    r=regime.reindex(b.index,method='ffill').fillna(0).astype(int)
    crosslong=(b.close>ema)&(b.close.shift(1)<=ema.shift(1))&(r==1)
    crossshort=(b.close<ema)&(b.close.shift(1)>=ema.shift(1))&(r==-1)
    loc=c.index.get_indexer(b.index);valid=loc>=0
    return {1:loc[valid&crosslong.to_numpy()],-1:loc[valid&crossshort.to_numpy()]}, {s:loc[valid&(r.to_numpy()!=s)] for s in (1,-1)}

class BarrierTree:
    def __init__(self,a,minimum=False):
        self.n=len(a);self.size=1<<(self.n-1).bit_length();self.sign=-1 if minimum else 1
        self.tree=np.full(2*self.size,-np.inf);self.tree[self.size:self.size+self.n]=self.sign*np.asarray(a)
        k=self.size
        while k>1:
            self.tree[k//2:k]=np.maximum(self.tree[k:2*k:2],self.tree[k+1:2*k:2]);k//=2
    def first(self,start,end,threshold):
        threshold*=self.sign;size=self.size;tree=self.tree
        def search(node,l,r):
            if r<=start or l>=end or tree[node]<threshold:return end
            if r-l==1:return l
            mid=(l+r)//2
            a=search(node*2,l,mid)
            return a if a<end else search(node*2+1,mid,r)
        return search(1,0,size)

class Tape:
    def __init__(self,c,f):
        self.c=c;self.index=c.index;self.o,self.h,self.l,self.cl=[c[x].to_numpy(float) for x in ('open','high','low','close')]
        self.hi=BarrierTree(self.h);self.lo=BarrierTree(self.l,True);self.book=FundingBook(c,f)
        ns=study.epoch_ns(c.index)
        self.f0=self.book.fp[np.searchsorted(self.book.ft,ns,side='right')]
        self.f1=self.book.fp[np.searchsorted(self.book.ft,ns+60_000_000_000,side='right')]
    def raw(self,i,side,target,end,regime_i):
        ep=self.o[i];stop=ep*(1-side*.01);tp=ep*(1+side*target)
        si=(self.lo if side==1 else self.hi).first(i,end,stop)
        ti=(self.hi if side==1 else self.lo).first(i,end,tp)
        ri=regime_i
        # Existing orders at regime-review open have priority. Later bar extrema do not.
        if ri<end and ri<=min(si,ti):
            if side*(self.o[ri]-stop)<=0:return {'entry_i':i,'exit_i':ri,'quote':float(self.o[ri]),'reason':'stop','ambiguous':False,'fund_mode':'bar'}
            if side*(self.o[ri]-tp)>=0:return {'entry_i':i,'exit_i':ri,'quote':float(tp),'reason':'target','ambiguous':False,'fund_mode':'bar'}
            return {'entry_i':i,'exit_i':ri,'quote':float(self.o[ri]),'reason':'regime','ambiguous':False,'fund_mode':'open'}
        if si<end and si<=ti:
            quote=min(stop,self.o[si]) if side==1 else max(stop,self.o[si])
            return {'entry_i':i,'exit_i':si,'quote':float(quote),'reason':'stop','ambiguous':si==ti,'fund_mode':'bar'}
        if ti<end:return {'entry_i':i,'exit_i':ti,'quote':float(tp),'reason':'target','ambiguous':False,'fund_mode':'bar'}
        return {'entry_i':i,'exit_i':end-1,'quote':float(self.cl[end-1]),'reason':'boundary_mtm','ambiguous':False,'fund_mode':'close'}
    def cost(self,raw,side,slip):
        i=raw.entry_i.to_numpy(int);j=raw.exit_i.to_numpy(int);ep=self.o[i]*(1+side*slip);xp=raw.quote.to_numpy()*(1-side*slip)
        early=side*(self.f0[j]-self.f0[i])/ep;late=side*(self.f1[j]-self.f0[i])/ep
        funding=np.where(raw.fund_mode=='open',early,np.where(raw.fund_mode=='close',late,np.maximum(early,late)))
        t=raw.copy();t['entry']=self.index[i];t['exit_bar']=self.index[j];t['entry_price']=ep;t['exit_price']=xp
        t['gross_return']=side*(xp/ep-1);t['fees']=study.FEE*(1+xp/ep);t['funding']=funding;t['net_return']=t.gross_return-t.fees-t.funding
        # Open-to-open regime exits: no extra minute; intrabar durations use upper minute bound.
        t['holding_minutes']=j-i+np.where(raw.fund_mode=='open',0,1);return t
    def mtm(self,t,side,slip,start,end):
        curve=np.empty(end-start);cursor=start;realized=0.
        for row in t.itertuples():
            i,j=int(row.entry_i),int(row.exit_i)
            curve[cursor-start:i-start]=realized
            ep=row.entry_price;xp=self.cl[i:j+1]*(1-side*slip)
            mtm=side*(xp/ep-1)-study.FEE*(1+xp/ep)-side*(self.f1[i:j+1]-self.f0[i])/ep
            curve[i-start:j+1-start]=realized+mtm
            realized+=row.net_return;curve[j-start]=realized;cursor=j+1
        curve[cursor-start:]=realized
        peak=np.maximum.accumulate(np.r_[0.,curve]);dd=float(np.max(peak[1:]-curve))
        return dd

def chronological(raw):
    keep=[];last=-1
    for k,r in enumerate(raw.itertuples()):
        if r.entry_i>last:keep.append(k);last=r.exit_i
    return raw.iloc[keep].copy()

def score(t):
    if not len(t):return dict(n=0,n_closed=0,mean=None,pf=None)
    v=t.net_return.to_numpy();win=v[v>0];loss=v[v<0];closed=t.reason!='boundary_mtm';streak=maxstreak=0
    for a in v:
        streak=streak+1 if a<0 else 0;maxstreak=max(streak,maxstreak)
    cum=np.r_[0,np.cumsum(v)]
    return {'n':len(t),'n_closed':int(closed.sum()),'mean':float(v.mean()),'closed_mean':float(t.loc[closed,'net_return'].mean()) if closed.any() else None,
      'pf':float(win.sum()/-loss.sum()) if len(loss) else None,'win_rate':float((v>0).mean()),'sum_return_units':float(v.sum()),
      'average_win':float(win.mean()) if len(win) else None,'average_loss':float(loss.mean()) if len(loss) else None,'max_losing_streak':maxstreak,
      'closed_trade_drawdown':float((np.maximum.accumulate(cum)-cum).max()),'mean_gross':float(t.gross_return.mean()),'mean_fees':float(t.fees.mean()),'mean_funding':float(t.funding.mean()),
      'median_hours':float(t.holding_minutes.median()/60),'p95_hours':float(t.holding_minutes.quantile(.95)/60),'max_hours':float(t.holding_minutes.max()/60),
      'boundary_count':int((~closed).sum()),'boundary_net':float(t.loc[~closed,'net_return'].sum()),
      'target_count':int((t.reason=='target').sum()),'stop_count':int((t.reason=='stop').sum()),'regime_count':int((t.reason=='regime').sum()),'ambiguous_count':int(t.ambiguous.sum())}

def block_interval(t,alpha):
    ix=pd.DatetimeIndex(pd.to_datetime(t.entry,utc=True)).tz_localize(None).to_period('W-SUN')
    q=pd.DataFrame({'week':ix,'v':t.net_return.to_numpy()}).groupby('week').v.agg(['sum','count'])
    q=q.reindex(pd.period_range(ix.min(),ix.max(),freq='W-SUN'),fill_value=0)
    rng=np.random.default_rng(20261004);draw=rng.integers(0,len(q),size=(10000,len(q)))
    den=q['count'].to_numpy()[draw].sum(1);num=q['sum'].to_numpy()[draw].sum(1)
    return np.quantile(num[den>0]/den[den>0],[alpha/2,1-alpha/2]).tolist()

def main(cache,out):
    out.mkdir(parents=True,exist_ok=False)
    source=HERE.parent/'entry_trailing_20261004/results_box_20261004/manifest.json';expected=json.loads(source.read_text())
    manifest={'status':'running','protocol_commit':'37e5dc00f98011c4766e2b6c5cbf7186d4a9cbdc','scores_2026':False,'inputs':{},'sources':{p.name:sha(p) for p in HERE.glob('*') if p.is_file()},'approval':'NONE','time_exit':False}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));rows=[];years=[];signalcounts=[]
    for sym in study.SYMBOLS:
        for p in [cache/f'{sym}_1m.parquet',cache/'funding'/f'{sym}_funding.parquet']:
            h=sha(p);assert h==expected['data'][sym]['sha256'][p.name];manifest['inputs'][p.name]=h
        c=study.load(cache/f'{sym}_1m.parquet');f=study.load(cache/'funding'/f'{sym}_funding.parquet',True);study.audit(c,f)
        cut=pd.Timestamp('2026-01-01',tz='UTC');c=c.loc[c.index<cut];f=f.loc[f.index<=cut];tape=Tape(c,f)
        for tf in (5,15,60):
            fires,invalid=decisions(c,tf)
            for side in (1,-1):
                for part,(a,b) in PARTS.items():
                    start=int(c.index.searchsorted(pd.Timestamp(a,tz='UTC')));end=int(c.index.searchsorted(pd.Timestamp(b,tz='UTC')))
                    entries=fires[side][(fires[side]>=start)&(fires[side]<end)]
                    signalcounts.append({'symbol':sym,'tf':tf,'side':side,'partition':part,'signals':len(entries)})
                    assert len(entries)>0
                    k=np.searchsorted(invalid[side],entries,side='right');reg=np.where(k<len(invalid[side]),invalid[side][np.minimum(k,len(invalid[side])-1)],end);reg=np.minimum(reg,end)
                    for target in TARGETS:
                        for policy in ('orders','regime'):
                            cid=f'{sym}_{tf}m_{"long" if side==1 else "short"}_{target*100:g}pct_{policy}'
                            raw=pd.DataFrame([tape.raw(int(i),side,target,end,int(r) if policy=='regime' else end) for i,r in zip(entries,reg)])
                            for view in ('paired','chronological'):
                                rr=raw if view=='paired' else chronological(raw)
                                for stress in (1,2):
                                    slip=(.001 if sym=='SOLUSDT' else .0005)*stress;t=tape.cost(rr,side,slip)
                                    meta={'id':cid,'symbol':sym,'tf':tf,'side':side,'target':target,'policy':policy,'partition':part,'view':view,'slippage_multiplier':stress}
                                    metrics=score(t)
                                    metrics['mtm_drawdown']=tape.mtm(t,side,slip,start,end) if view=='chronological' else None
                                    metrics['exposure']=float(t.holding_minutes.sum()/(end-start)) if view=='chronological' else None
                                    rows.append({**meta,**metrics})
                                    if view=='chronological':
                                        t.to_csv(out/f'{cid}_{part}_{stress}_trades.csv.gz',index=False)
                                        for year,z in t.groupby(t.entry.dt.year):years.append({**meta,'entry_year':int(year),**score(z)})
                            print(sym,tf,side,part,target,policy,flush=True)
        print('TOKEN COMPLETE',sym,flush=True)
    result=pd.DataFrame(rows);result.to_csv(out/'all_results.csv',index=False);pd.DataFrame(years).to_csv(out/'by_entry_year.csv',index=False);pd.DataFrame(signalcounts).to_csv(out/'signals.csv',index=False)
    screens=[];cis=[]
    chron=result[result.view=='chronological']
    for cid,g in chron.groupby('id'):
        base=g[g.slippage_multiplier==1];stress=g[g.slippage_multiplier==2]
        passed=bool((base.n_closed>=50).all() and (base['mean']>0).all() and (base.pf>=1.15).all() and (stress['mean']>0).all())
        q=base.iloc[0];screens.append({k:q[k] for k in ['id','symbol','tf','side','target','policy']}|{'passes_screen':passed})
        if passed:
            t=pd.read_csv(out/f'{cid}_validation_1_trades.csv.gz');cis.append({'id':cid,'ci95':block_interval(t,.05),'ci_bonf180':block_interval(t,.05/180)})
    screen=pd.DataFrame(screens);screen['adjacent_pass']=False
    for _,g in screen.groupby(['symbol','tf','side','policy']):
        g=g.sort_values('target');v=g.passes_screen.to_numpy();stable=v&(np.r_[False,v[:-1]]|np.r_[v[1:],False]);screen.loc[g.index,'adjacent_pass']=stable
    screen.to_csv(out/'screen.csv',index=False);pd.DataFrame(cis).to_csv(out/'pass_intervals.csv',index=False)
    selected=[]
    for (sym,tf),g in chron[(chron.partition=='discovery')&(chron.slippage_multiplier==1)&(chron.n_closed>=50)].groupby(['symbol','tf']):
        best=g.sort_values(['mean','id'],ascending=[False,True]).iloc[0]
        selected.append({'symbol':sym,'tf':int(tf),'id':best.id})
    (out/'discovery_selected.json').write_text(json.dumps(selected,indent=2))
    manifest.update(status='complete',configurations=180,result_rows=len(result),passing_configurations=int(screen.passes_screen.sum()),adjacent_pass_configurations=int(screen.adjacent_pass.sum()),runtime={'numpy':np.__version__,'pandas':pd.__version__,'python':sys.version})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));print('COMPLETE',manifest['passing_configurations'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.cache,a.out)
