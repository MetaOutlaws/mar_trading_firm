"""Funding-aware planned-loss protection; isolated historical research only."""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
PARENT=ROOT.parent/'parent'
sys.path.insert(0,str(PARENT/'code'))
import run_study as parent
DATA=ROOT.parent/'restored/MAR_relative_value_checkpoint_20261020'
O=ROOT/'results';N=parent.N;FEE=parent.FEE;START=parent.START
COSTS=parent.COSTS;CASES=parent.CASES

def required_stop(entry,quantity,budget,side,stop_slip,funding_paid):
    """Solve actual entry + planned stop fill + fees + paid funding = -budget."""
    if side==1:
        return (entry*(1+FEE)+(funding_paid-budget)/quantity)/((1-stop_slip)*(1-FEE))
    return (entry*(1-FEE)+(budget-funding_paid)/quantity)/((1+stop_slip)*(1+FEE))

def levels(entry,quantity,budget,side,stop_slip,initial_stop,known_funding):
    required=required_stop(entry,quantity,budget,side,stop_slip,known_funding)
    required=np.where(np.asarray(known_funding)==0.,initial_stop,required)
    if side==1:return np.maximum.accumulate(np.maximum(required,initial_stop))
    return np.minimum.accumulate(np.minimum(required,initial_stop))

def funding_path(opens,funding_ok,fc,signal,sigma,day,side,stop,delay,slip,stop_slip):
    e=day*1440+delay;entry=opens[e]*(1+side*slip);q=1000/entry
    planned_stop=stop*(1-side*stop_slip)
    budget=q*(side*(entry-planned_stop)+FEE*(entry+planned_stop))
    future=np.arange(day+1,len(signal))
    exits=future[(signal[future]==-side)|~np.isfinite(sigma[future])]
    scheduled=min(int(exits[0]*1440+delay),len(opens)-1) if len(exits) else len(opens)-1
    minutes=np.arange(e+1,scheduled+1)
    # A settlement at minute t affects the stop from t+1, never retroactively.
    known=side*q*(fc[minutes-1]-fc[e])
    stop_curve=levels(entry,q,budget,side,stop_slip,stop,known)
    bad=np.flatnonzero(~np.isfinite(opens[minutes])|~funding_ok[minutes])
    hits=np.flatnonzero(side*(opens[minutes]-stop_curve)<=0)
    first_bad=int(minutes[bad[0]]) if len(bad) else len(opens)
    hit=int(minutes[hits[0]]) if len(hits) else len(opens)
    if first_bad<=min(hit,scheduled):x=first_bad-1;reason='data_censor';trigger=x
    elif hit<=scheduled:
        x=min(hit+1,len(opens)-1);reason='stop' if hit+1<len(opens) else 'terminal';trigger=hit
        if not np.isfinite(opens[x]) or not funding_ok[x]:x=hit;reason='data_censor'
    else:
        x=scheduled;trigger=x
        reason=('opposite_signal' if len(exits) and scheduled<len(opens)-1 and signal[exits[0]]==-side
                else 'invalid_feature' if len(exits) and scheduled<len(opens)-1 else 'terminal')
    used=stop_curve[minutes<=trigger]
    last_stop=float(used[-1]) if len(used) else float(stop)
    tol=max(abs(stop)*1e-12,1e-14)
    tightened=int(np.sum(side*np.diff(np.r_[stop,used])>tol))
    return x,reason,dict(trigger=trigger,stop_at_trigger=last_stop,stop_updates=tightened,
                         tightened_at_exit=bool(side*(last_stop-stop)>tol),initial_budget=float(budget))

