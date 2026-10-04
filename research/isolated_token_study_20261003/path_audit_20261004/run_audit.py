"""Independent offline diagnostics on archived entries. See frozen PROTOCOL.md."""
import argparse, hashlib, json, sys
from pathlib import Path
from dataclasses import replace
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import study
from entry_trailing_20261004.execution import FundingBook, fixed_horizon_trade, simulate_trade, exit_specs
from entry_trailing_20261004.features import bars_15m, compute_features, atr_price

SEED=20261004
H=240
SOURCE=Path(__file__).resolve().parents[1]/'entry_trailing_20261004/results_box_20261004'
PARTS={'discovery':(pd.Timestamp('2022-01-01',tz='UTC'),pd.Timestamp('2025-01-01',tz='UTC')), 'validation':(pd.Timestamp('2025-01-01',tz='UTC'),pd.Timestamp('2026-01-01',tz='UTC'))}

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def interval(values,entries,alpha=.05):
    v=np.asarray(values,float); entries=pd.DatetimeIndex(entries)
    good=np.isfinite(v);v=v[good];entries=entries[good]
    if not len(v):return [None,None]
    weeks=entries.tz_localize(None).to_period('W-SUN')
    z=pd.DataFrame({'v':v,'week':weeks}).groupby('week').v.agg(['sum','count'])
    # Include empty intervening calendar weeks to retain the study's inactive weeks.
    z=z.reindex(pd.period_range(weeks.min(),weeks.max(),freq='W-SUN'),fill_value=0)
    rng=np.random.default_rng(SEED); pick=rng.integers(0,len(z),size=(5000,len(z)))
    den=z['count'].to_numpy()[pick].sum(axis=1); num=z['sum'].to_numpy()[pick].sum(axis=1)
    means=num[den>0]/den[den>0]
    return np.quantile(means,[alpha/2,1-alpha/2]).tolist()

def stats(t):
    v=t.net_return.to_numpy(float); pos=v[v>0];neg=v[v<0]
    cum=np.r_[0,np.cumsum(v)];run=longest=0
    for a in v:
        run=run+1 if a<0 else 0;longest=max(longest,run)
    return {'n':len(v),'mean':float(v.mean()),'pf':float(pos.sum()/-neg.sum()) if len(neg) else None,
      'win_rate':float((v>0).mean()),'average_win':float(pos.mean()) if len(pos) else None,
      'average_loss':float(neg.mean()) if len(neg) else None,'max_losing_streak':longest,
      'additive_drawdown':float((np.maximum.accumulate(cum)-cum).max()),
      'mean_holding_minutes':float(t.holding_minutes.mean()) if 'holding_minutes' in t else H,
      'mean_giveback':float(t.giveback.mean()) if 'giveback' in t else None,
      'activation_rate':float(t.activated.mean()) if 'activated' in t else None,
      'mean_ci95':interval(v,t.entry)}

class Tape:
    def __init__(self,c,f):
        self.c=c;self.index=c.index
        self.o,self.h,self.l,self.cl=[c[k].to_numpy(float) for k in ('open','high','low','close')]
        self.book=FundingBook(c,f)
        ns=study.epoch_ns(c.index)
        self.fp0=self.book.fp[np.searchsorted(self.book.ft,ns,side='right')]
        self.fp1=self.book.fp[np.searchsorted(self.book.ft,ns+60_000_000_000,side='right')]
        self.cache={}
    def diagnostic(self,i,side,slip):
        key=(i,side,slip)
        if key in self.cache:return self.cache[key].copy()
        assert i>=0 and i+H<=len(self.index)
        ep=self.o[i]*(1+side*slip); sl=slice(i,i+H)
        favorable=self.h[sl] if side==1 else self.l[sl]
        adverse=self.l[sl] if side==1 else self.h[sl]
        quoted=side*(favorable/ep-1); adv=-side*(adverse/ep-1)
        xp=favorable*(1-side*slip)
        early=side*(self.fp0[sl]-self.fp0[i])/ep;late=side*(self.fp1[sl]-self.fp0[i])/ep
        net=side*(xp/ep-1)-study.FEE*(1+xp/ep)-np.maximum(early,late)
        hit=np.flatnonzero(adv>=.01);first_stop=int(hit[0]) if len(hit) else H
        before=net[:first_stop]; peak_i=int(np.argmax(net))
        finalxp=self.cl[i+H-1]*(1-side*slip)
        endpoint=side*(finalxp/ep-1)-study.FEE*(1+finalxp/ep)-late[-1]
        d={'entry':self.index[i], 'entry_i':i,'side':side,'mfe':float(max(0,quoted.max())),
           'mae':float(max(0,adv.max())),'peak_hypothetical_net':float(net[peak_i]),
           'peak_minute':peak_i+1,'stop_minute':first_stop+1 if first_stop<H else None,
           'net_return':float(endpoint),'net_giveback':float(net[peak_i]-endpoint),
           'positive_peak_ended_loss':bool(net.max()>0 and endpoint<0)}
        for threshold,name in [(0,'0'),(.005,'05'),(.01,'1'),(.02,'2')]:
            d['reach_'+name]=bool(np.any(before>threshold))
        self.cache[key]=d
        return d.copy()
    def execute(self,i,side,slip,spec,atr):
        return simulate_trade(self.index,self.o,self.h,self.l,self.cl,i,side,slip,spec,self.book,atr)

