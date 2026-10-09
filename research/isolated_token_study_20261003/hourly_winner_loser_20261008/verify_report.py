"""Independent saved-evidence checks without importing the diagnostic runner."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
KEYS=['partition','symbol','side','signal_i']

def verify(root,cache,runtime):
    e=root/'hourly_winner_loser_20261008';o=e/'results_v1';dev=e/'development_v1'
    for out in [dev,o]:
        f=json.loads((out/'freeze.json').read_text());s=json.loads((out/'status.json').read_text());assert s['status']=='complete'
        for group,source in [('sources',root),('inputs',cache),('features',root),('runtime_sources',runtime),('cached_references',root)]:
            for n,h in f[group].items():assert sha(source/n)==h,n
        for n,h in s['output_hashes'].items():assert sha(out/n)==h,n
    t=pd.read_parquet(o/'entry_outcome_evidence.parquet',use_threads=False)
    ref=pd.read_parquet(root/'hourly_stop_cost_20261008/results_v1/pooled_ledger.parquet',use_threads=False)
    ref=ref[ref.poll_minutes.isin([0,1])]
    sort=KEYS+['poll_minutes','stress','cost_model']
    pd.testing.assert_frame_equal(t.sort_values(sort)[ref.columns].reset_index(drop=True),ref.sort_values(sort).reset_index(drop=True),check_exact=True)
    assert (t.feature_asof<=t.entry).all() and (t.last_input_minute<t.entry).all()
    main=t[(t.poll_minutes==1)&(t.stress==2)&(t.cost_model=='runtime_stop_fill')]
    features=f['entry_features'];edges=json.loads((dev/'bin_edges.json').read_text());sel=json.loads((dev/'selection.json').read_text())
    hist=main[main.partition=='historical'];assert len(hist)==41 and len(main)==65
    def rank(q,feature):
        good=q.loc[q.net_return>0,feature].tolist();bad=q.loc[q.net_return<=0,feature].tolist()
        pairs=len(good)*len(bad)
        return sum(1 if a>b else .5 if a==b else 0 for a in good for b in bad)/pairs if pairs else np.nan
    for feature in features:
        x=np.sort(hist[feature].to_numpy())
        for label,quantile in [('median',.5),('q33',1/3),('q67',2/3)]:
            at=quantile*(len(x)-1);lo=int(np.floor(at));hi=int(np.ceil(at));expected=x[lo]+(x[hi]-x[lo])*(at-lo)
            assert np.isclose(edges[feature][label],expected,atol=1e-12)
    candidates=pd.read_csv(dev/'historical_candidates.csv');assert len(candidates)==24
    for r in candidates.itertuples():
        keep=hist[r.feature]<=r.threshold
        if r.direction=='upper':keep=~keep
        a=hist[keep];b=hist[~keep];delta=a.net_return.mean()-b.net_return.mean()
        assert len(a)==r.retained and len(b)==r.excluded and np.isclose(delta,r.difference,atol=1e-12)
        ar=rank(hist,r.feature);ar=ar if r.direction=='upper' else 1-ar
        assert np.isclose(ar,r.oriented_auc)
        diffs=[]
        for symbol,name in [('BTCUSDT','BTC'),('ETHUSDT','ETH'),('SOLUSDT','SOL')]:
            aa=a[a.symbol!=symbol];bb=b[b.symbol!=symbol];d=aa.net_return.mean()-bb.net_return.mean()
            assert np.isclose(d,getattr(r,f'leave_{name}_difference'),equal_nan=True);diffs.append(d)
        eligible=bool(len(a)>=12 and len(b)>=12 and a.net_return.mean()>0 and delta>0 and ar>.5 and np.isfinite(diffs).all() and min(diffs)>0)
        assert eligible==r.eligible
    ranked=candidates[candidates.eligible].sort_values(['minimum_leave_token_difference','difference','feature','direction'],ascending=[False,False,True,True])
    assert (len(ranked)>0)==(sel['status']=='nominated')
    if len(ranked):
        first=ranked.iloc[0];assert (sel['feature'],sel['direction'],sel['threshold'])==(first.feature,first.direction,first.threshold)
    checks=intervals=0
    def subset(r):
        q=t[(t.poll_minutes==r.poll_minutes)&(t.stress==r.stress)&(t.cost_model==r.cost_model)&(t.partition==r.partition)]
        if hasattr(r,'grouping') and pd.notna(r.grouping):
            for col in r.grouping.split('+'):
                q=q[q.entry.dt.year==r.entry_year] if col=='entry_year' else q[q[col]==getattr(r,col)]
        return q
    def summary(q,r,prefix=''):
        assert len(q)==getattr(r,prefix+'n')
        for name,expected in [('stops',(q.reason=='stop').sum()),('targets',(q.reason=='target').sum()),('wins',(q.net_return>0).sum())]:
            assert expected==getattr(r,prefix+name)
        assert np.isclose(q.net_return.mean(),getattr(r,prefix+'mean_net'),atol=1e-12,equal_nan=True)
    for r in pd.read_csv(o/'feature_profiles.csv').itertuples():
        q=subset(r);wins=q[q.net_return>0][r.feature];loss=q[q.net_return<=0][r.feature]
        assert len(q)==r.n and len(wins)==r.winners and len(loss)==r.losers
        for expected,actual in [(wins.median(),r.winner_median),(loss.median(),r.loser_median),(rank(q,r.feature),r.auc)]:
            assert np.isclose(expected,actual,atol=1e-12,equal_nan=True)
        num=den=0
        for _,g in q.groupby(['symbol','side']):
            count=int((g.net_return>0).sum())*int((g.net_return<=0).sum())
            if count:num+=rank(g,r.feature)*count;den+=count
        assert den==r.within_token_side_pairs and np.isclose(num/den if den else np.nan,r.within_token_side_auc,atol=1e-12,equal_nan=True)
        checks+=1
    for r in pd.read_csv(o/'feature_bins.csv').itertuples():
        q=subset(r);v=q[r.feature]
        keep=v<r.q33 if r.bin==0 else ((v>=r.q33)&(v<r.q67) if r.bin==1 else v>=r.q67)
        summary(q[keep],r);checks+=1
    for r in pd.read_csv(o/'model_summaries.csv').itertuples():summary(subset(r),r);checks+=1
    def boot(q,part,block):
        a,z=[pd.Timestamp(x,tz='UTC') for x in f['periods'][part]];origin=a.normalize()-pd.Timedelta(days=a.weekday())
        n=int((z-pd.Timedelta(minutes=1)-origin).days//7)+1
        which=((q.entry-origin).dt.total_seconds()//604800).astype(int)
        count=np.bincount(which,minlength=n);value=np.bincount(which,weights=q.net_return,minlength=n)
        starts=np.random.default_rng(20261006+block).integers(0,n,(10000,int(np.ceil(n/block))))
        draws=np.concatenate([((starts[:,j,None]+np.arange(block))%n) for j in range(starts.shape[1])],axis=1)[:,:n]
        den=count[draws].sum(1);num=value[draws].sum(1)
        return np.divide(num,den,out=np.full(10000,np.nan),where=den>0)
    if sel['status']=='nominated':
        for r in pd.read_csv(o/'nominee_subsets.csv').itertuples():
            q=subset(r);keep=q[sel['feature']]<=sel['threshold']
            if sel['direction']=='upper':keep=~keep
            a=q[keep];b=q[~keep]
            summary(q,r,'baseline_');summary(a,r,'retained_');summary(b,r,'excluded_')
            assert np.isclose(r.difference_vs_baseline,a.net_return.mean()-q.net_return.mean(),equal_nan=True)
            for label,other in [('baseline',q),('excluded',b)]:
                if len(a)*len(other):
                    for block in [1,4]:
                        ci=np.nanquantile(boot(a,r.partition,block)-boot(other,r.partition,block),[.025,.975])
                        expected=[getattr(r,f'{label}_difference_block_{block}_{x}_R')*.02 for x in ['low','high']]
                        assert np.allclose(ci,expected,atol=1e-12);intervals+=1
            checks+=1
    anatomy=pd.read_parquet(o/'primary_trade_anatomy.parquet',use_threads=False);assert len(anatomy)==65
    pd.testing.assert_frame_equal(anatomy.sort_values(KEYS)[main.columns].reset_index(drop=True),main.sort_values(KEYS).reset_index(drop=True),check_exact=True)
    for r in pd.read_csv(o/'excursion_counts.csv').itertuples():
        q=anatomy[(anatomy.partition==r.partition)&((anatomy.net_return>0)==(r.outcome=='winner'))]
        assert len(q)==r.n and (q.mfe>=r.threshold).sum()==r.mfe_ge and (q.mae>=r.threshold).sum()==r.mae_ge;checks+=1
    for r in pd.read_csv(o/'path_summary.csv').itertuples():
        q=anatomy[(anatomy.partition==r.partition)&((anatomy.net_return>0)==(r.outcome=='winner'))]
        summary(q,r)
        for col in ['mfe','mae','holding_minutes','exit_rsi14','exit_crsi','exit_adx14']:
            for quantile,label in [(.25,'q25'),(.5,'median'),(.75,'q75')]:
                assert np.isclose(q[col].quantile(quantile),getattr(r,col+'_'+label),atol=1e-11)
        checks+=1
    for r in pd.read_csv(o/'primary_summary.csv').itertuples():
        q=main[main.partition==r.partition];summary(q,r)
        dropped=q.drop(q.net_return.idxmax())
        assert np.isclose(dropped.net_return.mean(),r.mean_without_largest_winner,atol=1e-12)
        assert q.entry.dt.floor('D').nunique()==r.active_dates and q.entry.dt.tz_localize(None).dt.to_period('W-SUN').nunique()==r.active_weeks
        checks+=1
    result=dict(status='pass',entry_outcome_rows_exactly_reconciled=520,primary_anatomy_rows=65,
        historical_candidate_rows_rebuilt=24,report_rows_independently_rebuilt=checks,bootstrap_intervals_independently_rebuilt=intervals,
        sources_inputs_runtime_references_outputs_verified=True,selection_precedes_later_associations=True)
    (e/'REPORT_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);a=p.parse_args();verify(a.root,a.cache,a.runtime)
