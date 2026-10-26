"""Second implementation: settlement-interval simulation and paired statistics."""
from pathlib import Path
import sys,json,math,hashlib,importlib.util
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT.parent;O=ROOT/'results';DATA=BASE/'restored/MAR_relative_value_checkpoint_20261020';N=2103840;DAYS=N//1440;START=pd.Timestamp('2022-01-01',tz='UTC')
spec=importlib.util.spec_from_file_location('parent_analysis',BASE/'parent/code/verify_and_analyze.py');pa=importlib.util.module_from_spec(spec);spec.loader.exec_module(pa)
stats=pa.stats;PERIODS=pa.PERIODS;COSTS=pa.COSTS;FEE=.00055

def independent_path(p,ok,fi,fr,sig,sd,day,side,delay,slip,stop_slip):
    e=day*1440+delay;E=p[e]*(1+side*slip);q=1000/E;initial=p[e]*(1-side*2*sd[day]);stop=initial
    ex0=initial*(1-side*stop_slip);budget=q*(side*(E-ex0)+FEE*(E+ex0))
    days=[j for j in range(day+1,len(sig)) if sig[j]==-side or not np.isfinite(sd[j])]
    end=min(days[0]*1440+delay,N-1) if days else N-1
    events=np.flatnonzero((fi>e)&(fi<end));bounds=np.unique(np.r_[e+1,fi[events]+1,end+1]).astype(int)
    funding=0.;k=int(np.searchsorted(fi,e,side='right'));updates=0;tol=max(abs(initial)*1e-12,1e-14)
    for lo,hi in zip(bounds[:-1],bounds[1:]):
        while k<len(fi) and fi[k]<lo:
            funding+=side*q*p[fi[k]]*fr[k];k+=1
        # Recover the required stop by solving the affine net-P&L equation at raw prices 0 and 1.
        def pnl(raw):
            xp=raw*(1-side*stop_slip)
            return side*q*(xp-E)-q*FEE*(E+xp)-funding
        zero=pnl(0.);slope=pnl(1.)-zero
        needed=(-budget-zero)/slope if funding!=0 else initial
        new=max(stop,needed) if side==1 else min(stop,needed)
        if side*(new-stop)>tol:updates+=1
        assert side*(new-stop)>=-1e-9
        stop=new
        assert pnl(stop)>=-budget-1e-6
        times=np.arange(lo,hi);bad=times[~np.isfinite(p[times])|~ok[times]];hits=times[side*(p[times]-stop)<=0]
        fb=int(bad[0]) if len(bad) else N;hit=int(hits[0]) if len(hits) else N
        if fb<=hit and fb<N:
            # If first unavailable point is lo, its new funding stop was not observed at a valid quote.
            return fb-1,'data_censor',fb-1,None,None,budget
        if hit<N:
            x=min(hit+1,N-1);reason='stop' if hit+1<N else 'terminal'
            if not np.isfinite(p[x]) or not ok[x]:x=hit;reason='data_censor'
            return x,reason,hit,stop,updates,budget
    reason='opposite_signal' if days and end<N-1 and sig[days[0]]==-side else 'invalid_feature' if days and end<N-1 else 'terminal'
    return end,reason,end,stop,updates,budget