def control_parity():
    saved=ROOT.parent/'parent_saved/results';checks={}
    for name in ['events.parquet','decisions.parquet','signals.parquet','daily.parquet','token_daily.parquet','experimental_drawdown.csv']:
        a=pd.read_parquet(PARENT/'results'/name) if name.endswith('parquet') else pd.read_csv(PARENT/'results'/name)
        b=pd.read_parquet(saved/name) if name.endswith('parquet') else pd.read_csv(saved/name)
        pd.testing.assert_frame_equal(a,b,check_exact=True)
        checks[name]={'rows':len(a),'exact_dataframe_match':True,'bytes_match':hashlib.sha256((PARENT/'results'/name).read_bytes()).hexdigest()==hashlib.sha256((saved/name).read_bytes()).hexdigest()}
    receipt={'all_14_parent_books_reproduced':True,'checks':checks}
    (O/'CONTROL_PARITY.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

def main():
    freeze=json.loads((ROOT/'FREEZE.json').read_text())
    for path,h in freeze['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h,path
    print(json.dumps(control_parity()),flush=True)
    uni=pd.read_csv(DATA/'results/universe.csv');rows=[];decisions=[];paired=[];td=[]
    original=pd.read_parquet(PARENT/'results/events.parquet')
    curves={(arm,c,d):np.zeros(N) for arm in ['S01F','S00F'] for c,d in CASES}
    rcurves={k:np.zeros(N) for k in curves};endpoints=np.arange(1439,N,1440)
    btc=np.load(DATA/'cache/BTCUSDT.npz')['hourly_close'];audits=[]
    for i,u in enumerate(uni.itertuples()):
        z=np.load(DATA/'cache'/f'{u.symbol}.npz');op=z['opens'];hc=z['hourly_close'];fi=z['funding_index'];fr=z['funding_rate']
        fg=np.isfinite(op[fi])&np.isfinite(fr);fe=np.zeros(N);np.add.at(fe,fi[fg],op[fi[fg]]*fr[fg]);fc=np.cumsum(fe)
        ae=np.zeros(N);np.add.at(ae,fi[fg],np.abs(op[fi[fg]]*fr[fg]));af=np.cumsum(ae)
        j=np.searchsorted(fi,np.arange(N),side='right')-1
        fok=(j>=0)&(np.arange(N)-fi[np.maximum(j,0)]<=480)&fg[np.maximum(j,0)]
        symbol_parent=original[original.symbol==u.symbol]
        for entry_arm,cap in parent.ARMS.items():
            close,sigma,zscore,sig,_,_=parent.features(hc,cap);arm=entry_arm+'F'
            for cost,delay in CASES:
                slip,st=COSTS[cost];busy=-1;censored=False;curve=curves[(arm,cost,delay)];rc=rcurves[(arm,cost,delay)]
                tok=np.zeros(N//1440);tokr=np.zeros(N//1440);path_cache={}
                def trade(day):
                    e=int(day*1440+delay);side=int(sig[day]);raw=op[e];stop=raw*(1-side*2*sigma[day])
                    x,reason,detail=funding_path(op,fok,fc,sig,sigma,int(day),side,stop,delay,slip,st)
                    econ=parent.economics(side,raw,op[x],stop,slip,st,reason,fc[x]-fc[e])
                    h=int(day)*24;br=np.log(btc[h]/btc[h-168]) if h>=168 and np.isfinite(btc[h-168:h+1]).all() else np.nan
                    regime='up' if br>=np.log(1.05) else 'down' if br<=np.log(.95) else 'sideways' if np.isfinite(br) else 'unknown'
                    row=dict(symbol=u.symbol,sector=u.sector,arm=arm,entry_arm=entry_arm,cost=cost,delay=delay,day=int(day),e=e,x=x,side=side,stop=stop,stop_pct=side*(econ['entry_price']-stop)/econ['entry_price'],reason=reason,duration_days=(x-e)/1440,year=(START+pd.Timedelta(minutes=e)).year,week=e//10080,regime=regime,sigma=float(sigma[day]),z=float(zscore[day]),absolute_funding=econ['quantity']*(af[x]-af[e]),**econ,**detail)
                    row['risk_overrun_usdt']=max(0.,-row['net']-row['planned_risk'])
                    row['loss_to_budget']=max(0.,-row['net'])/row['planned_risk']
                    row['exit_kind']='funding_stop' if reason=='stop' and row['tightened_at_exit'] else reason
                    return row
                for day in np.flatnonzero(sig):
                    e=int(day*1440+delay);side=int(sig[day]);why='admitted'
                    if censored:why='after_data_censor'
                    elif e<=busy:why='token_busy'
                    elif e>=N:why='outside_window'
                    elif not np.isfinite(op[e]) or not fok[e]:why='entry_data_unavailable'
                    if why=='admitted':
                        stop=op[e]*(1-side*2*sigma[day]);ep=op[e]*(1+side*slip);dist=side*(ep-stop)/ep
                        if not .005<=dist<=.15 or stop<=0:why='stop_bound'
                    decisions.append(dict(symbol=u.symbol,arm=arm,cost=cost,delay=delay,day=int(day),decision=why))
                    if why!='admitted':continue
                    row=trade(int(day));rows.append(row);path_cache[int(day)]=row;x=row['x'];busy=x;censored=row['reason']=='data_censor'
                    q=row['quantity'];mark=side*q*(op[e:x+1]-row['entry_price'])-FEE*1000-side*q*(fc[e:x+1]-fc[e]);mark[-1]=row['net'];assert np.isfinite(mark).all()
                    # Difference accumulation avoids repeatedly adding final P&L across the remaining tape.
                    delta=np.diff(np.r_[0.,mark]);curve[e:x+1]+=delta;rc[e:x+1]+=delta/row['risk']
                    inside=(endpoints>=e)&(endpoints<=x);tok[inside]+=mark[endpoints[inside]-e];tok[endpoints>x]+=row['net'];tokr[inside]+=mark[endpoints[inside]-e]/row['risk'];tokr[endpoints>x]+=row['net_R']
                td.append(pd.DataFrame(dict(symbol=u.symbol,sector=u.sector,arm=arm,cost=cost,delay=delay,day=np.arange(N//1440),net=np.diff(np.r_[0.,tok]),net_R=np.diff(np.r_[0.,tokr]))))
                # Fixed original entries isolate exit effects from newly available opportunities.
                ref=symbol_parent[(symbol_parent.arm==entry_arm)&(symbol_parent.cost==cost)&(symbol_parent.delay==delay)]
                for rr in ref.itertuples():
                    row=path_cache.get(int(rr.day))
                    if row is None:row=trade(int(rr.day))
                    paired.append(row|{'parent_e':int(rr.e),'parent_x':int(rr.x),'parent_net':float(rr.net),'parent_R':float(rr.net_R),'parent_funding':float(rr.funding_cost),'parent_gross':float(rr.gross),'parent_fees_slippage':float(rr.fees+rr.slippage),'parent_reason':rr.reason})
        audits.append({'symbol':u.symbol,'verified_input_sha256':hashlib.sha256((DATA/'cache'/f'{u.symbol}.npz').read_bytes()).hexdigest()})
        if (i+1)%12==0:print(f'{i+1}/96 tokens; {len(rows)} new event rows; {len(paired)} fixed-entry pairs',flush=True)
    events=pd.DataFrame(rows);events.to_parquet(O/'events.parquet',index=False);pd.DataFrame(paired).to_parquet(O/'paired_entries.parquet',index=False)
    pd.DataFrame(decisions).to_parquet(O/'decisions.parquet',index=False);pd.concat(td,ignore_index=True).to_parquet(O/'token_daily.parquet',index=False)
    daily=[];drawdowns=[]
    periods={str(y):(int((pd.Timestamp(f'{y}-01-01',tz='UTC')-START).days)*1440,int((pd.Timestamp(f'{y+1}-01-01',tz='UTC')-START).days)*1440) for y in range(2022,2026)}|{'2022-25':(0,N),'2023-25':(365*1440,N)}
    for (arm,cost,delay),changes in curves.items():
        curve=np.cumsum(changes);rr=np.cumsum(rcurves[(arm,cost,delay)]);g=events[(events.arm==arm)&(events.cost==cost)&(events.delay==delay)]
        assert np.isclose(curve[-1],g.net.sum(),atol=1e-6,rtol=1e-10);assert np.isclose(rr[-1],g.net_R.sum(),atol=1e-6,rtol=1e-10)
        for day,(v,r) in enumerate(zip(np.diff(np.r_[0.,curve[endpoints]]),np.diff(np.r_[0.,rr[endpoints]]))):daily.append(dict(arm=arm,cost=cost,delay=delay,day=day,net=v,net_R=r))
        for period,(a,b) in periods.items():
            cv=np.r_[curve[a-1] if a else 0.,curve[a:b]];rv=np.r_[rr[a-1] if a else 0.,rr[a:b]]
            drawdowns.append(dict(arm=arm,cost=cost,delay=delay,period=period,opportunity_drawdown_usdt=float(np.max(np.maximum.accumulate(cv)-cv)),opportunity_drawdown_R=float(np.max(np.maximum.accumulate(rv)-rv))))
    pd.DataFrame(daily).to_parquet(O/'daily.parquet',index=False);pd.DataFrame(drawdowns).to_csv(O/'experimental_drawdown.csv',index=False)
    (O/'RUN_VERIFICATION.json').write_text(json.dumps({'input_tokens':len(audits),'events':len(rows),'pairs':len(paired),'all_final_cash_and_R_reconcile':True,'input_hashes':audits},indent=2)+'\n')
    print('Complete',len(events),'new events',flush=True)

if __name__=='__main__':main()
