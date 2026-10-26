"""Independent reconstruction plus predeclared descriptive analysis."""
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1];O=ROOT/'results'
DATA=ROOT.parent/'restored/MAR_relative_value_checkpoint_20261020'
N=2103840;DAYS=N//1440;START=pd.Timestamp('2022-01-01',tz='UTC')
COSTS={'baseline':(.002,0.),'moderate':(.003,.002),'desk':(.00255,.00255),'severe':(.01,.01)}
PERIODS={str(y):(int((pd.Timestamp(f'{y}-01-01',tz='UTC')-START).days),int((pd.Timestamp(f'{y+1}-01-01',tz='UTC')-START).days)) for y in range(2022,2026)}|{'2022-25':(0,DAYS),'2023-25':(365,DAYS)}

def independent_features(hc,cap):
    dc=np.full(len(hc)//24+1,np.nan)
    dc=dc[:(len(hc)-1)//24+1]
    for d in range(1,len(dc)):
        if all(math.isfinite(x) for x in hc[d*24-23:d*24+1]):dc[d]=hc[d*24]
    returns=np.full(len(dc),np.nan)
    for d in range(1,len(dc)):
        if math.isfinite(dc[d-1]) and math.isfinite(dc[d]):returns[d]=math.log(dc[d]/dc[d-1])
    sig=np.zeros(len(dc),int);scale=np.full(len(dc),np.nan);zs=np.full(len(dc),np.nan);up=dn=0.
    for d in range(len(dc)):
        values=returns[max(0,d-60):d]
        if len(values)==60 and np.isfinite(values).all():scale[d]=np.std(values)
        if not math.isfinite(returns[d]) or not math.isfinite(scale[d]) or scale[d]<=0:up=dn=0.;continue
        zs[d]=returns[d]/scale[d];value=max(-cap,min(cap,zs[d]));up=max(0.,up+value-.5);dn=max(0.,dn-value-.5)
        sig[d]=1 if up>=5 else -1 if dn>=5 else 0
        if sig[d]:up=dn=0.
    return sig,scale,zs

def verify():
    events=pd.read_parquet(O/'events.parquet');signals=pd.read_parquet(O/'signals.parquet');dec=pd.read_parquet(O/'decisions.parquet')
    absolute={};checked=0;funding_settlements=0
    for symbol in pd.read_csv(DATA/'results/universe.csv').symbol:
        group=events[events.symbol==symbol]
        z=np.load(DATA/'cache'/f'{symbol}.npz');p=z['opens'];fi=z['funding_index'];fr=z['funding_rate'];hc=z['hourly_close']
        latest=np.searchsorted(fi,np.arange(len(p)),side='right')-1
        good=(latest>=0)&(np.arange(len(p))-fi[np.maximum(latest,0)]<=480)&np.isfinite(p[fi[np.maximum(latest,0)]])
        features={}
        for arm,cap in [('S01',3.),('S00',float('inf'))]:
            ss,sd,zz=independent_features(hc,cap);features[arm]=(ss,sd)
            selected=signals[(signals.symbol==symbol)&(signals.arm==arm)].sort_values('day')
            np.testing.assert_array_equal(selected.day,np.flatnonzero(ss));np.testing.assert_array_equal(selected.side,ss[selected.day])
            np.testing.assert_allclose(selected.sigma,sd[selected.day],rtol=1e-8)
            # Reconstruct every admission/occupancy/stop-bound decision without original helpers.
            for (cost,delay),dd in dec[(dec.symbol==symbol)&(dec.arm==arm)].groupby(['cost','delay']):
                busy=-1;censored=False;gg=group[(group.arm==arm)&(group.cost==cost)&(group.delay==delay)].set_index('day')
                for rr in dd.sort_values('day').itertuples():
                    e=rr.day*1440+delay;why='admitted'
                    if censored:why='after_data_censor'
                    elif e<=busy:why='token_busy'
                    elif e>=N:why='outside_window'
                    elif not np.isfinite(p[e]) or not good[e]:why='entry_data_unavailable'
                    if why=='admitted':
                        side=ss[rr.day];ep=p[e]*(1+side*COSTS[cost][0]);stop=p[e]*(1-side*2*sd[rr.day]);dist=side*(ep-stop)/ep
                        if not .005<=dist<=.15 or stop<=0:why='stop_bound'
                    assert rr.decision==why,(symbol,arm,cost,rr.day,why,rr.decision)
                    if why=='admitted':busy=int(gg.loc[rr.day,'x']);censored=gg.loc[rr.day,'reason']=='data_censor'
        for idx,r in group.iterrows():
            sig,sd=features[r.arm];e=int(r.e);x=int(r.x);side=int(r.side)
            candidates=np.flatnonzero((np.arange(len(sig))>r.day)&((sig==-side)|~np.isfinite(sd)))
            scheduled=min(int(candidates[0]*1440+r.delay),N-1) if len(candidates) else N-1
            window=np.arange(e+1,scheduled+1)
            stops=window[side*(p[window]-r.stop)<=0];bad=window[~np.isfinite(p[window])|~good[window]]
            hit=int(stops[0]) if len(stops) else N;firstbad=int(bad[0]) if len(bad) else N
            if firstbad<=min(hit,scheduled):xx=firstbad-1;reason='data_censor'
            elif hit<=scheduled:
                xx=min(hit+1,N-1);reason='stop' if hit+1<N else 'terminal'
                if not np.isfinite(p[xx]) or not good[xx]:xx=hit;reason='data_censor'
            else:
                xx=scheduled;reason='terminal'
                if len(candidates) and scheduled<N-1:reason='opposite_signal' if sig[candidates[0]]==-side else 'invalid_feature'
            assert (x,r.reason)==(xx,reason),(idx,r.reason,reason,x,xx)
            slip,stopslip=COSTS[r.cost];entry=p[e]*(1+side*slip);exit=p[x]*(1-side*(stopslip if r.reason=='stop' else slip));q=1000/entry
            jj=(fi>e)&(fi<=x);assert np.isfinite(p[fi[jj]]).all()
            funding=side*q*np.sum(p[fi[jj]]*fr[jj]);absfund=q*np.sum(np.abs(p[fi[jj]]*fr[jj]));funding_settlements+=int(jj.sum());absolute[idx]=absfund
            fee=.00055*q*(entry+exit);net=side*q*(exit-entry)-fee-funding;risk=side*q*(entry-r.stop)
            for a,b in [(net,r.net),(net/risk,r.net_R),(funding,r.funding_cost),(risk,r.risk),(entry,r.entry_price),(exit,r.exit_price)]:assert np.isclose(a,b,atol=1e-7,rtol=1e-9),(idx,a,b)
            checked+=1
    events['absolute_funding']=pd.Series(absolute);events.to_parquet(O/'events_verified.parquet',index=False)
    daily=pd.read_parquet(O/'daily.parquet');td=pd.read_parquet(O/'token_daily.parquet')
    sums=td.groupby(['arm','cost','delay','day'])[['net','net_R']].sum().sort_index()
    np.testing.assert_allclose(sums,daily.set_index(['arm','cost','delay','day']).sort_index()[['net','net_R']],atol=1e-7)
    receipt={'independent_event_paths_and_cashflows':checked,'independent_all_decisions':len(dec),'independent_signal_rows':len(signals),'funding_settlement_evaluations':funding_settlements,'token_to_total_daily_reconciliation':True,'historical_2026_opened':False}
    (O/'INDEPENDENT_VERIFICATION.json').write_text(json.dumps(receipt,indent=2));print(receipt,flush=True)
    return events,daily,td

def stats(g):
    wins=g[g.net>0];losses=g[g.net<0];n=len(g);w=len(wins);p=w/n if n else 0;z=1.96;den=1+z*z/max(n,1);mid=(p+z*z/(2*max(n,1)))/den;half=z*math.sqrt(p*(1-p)/max(n,1)+z*z/(4*max(n,1)**2))/den
    return dict(trades=n,net=float(g.net.sum()),net_R=float(g.net_R.sum()),mean_R=float(g.net_R.mean()) if n else 0.,mean_net_pct=float(g.net.mean()/10) if n else 0.,win_pct=100*p,win_ci_low_pct=100*(mid-half) if n else 0,win_ci_high_pct=100*(mid+half) if n else 0,profit_factor=float(wins.net.sum()/-losses.net.sum()) if len(losses) else None,average_win=float(wins.net.mean()) if len(wins) else 0.,average_loss=float(losses.net.mean()) if len(losses) else 0.,tokens=int(g.symbol.nunique()),weeks=int(g.week.nunique()),closed=int((~g.reason.isin(['terminal','data_censor'])).sum()),data_censors=int(g.reason.eq('data_censor').sum()),terminal=int(g.reason.eq('terminal').sum()),duration_median_days=float(g.duration_days.median()) if n else 0,gross=float(g.gross.sum()),slippage=float(g.slippage.sum()),fees=float(g.fees.sum()),funding_cost=float(g.funding_cost.sum()),funding_proxy_stress=float(g.net.sum()-.01*g.absolute_funding.sum()))

def analyze(events,daily,td):
    summary=[];breakdowns=[];uni=pd.read_csv(DATA/'results/universe.csv')
    dd=pd.read_csv(O/'experimental_drawdown.csv').set_index(['arm','cost','delay','period'])
    for (arm,cost,delay),g in events.groupby(['arm','cost','delay']):
        day=daily[(daily.arm==arm)&(daily.cost==cost)&(daily.delay==delay)]
        for period,(a,b) in PERIODS.items():
            ev=g[(g.e>=a*1440)&(g.e<b*1440)];dg=day[(day.day>=a)&(day.day<b)];s=stats(ev)
            row=dict(arm=arm,cost=cost,delay=delay,period=period,**s,calendar_net=float(dg.net.sum()),calendar_R=float(dg.net_R.sum()),closed_net=float(ev[~ev.reason.isin(['terminal','data_censor'])].net.sum()),**dd.loc[(arm,cost,delay,period)].to_dict());summary.append(row)
            t=td[(td.arm==arm)&(td.cost==cost)&(td.delay==delay)&(td.day>=a)&(td.day<b)]
            for dim,values in [('symbol',uni.symbol.tolist()),('sector',sorted(uni.sector.unique())),('side',[-1,1]),('regime',['up','down','sideways','unknown'])]:
                for value in values:
                    sub=ev[ev[dim]==value];rr=dict(arm=arm,cost=cost,delay=delay,period=period,dimension=dim,group=value,**stats(sub))
                    if dim in ('symbol','sector'):rr['calendar_net']=float(t[t[dim]==value].net.sum());rr['calendar_R']=float(t[t[dim]==value].net_R.sum())
                    breakdowns.append(rr)
    summ=pd.DataFrame(summary);summ.to_csv(O/'summary.csv',index=False);pd.DataFrame(breakdowns).to_csv(O/'breakdowns.csv',index=False)
    decisions={};central=['baseline','moderate','desk']
    primary=summ[summ.arm=='S01'];main=primary[(primary.delay==1)&primary.cost.isin(central)];both=primary[primary.cost.isin(central)&primary.period.isin(['2022-25','2023-25'])]
    later=main[main.period=='2023-25'];full=main[main.period.isin(['2022-25','2023-25'])]
    gates={'positive_full_and_later_cohort_and_calendar':bool((full.net>0).all() and (full.calendar_net>0).all()),'later_closed_only_positive':bool((later.closed_net>0).all()),'two_positive_later_calendar_years':bool(all((main[(main.cost==c)&main.period.isin(['2023','2024','2025'])].calendar_net>0).sum()>=2 for c in central)),'delay_positive_full_and_later':bool((both.net>0).all() and (both.calendar_net>0).all()),'support':bool(((later.closed>=100)&(later.weeks>=26)&(later.tokens>=10)&(later.data_censors/later.trades<=.01)).all()),'funding_proxy_stress_positive':bool((later.funding_proxy_stress>0).all())}
    decision={'study_id':'MAR-SEQUENTIAL-DRIFT-01','primary':'S01 bounded evidence','gates':gates,'decision':'ADVANCE_TO_MATCHED_ACCOUNT_TEST' if all(gates.values()) else 'REJECT_FROZEN_SPECIFICATION','paper_nomination':False,'best_strategy_superiority_established':False,'historical_2026_opened':False}
    (O/'DECISION.json').write_text(json.dumps(decision,indent=2));print(json.dumps(decision,indent=2),flush=True)
    # Week blocks synchronize all assets and arms; resample calendar clusters, never individual trades.
    intervals=[];concentration=[];fixed=[]
    for period,(a,b) in {k:v for k,v in PERIODS.items() if k in ['2022-25','2023-25']}.items():
        for block in [4,13]:
            nw=math.ceil((b-a)/7);rng=np.random.default_rng(20261026+block)
            starts=rng.integers(0,nw,size=(4000,math.ceil(nw/block)));ix=((starts[:,:,None]+np.arange(block))%nw).reshape(4000,-1)[:,:nw]
            for cost in central:
                arrs={}
                for arm in ['S01','S00']:
                    g=events[(events.arm==arm)&(events.cost==cost)&(events.delay==1)&(events.e>=a*1440)&(events.e<b*1440)]
                    weeks=((g.e.to_numpy()//1440-a)//7).astype(int);rr=np.bincount(weeks,weights=g.net_R,minlength=nw);nn=np.bincount(weeks,minlength=nw);pn=np.bincount(weeks,weights=g.net,minlength=nw)
                    arrs[arm]=(rr,nn,pn)
                rr,nn,pn=arrs['S01'];counts=nn[ix].sum(1);means=np.divide(rr[ix].sum(1),counts,out=np.full(4000,np.nan),where=counts>0);money=pn[ix].sum(1)
                for metric,values,point in [('mean_R',means,float(rr.sum()/nn.sum())),('cohort_net_usdt',money,float(pn.sum()))]:
                    q=np.nanquantile(values,[.025,.975,.025/6,1-.025/6]);intervals.append(dict(period=period,cost=cost,block_weeks=block,metric=metric,point=point,lo95=q[0],hi95=q[1],family_lo95=q[2],family_hi95=q[3]))
                r0,n0,p0=arrs['S00'];diff=pn[ix].sum(1)-p0[ix].sum(1);q=np.quantile(diff,[.025,.975]);intervals.append(dict(period=period,cost=cost,block_weeks=block,metric='S01_minus_S00_cohort_net',point=float(pn.sum()-p0.sum()),lo95=q[0],hi95=q[1],family_lo95=None,family_hi95=None))
        for arm in ['S01','S00']:
            for cost in COSTS:
                g=events[(events.arm==arm)&(events.cost==cost)&(events.delay==1)&(events.e>=a*1440)&(events.e<b*1440)];tk=g.groupby('symbol').net.sum().sort_values(ascending=False);sc=g.groupby('sector').net.sum()
                concentration.append(dict(arm=arm,cost=cost,period=period,active_tokens=len(tk),profitable_tokens=int((tk>0).sum()),losing_tokens=int((tk<0).sum()),inactive_tokens=96-len(tk),profitable_sectors=int((sc>0).sum()),active_sectors=len(sc),top5_net=float(tk.head(5).sum()),net_without_top5=float(tk.iloc[5:].sum()),top5_tokens=', '.join(tk.head(5).index)))
            g=events[(events.arm==arm)&(events.cost=='baseline')&(events.delay==1)&(events.e>=a*1440)&(events.e<b*1440)]
            for cost,(sl,st) in COSTS.items():
                raw_e=g.entry_price/(1+g.side*.002);raw_x=g.exit_price/(1-g.side*np.where(g.reason=='stop',0.,.002));ep=raw_e*(1+g.side*sl);xp=raw_x*(1-g.side*np.where(g.reason=='stop',st,sl));q=1000/ep;fund=g.funding_cost/g.quantity*q;net=g.side*q*(xp-ep)-.00055*q*(ep+xp)-fund
                fixed.append(dict(arm=arm,period=period,cost=cost,trades=len(g),net=float(net.sum()),mean_net_pct=float(net.mean()/10)))
    pd.DataFrame(intervals).to_csv(O/'uncertainty.csv',index=False);pd.DataFrame(concentration).to_csv(O/'concentration.csv',index=False);pd.DataFrame(fixed).to_csv(O/'fixed_sample_costs.csv',index=False)
    # Hypothesis-generating feature groups: thresholds fit to 2022 FEATURES only, no winners selected.
    feature_rows=[];cuts={}
    for arm in ['S01','S00']:
        train=events[(events.arm==arm)&(events.cost=='baseline')&(events.delay==1)&(events.year==2022)]
        cuts[arm]=np.quantile(train.sigma,[.25,.5,.75]).tolist()
        for cost in central:
            for year in [2023,2024,2025]:
                g=events[(events.arm==arm)&(events.cost==cost)&(events.delay==1)&(events.year==year)].copy();g['vol_bin']=np.searchsorted(cuts[arm],g.sigma)+1
                for b in range(1,5):feature_rows.append(dict(arm=arm,cost=cost,year=year,volatility_quartile=b,**stats(g[g.vol_bin==b])))
    pd.DataFrame(feature_rows).to_csv(O/'feature_diagnostics.csv',index=False);(O/'FEATURE_CUTS.json').write_text(json.dumps(cuts,indent=2))
    print(summ[(summ.arm=='S01')&(summ.delay==1)&summ.cost.isin(central)][['cost','period','trades','mean_net_pct','net_R','profit_factor','calendar_net','opportunity_drawdown_R']].to_string(index=False))

if __name__=='__main__':analyze(*verify())
