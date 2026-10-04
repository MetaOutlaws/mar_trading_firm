"""Frozen structure/zone entry-permission ablation. No production imports."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'regime_target_20261004'))
import run_study as base
HERE=Path(__file__).resolve().parent
DAY_NS=86400_000_000_000

def pivots(b):
    h=b.high.to_numpy();l=b.low.to_numpy();n=len(b);hi=np.zeros(n,bool);lo=hi.copy()
    for k in range(2,n-2):
        hi[k+2]=bool(np.all(h[k]>h[[k-2,k-1,k+1,k+2]]))
        lo[k+2]=bool(np.all(l[k]<l[[k-2,k-1,k+1,k+2]]))
    return hi,lo

def structure(b):
    hi,lo=pivots(b);highs=[];lows=[];states=[]
    for j in range(len(b)):
        if hi[j]:highs.append(float(b.high.iloc[j-2]))
        if lo[j]:lows.append(float(b.low.iloc[j-2]))
        s=0
        if len(highs)>=2 and len(lows)>=2:
            if highs[-1]>highs[-2] and lows[-1]>lows[-2]:s=1
            elif highs[-1]<highs[-2] and lows[-1]<lows[-2]:s=-1
        states.append(s)
    return pd.Series(states,index=b.index)

def zone_states(b):
    hi,lo=pivots(b);prev=b.close.shift(1)
    atr=pd.concat([b.high-b.low,(b.high-prev).abs(),(b.low-prev).abs()],axis=1).max(axis=1).rolling(14,min_periods=14).mean().to_numpy()
    active={1:[],-1:[]};out=[]
    for j in range(len(b)):
        ts=b.index[j].value;cl=float(b.close.iloc[j])
        for side in (1,-1):
            # Tuple: low,high,confirmation_ns,pivot_ns. Old zones expire and invalidation is irreversible.
            active[side]=[z for z in active[side] if ts-z[2]<=30*DAY_NS and (cl>=z[0] if side==1 else cl<=z[1])]
            if (lo[j] if side==1 else hi[j]) and np.isfinite(atr[j-2]):
                center=float(b.low.iloc[j-2] if side==1 else b.high.iloc[j-2]);w=.25*atr[j-2]
                z=(center-w,center+w,ts,b.index[j-2].value)
                if cl>=z[0] if side==1 else cl<=z[1]:active[side].append(z)
            active[side]=active[side][-6:]
        out.append((tuple(active[1]),tuple(active[-1])))
    return out

def assess_zones(state,side,bar,quote,target,now_ns):
    demand,supply=state;demand=[z for z in demand if now_ns-z[2]<=30*DAY_NS];supply=[z for z in supply if now_ns-z[2]<=30*DAY_NS]
    candidates=[]
    for z in demand if side==1 else supply:
        overlap=bar.low<=z[1] and bar.high>=z[0]
        reject=(bar.close>z[1] and bar.close>bar.open and quote>z[1]) if side==1 else (bar.close<z[0] and bar.close<bar.open and quote<z[0])
        if overlap and reject:candidates.append(z)
    chosen=None
    if candidates:chosen=min(candidates,key=lambda z:(abs(quote-(z[1] if side==1 else z[0])),-z[2]))
    targetquote=quote*(1+side*target);lower,upper=sorted([quote,targetquote]);opposing=supply if side==1 else demand
    blockers=[z for z in opposing if z[0]<=upper and z[1]>=lower]
    blocker=min(blockers,key=lambda z:abs(quote-(z[0] if side==1 else z[1]))) if blockers else None
    return chosen,blocker

def context_table(c,tf,fires,s,zb,zstates):
    b=base.bars(c,tf);all_entries=np.sort(np.r_[fires[1],fires[-1]])
    lookup_s=s.reindex(c.index[all_entries],method='ffill').fillna(0)
    state_map=dict(zip(all_entries,lookup_s.astype(int)))
    zonepos=zb.index.get_indexer(c.index[all_entries],method='pad');zmap=dict(zip(all_entries,zonepos))
    out=[]
    for side in (1,-1):
        for i in fires[side]:
            ts=c.index[i];bar=b.loc[ts];quote=float(c.open.iloc[i]);j=zmap[i];state=zstates[j] if j>=0 else ((),())
            for target in base.TARGETS:
                chosen,blocked=assess_zones(state,side,bar,quote,target,ts.value)
                r={'entry_i':int(i),'entry':ts,'side':side,'target':target,'structure_state':state_map[i],
                  'structure_ok':state_map[i]==side,'zone_rejection':chosen is not None,'room_ok':blocked is None,'zone_ok':chosen is not None and blocked is None}
                for name,z in [('chosen',chosen),('blocking',blocked)]:
                    for k,val in zip(['low','high','confirmed_ns','pivot_ns'],z or (None,)*4):r[name+'_'+k]=val
                out.append(r)
    return pd.DataFrame(out)

def run(cache,out,baseline):
    out.mkdir(parents=True,exist_ok=False)
    known=json.loads((baseline/'manifest.json').read_text());baseline_rows=pd.read_csv(baseline/'all_results.csv');baseline_rows['filter']='baseline'
    assert known['status']=='complete' and len(baseline_rows)==1440
    manifest={'status':'running','protocol_commit':'c3905f1ef2fd1f01c5b5926b3cde49d16f09cd13','source_sha256':{p.name:base.sha(p) for p in HERE.glob('*') if p.is_file()},'baseline_source_sha256':base.sha(Path(base.__file__)),'baseline_results_sha256':base.sha(baseline/'all_results.csv'),'inputs':{},'scores_2026':False,'approval':'NONE'}
    assert manifest['baseline_source_sha256']==known['sources']['run_study.py']
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));rows=[];retention=[];reconcile=[]
    for sym in base.study.SYMBOLS:
        for p in [cache/f'{sym}_1m.parquet',cache/'funding'/f'{sym}_funding.parquet']:
            h=base.sha(p);assert h==known['inputs'][p.name];manifest['inputs'][p.name]=h
        c=base.study.load(cache/f'{sym}_1m.parquet');f=base.study.load(cache/'funding'/f'{sym}_funding.parquet',True)
        cut=pd.Timestamp('2026-01-01',tz='UTC');c=c.loc[c.index<cut];f=f.loc[f.index<=cut];tape=base.Tape(c,f)
        s=structure(base.bars(c,240));zb=base.bars(c,60);zs=zone_states(zb)
        for tf in (5,15,60):
            fires,invalid=base.decisions(c,tf);audit=context_table(c,tf,fires,s,zb,zs)
            audit.to_csv(out/f'{sym}_{tf}m_entry_audit.csv.gz',index=False)
            for side in (1,-1):
                for part,(a,b) in base.PARTS.items():
                    start=int(c.index.searchsorted(pd.Timestamp(a,tz='UTC')));end=int(c.index.searchsorted(pd.Timestamp(b,tz='UTC')))
                    entries=fires[side][(fires[side]>=start)&(fires[side]<end)]
                    k=np.searchsorted(invalid[side],entries,side='right');reg=np.minimum(np.where(k<len(invalid[side]),invalid[side][np.minimum(k,len(invalid[side])-1)],end),end)
                    for target in base.TARGETS:
                        aa=audit[(audit.side==side)&(audit.target==target)].set_index('entry_i').loc[entries]
                        permission={'structure':aa.structure_ok.to_numpy(),'zones':aa.zone_ok.to_numpy(),'both':(aa.structure_ok&aa.zone_ok).to_numpy()}
                        for key,mask in permission.items():retention.append({'symbol':sym,'tf':tf,'side':side,'partition':part,'target':target,'filter':key,'opportunities':len(entries),'retained':int(mask.sum()),'structure_pass':int(aa.structure_ok.sum()),'zone_rejection_pass':int(aa.zone_rejection.sum()),'room_pass':int(aa.room_ok.sum())})
                        for policy in ('orders','regime'):
                            cid=f'{sym}_{tf}m_{"long" if side==1 else "short"}_{target*100:g}pct_{policy}'
                            raw=pd.DataFrame([tape.raw(int(i),side,target,end,int(r) if policy=='regime' else end) for i,r in zip(entries,reg)])
                            # Full chronological base result identity checked, not inferred from shared code alone.
                            rr=base.chronological(raw);original=tape.cost(rr,side,.001 if sym=='SOLUSDT' else .0005);measured=base.score(original)
                            old=baseline_rows[(baseline_rows.id==cid)&(baseline_rows.partition==part)&(baseline_rows.view=='chronological')&(baseline_rows.slippage_multiplier==1)].iloc[0]
                            assert len(original)==old.n and abs(measured['mean']-old['mean'])<1e-12
                            reconcile.append({'id':cid,'partition':part,'n':len(original),'mean_difference':measured['mean']-old['mean']})
                            for filt,mask in permission.items():
                                filtered=raw.loc[mask]
                                for view in ('paired','chronological'):
                                    rr=filtered if view=='paired' else base.chronological(filtered)
                                    for stress in (1,2):
                                        slip=(.001 if sym=='SOLUSDT' else .0005)*stress;t=tape.cost(rr,side,slip)
                                        meta={'id':cid,'symbol':sym,'tf':tf,'side':side,'target':target,'policy':policy,'partition':part,'view':view,'slippage_multiplier':stress,'filter':filt}
                                        metrics=base.score(t);metrics['mtm_drawdown']=tape.mtm(t,side,slip,start,end) if view=='chronological' else None;metrics['exposure']=float(t.holding_minutes.sum()/(end-start)) if view=='chronological' else None
                                        metrics['original_opportunities']=len(entries);metrics['retained_opportunities']=int(mask.sum());rows.append({**meta,**metrics})
                                        if view=='chronological':t.to_csv(out/f'{cid}_{filt}_{part}_{stress}_trades.csv.gz',index=False)
            print('COMPLETE',sym,tf,flush=True)
    result=pd.concat([baseline_rows,pd.DataFrame(rows)],ignore_index=True);result.to_csv(out/'all_results.csv',index=False);pd.DataFrame(retention).to_csv(out/'retention.csv',index=False);pd.DataFrame(reconcile).to_csv(out/'baseline_reconciliation.csv',index=False)
    chron=result[result.view=='chronological'];screen=[];cis=[]
    for (cid,filt),g in chron.groupby(['id','filter']):
        b=g[g.slippage_multiplier==1];st=g[g.slippage_multiplier==2]
        passed=bool((b.n_closed>=50).all() and (b['mean']>0).all() and (b.pf>=1.15).all() and (st['mean']>0).all())
        q=b.iloc[0];screen.append({k:q[k] for k in ['id','symbol','tf','side','target','policy','filter']}|{'passes_screen':passed})
        if passed:
            fp=(baseline/f'{cid}_validation_1_trades.csv.gz') if filt=='baseline' else out/f'{cid}_{filt}_validation_1_trades.csv.gz'
            t=pd.read_csv(fp);cis.append({'id':cid,'filter':filt,'ci95':base.block_interval(t,.05),'ci_bonf720':base.block_interval(t,.05/720)})
    ss=pd.DataFrame(screen);ss['adjacent_pass']=False
    for _,g in ss.groupby(['symbol','tf','side','policy','filter']):
        g=g.sort_values('target');v=g.passes_screen.to_numpy();ss.loc[g.index,'adjacent_pass']=v&(np.r_[False,v[:-1]]|np.r_[v[1:],False])
    ss.to_csv(out/'screen.csv',index=False);pd.DataFrame(cis).to_csv(out/'pass_intervals.csv',index=False)
    select=[]
    for (sym,tf,filt),g in chron[(chron.partition=='discovery')&(chron.slippage_multiplier==1)&(chron.n_closed>=50)].groupby(['symbol','tf','filter']):
        q=g.sort_values(['mean','id'],ascending=[False,True]).iloc[0];select.append({'symbol':sym,'tf':int(tf),'filter':filt,'id':q.id})
    (out/'discovery_selected.json').write_text(json.dumps(select,indent=2))
    manifest.update(status='complete',total_configurations=720,result_rows=len(result),passes=int(ss.passes_screen.sum()),adjacent_passes=int(ss.adjacent_pass.sum()),baseline_reconciliation_max_error=float(pd.DataFrame(reconcile).mean_difference.abs().max()))
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2));print('FINISHED',manifest['passes'],flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);a=p.parse_args();run(a.cache,a.out,a.baseline)