def eligible_controls(pool,real_i):
    idx=np.searchsorted(real_i,pool)
    left=np.where(idx>0,real_i[np.maximum(0,idx-1)],-10**12)
    right=np.where(idx<len(real_i),real_i[np.minimum(len(real_i)-1,idx)],10**12)
    return pool[(pool-left>=H)&(right-pool>=H)]

def main(cache,out,only_diagnostics=False):
    out.mkdir(exist_ok=False,parents=True)
    manifest={'status':'running','source_pr94':'d79735916aab139ced1d827d601404484cb30003','protocol_remote_commit':'4faf3d4c141b50ecc38da85521690b1d6b9c639c',
      'source_hashes':{p.name:digest(p) for p in Path(__file__).parent.glob('*') if p.is_file()},'scores_2026':False,'inputs':{},'archive_reconciliation_max_error':0,'approval':'NONE'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    recorded=json.loads((SOURCE/'manifest.json').read_text())
    summary=[];data={};tapes={};atrs={};rng=np.random.default_rng(SEED)
    for symbol in study.SYMBOLS:
        for p in (cache/f'{symbol}_1m.parquet',cache/'funding'/f'{symbol}_funding.parquet'):
            actual=digest(p);assert actual==recorded['data'][symbol]['sha256'][p.name],p
            manifest['inputs'][p.name]=actual
        c=study.load(cache/f'{symbol}_1m.parquet');f=study.load(cache/'funding'/f'{symbol}_funding.parquet',True)
        study.audit(c,f)
        c=c.loc[c.index<pd.Timestamp('2026-01-01',tz='UTC')];f=f.loc[f.index<=pd.Timestamp('2026-01-01',tz='UTC')]
        tape=Tape(c,f);tapes[symbol]=tape
        bars=bars_15m(c);features=compute_features(bars);atr=atr_price(bars,features);atrs[symbol]=atr
        train=features.loc[features.index.year==2022,'rv_24h'].dropna();edges=np.quantile(train,[.25,.5,.75])
        loc=c.index.get_indexer(features.index);good=(loc>=0)&(loc+H<=len(c))&np.isfinite(features.rv_24h.to_numpy())&np.isfinite(atr.to_numpy())
        pool=pd.DataFrame({'entry_i':loc[good],'hour':features.index[good].hour,'quarter':features.index[good].tz_localize(None).to_period('Q').astype(str),'volbin':np.searchsorted(edges,features.rv_24h.to_numpy()[good])},index=features.index[good])
        slip=.001 if symbol=='SOLUSDT' else .0005
        for part,(start,end) in PARTS.items():
            for file in sorted(SOURCE.glob(f'*{symbol}_*_{part}_comparable_trades.csv.gz')):
                archived=pd.read_csv(file);archived['entry']=pd.to_datetime(archived.entry,utc=True)
                cid=file.name.removesuffix(f'_{part}_comparable_trades.csv.gz'); side=int(archived.side.iloc[0])
                real_i=c.index.get_indexer(archived.entry);assert np.all(real_i>=0) and np.all(np.diff(real_i)>=H)
                lower=pd.Timestamp('2023-01-01',tz='UTC') if part=='discovery' and cid.startswith('model') else start
                pp=pool.loc[(pool.index>=lower)&(pool.index+pd.Timedelta(minutes=H)<=end)]
                allowed=eligible_controls(pp.entry_i.to_numpy(),real_i);pp=pp.loc[pp.entry_i.isin(allowed)]
                groups={key:v.entry_i.to_numpy() for key,v in pp.groupby(['quarter','hour','volbin'])}
                real=[];controls=[]
                for row,i in zip(archived.itertuples(),real_i):
                    d=tape.diagnostic(int(i),side,slip);d['set_id']=len(real);real.append(d)
                    err=abs(d['net_return']-row.net_return);assert err<1e-10,(cid,part,err)
                    manifest['archive_reconciliation_max_error']=max(manifest['archive_reconciliation_max_error'],err)
                    time=c.index[i];vol=features.loc[time,'rv_24h'];key=(str(time.tz_localize(None).to_period('Q')),time.hour,int(np.searchsorted(edges,vol)))
                    choices=groups.get(key,np.array([],int));picked=rng.choice(choices,min(5,len(choices)),replace=False)
                    for ci in picked:
                        q=tape.diagnostic(int(ci),side,slip);q['set_id']=d['set_id'];controls.append(q)
                real=pd.DataFrame(real);controls=pd.DataFrame(controls)
                if controls.empty:raise ValueError('No controls for '+cid)
                means=controls.groupby('set_id')[['reach_1','peak_hypothetical_net','net_return']].mean()
                pair=real.join(means,on='set_id',rsuffix='_control');diff=pair.reach_1.astype(float)-pair.reach_1_control
                matched=pair.reach_1_control.notna(); coverage=float(matched.mean())
                row={'id':cid,'symbol':symbol,'side':side,'partition':part,'n':len(real),'matched_fraction':coverage,
                 'control_draws':len(controls),'unique_controls':int(controls.entry_i.nunique()),'mean_mfe':float(real.mfe.mean()),'mean_mae':float(real.mae.mean()),
                 'mean_peak_hypothetical_net':float(real.peak_hypothetical_net.mean()),'mean_endpoint_net':float(real.net_return.mean()),
                 'mean_net_giveback':float(real.net_giveback.mean()),'positive_peak_ended_loss_fraction':float(real.positive_peak_ended_loss.mean()),
                 'mean_endpoint_given_peak_and_loss':float(real.loc[real.positive_peak_ended_loss,'net_return'].mean()),
                 'reach_0':float(real.reach_0.mean()),'reach_05':float(real.reach_05.mean()),'reach_1':float(real.reach_1.mean()),'reach_2':float(real.reach_2.mean()),
                 'control_reach_1':float(pair.reach_1_control.mean()),'paired_excess_reach_1':float(diff.mean()),
                 'paired_ci95':interval(diff,real.entry),'paired_ci_bonf18':interval(diff,real.entry,.05/18)}
                summary.append(row);data[cid,part]=(real,controls)
                real.to_csv(out/f'{cid}_{part}_paths.csv.gz',index=False);controls.to_csv(out/f'{cid}_{part}_controls.csv.gz',index=False)
                print('DIAGNOSTIC',cid,part,'n',len(real),'reach1',round(row['reach_1'],3),'excess',round(row['paired_excess_reach_1'],3),flush=True)
        tape.cache.clear()
    diag=pd.DataFrame(summary);diag.to_csv(out/'diagnostics.csv',index=False)
    selection={sym:None for sym in study.SYMBOLS}
    for sym in study.SYMBOLS:
        q=diag.loc[(diag.symbol==sym)&(diag.partition=='discovery')&(diag.n>=50)&(diag.matched_fraction>=.9)&(diag.reach_1>=.1)]
        if len(q):selection[sym]=q.sort_values(['paired_excess_reach_1','id'],ascending=[False,True]).iloc[0].id
    (out/'frozen_exit_selection.json').write_text(json.dumps(selection,indent=2));print('FROZEN',selection,flush=True)
    manifest['diagnostic_selection']=selection
    if not only_diagnostics:
        exitrows=[];checks=[]
        for sym,cid in selection.items():
            if cid is None:continue
            tape=tapes[sym];atr=atrs[sym];side=int(data[cid,'discovery'][0].side.iloc[0]);slip=.001 if sym=='SOLUSDT' else .0005
            for part in PARTS:
                real,controls=data[cid,part]
                for name,oldspec in exit_specs().items():
                    spec=replace(oldspec,holding=H)
                    for stress in (1,2):
                        simulated={}
                        for label,source in [('real',real),('control',controls)]:
                            # Reused control timestamps evaluated once per exit/cost.
                            by_i={}
                            records=[]
                            for row in source.itertuples():
                                i=int(row.entry_i)
                                if i not in by_i:by_i[i]=tape.execute(i,side,slip*stress,spec,float(atr.loc[tape.index[i]]))
                                records.append({**by_i[i],'set_id':row.set_id})
                            t=pd.DataFrame(records);simulated[label]=t
                            t.to_csv(out/f'{cid}_{part}_{name}_{stress}_{label}_exits.csv.gz',index=False)
                        realx=simulated['real'];cm=simulated['control'].groupby('set_id').net_return.mean()
                        paired=realx.net_return-realx.set_id.map(cm)
                        row={'id':cid,'symbol':sym,'partition':part,'exit':name,'slippage_multiplier':stress,**stats(realx),
                          'paired_excess_net':float(paired.mean()),'paired_excess_ci95':interval(paired,realx.entry),
                          'matched_control_mean':float(realx.set_id.map(cm).mean()),'reason_counts':json.dumps(realx.reason.value_counts().to_dict(),sort_keys=True)}
                        exitrows.append(row);print('EXIT',sym,part,name,stress,round(row['mean'],6),flush=True)
        exits=pd.DataFrame(exitrows);exits.to_csv(out/'exit_results.csv',index=False)
        if len(exits):
            for (sym,name),q in exits.groupby(['symbol','exit']):
                base=q.loc[q.slippage_multiplier==1];stressed=q.loc[q.slippage_multiplier==2]
                passed=bool(len(base)==2 and (base.n>=50).all() and (base['mean']>0).all() and (base.pf>=1.15).all() and (base.paired_excess_net>0).all() and (stressed['mean']>0).all())
                checks.append({'symbol':sym,'exit':name,'passes_exploratory_screen':passed})
        pd.DataFrame(checks).to_csv(out/'exit_screen.csv',index=False)
    manifest['status']='diagnostics_only' if only_diagnostics else 'complete'
    manifest['runtime']={'numpy':np.__version__,'pandas':pd.__version__,'python':sys.version}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));print('COMPLETE',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--diagnostics-only',action='store_true');a=p.parse_args();main(a.cache,a.out,a.diagnostics_only)
