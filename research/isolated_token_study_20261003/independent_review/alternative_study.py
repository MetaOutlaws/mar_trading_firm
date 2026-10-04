"""Fixed 20-candidate independent research. Offline and no production imports."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import study

def hourly(c):
    b=c.resample('1h',closed='left',label='right').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'})
    count=c.close.resample('1h',closed='left',label='right').count()
    return b.loc[count==60]

def continuation_features(c):
    b=hourly(c);prev=b.close.shift()
    atr=pd.concat([b.high-b.low,(b.high-prev).abs(),(b.low-prev).abs()],axis=1).max(axis=1).rolling(24,min_periods=24).mean()
    ap=atr/b.close
    b['atr']=atr;b['filter']=ap>ap.shift().rolling(720,min_periods=720).median()
    b['long']=(b.close>b.high.shift().rolling(24).max())&(b.close>b.close.ewm(span=168,adjust=False,min_periods=720).mean())
    b['short']=(b.close<b.low.shift().rolling(24).min())&(b.close<b.close.ewm(span=168,adjust=False,min_periods=720).mean())
    return b

def continuation(tape,b,side,filtered,slip,begin,end):
    mask=b.long if side==1 else b.short
    if filtered:mask=mask&b['filter']
    sig=b.loc[mask];rows=[];last=None
    for ts,r in sig.iterrows():
        if ts<begin or ts+pd.Timedelta(hours=24)>end or ts not in tape.idx:continue
        if last is not None and ts<=last:continue
        ep=float(tape.c.loc[ts,'open'])*(1+side*slip)
        stop=1.5*r.atr/ep;target=3*r.atr/ep
        if not 0<stop<1 or not 0<target<1:continue
        t=tape.run(pd.DatetimeIndex([ts]),side,target,stop,slip,begin,end)
        if t.empty:continue
        t['atr_at_signal']=r.atr; rows.append(t);last=t.exit_bar.iloc[0]
    return pd.concat(rows,ignore_index=True) if rows else pd.DataFrame()

def residual_features(token,btc):
    a=np.log(hourly(token).close).diff();b=np.log(hourly(btc).close).diff()
    beta=a.rolling(720,min_periods=720).cov(b)/b.rolling(720,min_periods=720).var()
    beta=beta.shift();res=a-beta*b
    std=res.shift().rolling(720,min_periods=720).std()
    z=res/std
    return pd.DataFrame({'beta':beta,'z':z,'long':(z< -2.5)&(z.shift()>=-2.5),'short':(z>2.5)&(z.shift()<=2.5)})

def pair_trade(token,btc,ts,beta,side,slip,btcslip,exit_time):
    i=token.idx.get_indexer([ts])[0];j=token.idx.get_indexer([exit_time])[0]
    if i<0 or j<0 or j<=i:return None
    w=1/(1+beta);v=beta/(1+beta)
    ep=token.o[i]*(1+side*slip);eb=btc.o[i]*(1-side*btcslip)
    # Synchronized OPEN observations; never combine unrelated leg extremes.
    package=side*w*(token.o[i+1:j+1]/ep-1)-side*v*(btc.o[i+1:j+1]/eb-1)
    hit=np.flatnonzero(package<=-.01)
    stopped=bool(len(hit))
    if stopped:j=i+1+int(hit[0])
    xp=token.o[j]*(1-side*slip);xb=btc.o[j]*(1+side*btcslip)
    gross=side*w*(xp/ep-1)-side*v*(xb/eb-1)
    fees=study.FEE*(w*(1+xp/ep)+v*(1+xb/eb))
    def fc(tape,d,e):
        a=np.searchsorted(tape.ft,ts.value,side='right');b=np.searchsorted(tape.ft,tape.idx[j].value,side='right')
        return d*(tape.fp[b]-tape.fp[a])/e
    funding=w*fc(token,side,ep)+v*fc(btc,-side,eb)
    return {'entry':ts,'exit_bar':token.idx[j],'side':side,'beta':beta,'token_weight':w,'btc_weight':v,
        'entry_price':ep,'btc_entry_price':eb,'exit_price':xp,'btc_exit_price':xb,
        'gross_return':gross,'fees':fees,'funding':funding,'net_return':gross-fees-funding,
        'reason':'stop' if stopped else 'time','ambiguous':False,'holding_minutes':j-i}

def residual(token,btc,b,side,normalize,slip,btcslip,begin,end):
    sig=b.loc[b.long if side==1 else b.short];rows=[];last=None
    for ts,r in sig.iterrows():
        if ts<begin or ts+pd.Timedelta(hours=4)>=end:continue
        if last is not None and ts<=last:continue
        if not np.isfinite(r.beta) or r.beta<=0:continue
        exit_time=ts+pd.Timedelta(hours=4);normal=False
        if normalize:
            zs=b.loc[(b.index>ts)&(b.index<exit_time),'z']
            hit=zs.loc[zs>=0] if side==1 else zs.loc[zs<=0]
            if len(hit):exit_time=hit.index[0];normal=True
        trade=pair_trade(token,btc,ts,float(r.beta),side,slip,btcslip,exit_time)
        if trade:
            if normal and trade['reason']=='time':trade['reason']='normalization'
            rows.append(trade);last=trade['exit_bar']
    return pd.DataFrame(rows)

def main(cache,out):
    out.mkdir(parents=True,exist_ok=False)
    manifest={'status':'auditing','study':'20 preregistered alternative cells','source_hashes':{},'data':{},'approval':'NONE'}
    here=Path(__file__).parent
    for name in ['NEXT_EXPERIMENTS.md','EXECUTION_ADDENDUM.md','alternative_study.py']:
        manifest['source_hashes'][name]=hashlib.sha256((here/name).read_bytes()).hexdigest()
    tape={};cf={};rf={};rows=[];results={};configs={}
    # Store immutable assumptions before calculating returns.
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    for sym in study.SYMBOLS:
        cp=cache/f'{sym}_1m.parquet';fp=cache/'funding'/f'{sym}_funding.parquet'
        c=study.load(cp);f=study.load(fp,True)
        manifest['data'][sym]={'audit':study.audit(c,f),'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (cp,fp)}}
        # Do not load reserved returns into indicators before selecting candidates.
        cutoff=study.PARTS['validation'][1]; c=c.loc[(c.index>=study.START)&(c.index<cutoff)]
        tape[sym]=study.Tape(c,f.loc[f.index<=cutoff]);cf[sym]=continuation_features(c)
    for sym in ('ETHUSDT','SOLUSDT'):rf[sym]=residual_features(tape[sym].c,tape['BTCUSDT'].c)
    for family in ('continuation','residual'):
        for sym in study.SYMBOLS if family=='continuation' else ('ETHUSDT','SOLUSDT'):
            for side in (1,-1):
                for variant in (0,1):
                    cid=f'{family}_{sym}_{side}_{variant}'; configs[cid]={'family':family,'symbol':sym,'side':side,'variant':variant}
                    results[cid]={}
                    for part in ('discovery','validation'):
                        for stress in (1,2):
                            slip=(.001 if sym=='SOLUSDT' else .0005)*stress
                            if family=='continuation':
                                t=continuation(tape[sym],cf[sym],side,variant,slip,*study.PARTS[part])
                            else:t=residual(tape[sym],tape['BTCUSDT'],rf[sym],side,variant,slip,.0005*stress,*study.PARTS[part])
                            stats=study.score(t);results[cid][part,stress]=stats
                            rows.append({'id':cid,**configs[cid],'partition':part,'slippage_multiplier':stress,**stats})
                            if not t.empty:t.to_csv(out/f'{cid}_{part}_{stress}_trades.csv.gz',index=False)
                    print(cid,results[cid]['validation',1],flush=True)
    selection={sym:None for sym in study.SYMBOLS}
    for sym in study.SYMBOLS:
        eligible=[]
        for cid,config in configs.items():
            if config['symbol']!=sym:continue
            r=results[cid]
            passed=all(r[p,1]['trades']>=50 and r[p,1]['mean']>0 and r[p,1]['pf'] is not None and r[p,1]['pf']>=1.15 and r[p,2]['mean'] is not None and r[p,2]['mean']>0 for p in ('discovery','validation'))
            if passed:eligible.append((r['validation',1]['mean'],cid))
        if eligible:selection[sym]=max(eligible)[1]
    pd.DataFrame(rows).to_csv(out/'alternative_results.csv',index=False)
    (out/'frozen_selection.json').write_text(json.dumps(selection,indent=2))
    manifest.update(status='discovery_validation_complete',reserved_evaluation='not run; evaluate only frozen survivors',selection=selection)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('SELECTION',json.dumps(selection),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.cache,a.out)