def verify():
    ev=pd.read_parquet(O/'events.parquet');pairs=pd.read_parquet(O/'paired_entries.parquet');dec=pd.read_parquet(O/'decisions.parquet');uni=pd.read_csv(DATA/'results/universe.csv')
    combined=pd.concat([ev.assign(check_source='admitted'),pairs.assign(check_source='fixed_parent_entry')],ignore_index=True)
    keys=['symbol','arm','cost','delay','day'];unique=combined.drop_duplicates(keys)
    checked=0;settlements=0;prefix_checks=0;overlap_checks=0
    for symbol in uni.symbol:
        g=unique[unique.symbol==symbol];zz=np.load(DATA/'cache'/f'{symbol}.npz');p=zz['opens'];fi=zz['funding_index'];fr=zz['funding_rate'];hc=zz['hourly_close'];j=np.searchsorted(fi,np.arange(N),side='right')-1
        ok=(j>=0)&(np.arange(N)-fi[np.maximum(j,0)]<=480)&np.isfinite(p[fi[np.maximum(j,0)]])
        feats={arm:pa.independent_features(hc,cap) for arm,cap in [('S01F',3.),('S00F',np.inf)]}
        for row in g.itertuples():
            sig,sd,z=feats[row.arm];sl,ss=COSTS[row.cost]
            x,reason,trigger,stop,updates,budget=independent_path(p,ok,fi,fr,sig,sd,int(row.day),int(row.side),int(row.delay),sl,ss)
            assert (x,reason,trigger)==(row.x,row.reason,row.trigger),(symbol,row.arm,row.cost,row.day,x,row.x,reason,row.reason,trigger,row.trigger)
            if stop is not None:
                assert np.isclose(stop,row.stop_at_trigger,rtol=1e-9,atol=1e-9),(symbol,stop,row.stop_at_trigger)
                assert updates==row.stop_updates,(symbol,updates,row.stop_updates)
            e=int(row.e);side=int(row.side);E=p[e]*(1+side*sl);X=p[x]*(1-side*(ss if reason=='stop' else sl));q=1000/E;jj=(fi>e)&(fi<=x)
            F=side*q*np.sum(p[fi[jj]]*fr[jj]);absF=q*np.sum(np.abs(p[fi[jj]]*fr[jj]));fee=q*FEE*(E+X);net=side*q*(X-E)-fee-F;risk=side*q*(E-row.stop)
            for a,b in [(net,row.net),(F,row.funding_cost),(absF,row.absolute_funding),(budget,row.planned_risk),(risk,row.risk),(net/risk,row.net_R)]:assert np.isclose(a,b,rtol=1e-8,atol=1e-6),(symbol,row.day,a,b)
            assert np.isclose(max(0.,-net-budget),row.risk_overrun_usdt,atol=1e-6)
            checked+=1;settlements+=int(jj.sum())
        # Every new admission/rejection is independently reconstructed; event paths alone are insufficient.
        for (arm,cost,delay),dd in dec[dec.symbol==symbol].groupby(['arm','cost','delay']):
            sig,sd,_=feats[arm];ee=ev[(ev.symbol==symbol)&(ev.arm==arm)&(ev.cost==cost)&(ev.delay==delay)].set_index('day');busy=-1;censored=False
            np.testing.assert_array_equal(dd.day.to_numpy(),np.flatnonzero(sig))
            for r in dd.itertuples():
                e=int(r.day*1440+delay);why='admitted'
                if censored:why='after_data_censor'
                elif e<=busy:why='token_busy'
                elif e>=N:why='outside_window'
                elif not np.isfinite(p[e]) or not ok[e]:why='entry_data_unavailable'
                if why=='admitted':
                    side=int(sig[r.day]);E=p[e]*(1+side*COSTS[cost][0]);stop=p[e]*(1-side*2*sd[r.day]);distance=side*(E-stop)/E
                    if not .005<=distance<=.15 or stop<=0:why='stop_bound'
                assert why==r.decision,(symbol,arm,cost,r.day,why,r.decision)
                if why=='admitted':busy=int(ee.loc[r.day,'x']);censored=ee.loc[r.day,'reason']=='data_censor'
        # Common actual/fixed-entry rows must have exactly the same economics.
        du=combined[combined.symbol==symbol].groupby(keys)
        for _,same in du:
            if len(same)>1:
                for col in ['x','net','net_R','funding_cost','stop_at_trigger','stop_updates']:assert same[col].nunique()==1
                overlap_checks+=1
    daily=pd.read_parquet(O/'daily.parquet');td=pd.read_parquet(O/'token_daily.parquet')
    agg=td.groupby(['arm','cost','delay','day'])[['net','net_R']].sum().sort_index();ref=daily.set_index(['arm','cost','delay','day']).sort_index()[['net','net_R']]
    np.testing.assert_allclose(agg,ref,atol=1e-6,rtol=1e-9)
    # Independent daily marked P&L, without using scorer difference arrays.
    rebuilt={key:np.zeros(DAYS) for key in ev.groupby(['arm','cost','delay']).groups};rebuiltR={k:np.zeros(DAYS) for k in rebuilt};ends=np.arange(1439,N,1440)
    for symbol,g in ev.groupby('symbol'):
        z=np.load(DATA/'cache'/f'{symbol}.npz');p=z['opens'];fi=z['funding_index'];fr=z['funding_rate']
        for r in g.itertuples():
            curve=np.zeros(DAYS);inside=(ends>=r.e)&(ends<=r.x);ts=ends[inside];positions=np.flatnonzero(inside)
            for ix,t in zip(positions,ts):
                funding=r.side*r.quantity*np.sum(p[fi[(fi>r.e)&(fi<=t)]]*fr[(fi>r.e)&(fi<=t)])
                curve[ix]=r.side*r.quantity*(p[t]-r.entry_price)-.00055*1000-funding
                if t==r.x:curve[ix]=r.net
            curve[ends>r.x]=r.net;key=(r.arm,r.cost,r.delay);rebuilt[key]+=np.diff(np.r_[0.,curve]);rebuiltR[key]+=np.diff(np.r_[0.,curve])/r.risk
    for key,a in rebuilt.items():
        q=daily[(daily.arm==key[0])&(daily.cost==key[1])&(daily.delay==key[2])].sort_values('day')
        np.testing.assert_allclose(a,q.net,atol=1e-6,rtol=1e-8);np.testing.assert_allclose(rebuiltR[key],q.net_R,atol=1e-6,rtol=1e-8)
    receipt={'independent_unique_paths_and_cashflows':checked,'admitted_event_rows':len(ev),'fixed_parent_entry_rows':len(pairs),'all_decisions_checked':len(dec),'funding_settlements_checked':settlements,'overlapping_pair_rows_match':overlap_checks,'independent_daily_reconstruction':True,'token_daily_reconciled':True,'historical_2026_opened':False}
    (O/'INDEPENDENT_VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
    return ev,pairs,daily,td

def gates(s,arm):
    central=['baseline','moderate','desk'];p=s[s.arm==arm];main=p[(p.delay==1)&p.cost.isin(central)];later=main[main.period=='2023-25'];full=main[main.period.isin(['2022-25','2023-25'])];both=p[p.cost.isin(central)&p.period.isin(['2022-25','2023-25'])]
    return {'positive_full_and_later_cohort_and_calendar':bool((full.net>0).all() and (full.calendar_net>0).all()),'later_closed_only_positive':bool((later.closed_net>0).all()),'two_positive_later_calendar_years':bool(all((main[(main.cost==c)&main.period.isin(['2023','2024','2025'])].calendar_net>0).sum()>=2 for c in central)),'delay_positive_full_and_later':bool((both.net>0).all() and (both.calendar_net>0).all()),'support':bool(((later.closed>=100)&(later.weeks>=26)&(later.tokens>=10)&(later.data_censors/later.trades<=.01)).all()),'funding_proxy_stress_positive':bool((later.funding_proxy_stress>0).all())}

def analyze(ev,pairs,daily,td):
    old=pd.read_parquet(BASE/'parent_saved/results/events_verified.parquet');old['entry_arm']=old.arm;old['risk_overrun_usdt']=np.maximum(0.,-old.net-old.planned_risk);old['loss_to_budget']=np.maximum(0.,-old.net)/old.planned_risk;old['exit_kind']=old.reason
    all_events=pd.concat([old,ev],ignore_index=True);all_daily=pd.concat([pd.read_parquet(BASE/'parent/results/daily.parquet'),daily],ignore_index=True);all_td=pd.concat([pd.read_parquet(BASE/'parent/results/token_daily.parquet'),td],ignore_index=True)
    draw=pd.concat([pd.read_csv(BASE/'parent/results/experimental_drawdown.csv'),pd.read_csv(O/'experimental_drawdown.csv')]).set_index(['arm','cost','delay','period'])
    uni=pd.read_csv(DATA/'results/universe.csv');summary=[];breakdowns=[];tails=[];concentration=[];bridge=[];paired_stats=[]
    for (arm,cost,delay),g in all_events.groupby(['arm','cost','delay']):
        dg=all_daily[(all_daily.arm==arm)&(all_daily.cost==cost)&(all_daily.delay==delay)];tg=all_td[(all_td.arm==arm)&(all_td.cost==cost)&(all_td.delay==delay)]
        for period,(a,b) in PERIODS.items():
            sub=g[(g.e>=a*1440)&(g.e<b*1440)];dp=dg[(dg.day>=a)&(dg.day<b)];tp=tg[(tg.day>=a)&(tg.day<b)]
            summary.append(dict(arm=arm,cost=cost,delay=delay,period=period,**stats(sub),calendar_net=float(dp.net.sum()),calendar_R=float(dp.net_R.sum()),closed_net=float(sub[~sub.reason.isin(['terminal','data_censor'])].net.sum()),**draw.loc[(arm,cost,delay,period)].to_dict()))
            tails.append(dict(arm=arm,cost=cost,delay=delay,period=period,trades=len(sub),budget_exceed_count=int((sub.risk_overrun_usdt>1e-7).sum()),budget_exceed_pct=100*float((sub.risk_overrun_usdt>1e-7).mean()) if len(sub) else 0,worst_loss_to_budget=float(sub.loss_to_budget.max()) if len(sub) else 0,aggregate_overrun_usdt=float(sub.risk_overrun_usdt.sum()),worst_trade_net=float(sub.net.min()) if len(sub) else 0,funding_stop_exits=int(sub.exit_kind.eq('funding_stop').sum()),median_days=float(sub.duration_days.median()) if len(sub) else 0,max_days=float(sub.duration_days.max()) if len(sub) else 0))
            token=sub.groupby('symbol').net.sum().sort_values(ascending=False);sectors=sub.groupby('sector').net.sum();concentration.append(dict(arm=arm,cost=cost,delay=delay,period=period,active_tokens=len(token),profitable_tokens=int((token>0).sum()),losing_tokens=int((token<0).sum()),inactive_tokens=96-len(token),profitable_sectors=int((sectors>0).sum()),active_sectors=len(sectors),top5_net=float(token.head(5).sum()),net_without_top5=float(token.iloc[5:].sum()),top5_tokens=', '.join(token.head(5).index)))
            for dim,values in [('symbol',uni.symbol.tolist()),('sector',sorted(uni.sector.unique())),('side',[-1,1]),('regime',['up','down','sideways','unknown'])]:
                calendar=tp.groupby(dim)[['net','net_R']].sum() if dim in ['symbol','sector'] else None
                groups={k:v for k,v in sub.groupby(dim)}
                for value in values:
                    z=groups.get(value,sub.iloc[:0]);row=dict(arm=arm,cost=cost,delay=delay,period=period,dimension=dim,group=value,**stats(z))
                    if calendar is not None:row['calendar_net']=float(calendar.loc[value,'net']) if value in calendar.index else 0;row['calendar_R']=float(calendar.loc[value,'net_R']) if value in calendar.index else 0
                    breakdowns.append(row)
    s=pd.DataFrame(summary);s.to_csv(O/'summary.csv',index=False);pd.DataFrame(breakdowns).to_csv(O/'breakdowns.csv',index=False);pd.DataFrame(tails).to_csv(O/'loss_budget.csv',index=False);pd.DataFrame(concentration).to_csv(O/'concentration.csv',index=False)
    for (arm,cost,delay),new in ev.groupby(['arm','cost','delay']):
        par=old[(old.arm==arm[:-1])&(old.cost==cost)&(old.delay==delay)]
        pp=pairs[(pairs.arm==arm)&(pairs.cost==cost)&(pairs.delay==delay)]
        for period,(a,b) in PERIODS.items():
            nn=new[(new.e>=a*1440)&(new.e<b*1440)].set_index(['symbol','e']);oo=par[(par.e>=a*1440)&(par.e<b*1440)].set_index(['symbol','e']);common=nn.index.intersection(oo.index);added=nn.index.difference(oo.index);removed=oo.index.difference(nn.index)
            common_delta=float((nn.loc[common].net-oo.loc[common].net).sum());added_net=float(nn.loc[added].net.sum());removed_net=float(oo.loc[removed].net.sum());delta=float(nn.net.sum()-oo.net.sum());assert np.isclose(delta,common_delta+added_net-removed_net,atol=1e-6)
            commonR=float((nn.loc[common].net_R-oo.loc[common].net_R).sum());addR=float(nn.loc[added].net_R.sum());remR=float(oo.loc[removed].net_R.sum());deltaR=float(nn.net_R.sum()-oo.net_R.sum());assert np.isclose(deltaR,commonR+addR-remR,atol=1e-6)
            bridge.append(dict(arm=arm,cost=cost,delay=delay,period=period,parent_trades=len(oo),new_trades=len(nn),common_trades=len(common),added_trades=len(added),removed_trades=len(removed),common_net_change=common_delta,added_net=added_net,removed_parent_net=removed_net,total_net_change=delta,common_R_change=commonR,added_R=addR,removed_parent_R=remR,total_R_change=deltaR))
            z=pp[(pp.e>=a*1440)&(pp.e<b*1440)];paired_stats.append(dict(arm=arm,cost=cost,delay=delay,period=period,pairs=len(z),parent_net=float(z.parent_net.sum()),same_entries_new_net=float(z.net.sum()),paired_delta=float((z.net-z.parent_net).sum()),funding_saved=float((z.parent_funding-z.funding_cost).sum()),gross_change=float((z.gross-z.parent_gross).sum()),fill_cost_change=float((z.fees+z.slippage-z.parent_fees_slippage).sum()),shorter_exits=int((z.x<z.parent_x).sum()),longer_exits=int((z.x>z.parent_x).sum()),unchanged_exits=int((z.x==z.parent_x).sum())))
    pd.DataFrame(bridge).to_csv(O/'admission_bridge.csv',index=False);pd.DataFrame(paired_stats).to_csv(O/'paired_exit_summary.csv',index=False)
    result={'study_id':'MAR-FUNDING-AWARE-RISK-01','primary':'S01F','gates':gates(s,'S01F'),'control_gates':gates(s,'S00F'),'paper_nomination':False,'historical_2026_opened':False,'runtime_changed':False,'account_comparison_performed':False}
    result['decision']='ADVANCE_TO_MATCHED_ACCOUNT_TEST' if all(result['gates'].values()) else 'REJECT_FUNDING_AWARE_CANDIDATE'
    (O/'DECISION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
    intervals=[]
    for period,(a,b) in {k:v for k,v in PERIODS.items() if k in ['2022-25','2023-25']}.items():
        nw=math.ceil((b-a)/7)
        for block in [4,13]:
            rng=np.random.default_rng(20261026+block);starts=rng.integers(0,nw,size=(4000,math.ceil(nw/block)));ix=((starts[:,:,None]+np.arange(block))%nw).reshape(4000,-1)[:,:nw]
            for cost in ['baseline','moderate','desk']:
                g=ev[(ev.arm=='S01F')&(ev.cost==cost)&(ev.delay==1)&(ev.e>=a*1440)&(ev.e<b*1440)];w=((g.e.to_numpy()//1440-a)//7).astype(int);pn=np.bincount(w,weights=g.net,minlength=nw);rr=np.bincount(w,weights=g.net_R,minlength=nw);count=np.bincount(w,minlength=nw)
                counts=count[ix].sum(1);meanR=np.divide(rr[ix].sum(1),counts,out=np.full(4000,np.nan),where=counts>0)
                dd=all_daily[(all_daily.cost==cost)&(all_daily.delay==1)&(all_daily.day>=a)&(all_daily.day<b)];cg={}
                for arm in ['S01','S01F']:
                    q=dd[dd.arm==arm];cg[arm]=np.bincount(((q.day.to_numpy()-a)//7).astype(int),weights=q.net,minlength=nw)
                cd=cg['S01F']-cg['S01']
                for metric,values,point,family in [('cohort_net_usdt',pn[ix].sum(1),float(pn.sum()),True),('calendar_net_uplift_usdt',cd[ix].sum(1),float(cd.sum()),True),('mean_R',meanR,float(rr.sum()/count.sum()),False)]:
                    qu=np.nanquantile(values,[.025,.975,.025/12,1-.025/12]);intervals.append(dict(period=period,cost=cost,block_weeks=block,metric=metric,point=point,lo95=qu[0],hi95=qu[1],family_lo95=qu[2] if family else None,family_hi95=qu[3] if family else None))
    pd.DataFrame(intervals).to_csv(O/'uncertainty.csv',index=False)
    all_events.to_parquet(O/'all_events.parquet',index=False);all_daily.to_parquet(O/'all_daily.parquet',index=False)
    print(s[(s.arm.isin(['S01','S01F']))&(s.delay==1)&s.cost.isin(['baseline','moderate','desk'])&s.period.isin(['2022-25','2023-25'])][['arm','cost','period','trades','net_R','mean_net_pct','net','calendar_net','opportunity_drawdown_R']].to_string(index=False),flush=True)

if __name__=='__main__':analyze(*verify())
