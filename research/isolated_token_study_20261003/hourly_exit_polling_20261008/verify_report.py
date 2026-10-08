"""Rebuild saved aggregates and bootstrap intervals independently of the runner."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def verify(root,cache,runtime,out):
    e=root/'hourly_exit_polling_20261008';o=e/'results_v1'
    frozen=json.loads((o/'freeze.json').read_text());status=json.loads((o/'status.json').read_text());assert status['status']=='complete'
    for group,source in [('sources',root),('inputs',cache),('runtime_sources',runtime),('cached_references',root)]:
        for n,h in frozen[group].items():assert sha(source/n)==h,n
    for n,h in status['output_hashes'].items():assert sha(o/n)==h,n
    t=pd.read_parquet(o/'pooled_ledger.parquet',use_threads=False);raw=pd.read_parquet(o/'all_opportunities.parquet',use_threads=False)
    s=pd.read_csv(o/'pooled_results.csv');sub=pd.read_csv(o/'subgroups.csv');con=pd.read_csv(o/'contrasts.csv');p=pd.read_csv(o/'paired_raw_outcomes.csv')
    tr=pd.read_csv(o/'outcome_transitions.csv');decomp=pd.read_csv(o/'admission_decomposition.csv');matched=pd.read_csv(o/'matched_results.csv')
    periods=frozen['periods'];checks=intervals=0;keys=['partition','symbol','side','signal_i']
    def select(frame,delay,part,stress):return frame[(frame.poll_minutes==delay)&(frame.partition==part)&(frame.stress==stress)]
    def boot(q,part,block,clock='entry'):
        a,z=[pd.Timestamp(v,tz='UTC') for v in periods[part]];origin=a.normalize()-pd.Timedelta(days=a.weekday())
        n=int((z-pd.Timedelta(minutes=1)-origin).days//7)+1
        which=((q[clock]-origin).dt.total_seconds()//604800).astype(int)
        count=np.bincount(which,minlength=n);value=np.bincount(which,weights=q.net_return,minlength=n)
        rng=np.random.default_rng(20261006+block);starts=rng.integers(0,n,(10000,int(np.ceil(n/block))))
        ix=np.concatenate([((starts[:,j,None]+np.arange(block))%n) for j in range(starts.shape[1])],axis=1)[:,:n]
        den=count[ix].sum(1);num=value[ix].sum(1)
        return np.divide(num,den,out=np.full(10000,np.nan),where=den>0)
    def basic(q,r):
        closed=q[q.reason!='boundary_mtm']
        assert len(q)==r.n and len(closed)==r.n_closed
        assert (q.reason=='stop').sum()==r.stop_count and (q.reason=='target').sum()==r.target_count and (q.reason=='boundary_mtm').sum()==r.boundary_count
        assert np.isclose(q.net_return.mean(),r.mean,atol=1e-14)
        if len(closed):assert np.isclose((closed.net_return>0).mean(),r.closed_win_rate)
    for r in s.itertuples():
        q=select(t,r.poll_minutes,r.partition,r.stress);basic(q,r)
        for block in [1,4]:
            lo,hi=np.nanquantile(boot(q,r.partition,block),[.025,.975])
            assert np.allclose([lo,hi],.02*np.array([getattr(r,f'block_{block}_low_R'),getattr(r,f'block_{block}_high_R')]),atol=1e-12);intervals+=1
        checks+=1
    for r in sub.itertuples():
        q=select(t,r.poll_minutes,r.partition,r.stress)
        for col in r.grouping.split('+'):q=q[q.entry.dt.year==r.entry_year] if col=='entry_year' else q[q[col]==getattr(r,col)]
        assert len(q)==r.n and np.isclose(q.net_return.mean(),r.mean,atol=1e-14)
        assert (q.reason=='stop').sum()==r.stop_count and (q.reason=='target').sum()==r.target_count;checks+=1
    for r in con.itertuples():
        a=select(t,0,r.partition,r.stress);b=select(t,r.poll_minutes,r.partition,r.stress)
        if r.view.startswith('counterfactual'):
            b=select(raw,r.poll_minutes,r.partition,r.stress)
            b=b[pd.MultiIndex.from_frame(b[keys]).isin(pd.MultiIndex.from_frame(a[keys]))]
            a=a[pd.MultiIndex.from_frame(a[keys]).isin(pd.MultiIndex.from_frame(b[keys]))]
        assert np.isclose(b.net_return.mean()-a.net_return.mean(),r.difference_mean_net,atol=1e-14)
        for block in [1,4]:
            lo,hi=np.nanquantile(boot(b,r.partition,block,'signal_time')-boot(a,r.partition,block,'signal_time'),[.025,.975])
            assert np.allclose([lo,hi],.02*np.array([getattr(r,f'difference_block_{block}_low_R'),getattr(r,f'difference_block_{block}_high_R')]),atol=1e-12);intervals+=1
        checks+=1
    for r in matched.itertuples():
        a=select(t,0,r.partition,r.stress);q=select(raw,r.poll_minutes,r.partition,r.stress)
        q=q[pd.MultiIndex.from_frame(q[keys]).isin(pd.MultiIndex.from_frame(a[keys]))];basic(q,r)
        assert r.original_admitted==len(a) and r.unfilled_endpoints==len(a)-len(q)
        for block in [1,4]:
            lo,hi=np.nanquantile(boot(q,r.partition,block),[.025,.975])
            assert np.allclose([lo,hi],.02*np.array([getattr(r,f'block_{block}_low_R'),getattr(r,f'block_{block}_high_R')]),atol=1e-12);intervals+=1
        checks+=1
    for r in tr.itertuples():
        q=select(p,r.poll_minutes,r.partition,r.stress)
        if r.scope=='baseline_admitted':q=q[q.baseline_admitted]
        q=q[(q.reason_baseline==r.from_reason)&(q.reason_sampled==r.to_reason)]
        assert len(q)==r.n and np.isclose(q.delta_net_return.sum(),r.difference_additive_sum,atol=1e-12);checks+=1
    for r in decomp.itertuples():
        q=select(p,r.poll_minutes,r.partition,r.stress)
        common=q[q.baseline_admitted&q.sampled_admitted];new=q[~q.baseline_admitted&q.sampled_admitted];lost=q[q.baseline_admitted&~q.sampled_admitted]
        assert len(common)==r.shared and len(new)==r.newly_admitted and len(lost)==r.displaced
        change=common.delta_net_return.sum()+new.net_return_sampled.sum()-lost.net_return_baseline.sum()
        assert np.isclose(change,r.actual_difference_additive_sum,atol=1e-12);checks+=1
    assert (raw.entry==raw.signal_time).all()
    assert (raw.feature_asof==raw.signal_time).all() and not raw.duplicated(keys+['stress','poll_minutes']).any()
    assert np.allclose(raw.net_return,raw.quoted_return-raw.slippage_drag-raw.fees-raw.funding,atol=1e-12,rtol=0)
    for r in pd.read_csv(o/'leave_one_token_out.csv').itertuples():
        q=select(t,r.poll_minutes,r.partition,r.stress);q=q[q.symbol!=r.excluded_symbol]
        assert len(q)==r.n and np.isclose(q.net_return.mean(),r.mean_net,atol=1e-14);checks+=1
    for r in pd.read_csv(o/'exit_price_diagnostics.csv').itertuples():
        q=select(t,r.poll_minutes,r.partition,r.stress);stops=q[q.reason=='stop'];targets=q[q.reason=='target']
        stop_overshoot=np.maximum(0,stops.side*(stops.stop_price-stops.quote)/stops.entry_price)
        target_overshoot=np.maximum(0,targets.side*(targets.quote-targets.target_price)/targets.entry_price)
        assert len(q)==r.n and len(stops)==r.stops and len(targets)==r.targets
        for actual,expected in [(r.mean_stopped_net,stops.net_return.mean()),(r.worst_stopped_net,stops.net_return.min()),(r.worst_trade_net,q.net_return.min()),(r.mean_stop_quote_overshoot,stop_overshoot.mean()),(r.worst_stop_quote_overshoot,stop_overshoot.max()),(r.mean_target_quote_overshoot,target_overshoot.mean()),(r.max_target_quote_overshoot,target_overshoot.max())]:assert np.isclose(actual,expected,atol=1e-12,equal_nan=True)
        assert r.stops_beyond_nominal==(stop_overshoot>1e-12).sum();checks+=1
    result=dict(status='pass',report_rows_independently_rebuilt=checks,bootstrap_intervals_independently_rebuilt=intervals,raw_rows=len(raw),ledger_rows=len(t),frozen_sources_inputs_references_and_output_hashes_verified=True)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();verify(a.root,a.cache,a.runtime,a.out)
